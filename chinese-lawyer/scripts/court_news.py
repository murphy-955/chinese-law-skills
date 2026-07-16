# -*- coding: utf-8 -*-
"""中华人民共和国最高人民法院官网 (www.court.gov.cn) 公开新闻/公告抓取。"""

import argparse
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup
from utils import create_session, safe_request, save_json, sleep_seconds

BASE_URL = "https://www.court.gov.cn"


def fetch_news_list(channel: str = "", page: int = 1, limit: int = 20) -> List[Dict[str, str]]:
    """抓取最高法官网新闻列表。

    常见栏目示例：
    - 新闻：zixun/
    - 政务：zhengwu/
    - 公报：gongbao/
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
    selectors = [
        ".news_list li a",
        ".list_cont li a",
        ".content-list li a",
        ".main-list li a",
        ".newsBox li a",
        "ul.news-list li a",
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
    """抓取单篇正文。"""
    session = create_session()
    resp = safe_request(session, "GET", url)
    if resp is None:
        return {"url": url, "error": "请求失败"}

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    content = "\n".join(p.get_text(strip=True) for p in soup.select(".detail-cont p, .content p, #content p, .TRS_Editor p, p"))
    pub_time = ""
    for sel in [".detail_time", ".time", ".date", ".source", "span.time"]:
        node = soup.select_one(sel)
        if node:
            pub_time = node.get_text(strip=True)
            break

    sleep_seconds(1)
    return {"url": url, "title": title, "pub_time": pub_time, "content": content}


def main() -> None:
    parser = argparse.ArgumentParser(description="最高人民法院官网公开新闻抓取")
    parser.add_argument("--channel", default="", help="栏目路径片段，例如 zixun")
    parser.add_argument("--page", type=int, default=1, help="页码")
    parser.add_argument("--limit", type=int, default=20, help="最多条数")
    parser.add_argument("--article-url", default="", help="如提供则抓取单篇正文")
    parser.add_argument("--output", type=Path, default=Path("output/court_news.json"))
    args = parser.parse_args()

    if args.article_url:
        result = fetch_article(args.article_url)
    else:
        result = fetch_news_list(args.channel, args.page, args.limit)

    save_json(result, args.output)


if __name__ == "__main__":
    main()
