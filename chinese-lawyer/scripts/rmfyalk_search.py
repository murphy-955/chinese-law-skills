# -*- coding: utf-8 -*-
"""人民法院案例库 (rmfyalk.court.gov.cn) 案例检索。

说明：
- 未登录时案例库的部分检索/详情接口可能受限。
- 本脚本支持通过 account.court.gov.cn 统一认证登录，登录成功后复用 Session。
- 账号、密码优先从环境变量获取，也可通过命令行传入；密码建议使用交互式输入。
- 验证码需人工识别后输入。

安全提示：
- 不要将真实密码写入脚本或命令历史。
- 使用 --save-session 可将登录态保存到本地，下次通过 --load-session 复用。
"""

import argparse
import base64
import getpass
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

from bs4 import BeautifulSoup
from utils import create_session, safe_request, save_json, sleep_seconds

BASE_URL = "https://rmfyalk.court.gov.cn"
ACCOUNT_URL = "https://account.court.gov.cn"
LOGIN_API = f"{ACCOUNT_URL}/api/login"
SEARCH_API = f"{BASE_URL}/rest/listQuery"
DETAIL_API = f"{BASE_URL}/rest/detail"

ENV_USERNAME = "RMFYALK_USERNAME"
ENV_PASSWORD = "RMFYALK_PASSWORD"


def _extract_login_back_url(html: str) -> Optional[str]:
    """从页面 HTML 中提取登录跳转 URL（含 OAuth 参数）。"""
    # 方案 1：直接在 script 或 a 标签中查找 account.court.gov.cn/app
    patterns = [
        r'account\.court\.gov\.cn/app\?back_url=([^"\'\s<>]+)',
        r'["\'](https://account\.court\.gov\.cn/app\?back_url=[^"\'\s<>]+)["\']',
    ]
    for pat in patterns:
        match = re.search(pat, html)
        if match:
            raw = match.group(1)
            if raw.startswith("http"):
                return raw
            return f"{ACCOUNT_URL}/app?back_url={raw}"
    return None


def _get_oauth_authorize_url(session: Any) -> Optional[str]:
    """访问案例库登录入口，获取统一认证授权 URL。"""
    # 先访问首页，拿到初始 Cookie
    home_resp = safe_request(session, "GET", BASE_URL)
    if home_resp is None:
        return None

    # 尝试从首页解析登录链接
    back_url = _extract_login_back_url(home_resp.text)
    if back_url:
        return back_url

    # 若首页未解析到，尝试访问一个可能触发登录的页面（如个人中心），观察重定向
    trigger_url = f"{BASE_URL}/#/login"
    resp = session.get(trigger_url, allow_redirects=True)
    back_url = _extract_login_back_url(resp.text)
    if back_url:
        return back_url

    print("[WARN] 未能自动提取登录授权 URL，请确认网站结构是否变更。")
    return None


def _get_captcha(session: Any, captcha_url: Optional[str] = None) -> Optional[str]:
    """获取并显示验证码，返回用户输入的验证码文本。"""
    if captcha_url is None:
        # account.court.gov.cn 常见验证码接口
        captcha_url = f"{ACCOUNT_URL}/api/captcha?r={os.urandom(4).hex()}"

    resp = safe_request(session, "GET", captcha_url)
    if resp is None or not resp.content:
        return None

    content_type = resp.headers.get("Content-Type", "")
    if "json" in content_type:
        try:
            data = resp.json()
            # 可能的返回格式：{ "code": 200, "data": { "image": "base64..." } }
            image_b64 = data.get("data", {}).get("image") or data.get("image")
            if image_b64:
                image_bytes = base64.b64decode(image_b64)
            else:
                print("[WARN] 验证码接口返回 JSON 但无图片字段。")
                return None
        except json.JSONDecodeError:
            image_bytes = resp.content
    else:
        image_bytes = resp.content

    # 保存验证码图片供人工识别
    captcha_path = Path("output/rmfyalk_captcha.jpg")
    captcha_path.parent.mkdir(parents=True, exist_ok=True)
    captcha_path.write_bytes(image_bytes)
    print(f"[INFO] 验证码已保存：{captcha_path.resolve()}")
    code = input("请输入验证码（不区分大小写）：").strip()
    return code


def _extract_hidden_inputs(html: str) -> Dict[str, str]:
    """从登录页表单提取隐藏字段。"""
    soup = BeautifulSoup(html, "html.parser")
    fields: Dict[str, str] = {}
    for inp in soup.find_all("input", {"type": "hidden"}):
        name = inp.get("name") or inp.get("id")
        value = inp.get("value", "")
        if name:
            fields[name] = value
    return fields


