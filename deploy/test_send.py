"""频道发送连通性测试 + 抖音分享接口探测(在服务器上运行)。"""
import asyncio
import subprocess
import sys

sys.path.insert(0, "/opt/wmfree/backend")
import config  # noqa: E402
import tg  # noqa: E402

config.ensure_dirs()


async def main():
    # 1. 生成 3 秒测试视频
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=24",
        "-pix_fmt", "yuv420p", "/opt/wmfree/data/tmp/test.mp4",
    ], check=True)
    print("ffmpeg test video generated")

    # 2. 发到频道,验证 bot 发帖权限
    msg = await tg.send_video(config.CHANNEL, "/opt/wmfree/data/tmp/test.mp4", "系统连通性测试(可删除)")
    if msg:
        print("SEND_OK message_id=", msg.get("message_id"))
        print("LINK:", tg.channel_link(msg))
    else:
        print("SEND_FAILED: bot 无频道发帖权限,请把 bot 加为频道管理员")

    # 3. 清理测试文件
    import os
    os.remove("/opt/wmfree/data/tmp/test.mp4")


asyncio.run(main())
