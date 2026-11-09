"""扫码登录:Playwright 无头浏览器打开平台登录页,截取二维码给后台显示,
用户手机扫码确认后自动导出全部 Cookie 落库。

每个 session 在独立线程跑 sync_playwright,与 FastAPI 事件循环零耦合。
"""
import base64
import threading
import time
import uuid

from store import save_cookie_sync

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# platform -> 登录页配置
LOGIN_PAGES = {
    "douyin": {
        "url": "https://sso.douyin.com/login/?service=https%3A%2F%2Fwww.douyin.com&from_site=1",
        "key_cookie": "sessionid",
        "selectors": [
            "img[src*='qrcode']", "img[id*='qr']", "img[class*='qr']",
            "img[src^='data:image']", "canvas",
        ],
    },
    "kuaishou": {
        "url": "https://www.kuaishou.com/login",
        "key_cookie": "passToken",
        "selectors": [
            "img[src*='qrcode']", "img[src^='data:image']", "img[class*='qr']", "canvas",
        ],
    },
    "bilibili": {
        "url": "https://passport.bilibili.com/login",
        "key_cookie": "SESSDATA",
        "selectors": [
            "img[class*='qr']", "img[src^='data:image']", "canvas",
        ],
    },
    "tiktok": {
        "url": "https://www.tiktok.com/login/phone-or-email/qr",
        "key_cookie": "sessionid",
        "selectors": [
            "img[src*='qr']", "img[src^='data:image']", "canvas",
        ],
    },
}

TIMEOUT_SEC = 300

# session_id -> {platform, state, image, error, started}
SESSIONS = {}
_LOCK = threading.Lock()

CHROMIUM_ARGS = ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]


def start_session(platform: str) -> str | None:
    if platform not in LOGIN_PAGES:
        return None
    sid = uuid.uuid4().hex[:12]
    with _LOCK:
        SESSIONS[sid] = {
            "platform": platform, "state": "starting",
            "image": "", "error": "", "started": time.time(),
        }
    threading.Thread(target=_run_session, args=(sid, platform), daemon=True).start()
    return sid


def status(sid: str) -> dict:
    with _LOCK:
        s = SESSIONS.get(sid)
        if not s:
            return {"state": "unknown", "error": "会话不存在或已过期"}
        out = dict(s)
        # 会话超过 10 分钟自动清理,防内存堆积
        if s["state"] in ("done", "failed", "expired", "cancelled"):
            if time.time() - s["started"] > 600:
                SESSIONS.pop(sid, None)
        return out


def cancel(sid: str):
    with _LOCK:
        s = SESSIONS.get(sid)
        if s and s["state"] not in ("done", "failed", "expired"):
            s["state"] = "cancelled"


def _set(sid: str, **kw):
    with _LOCK:
        s = SESSIONS.get(sid)
        if s:
            s.update(kw)


def _is_cancelled(sid: str) -> bool:
    with _LOCK:
        s = SESSIONS.get(sid)
        return bool(s and s["state"] == "cancelled")


def _run_session(sid: str, platform: str):
    from playwright.sync_api import sync_playwright
    cfg = LOGIN_PAGES[platform]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=CHROMIUM_ARGS)
            ctx = browser.new_context(
                user_agent=UA_DESKTOP,
                viewport={"width": 1280, "height": 800},
                locale="zh-CN",
            )
            page = ctx.new_page()
            page.goto(cfg["url"], timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            # 找二维码元素截图;找不到就整页截图(登录页二维码通常居中,整页也能扫)
            shot = None
            for sel in cfg["selectors"]:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        box = el.bounding_box()
                        if box and box["width"] > 60 and box["height"] > 60:
                            shot = el.screenshot(type="png")
                            break
                except Exception:
                    continue
            if not shot:
                shot = page.screenshot(type="png")

            _set(sid, state="waiting_scan",
                 image=base64.b64encode(shot).decode())

            # 轮询关键 cookie 出现即视为登录成功
            deadline = time.time() + TIMEOUT_SEC
            while time.time() < deadline:
                if _is_cancelled(sid):
                    ctx.close()
                    browser.close()
                    return
                try:
                    cookies = ctx.cookies()
                    names = {c["name"] for c in cookies}
                    if cfg["key_cookie"] in names:
                        raw = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
                        save_cookie_sync(platform, raw)
                        _set(sid, state="done",
                             cookie_names=sorted(names)[:20])
                        ctx.close()
                        browser.close()
                        return
                except Exception:
                    pass
                time.sleep(2)

            _set(sid, state="expired", error="二维码超时,请重新发起扫码")
            ctx.close()
            browser.close()
    except Exception as e:
        _set(sid, state="failed", error=f"{type(e).__name__}: {e}")
