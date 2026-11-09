"""本地扫码登录:本机浏览器打开抖音登录页(国内 IP,无异地风控),
二维码展示给用户扫,登录成功后自动提取全部 Cookie 并推送到服务器落库。

用法: python qr_local.py
输出: dist/qr_local.png(二维码图) + 控制台状态
"""
import base64
import json
import time
import urllib.request

from playwright.sync_api import sync_playwright

SERVER = "http://47.130.212.185:8081"
ADMIN_TOKEN = "33aaca90dc834912"
PNG_PATH = r"D:/y700/1212/wmfree/dist/qr_local.png"
LOGIN_URL = ("https://sso.douyin.com/login/"
             "?service=https%3A%2F%2Fwww.douyin.com&from_site=1")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT_SEC = 300

SELECTORS = [
    "img[src*='qrcode']", "img[id*='qr']", "img[class*='qr']",
    "img[src^='data:image']", "canvas",
]


def push_cookie(raw: str):
    req = urllib.request.Request(
        SERVER + "/api/admin/cookies", method="POST",
        headers={"X-Admin-Token": ADMIN_TOKEN, "Content-Type": "application/json"})
    req.data = json.dumps({"platform": "douyin", "cookie": raw}).encode()
    with urllib.request.urlopen(req, timeout=30) as r:
        print("server resp:", r.read().decode()[:120])


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 800},
                                  locale="zh-CN")
        page = ctx.new_page()
        print("[1] 打开抖音登录页…")
        page.goto(LOGIN_URL, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        shot = None
        for sel in SELECTORS:
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
        with open(PNG_PATH, "wb") as f:
            f.write(shot)
        print("[2] 二维码已保存:", PNG_PATH, "bytes=", len(shot))
        print(">>> 请用手机抖音扫描该图片,并在手机上点【确认登录】 <<<")

        deadline = time.time() + TIMEOUT_SEC
        last_shot = 0.0
        while time.time() < deadline:
            cookies = ctx.cookies()
            names = sorted({c["name"] for c in cookies})
            try:
                cur = page.url
            except Exception:
                cur = ""
            if "sessionid" in names:
                raw = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
                print("[3] 登录成功!cookie 长度:", len(raw))
                push_cookie(raw)
                print("[4] 已推送服务器,抖音登录态配置完成")
                browser.close()
                return
            # 每 15 秒刷新一次二维码区截图(页面可能刷新二维码)
            if time.time() - last_shot > 15:
                try:
                    el = None
                    for sel in SELECTORS:
                        el = page.query_selector(sel)
                        if el and el.is_visible():
                            break
                    if el:
                        with open(PNG_PATH, "wb") as f:
                            f.write(el.screenshot(type="png"))
                        last_shot = time.time()
                        print(f"[refresh] {int(deadline-time.time())}s left | page={cur[:60]} | cookies={len(cookies)}")
                except Exception:
                    pass
            time.sleep(2)

        print("TIMEOUT: 5 分钟内未检测到登录成功,请重新运行")
        browser.close()


main()