def login(
    username: str,
    password: str,
    session: Optional[Any] = None,
    verify_code: Optional[str] = None,
) -> Any:
    """执行 account.court.gov.cn 登录，并返回带登录态的 Session。"""
    if session is None:
        session = create_session()

    # 1. 获取授权页 URL
    authorize_url = _get_oauth_authorize_url(session)
    if authorize_url is None:
        print("[ERROR] 无法获取登录授权页，登录失败。")
        return session

    # 2. 访问授权页，拿到登录表单及必要 Cookie
    resp = session.get(authorize_url, allow_redirects=True)
    resp.raise_for_status()
    login_page_html = resp.text
    hidden_fields = _extract_hidden_inputs(login_page_html)

    # 3. 如需验证码且未提供，则获取
    if verify_code is None and "captcha" in login_page_html.lower():
        verify_code = _get_captcha(session)

    # 4. 调用登录接口
    payload: Dict[str, Any] = {
        "username": username,
        "password": password,
        **hidden_fields,
    }
    if verify_code:
        payload["verifyCode"] = verify_code
        payload["captcha"] = verify_code

    print(f"[INFO] 正在登录 {LOGIN_API} ...")
    login_resp = session.post(LOGIN_API, json=payload, allow_redirects=True)

    try:
        login_data = login_resp.json()
        if login_data.get("code") not in (200, "200", 0, "0", None):
            print(f"[ERROR] 登录接口返回异常：{login_data}")
            return session
        print("[INFO] 登录接口调用成功，正在完成授权跳转...")
    except json.JSONDecodeError:
        # 部分场景登录成功后直接返回 302/html，走 OAuth 重定向
        print("[INFO] 登录响应非 JSON，尝试跟随页面重定向...")

    # 5. 跟随 OAuth 重定向回到 rmfyalk
    # requests 默认已跟随重定向，但为确保拿到最终 rmfyalk Cookie，再访问一次首页
    final_resp = session.get(BASE_URL, allow_redirects=True)
    if BASE_URL in final_resp.url:
        print("[INFO] 登录态已写入 rmfyalk.court.gov.cn Session。")
    else:
        print(f"[WARN] 最终 URL 为 {final_resp.url}，请检查是否登录成功。")

    sleep_seconds(1)
    return session


def save_session(session: Any, path: Path) -> None:
    """将 Session 的 cookies 序列化保存。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cookies = {c.name: c.value for c in session.cookies}
    with path.open("w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Session cookies 已保存：{path}")


def load_session(session: Any, path: Path) -> Any:
    """从文件加载 cookies 到 Session。"""
    path = Path(path)
    if not path.exists():
        return session
    with path.open("r", encoding="utf-8") as f:
        cookies = json.load(f)
    session.cookies.update(cookies)
    print(f"[INFO] 已从 {path} 加载 Session cookies。")
    return session


def search_cases(
    session: Any,
    keyword: str = "",
    case_type: str = "",
    page: int = 1,
    page_size: int = 10,
) -> Optional[Dict[str, Any]]:
    """案例库列表查询。"""
    payload = {
        "pageNum": page,
        "pageSize": page_size,
        "keyword": keyword,
        "caseType": case_type,
    }
    resp = safe_request(session, "POST", SEARCH_API, json=payload)
    if resp is None:
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        print("[WARN] 返回非 JSON，可能接口已变更、未登录或触发反爬。")
        return {"raw_html_length": len(resp.text), "url": resp.url}


def fetch_case_detail(session: Any, case_id: str) -> Optional[Dict[str, Any]]:
    """根据案例 ID 获取详情。"""
    resp = safe_request(session, "POST", DETAIL_API, json={"id": case_id})
    if resp is None:
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        return {"raw_html_length": len(resp.text), "url": resp.url}


def _read_secret(env_name: str, prompt: str) -> str:
    """从环境变量读取，否则交互式输入。"""
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    return getpass.getpass(prompt)


def main() -> None:
    parser = argparse.ArgumentParser(description="人民法院案例库案例检索（支持登录）")
    parser.add_argument("--keyword", default="", help="检索关键词")
    parser.add_argument("--case-type", default="", help="案例类型代码")
    parser.add_argument("--page", type=int, default=1, help="页码")
    parser.add_argument("--page-size", type=int, default=10, help="每页条数")
    parser.add_argument("--case-id", default="", help="案例 ID，提供时获取详情")
    parser.add_argument("--username", default="", help=f"账号（也可通过环境变量 {ENV_USERNAME} 设置）")
    parser.add_argument("--password", default="", help="密码（建议用环境变量或交互式输入，避免历史记录）")
    parser.add_argument("--verify-code", default="", help="验证码")
    parser.add_argument("--save-session", type=Path, default=None, help="登录成功后保存 cookies 到文件")
    parser.add_argument("--load-session", type=Path, default=None, help="从文件加载 cookies，跳过登录")
    parser.add_argument("--output", type=Path, default=Path("output/rmfyalk_result.json"))
    args = parser.parse_args()

    # 初始化 Session
    session = create_session()

    # 优先加载已有 Session
    if args.load_session:
        session = load_session(session, args.load_session)
    elif args.username or os.environ.get(ENV_USERNAME):
        username = args.username or os.environ.get(ENV_USERNAME, "").strip()
        password = args.password or _read_secret(ENV_PASSWORD, "请输入登录密码：")
        session = login(username, password, session=session, verify_code=args.verify_code or None)
        if args.save_session:
            save_session(session, args.save_session)
    else:
        print("[INFO] 未提供账号，将以未登录模式访问。")

    # 执行查询
    if args.case_id:
        result = fetch_case_detail(session, args.case_id)
    else:
        result = search_cases(session, args.keyword, args.case_type, args.page, args.page_size)

    if result is not None:
        save_json(result, args.output)
    else:
        print("[ERROR] 未获取到结果。")


if __name__ == "__main__":
    main()
