"""全局配置:Token/频道/端口,支持环境变量覆盖。

敏感值(Bot Token)不写入代码,由部署环境注入:
    systemd Environment=WM_BOT_TOKEN=...
"""
import os
import secrets

BOT_TOKEN = os.environ.get("WM_BOT_TOKEN", "")
# 目标频道:下载完成的无水印视频自动发到这里
CHANNEL = os.environ.get("WM_CHANNEL", "@dsfsfsdfwsdad")

PORT = int(os.environ.get("WM_PORT", "8081"))
DATA_DIR = os.environ.get("WM_DATA_DIR", "/opt/wmfree/data")

# 后台管理 Token:首次启动随机生成并落盘,网页后台登录用
ADMIN_TOKEN = os.environ.get("WM_ADMIN_TOKEN", "")

# Bot API 视频上传硬上限 50MB,留出 multipart 开销
MAX_TG_MB = 48

TMP_DIR = os.path.join(DATA_DIR, "tmp")

_ensure = None  # 占位,main.py 启动时 ensure_dirs()


def ensure_dirs():
    import pathlib
    pathlib.Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    pathlib.Path(TMP_DIR).mkdir(parents=True, exist_ok=True)


def admin_token() -> str:
    """读取或生成后台管理 Token。"""
    global ADMIN_TOKEN
    if ADMIN_TOKEN:
        return ADMIN_TOKEN
    p = os.path.join(DATA_DIR, "admin_token.txt")
    if os.path.exists(p):
        ADMIN_TOKEN = open(p, encoding="utf-8").read().strip()
    else:
        ADMIN_TOKEN = secrets.token_hex(8)
        with open(p, "w", encoding="utf-8") as f:
            f.write(ADMIN_TOKEN)
    return ADMIN_TOKEN
