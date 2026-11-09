"""扫码登录端到端验证:发起抖音扫码会话,检查二维码截图是否生成。"""
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
print("SID:", sid)

for i in range(10):
    time.sleep(3)
    s = api(f"/api/admin/qr-login/status/{sid}")
    state = s.get("state")
    print(f"[{i*3}s] state={state}")
    if state in ("waiting_scan", "done", "failed", "expired"):
        img = s.get("image") or ""
        if img:
            raw = base64.b64decode(img)
            open("/tmp/qr_test.png", "wb").write(raw)
            print("QR_PNG_BYTES:", len(raw))
        else:
            print("NO_IMAGE")
        print("ERROR:", s.get("error", ""))
        break
