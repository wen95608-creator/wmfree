"""Telegram 侧:发视频到频道 / 回复用户 / Bot 私聊轮询处理。"""
import asyncio
import os
import re

import httpx

import config
from engine import ParseError, extract_url, parse
from downloader import download_video
import store

API = f"https://api.telegram.org/bot{config.BOT_TOKEN}"
UPLOAD_TIMEOUT = httpx.Timeout(600.0)


async def tg_call(method: str, **kwargs):
    async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT) as c:
        r = await c.post(f"{API}/{method}", **kwargs)
        return r.json()


# ---------------- 发送 ----------------

async def send_video(chat_id, file_path: str, caption: str = "") -> dict | None:
    """multipart sendVideo。失败返回 None(调用方降级发文本)。"""
    with open(file_path, "rb") as f:
        r = await tg_call(
            "sendVideo",
            data={
                "chat_id": chat_id,
                "caption": caption[:1024],
                "supports_streaming": "true",
            },
            files={"video": (os.path.basename(file_path), f, "video/mp4")},
        )
    if r.get("ok"):
        return r["result"]
    return None


async def send_text(chat_id, text: str):
    return await tg_call("sendMessage", data={"chat_id": chat_id, "text": text[:4096]})


async def edit_text(chat_id, message_id, text: str):
    return await tg_call(
        "editMessageText",
        data={"chat_id": chat_id, "message_id": message_id, "text": text[:4096]},
    )


def channel_link(msg: dict) -> str:
    ch = (msg.get("chat") or {}).get("username")
    mid = msg.get("message_id")
    return f"https://t.me/{ch}/{mid}" if ch else f"https://t.me/c/{str((msg.get('chat') or {}).get('id', ''))[4:]}/{mid}"


# ---------------- 核心流程 ----------------

async def process(url: str, source: str, chat_id=None, progress_msg=None):
    """解析 -> 下载 -> 发频道 -> (可选)发用户 -> 清理临时文件。

    返回 dict 结果(含频道链接),异常抛 ParseError。
    """
    cookies = await store.load_cookies()
    res = await parse(url, cookies)
    # 下载阶段同样需要按域名选 cookie(yt-dlp 下载时用)
    from engine import cookie_for
    cookie = cookie_for(url, cookies)

    tmp = os.path.join(config.TMP_DIR, re.sub(r"[^0-9A-Za-z_.-]", "_", res.title)[:40] + f"_{os.getpid()}_{int(asyncio.get_event_loop().time()*1000)%100000}")
    path, fname = await download_video(res, tmp, cookie)

    size_mb = os.path.getsize(path) / 1048576
    # 成片验证:分辨率 + 音轨(用户要求最高画质且必须有声),写进频道 caption 便于核对
    from downloader import probe_media
    meta = probe_media(path)
    res_label = f"{meta['width']}x{meta['height']}" if meta["width"] else "分辨率未知"
    audio_label = "有声" if meta["has_audio"] else "⚠️无音轨"
    caption = f"{res.platform} | {res.title}\n{res_label} · {audio_label} · {size_mb:.1f}MB\nvia @{(await tg_getbotname())}"

    if size_mb > config.MAX_TG_MB:
        # 超 50MB:yt-dlp 可降画质重下(<46MB 格式),直链没法降,只能报错
        if res.use_ytdlp:
            os.remove(path)
            path = await _ytdlp_low(res.source_url, tmp, cookie)
            fname = os.path.basename(path)
            size_mb = os.path.getsize(path) / 1048576
            if size_mb > config.MAX_TG_MB:
                os.remove(path)
                raise ParseError(f"最低画质仍有 {size_mb:.0f}MB,超过 Telegram Bot 50MB 上传上限")
        else:
            os.remove(path)
            raise ParseError(f"视频 {size_mb:.0f}MB 超过 Telegram Bot 50MB 上传上限,无法直传频道")

    # 发频道
    msg = await send_video(config.CHANNEL, path, caption)
    if not msg:
        os.remove(path)
        raise ParseError("发送到频道失败:请确认机器人已被添加为频道管理员且有发帖权限")
    link = channel_link(msg)

    # 同时发给用户私聊(体验:用户自己也能马上拿到视频)
    if chat_id and str(chat_id) != str(config.CHANNEL):
        ok = await send_video(chat_id, path, f"{caption}\n{link}")
        if not ok:
            await send_text(chat_id, f"视频已发到频道,但直发你这里失败(可能超 50MB):\n{link}")

    os.remove(path)  # 不在本地保存,发完即删

    await store.append_history({
        "time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "platform": res.platform,
        "title": res.title,
        "size_mb": round(size_mb, 1),
        "channel_link": link,
    })
    return {"platform": res.platform, "title": res.title, "size_mb": round(size_mb, 1),
            "channel_link": link}


async def _ytdlp_low(source_url: str, tmp: str, cookie: str | None) -> str:
    from downloader import download_ytdlp
    return await download_ytdlp(source_url, tmp, cookie, low_size=True)


_botname_cache = ""


async def tg_getbotname() -> str:
    global _botname_cache
    if not _botname_cache:
        r = await tg_call("getMe")
        _botname_cache = "@" + ((r.get("result") or {}).get("username") or "bot")
    return _botname_cache


# ---------------- Bot 私聊轮询 ----------------

async def handle_update(upd: dict):
    msg = upd.get("message") or upd.get("edited_message")
    if not msg:
        return
    text = msg.get("text") or msg.get("caption") or ""
    chat_id = (msg.get("chat") or {}).get("id")
    if not chat_id or not text:
        return
    urls = re.findall(r"https?://\S+", text)
    if not urls:
        await send_text(chat_id, "直接发送视频链接即可(支持抖音/快手/YouTube/B站/TikTok 等全网链接),我会解析无水印原画并发到频道 @dsfsfsdfwsdad。")
        return

    for url in urls[:2]:
        url = extract_url(url)
        prog = await send_text(chat_id, "⏳ 解析中,请稍候…")
        prog_id = (prog.get("result") or {}).get("message_id")
        try:
            out = await process(url, source="bot", chat_id=chat_id)
            done = (f"✅ 完成\n\n📺 平台:{out['platform']}\n🎬 标题:{out['title']}\n"
                    f"💾 大小:{out['size_mb']}MB\n\n频道已发布:{out['channel_link']}")
            if prog_id:
                await edit_text(chat_id, prog_id, done)
            else:
                await send_text(chat_id, done)
        except ParseError as e:
            fail = f"❌ 失败:{e}"
            if prog_id:
                await edit_text(chat_id, prog_id, fail)
            else:
                await send_text(chat_id, fail)
        except Exception as e:
            if prog_id:
                await edit_text(chat_id, prog_id, f"❌ 处理异常:{e}")


async def bot_loop():
    """getUpdates 长轮询,异常自动重启,间隔 3s。"""
    await tg_call("deleteWebhook", data={"drop_pending_updates": False})
    offset = 0
    while True:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(35.0)) as c:
                r = await c.get(f"{API}/getUpdates",
                                params={"offset": offset, "timeout": 25,
                                        "allowed_updates": '["message","edited_message"]'})
                data = r.json()
            for upd in (data.get("result") or []):
                offset = upd["update_id"] + 1
                asyncio.create_task(handle_update(upd))
        except Exception:
            await asyncio.sleep(3)
