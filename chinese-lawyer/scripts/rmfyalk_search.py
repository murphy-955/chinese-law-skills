# -*- coding: utf-8 -*-
"""人民法院案例库 (rmfyalk.court.gov.cn) 案例检索与详情获取。

本脚本直接调用 `cpws_al_api` 接口：
- 检索：POST /cpws_al_api/api/cpwsAl/search
- 详情：POST /cpws_al_api/api/cpwsAl/content

登录策略：
1. 优先使用命令行或环境变量传入的 `faxin-cpws-al-token`。
2. 若未提供 Token 或 Token 已过期，启用浏览器自动化登录：
   - 自动打开 Chromium 浏览器并跳转至人民法院案例库登录页；
   - 用户在浏览器中自由选择账号密码、支付宝、短信等方式完成登录；
   - 登录成功后脚本自动从 Cookie 中提取 Token 并保存。
3. Token 保存到本地文件后可复用，4 小时过期前无需再次登录。

说明：
- 浏览器模式默认非无头（headless=False），以便用户扫码/授权。
- 支付宝、短信等登录方式均由用户在真实浏览器中完成，脚本不做特殊处理。
"""

import argparse
import base64
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from utils import create_session, safe_request, save_json, sleep_seconds

BASE_URL = "https://rmfyalk.court.gov.cn"
LOGIN_TRIGGER_URL = f"{BASE_URL}/#/login"
SEARCH_API = f"{BASE_URL}/cpws_al_api/api/cpwsAl/search"
DETAIL_API = f"{BASE_URL}/cpws_al_api/api/cpwsAl/content"

ENV_TOKEN = "RMFYALK_TOKEN"
TOKEN_COOKIE_NAME = "faxin-cpws-al-token"


def _build_headers(token: str) -> Dict[str, str]:
    """构造接口请求头，Token 同时放入 Cookie 与自定义请求头。"""
    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Connection": "keep-alive",
        "Content-Type": "application/json;charset=UTF-8",
        "Cookie": f"{TOKEN_COOKIE_NAME}={token}",
        TOKEN_COOKIE_NAME: token,
        "Host": "rmfyalk.court.gov.cn",
        "Origin": "https://rmfyalk.court.gov.cn",
        "Referer": "https://rmfyalk.court.gov.cn/view/list.html",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }


def _decode_jwt_exp(token: str) -> Optional[int]:
    """解析 JWT 的 exp 字段，返回 Unix 时间戳。"""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64).decode("utf-8"))
        return int(payload.get("exp", 0))
    except Exception:
        return None


def is_token_expired(token: str, margin_seconds: int = 300) -> bool:
    """判断 Token 是否在 margin_seconds 内过期（默认提前 5 分钟视为过期）。"""
    exp = _decode_jwt_exp(token)
    if not exp:
        return True
    return time.time() + margin_seconds >= exp


def format_expiry(token: str) -> str:
    """格式化 Token 过期时间。"""
    exp = _decode_jwt_exp(token)
    if not exp:
        return "未知"
    dt = datetime.fromtimestamp(exp, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def load_token(path: Path) -> Optional[str]:
    """从文件加载 Token，过期返回 None。"""
    path = Path(path)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        token = data.get("token") if isinstance(data, dict) else data
        if token and not is_token_expired(token):
            print(f"[INFO] 已从 {path} 加载有效 Token，过期时间：{format_expiry(token)}")
            return token
        if token:
            print(f"[INFO] 文件中的 Token 已过期（过期时间：{format_expiry(token)}）。")
        return None
    except Exception as exc:
        print(f"[WARN] 加载 Token 文件失败：{exc}")
        return None


def save_token(token: str, path: Path) -> None:
    """保存 Token 及过期时间到文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "token": token,
        "exp": _decode_jwt_exp(token),
        "exp_readable": format_expiry(token),
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Token 已保存：{path}")


def browser_login(
    headless: bool = False,
    timeout: int = 300,
    user_data_dir: Optional[Path] = None,
) -> Optional[str]:
    """通过 Playwright 打开浏览器让用户完成登录，并提取 Token。

    参数：
        headless: 是否无头运行。默认 False，因为支付宝等需要用户交互。
        timeout: 等待登录的最大秒数，默认 300 秒（5 分钟）。
        user_data_dir: 持久化浏览器用户数据目录，可复用登录态。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "[ERROR] 未安装 Playwright。请执行：pip install playwright && playwright install chromium"
        )

    token: Optional[str] = None

    with sync_playwright() as p:
        browser_type = p.chromium

        if user_data_dir:
            context = browser_type.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()
        else:
            browser = browser_type.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context()
            page = context.new_page()

        print("[INFO] 正在打开浏览器...")
        page.goto(LOGIN_TRIGGER_URL)

        print(
            "\n========================================\n"
            "请在浏览器中完成登录。\n"
            "支持方式：账号密码 / 支付宝 / 短信 等。\n"
            "登录成功后，脚本会自动提取 Token 并关闭浏览器。\n"
            "========================================\n"
        )

        deadline = time.time() + timeout
        while time.time() < deadline:
            cookies = context.cookies()
            for cookie in cookies:
                if cookie.get("name") == TOKEN_COOKIE_NAME:
                    token = cookie.get("value")
                    break
            if token:
                print(f"[INFO] 检测到登录 Token，过期时间：{format_expiry(token)}")
                break
            time.sleep(2)

        if user_data_dir:
            context.close()
        else:
            browser.close()

    return token


