"""视频下载器:直链流式下载(抖音/快手)+ yt-dlp 下载合并(全网)。"""
import asyncio
import os

import httpx

from engine import UA_DESKTOP, ParseError, ParseResult


async def download_direct(res: ParseResult, dest: str) -> str:
    """httpx 流式下载直链视频(抖音/快手)。"""
    headers = {"User-Agent": UA_DESKTOP}
    headers.update(res.headers or {})
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0), follow_redirects=True) as client:
        async with client.stream("GET", res.video_url, headers=headers) as r:
            if r.status_code != 200:
                raise ParseError(f"视频下载失败 HTTP {r.status_code}")
            size = 0
            with open(dest, "wb") as f:
                async for chunk in r.aiter_bytes(64 * 1024):
                    f.write(chunk)
                    size += len(chunk)
                    if size > 1024 * 1024 * 2048:  # 2GB 硬上限防异常巨包
                        raise ParseError("视频体积异常(>2GB),已中止")
            if size < 50 * 1024:
                raise ParseError("下载内容过小,可能是风控页而非视频")
    return dest


async def download_ytdlp(source_url: str, dest_noext: str, cookie: str | None,
                         low_size: bool = False) -> str:
    """yt-dlp 下载并合并为 mp4。low_size=True 时挑 <46MB 的格式(Bot 50MB 限制)。"""
    import yt_dlp

    def work() -> str:
        from engine import ytdlp_headers
        fmt = "bv*+ba/b"
        if low_size:
            fmt = "b[filesize<46M]/b[filesize_approx<46M]/b"
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": fmt,
            "merge_output_format": "mp4",
            "outtmpl": dest_noext + ".%(ext)s",
            "http_headers": ytdlp_headers(source_url, cookie),
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([source_url])
        # 找 outtmpl 实际落盘文件(扩展名可能是 mp4/webm/mkv)
        d = os.path.dirname(dest_noext) or "."
        base = os.path.basename(dest_noext)
        for f in sorted(os.listdir(d)):
            if f.startswith(base) and os.path.splitext(f)[1].lower() in (
                    ".mp4", ".webm", ".mkv", ".mov"):
                return os.path.join(d, f)
        raise ParseError("yt-dlp 下载完成但未找到输出文件")

    return await asyncio.to_thread(work)


async def download_video(res: ParseResult, dest: str, cookie: str | None = None) -> tuple[str, str]:
    """按解析结果分流下载。返回 (实际文件路径, 文件名)。"""
    if res.use_ytdlp:
        path = await download_ytdlp(res.source_url, dest, cookie)
    else:
        path = await download_direct(res, dest + ".mp4")
    return path, os.path.basename(path)


def probe_media(path: str) -> dict:
    """ffprobe 验证成片:分辨率 + 音轨存在性(要求最高画质且必须有声)。"""
    import json
    import subprocess
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, timeout=30)
        d = json.loads(out.stdout.decode())
        v = [s for s in d.get("streams", []) if s.get("codec_type") == "video"]
        a = [s for s in d.get("streams", []) if s.get("codec_type") == "audio"]
        return {
            "width": int(v[0].get("width") or 0) if v else 0,
            "height": int(v[0].get("height") or 0) if v else 0,
            "has_audio": bool(a),
        }
    except Exception:
        return {"width": 0, "height": 0, "has_audio": False}
