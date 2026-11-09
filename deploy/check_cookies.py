"""检查扫码登录结果:读取 cookies.json 概况。"""
import json

try:
    d = json.load(open("/opt/wmfree/data/cookies.json", encoding="utf-8"))
except Exception:
    d = {}

if not d:
    print("NO_COOKIES: cookies.json 不存在或为空 —— 扫码登录还没成功")
else:
    for k, v in d.items():
        print("platform:", k, "| cookie_len:", len(v),
              "| has_sessionid:", "sessionid=" in v)
