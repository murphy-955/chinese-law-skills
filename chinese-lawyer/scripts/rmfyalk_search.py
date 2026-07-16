# -*- coding: utf-8 -*-
"""人民法院案例库 (rmfyalk.court.gov.cn) 案例检索与详情获取。

本脚本直接调用 `cpws_al_api` 接口：
- 检索：POST /cpws_al_api/api/cpwsAl/search
- 详情：POST /cpws_al_api/api/cpwsAl/content

说明：
- 暂不考虑登录流程，调用前请通过浏览器开发者工具复制 `faxin-cpws-al-token`。
- Token 可通过环境变量 `RMFYALK_TOKEN` 或命令行 `--token` 传入。
- 接口返回的 id/gid 通常为 URL 编码形式，脚本会原样透传。
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from utils import create_session, safe_request, save_json, sleep_seconds

BASE_URL = "https://rmfyalk.court.gov.cn"
SEARCH_API = f"{BASE_URL}/cpws_al_api/api/cpwsAl/search"
DETAIL_API = f"{BASE_URL}/cpws_al_api/api/cpwsAl/content"

ENV_TOKEN = "RMFYALK_TOKEN"


def _build_headers(token: str) -> Dict[str, str]:
    """构造接口请求头，Token 同时放入 Cookie 与自定义请求头。"""
    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Connection": "keep-alive",
        "Content-Type": "application/json;charset=UTF-8",
        "Cookie": f"faxin-cpws-al-token={token}",
        "faxin-cpws-al-token": token,
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
    """案例库检索。

    参数：
        token: 登录态 JWT
        keyword: 检索关键词，对应 searchParams.keyTitle
        search_type: 用户检索类型，默认 1
        is_adv_search: 是否高级检索，默认 "0"
        select_value: 检索字段列表，默认 ["qw"]（全文）
        lib: 库标识，默认 "qb"（全部）
        page: 页码，从 1 开始
        size: 每页条数
        sort_field: 排序字段，默认空
    """
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
        """去除 HTML 标签并清理空白。"""
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


def _read_token(args_token: str) -> str:
    """从命令行或环境变量读取 Token。"""
    token = (args_token or os.environ.get(ENV_TOKEN, "")).strip()
    if not token:
        raise SystemExit(
            f"[ERROR] 未提供 Token。请通过 --token 传入或设置环境变量 {ENV_TOKEN}。"
        )
    return token


def main() -> None:
    parser = argparse.ArgumentParser(description="人民法院案例库接口查询（Token 模式）")
    parser.add_argument("--token", default="", help=f"登录 Token（也可设置环境变量 {ENV_TOKEN}）")
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
        help="仅提取详情中的注释/要旨信息（需配合 --gid 或 --keyword 使用）",
    )
    parser.add_argument("--output", type=Path, default=Path("output/rmfyalk_result.json"))
    args = parser.parse_args()

    token = _read_token(args.token)

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
            # 对检索结果中的每条案例获取详情并提取注释
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
