"""轮询扫码会话直到登录完成,报告 cookie 状态。"""
import json
import sys
import time
import urllib.request

sys.path.insert(0, "/opt/wmfree/backend")
import config  # noqa: E402

TOKEN = config.admin_token()
BASE = "http://127.0.0.1:8081"
SID = sys.argv[1]


def api(path):
    req = urllib.request.Request(BASE + path,
                                 headers={"X-Admin-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


deadline = time.time() + 330
while time.time() < deadline:
    s = api(f"/api/admin/qr-login/status/{SID}")
    st = s.get("state")
    diag = s.get("diag") or {}
    print(f"[{int(deadline-time.time())}s left] state={st} url={str(diag.get('url',''))[:70]} cookies={diag.get('cookie_count')}")
    if st == "done":
        print("LOGIN_OK")
        try:
            ck = json.load(open("/opt/wmfree/data/cookies.json", encoding="utf-8"))
            for k, v in ck.items():
                print("saved:", k, "len:", len(v), "sessionid:", "sessionid=" in v)
        except Exception as e:
            print("cookie read err:", e)
        break
    if st in ("failed", "expired", "cancelled"):
        print("END:", st, s.get("error", ""))
        break
    time.sleep(4)
else:
    print("TIMEOUT_WAITING")
