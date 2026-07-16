# -*- coding: utf-8 -*-
"""人民法院案例库 (rmfyalk.court.gov.cn) 公开案例检索。

说明：
- 该网站案例详情为公开内容，搜索接口无需登录。
- 如网站启用验证码或反爬，请降低请求频率或人工处理。
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils import create_session, safe_request, save_json, sleep_seconds

BASE_URL = "https://rmfyalk.court.gov.cn"
SEARCH_API = f"{BASE_URL}/rest/listQuery"


def search_cases(
    keyword: str = "",
    case_type: str = "",
    page: int = 1,
    page_size: int = 10,
) -> Optional[Dict[str, Any]]:
    """案例库列表查询。

    参数：
        keyword: 检索关键词
        case_type: 案例类型，如 ms（民事）、xs（刑事）、xz（行政）等
        page: 页码
        page_size: 每页条数
    """
    session = create_session()
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
        print("[WARN] 返回非 JSON，可能接口已变更或触发反爬。")
        return {"raw_html_length": len(resp.text)}


def fetch_case_detail(case_id: str) -> Optional[Dict[str, Any]]:
    """根据案例 ID 获取详情。"""
    session = create_session()
    url = f"{BASE_URL}/rest/detail"
    resp = safe_request(session, "POST", url, json={"id": case_id})
    if resp is None:
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        return {"raw_html_length": len(resp.text)}


def main() -> None:
    parser = argparse.ArgumentParser(description="人民法院案例库公开案例检索")
    parser.add_argument("--keyword", default="", help="检索关键词")
    parser.add_argument("--case-type", default="", help="案例类型代码")
    parser.add_argument("--page", type=int, default=1, help="页码")
    parser.add_argument("--page-size", type=int, default=10, help="每页条数")
    parser.add_argument("--case-id", default="", help="案例 ID，提供时获取详情")
    parser.add_argument("--output", type=Path, default=Path("output/rmfyalk_result.json"))
    args = parser.parse_args()

    if args.case_id:
        result = fetch_case_detail(args.case_id)
    else:
        result = search_cases(args.keyword, args.case_type, args.page, args.page_size)

    if result is not None:
        save_json(result, args.output)
    else:
        print("[ERROR] 未获取到结果。")


if __name__ == "__main__":
    main()
