# -*- coding: utf-8 -*-
"""中国法院网 (www.chinacourt.cn) 公开新闻/公告抓取。"""

import argparse
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup
from utils import create_session, safe_request, save_json, sleep_seconds

BASE_URL = "https://www.chinacourt.cn"


def fetch_channel_news(channel: str = "article", page: int = 1, limit: int = 20) -> List[Dict[str, str]]:
    """抓取中国法院网栏目新闻。

    常见栏目：
    - article: 法院资讯
    - search.shtml: 搜索页
    """
    session = create_session()
    if page > 1:
        url = f"{BASE_URL}/{channel.strip('/')}/index_{page}.shtml"
    else:
        url = f"{BASE_URL}/{channel.strip('/')}/"

    resp = safe_request(session, "GET", url)
    if resp is None:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items: List[Dict[str, str]] = []
    selectors = [
        ".news_list li a",
        ".list li a",
        ".main-list li a",
        "#news_list li a",
        "ul li a",
    ]
    for selector in selectors:
        for a in soup.select(selector):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if title and len(title) > 3:
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
    content = "\n".join(p.get_text(strip=True) for p in soup.select("#content p, .content p, .article-content p, p"))
    pub_time = ""
    for sel in [".date", ".time", "#pubtime", ".article-info", "span.time"]:
        node = soup.select_one(sel)
        if node:
            pub_time = node.get_text(strip=True)
            break

    sleep_seconds(1)
    return {"url": url, "title": title, "pub_time": pub_time, "content": content}


def main() -> None:
    parser = argparse.ArgumentParser(description="中国法院网公开新闻抓取")
    parser.add_argument("--channel", default="article", help="栏目路径")
    parser.add_argument("--page", type=int, default=1, help="页码")
    parser.add_argument("--limit", type=int, default=20, help="最多条数")
    parser.add_argument("--article-url", default="", help="如提供则抓取单篇正文")
    parser.add_argument("--output", type=Path, default=Path("output/chinacourt_news.json"))
    args = parser.parse_args()

    if args.article_url:
        result = fetch_article(args.article_url)
    else:
        result = fetch_channel_news(args.channel, args.page, args.limit)

    save_json(result, args.output)


if __name__ == "__main__":
    main()
