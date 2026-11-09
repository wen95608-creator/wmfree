"""FastAPI 入口:解析 API + 网页后台 + Bot 轮询启动。"""
import asyncio

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

import config
import store
import tg

config.ensure_dirs()
config.admin_token()

app = FastAPI(title="WMFree", docs_url=None, redoc_url=None)

_bot_task = None


@app.on_event("startup")
async def startup():
    global _bot_task
    _bot_task = asyncio.create_task(tg.bot_loop())


def check_admin(token: str):
    if not token or token != config.admin_token():
        raise HTTPException(status_code=401, detail="admin token 无效")


# ---------------- 对外 API(App / 任何客户端) ----------------

@app.get("/api/health")
async def health():
    me = await tg.tg_call("getMe")
    ch = await tg.tg_call("getChat", data={"chat_id": config.CHANNEL})
    return {
        "ok": True,
        "bot": (me.get("result") or {}).get("username"),
        "channel": config.CHANNEL,
        "channel_ok": bool(ch.get("ok")),
    }


@app.post("/api/parse")
async def api_parse(body: dict):
    """App 端入口:发来链接 -> 全流程 -> 返回频道消息链接。视频不落本地,发完即删。"""
    from engine import ParseError, extract_url

    url = extract_url((body.get("url") or "").strip())
    if not url:
        raise HTTPException(status_code=400, detail="未发现有效链接")
    try:
        out = await tg.process(url, source="app")
        return JSONResponse({"ok": True, **out})
    except ParseError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=422)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"处理异常: {e}"}, status_code=500)


# ---------------- 频道视频流(App 端刷视频) ----------------

@app.get("/api/videos")
async def api_videos(refresh: int = 0):
    """refresh=1 时触发频道全量扫描(t.me embed,限流 5 分钟一次)。"""
    import channel_index
    if refresh:
        try:
            await channel_index.scan_channel()
        except Exception:
            pass  # 扫描失败不影响已有索引返回
    vids = await store.list_videos(1000)
    # 服务器不存视频:全部走代理/302 直链,任意大小可播
    for v in vids:
        v["streamable"] = True
    return {"videos": vids}


@app.get("/api/videos/{mid}/stream")
async def api_video_stream(mid: int, range: str | None = Header(default=None, alias="Range")):
    """代理 Telegram getFile 直链,AVPlayer 可流式播放(Range 透传),token 不暴露。"""
    import httpx as _httpx

    v = await store.get_video(mid)
    if v and v.get("file_id"):
        r = await tg.tg_call("getFile", data={"file_id": v["file_id"]})
        if not r.get("ok"):
            raise HTTPException(status_code=410, detail=(
                "视频超过 20MB,Bot API 无法流式播放,请在 Telegram 频道查看。"))
        fp = r["result"]["file_path"]
        tgt = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{fp}"
        fwd = {"Range": range} if range else {}
        async with _httpx.AsyncClient(timeout=_httpx.Timeout(600.0)) as c:
            rr = await c.get(tgt, headers=fwd)

            async def gen():
                async for chunk in rr.aiter_bytes(256 * 1024):
                    yield chunk

            hdrs = {"Content-Type": rr.headers.get("content-type", "video/mp4"),
                    "Accept-Ranges": "bytes"}
            if "content-range" in rr.headers:
                hdrs["Content-Range"] = rr.headers["content-range"]
            if "content-length" in rr.headers:
                hdrs["Content-Length"] = rr.headers["content-length"]
            return StreamingResponse(gen(), status_code=rr.status_code, headers=hdrs)

    # 无 file_id(手动传到频道的视频等):实时抓 t.me embed 直链,302 给播放器
    import channel_index
    from fastapi.responses import RedirectResponse
    src = await channel_index.resolve_stream_url(mid)
    if not src:
        raise HTTPException(status_code=404, detail="无法解析该消息的视频直链")
    return RedirectResponse(src, status_code=302)


# ---------------- 网页后台 ----------------

@app.get("/admin")
async def admin_page():
    return FileResponse("admin.html")


@app.get("/api/admin/overview")
async def admin_overview(x_admin_token: str = Header(default="")):
    check_admin(x_admin_token)
    me = await tg.tg_call("getMe")
    ch = await tg.tg_call("getChat", data={"chat_id": config.CHANNEL})
    ch_admin = await tg.tg_call(
        "getChatMember", data={"chat_id": config.CHANNEL,
                               "user_id": (me.get("result") or {}).get("id")})
    return {
        "bot": (me.get("result") or {}).get("username"),
        "channel": config.CHANNEL,
        "channel_title": (ch.get("result") or {}).get("title"),
        "bot_in_channel": bool(ch.get("ok")),
        "bot_can_post": (ch_admin.get("result") or {}).get("status") in ("administrator", "creator"),
    }


@app.get("/api/admin/cookies")
async def admin_get_cookies(x_admin_token: str = Header(default="")):
    check_admin(x_admin_token)
    cookies = await store.load_cookies()
    return {"platforms": store.SUPPORTED_PLATFORMS, "cookies": cookies}


@app.post("/api/admin/cookies")
async def admin_set_cookie(body: dict, x_admin_token: str = Header(default="")):
    check_admin(x_admin_token)
    platform = body.get("platform") or ""
    raw = body.get("cookie") or ""
    ok = await store.save_cookie(platform, raw)
    if not ok:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {platform}")
    return {"ok": True}


@app.delete("/api/admin/cookies/{platform}")
async def admin_del_cookie(platform: str, x_admin_token: str = Header(default="")):
    check_admin(x_admin_token)
    await store.delete_cookie(platform)
    return {"ok": True}


@app.get("/api/admin/history")
async def admin_history(x_admin_token: str = Header(default="")):
    check_admin(x_admin_token)
    return {"history": await store.read_history()}


# ---------------- 扫码登录(Playwright 二维码 -> 自动配置 Cookie) ----------------

@app.post("/api/admin/qr-login/start")
async def qr_login_start(body: dict, x_admin_token: str = Header(default="")):
    check_admin(x_admin_token)
    import login_qr
    platform = body.get("platform") or ""
    if platform not in login_qr.LOGIN_PAGES:
        raise HTTPException(status_code=400, detail=f"不支持扫码的平台: {platform}")
    sid = login_qr.start_session(platform)
    if not sid:
        raise HTTPException(status_code=500, detail="扫码会话启动失败")
    return {"ok": True, "session_id": sid}


@app.get("/api/admin/qr-login/status/{sid}")
async def qr_login_status(sid: str, x_admin_token: str = Header(default="")):
    check_admin(x_admin_token)
    import login_qr
    return login_qr.status(sid)


@app.post("/api/admin/qr-login/cancel/{sid}")
async def qr_login_cancel(sid: str, x_admin_token: str = Header(default="")):
    check_admin(x_admin_token)
    import login_qr
    login_qr.cancel(sid)
    return {"ok": True}
