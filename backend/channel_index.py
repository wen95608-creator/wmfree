"""频道全量视频索引:扫描 t.me embed 页提取视频直链。

- 零登录、零 MTProto:公开频道 embed 页自带 CDN 直链(带签名 token)
- 服务器不存视频:直链实时解析,播放走 302 重定向到 Telegram CDN
- 索引(videos.json)只是文字元数据,几十 KB
"""
import asyncio
import json
import re
import time

import httpx

import config
import store

CHANNEL_USERNAME = config.CHANNEL.lstrip("@")
EMBED_URL = f"https://t.me/{CHANNEL_USERNAME}/{{mid}}?embed=1&mode=tme"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
CONCURRENCY = 12
STOP_AFTER_EMPTY = 12          # 连续 12 个 mid 无消息即认为到头
SCAN_INTERVAL = 300            # 增量扫描最小间隔(秒)

_link_cache = {}               # mid -> (src, ts)
_last_scan = 0.0
_scan_lock = asyncio.Lock()


def _parse_embed(html: str, mid: int) -> dict | None:
    m = re.search(r'<video[^>]*src="([^"]+)"', html)
    if not m:
        return None
    src = m.group(1).replace("&amp;", "&")
    title = ""
    mt = re.search(r'tgme_widget_message_text[^>]*>([^<]{1,120})', html)
    if mt:
        title = mt.group(1).strip()
    dur = 0
    md = re.search(r'(\d+):(\d\d)[\s<]', html)
    if md:
        dur = int(md.group(1)) * 60 + int(md.group(2))
    return {
        "mid": mid,
        "title": (title or f"频道视频 {mid}")[:80],
        "platform": "频道",
        "size_mb": 0,
        "duration": dur,
        "file_id": "",
        "source": "embed",
        "streamable": True,
        "time": "",
    }


async def _fetch_one(client: httpx.AsyncClient, mid: int) -> dict | None:
    try:
        r = await client.get(EMBED_URL.format(mid=mid), headers={"User-Agent": UA},
                             follow_redirects=True)
        if r.status_code != 200 or "tgme_widget_message" not in r.text:
            return None
        return _parse_embed(r.text, mid)
    except Exception:
        return None


async def scan_channel(force: bool = False) -> int:
    """扫描频道全部历史视频,合并进 videos.json。返回索引总数。"""
    global _last_scan
    async with _scan_lock:
        if not force and time.time() - _last_scan < SCAN_INTERVAL:
            vids = await store.list_videos(1000)
            return len(vids)

        known = {v["mid"]: v for v in await store.list_videos(2000)}
        max_known = max(known) if known else 0
        upper = max_known + 30     # 向上多探一段,防手动发过消息

        results = {}
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            sem = asyncio.Semaphore(CONCURRENCY)
            empty_streak = 0
            hit_upper = False

            async def probe(mid: int):
                nonlocal empty_streak
                async with sem:
                    if empty_streak >= STOP_AFTER_EMPTY:
                        return
                    v = await _fetch_one(client, mid)
                    if v:
                        empty_streak = 0
                        results[mid] = v
                        if mid > max_known:
                            hit_upper = True
                    else:
                        # 无视频也可能是文字消息;只有完全无消息页才算空
                        try:
                            r = await client.get(EMBED_URL.format(mid=mid),
                                                 headers={"User-Agent": UA},
                                                 follow_redirects=True)
                            if r.status_code != 200 or "tgme_widget_message" not in r.text:
                                empty_streak += 1
                            else:
                                empty_streak = 0
                        except Exception:
                            empty_streak += 1

            # 全量扫 1..upper(频道刚建,量小);以后增量走 known 之外区间
            lo = 1 if len(known) < max_known else max(1, max_known - 20)
            tasks = [probe(m) for m in range(lo, upper + 1)]
            await asyncio.gather(*tasks)

        # 合并:bot 索引(file_id)优先,embed 补充
        for mid, v in results.items():
            if mid not in known:
                known[mid] = v
        merged = sorted(known.values(), key=lambda x: -x["mid"])
        with open(store.VIDEO_FILE, "w", encoding="utf-8") as f:
            json.dump(merged[:1000], f, ensure_ascii=False, indent=2)
        _last_scan = time.time()
        return len(merged)


async def resolve_stream_url(mid: int) -> str | None:
    """实时解析 embed 直链(带 3 分钟缓存);bot file_id 的视频由调用方优先走 Bot API。"""
    cached = _link_cache.get(mid)
    if cached and time.time() - cached[1] < 180:
        return cached[0]
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        v = await _fetch_one(client, mid)
    if not v:
        return None
    # 直链内容未知时取页面 video src
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            r = await client.get(EMBED_URL.format(mid=mid), headers={"User-Agent": UA},
                                 follow_redirects=True)
        m = re.search(r'<video[^>]*src="([^"]+)"', r.text)
        if not m:
            return None
        src = m.group(1).replace("&amp;", "&")
        _link_cache[mid] = (src, time.time())
        return src
    except Exception:
        return None
