"""直接检查指定会话状态 + cookies.json。"""
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/wmfree/backend")
import config  # noqa: E402

TOKEN = config.admin_token()
BASE = "http://127.0.0.1:8081"
SID = sys.argv[1] if len(sys.argv) > 1 else "a75d18753bf4"

req = urllib.request.Request(f"{BASE}/api/admin/qr-login/status/{SID}",
                             headers={"X-Admin-Token": TOKEN})
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.loads(r.read().decode())

print("state:", d.get("state"))
diag = d.get("diag") or {}
print("page:", str(diag.get("url", ""))[:100])
print("cookie_count:", diag.get("cookie_count"))
print("cookie_names:", (diag.get("cookies") or [])[:15])
print("error:", d.get("error", ""))

try:
    ck = json.load(open("/opt/wmfree/data/cookies.json", encoding="utf-8"))
    for k, v in ck.items():
        print("saved:", k, "| len:", len(v), "| has_sessionid:", "sessionid=" in v)
except Exception as e:
    print("cookies.json:", e)
