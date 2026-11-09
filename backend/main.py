"""FastAPI 入口:解析 API + 网页后台 + Bot 轮询启动。"""
import asyncio

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse

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
