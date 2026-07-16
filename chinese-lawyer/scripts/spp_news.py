# -*- coding: utf-8 -*-
"""最高人民检察院官网 (www.spp.gov.cn) 公开新闻/公告抓取。"""

import argparse
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from utils import create_session, safe_request, save_json, sleep_seconds

BASE_URL = "https://www.spp.gov.cn"


def fetch_news_list(channel: str = "", page: int = 1, limit: int = 20) -> List[Dict[str, str]]:
    """抓取最高检官网新闻列表。

    参数：
        channel: 栏目路径片段，例如 "spp/zdgz/202407" 等；为空则抓取首页。
        page: 页码（部分栏目支持分页参数，如 page/2）。
        limit: 最多返回条数。
    """
    session = create_session()
    if channel:
        url = f"{BASE_URL}/{channel.strip('/')}/"
    else:
        url = BASE_URL

    if page > 1:
        url = f"{url.rstrip('/')}/index_{page}.html"

    resp = safe_request(session, "GET", url)
    if resp is None:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items: List[Dict[str, str]] = []

    # 通用选择器：覆盖首页与多数栏目页
    selectors = [
        ".news-list li a",
        ".list li a",
        ".cont-list li a",
        ".main-list li a",
        "#listbox li a",
        "ul.list-a li a",
        ".focus-news a",
    ]
    for selector in selectors:
        for a in soup.select(selector):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if title:
                if href and not href.startswith(("http://", "https://")):
                    href = f"{BASE_URL}{href}"
                items.append({"title": title, "href": href})
        if len(items) >= limit:
            break

    sleep_seconds(1)
    return items[:limit]


def fetch_article(url: str) -> Dict[str, str]:
    """抓取单篇正文，提取标题、发布时间、正文文本。"""
    session = create_session()
    resp = safe_request(session, "GET", url)
    if resp is None:
        return {"url": url, "error": "请求失败"}

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    content = "\n".join(p.get_text(strip=True) for p in soup.select(".detail-content p, .content p, #content p, p"))
    pub_time = ""
    for sel in [".date", ".time", ".pub-time", "span.time", "#pubTime"]:
        node = soup.select_one(sel)
        if node:
            pub_time = node.get_text(strip=True)
            break

    sleep_seconds(1)
    return {"url": url, "title": title, "pub_time": pub_time, "content": content}


def main() -> None:
    parser = argparse.ArgumentParser(description="最高人民检察院官网公开新闻抓取")
    parser.add_argument("--channel", default="", help="栏目路径片段")
    parser.add_argument("--page", type=int, default=1, help="页码")
    parser.add_argument("--limit", type=int, default=20, help="最多条数")
    parser.add_argument("--article-url", default="", help="如提供则抓取单篇正文")
    parser.add_argument("--output", type=Path, default=Path("output/spp_news.json"))
    args = parser.parse_args()

    if args.article_url:
        result = fetch_article(args.article_url)
    else:
        result = fetch_news_list(args.channel, args.page, args.limit)

    save_json(result, args.output)


if __name__ == "__main__":
    main()