def ensure_token(
    token: Optional[str],
    token_file: Path,
    use_browser: bool,
    headless: bool,
    browser_timeout: int,
    user_data_dir: Optional[Path],
) -> Optional[str]:
    """确保获取一个未过期的 Token。"""
    # 1. 直接使用命令行传入的 Token
    if token and not is_token_expired(token):
        print(f"[INFO] 使用传入 Token，过期时间：{format_expiry(token)}")
        return token

    # 2. 从文件加载
    file_token = load_token(token_file)
    if file_token:
        return file_token

    # 3. 浏览器自动化登录
    if use_browser:
        new_token = browser_login(
            headless=headless,
            timeout=browser_timeout,
            user_data_dir=user_data_dir,
        )
        if new_token:
            save_token(new_token, token_file)
        return new_token

    return None


def search_cases(
    token: str,
    keyword: str,
    search_type: int = 1,
    is_adv_search: str = "0",
    select_value: Optional[List[str]] = None,
    lib: str = "qb",
    page: int = 1,
    size: int = 10,
    sort_field: str = "",
) -> Optional[Dict[str, Any]]:
    """案例库检索。"""
    if select_value is None:
        select_value = ["qw"]

    session = create_session()
    headers = _build_headers(token)
    payload = {
        "page": page,
        "size": size,
        "lib": lib,
        "searchParams": {
            "userSearchType": search_type,
            "isAdvSearch": is_adv_search,
            "selectValue": select_value,
            "lib": "cpwsAl_qb",
            "sort_field": sort_field,
            "keyTitle": [keyword],
        },
    }

    resp = safe_request(session, "POST", SEARCH_API, headers=headers, json=payload)
    if resp is None:
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        print("[WARN] 返回非 JSON，可能 Token 失效或接口已变更。")
        return {"raw_html_length": len(resp.text), "url": resp.url}


def fetch_case_detail(token: str, gid: str) -> Optional[Dict[str, Any]]:
    """根据 gid 获取案例详情。"""
    session = create_session()
    headers = _build_headers(token)
    payload = {"gid": gid}

    resp = safe_request(session, "POST", DETAIL_API, headers=headers, json=payload)
    if resp is None:
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        print("[WARN] 返回非 JSON，可能 Token 失效或接口已变更。")
        return {"raw_html_length": len(resp.text), "url": resp.url}


