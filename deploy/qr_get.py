"""发起扫码会话并取回二维码 PNG(给用户直接扫)。"""
import base64
import json
import sys
import time
import urllib.request

sys.path.insert(0, "/opt/wmfree/backend")
import config  # noqa: E402

TOKEN = config.admin_token()
BASE = "http://127.0.0.1:8081"


def api(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 headers={"X-Admin-Token": TOKEN,
                                          "Content-Type": "application/json"})
    if body:
        req.data = json.dumps(body).encode()
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


d = api("/api/admin/qr-login/start", "POST", {"platform": "douyin"})
sid = d["session_id"]
print("SID:" + sid)

img = ""
state = "starting"
for i in range(20):
    time.sleep(3)
    s = api(f"/api/admin/qr-login/status/{sid}")
    state = s.get("state")
    img = s.get("image") or ""
    if state == "waiting_scan" and img:
        break
    if state in ("failed", "expired"):
        print("FAIL:" + s.get("error", ""))
        sys.exit(1)

if img:
    open("/tmp/qr_live.png", "wb").write(base64.b64decode(img))
    print("QR_READY bytes=", len(base64.b64decode(img)))
else:
    print("NO_IMAGE state=" + state)
    sys.exit(1)
