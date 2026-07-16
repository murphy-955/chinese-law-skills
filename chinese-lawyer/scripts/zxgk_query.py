# -*- coding: utf-8 -*-
"""中国执行信息公开网 (zxgk.court.gov.cn) 公开信息查询。

支持查询：
- 失信被执行人
- 被执行人
- 限制消费人员
- 被执行人信息综合查询（首页入口）

说明：本脚本仅使用网站公开页面/接口，不处理验证码与登录逻辑。
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils import create_session, safe_request, save_json, sleep_seconds

BASE_URL = "https://zxgk.court.gov.cn"


def search_dishonesty(
    name: str,
    card_num: str = "",
    page: int = 1,
    page_size: int = 10,
) -> Optional[Dict[str, Any]]:
    """查询失信被执行人列表。

    接口参考：zxgk.court.gov.cn/zhixing/new_index.html
    """
    session = create_session()
    url = f"{BASE_URL}/zhzxgk/newZhcxSearchMores.do"
    payload = {
        "searchCourtName": "全国法院（包含地方各级法院）",
        "pName": name,
        "pCardNum": card_num,
        "selectCourtId": 0,
        "pCode": "",
        "captchaId": "",
        "currentPage": page,
        "pageSize": page_size,
    }
    resp = safe_request(session, "POST", url, data=payload)
    if resp is None:
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        print("[WARN] 返回非 JSON，可能是页面更新或触发验证码。")
        return {"raw_html_length": len(resp.text)}


def search_zhixing(
    name: str,
    card_num: str = "",
    page: int = 1,
    page_size: int = 10,
) -> Optional[Dict[str, Any]]:
    """查询被执行人列表。"""
    session = create_session()
    url = f"{BASE_URL}/zhzxgk/newZhcxSearchMores.do"
    payload = {
        "searchCourtName": "全国法院（包含地方各级法院）",
        "pName": name,
        "pCardNum": card_num,
        "selectCourtId": 0,
        "pCode": "",
        "captchaId": "",
        "currentPage": page,
        "pageSize": page_size,
    }
    resp = safe_request(session, "POST", url, data=payload)
    if resp is None:
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        return {"raw_html_length": len(resp.text)}


def fetch_index_notices(limit: int = 10) -> List[Dict[str, str]]:
    """抓取首页公告/动态列表（如网站结构变更需调整选择器）。"""
    session = create_session()
    url = f"{BASE_URL}/"
    resp = safe_request(session, "GET", url)
    if resp is None:
        return []
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(resp.text, "html.parser")
    items: List[Dict[str, str]] = []
    for a in soup.select(".notice-list a, .news-list a, ul.list a")[:limit]:
        items.append({
            "title": a.get_text(strip=True),
            "href": a.get("href", ""),
        })
    sleep_seconds(1)
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="中国执行信息公开网公开数据查询")
    parser.add_argument("--name", required=True, help="被执行人/失信被执行人姓名或名称")
    parser.add_argument("--card-num", default="", help="身份证号/组织机构代码（可选）")
    parser.add_argument("--type", choices=["dishonesty", "zhixing", "index"], default="dishonesty",
                        help="查询类型：dishonesty=失信被执行人，zhixing=被执行人，index=首页公告")
    parser.add_argument("--page", type=int, default=1, help="页码")
    parser.add_argument("--page-size", type=int, default=10, help="每页条数")
    parser.add_argument("--output", type=Path, default=Path("output/zxgk_result.json"),
                        help="输出 JSON 路径")
    args = parser.parse_args()

    if args.type == "dishonesty":
        result = search_dishonesty(args.name, args.card_num, args.page, args.page_size)
    elif args.type == "zhixing":
        result = search_zhixing(args.name, args.card_num, args.page, args.page_size)
    else:
        result = fetch_index_notices(args.page_size)

    if result is not None:
        save_json(result, args.output)
    else:
        print("[ERROR] 未获取到结果。")


if __name__ == "__main__":
    main()
