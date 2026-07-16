# -*- coding: utf-8 -*-
"""公共工具函数：HTTP 会话、请求重试、结果保存等。"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def create_session(
    retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: int = 30,
) -> requests.Session:
    """创建带重试机制的 requests Session。"""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.timeout = timeout
    return session


def safe_request(
    session: requests.Session,
    method: str,
    url: str,
    **kwargs,
) -> Optional[requests.Response]:
    """发送请求并做基础异常处理。"""
    try:
        resp = session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        print(f"[ERROR] 请求失败 {method} {url}: {exc}")
        return None


def save_json(data: Any, output_path: Path, indent: int = 2) -> None:
    """将数据保存为 JSON 文件。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    print(f"[INFO] 结果已保存: {output_path}")


def sleep_seconds(seconds: float = 1.0) -> None:
    """礼貌暂停，避免请求过快。"""
    time.sleep(seconds)
