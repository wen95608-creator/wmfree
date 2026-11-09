"""验证频道全量扫描 + stream 302。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8081"

# 1. 触发全量扫描
req = urllib.request.Request(BASE + "/api/videos?refresh=1")
with urllib.request.urlopen(req, timeout=240) as r:
    d = json.loads(r.read().decode())
vs = d.get("videos", [])
print("TOTAL:", len(vs))
for v in vs[:6]:
    print(" -", v["mid"], v["title"][:30], v["platform"], v["size_mb"], "MB", "src:", v.get("file_id") and "bot" or "embed")

# 2. 验证 stream 302 / 200
for mid in [vs[0]["mid"] if vs else 297]:
    req = urllib.request.Request(BASE + f"/api/videos/{mid}/stream")
    opener = urllib.request.build_opener(_NoRed := type("NR", (urllib.request.HTTPRedirectHandler,), {
        "redirect_request": lambda self, *a, **k: None})())
    try:
        opener.open(req, timeout=30)
        print(f"stream {mid}: direct 200 (proxy)")
    except urllib.error.HTTPError as e:
        print(f"stream {mid}: HTTP", e.code, "redirect to:", (e.headers.get("Location") or "")[:60])
