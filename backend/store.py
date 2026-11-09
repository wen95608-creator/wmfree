"""数据仓库:平台 cookie 存取 + 下载历史。

cookie 写入统一走 _sync_save_cookies(文件锁),供异步接口和扫码登录线程共用。
"""
import asyncio
import json
import os
import threading

import config

COOKIES_FILE = os.path.join(config.DATA_DIR, "cookies.json")
HISTORY_FILE = os.path.join(config.DATA_DIR, "history.json")

_history_lock = asyncio.Lock()
_cookie_file_lock = threading.Lock()

SUPPORTED_PLATFORMS = [
    "douyin", "kuaishou", "tiktok", "instagram", "youtube",
    "twitter", "bilibili", "facebook",
]


def _sync_load_cookies() -> dict:
    with _cookie_file_lock:
        if os.path.exists(COOKIES_FILE):
            try:
                return json.load(open(COOKIES_FILE, encoding="utf-8"))
            except Exception:
                return {}
        return {}


def _sync_save_cookies(cookies: dict):
    with _cookie_file_lock:
        json.dump(cookies, open(COOKIES_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)


async def load_cookies() -> dict:
    return await asyncio.to_thread(_sync_load_cookies)


async def save_cookie(platform: str, raw: str) -> bool:
    if platform not in SUPPORTED_PLATFORMS:
        return False
    cookies = await asyncio.to_thread(_sync_load_cookies)
    cookies[platform] = raw.strip()
    await asyncio.to_thread(_sync_save_cookies, cookies)
    return True


def save_cookie_sync(platform: str, raw: str) -> bool:
    """扫码登录线程直接调用(无 asyncio 上下文)。"""
    if platform not in SUPPORTED_PLATFORMS:
        return False
    cookies = _sync_load_cookies()
    cookies[platform] = raw.strip()
    _sync_save_cookies(cookies)
    return True


async def delete_cookie(platform: str):
    cookies = await asyncio.to_thread(_sync_load_cookies)
    cookies.pop(platform, None)
    await asyncio.to_thread(_sync_save_cookies, cookies)


async def append_history(entry: dict):
    async with _history_lock:
        def write():
            hist = []
            if os.path.exists(HISTORY_FILE):
                try:
                    hist = json.load(open(HISTORY_FILE, encoding="utf-8"))
                except Exception:
                    hist = []
            hist.insert(0, entry)
            json.dump(hist[:500], open(HISTORY_FILE, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)

        await asyncio.to_thread(write)


async def read_history() -> list:
    def read():
        if os.path.exists(HISTORY_FILE):
            try:
                return json.load(open(HISTORY_FILE, encoding="utf-8"))
            except Exception:
                return []
        return []

    return await asyncio.to_thread(read)