def extract_annotations(detail_data: Dict[str, Any]) -> Dict[str, Any]:
    """从详情接口返回中提取注释/要旨类信息。

    对应接口.md 中的字段注释：
        - 入库编号 cpws_al_no
        - 一级标题 cpws_al_title
        - 二级标题 cpws_al_sub_title
        - 裁判要旨 cpws_al_cpyz
        - 关键词   cpws_al_keyword
        - 基本案情 cpws_al_jbaq
        - 裁判理由 cpws_al_cply
        - 关联索引 cpws_al_glsy
    """
    inner = detail_data.get("data", {}).get("data", {}) if isinstance(detail_data, dict) else {}

    def _strip_html(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = BeautifulSoup(value, "html.parser").get_text(separator="\n", strip=True)
        return text

    return {
        "入库编号": inner.get("cpws_al_no", ""),
        "一级标题": inner.get("cpws_al_title", ""),
        "二级标题": inner.get("cpws_al_sub_title", ""),
        "裁判要旨": _strip_html(inner.get("cpws_al_cpyz", "")),
        "关键词": inner.get("cpws_al_keyword", []),
        "基本案情": _strip_html(inner.get("cpws_al_jbaq", "")),
        "裁判理由": _strip_html(inner.get("cpws_al_cply", "")),
        "关联索引": _strip_html(inner.get("cpws_al_glsy", "")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="人民法院案例库接口查询（支持浏览器自动化登录）"
    )
    parser.add_argument("--token", default="", help=f"登录 Token（也可设置环境变量 {ENV_TOKEN}）")
    parser.add_argument(
        "--token-file",
        type=Path,
        default=Path("output/rmfyalk_token.json"),
        help="Token 缓存文件路径，默认 output/rmfyalk_token.json",
    )
    parser.add_argument(
        "--login-browser",
        action="store_true",
        help="使用浏览器自动化登录（支持账号密码/支付宝/短信等方式）",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="浏览器无头模式（默认非无头，以便扫码/授权）",
    )
    parser.add_argument(
        "--browser-timeout",
        type=int,
        default=300,
        help="等待浏览器登录的最大秒数，默认 300",
    )
    parser.add_argument(
        "--user-data-dir",
        type=Path,
        default=None,
        help="Playwright 持久化用户数据目录，可复用浏览器登录态",
    )
    parser.add_argument("--keyword", default="", help="检索关键词")
    parser.add_argument("--search-type", type=int, default=1, help="检索类型，默认 1")
    parser.add_argument("--is-adv-search", default="0", help="是否高级检索，默认 0")
    parser.add_argument("--select-value", nargs="+", default=["qw"], help="检索字段，默认 qw")
    parser.add_argument("--lib", default="qb", help="库标识，默认 qb")
    parser.add_argument("--page", type=int, default=1, help="页码")
    parser.add_argument("--size", type=int, default=10, help="每页条数")
    parser.add_argument("--gid", default="", help="案例 gid，提供时获取详情")
    parser.add_argument(
        "--annotations-only",
        action="store_true",
        help="仅提取详情中的注释/要旨信息",
    )
    parser.add_argument("--output", type=Path, default=Path("output/rmfyalk_result.json"))
    args = parser.parse_args()

    # 获取有效 Token
    token = ensure_token(
        token=(args.token or os.environ.get(ENV_TOKEN, "")).strip() or None,
        token_file=args.token_file,
        use_browser=args.login_browser,
        headless=args.headless,
        browser_timeout=args.browser_timeout,
        user_data_dir=args.user_data_dir,
    )
    if not token:
        raise SystemExit(
            "[ERROR] 未获取到有效 Token。请使用以下方式之一：\n"
            "  1) --token 或环境变量 RMFYALK_TOKEN 传入；\n"
            "  2) --login-browser 打开浏览器完成登录（支持支付宝等）；\n"
            "  3) --token-file 复用已保存的 Token。"
        )

    # 执行查询
    if args.gid:
        detail = fetch_case_detail(token, args.gid)
        result = extract_annotations(detail) if args.annotations_only else detail
    elif args.keyword:
        search_result = search_cases(
            token=token,
            keyword=args.keyword,
            search_type=args.search_type,
            is_adv_search=args.is_adv_search,
            select_value=args.select_value,
            lib=args.lib,
            page=args.page,
            size=args.size,
        )
        if search_result is None:
            print("[ERROR] 未获取到检索结果。")
            return

        if args.annotations_only:
            items = search_result.get("data", {}).get("datas", []) if isinstance(search_result, dict) else []
            annotations: List[Dict[str, Any]] = []
            for idx, item in enumerate(items, start=1):
                gid = item.get("cpws_al_id") or item.get("id")
                if not gid:
                    continue
                print(f"[INFO] 正在提取第 {idx}/{len(items)} 条案例注释：{item.get('cpws_al_title', '')}")
                detail = fetch_case_detail(token, gid)
                if detail is not None:
                    annotations.append(extract_annotations(detail))
                sleep_seconds(0.5)
            result = {
                "keyword": args.keyword,
                "total": len(annotations),
                "annotations": annotations,
            }
        else:
            result = search_result
    else:
        raise SystemExit("[ERROR] 必须提供 --gid 或 --keyword。")

    if result is not None:
        save_json(result, args.output)
    else:
        print("[ERROR] 未获取到结果。")


if __name__ == "__main__":
    main()
