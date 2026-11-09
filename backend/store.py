"""数据仓库:平台 cookie 存取 + 下载历史。"""
import asyncio
import json
import os

import config

COOKIES_FILE = os.path.join(config.DATA_DIR, "cookies.json")
HISTORY_FILE = os.path.join(config.DATA_DIR, "history.json")

_cookie_lock = asyncio.Lock()
_history_lock = asyncio.Lock()

SUPPORTED_PLATFORMS = [
    "douyin", "kuaishou", "tiktok", "instagram", "youtube",
    "twitter", "bilibili", "facebook",
]


async def load_cookies() -> dict:
    def read():
        if os.path.exists(COOKIES_FILE):
            try:
                return json.load(open(COOKIES_FILE, encoding="utf-8"))
            except Exception:
                return {}
        return {}

    return await asyncio.to_thread(read)


async def save_cookie(platform: str, raw: str) -> bool:
    if platform not in SUPPORTED_PLATFORMS:
        return False
    async with _cookie_lock:
        cookies = await load_cookies()
        cookies[platform] = raw.strip()
        await asyncio.to_thread(
            lambda: json.dump(cookies, open(COOKIES_FILE, "w", encoding="utf-8"),
                              ensure_ascii=False, indent=2))
    return True


async def delete_cookie(platform: str):
    async with _cookie_lock:
        cookies = await load_cookies()
        cookies.pop(platform, None)
        await asyncio.to_thread(
            lambda: json.dump(cookies, open(COOKIES_FILE, "w", encoding="utf-8"),
                              ensure_ascii=False, indent=2))


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
