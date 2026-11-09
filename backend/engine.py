"""平台解析引擎:抖音/快手专用解析 + yt-dlp 全网兜底。

无水印策略:
- 抖音:分享页 _ROUTER_DATA 接口拿 play_addr,url_list 里 playwm -> play 即无水印原画
- 快手:页面 __APOLLO_STATE__ 里 Photo.metaUrl 即无水印 CDN 直链
- 其余平台(YouTube/B站/Twitter/TikTok/Instagram/Twitter 等):yt-dlp,选最高画质
"""
import asyncio
import json
import re
from dataclasses import dataclass, field

import httpx

UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class ParseError(Exception):
    pass


@dataclass
class ParseResult:
    platform: str = ""
    title: str = ""
    # 直链(抖音/快手)则为 None,走 yt-dlp 下载
    video_url: str = ""
    # yt-dlp 原始链接(下载器再次调用)
    source_url: str = ""
    use_ytdlp: bool = False
    author: str = ""
    duration: int = 0
    headers: dict = field(default_factory=dict)


def extract_url(text: str) -> str | None:
    m = re.search(r"https?://[^\s\"'<>]+", text)
    return m.group(0).rstrip(")。,，") if m else None


def cookie_for(url: str, cookies: dict) -> str | None:
    """按 URL 域名挑选后台配置的 cookie。cookies: {platform_name: raw_cookie}"""
    domains = {
        "douyin": ["douyin.com", "iesdouyin.com"],
        "kuaishou": ["kuaishou.com", "chenzhongtech.com"],
        "tiktok": ["tiktok.com"],
        "instagram": ["instagram.com"],
        "youtube": ["youtube.com", "youtu.be"],
        "twitter": ["x.com", "twitter.com"],
        "bilibili": ["bilibili.com"],
        "facebook": ["facebook.com", "fb.watch"],
    }
    for name, ds in domains.items():
        raw = (cookies.get(name) or "").strip()
        if raw and any(d in url for d in ds):
            return raw
    return None


# ---------------- 抖音 ----------------

async def parse_douyin(client: httpx.AsyncClient, url: str, cookie: str | None) -> ParseResult:
    headers = {"User-Agent": UA_MOBILE}
    if cookie:
        headers["Cookie"] = cookie
    # 展开短链 v.douyin.com/xxxx
    if "v.douyin.com" in url or not re.search(r"/(?:video|note)/(\d+)", url):
        r = await client.get(url, headers=headers, follow_redirects=True)
        url = str(r.url)
    m = re.search(r"/(?:video|note)/(\d+)", url)
    if not m:
        raise ParseError("无法从抖音链接中提取视频 ID")
    vid = m.group(1)

    share = f"https://www.iesdouyin.com/share/video/{vid}"
    r = await client.get(share, headers=headers, follow_redirects=True)
    m2 = re.search(r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>", r.text, re.S)
    if not m2:
        raise ParseError("抖音分享页未返回数据(可能被风控),请稍后重试")
    try:
        data = json.loads(m2.group(1))
    except json.JSONDecodeError as e:
        raise ParseError(f"抖音数据解析失败: {e}")

    def _find_items(obj):
        """递归找第一个非空 item_list,防御 loaderData 结构变化。"""
        if isinstance(obj, dict):
            il = obj.get("item_list")
            if isinstance(il, list) and il:
                return il
            for vv in obj.values():
                rr = _find_items(vv)
                if rr:
                    return rr
        elif isinstance(obj, list):
            for vv in obj:
                rr = _find_items(vv)
                if rr:
                    return rr
        return None

    loader = data.get("loaderData") or {}
    item = None
    reason = ""
    for v in loader.values():
        # loaderData 里可能混有 None/字符串值,不做类型防御直接 .get 会崩
        if not isinstance(v, dict):
            continue
        vir = v.get("videoInfoRes")
        if not isinstance(vir, dict):
            continue
        cand = vir.get("item_list") or []
        if cand:
            item = cand[0]
            break
        if vir.get("filter_reason"):
            reason = str(vir.get("filter_reason"))
    if not item:
        items = _find_items(data)
        item = items[0] if items else None
    if not item:
        raise ParseError(f"抖音接口返回为空{(': ' + reason) if reason else '(视频可能已删除或私密)'}")

    video = item.get("video") or {}
    urls = ((video.get("play_addr") or {}).get("url_list")) or []
    play = ""
    if urls:
        # playwm 是带水印地址,替换成 play 即无水印;并强制 1080p 档保证最高画质
        play = re.sub(r"ratio=\d+p", "ratio=1080p", urls[0].replace("playwm", "play"))
    if not play:
        uri = (video.get("play_addr") or {}).get("uri") or ""
        if uri:
            play = f"https://www.douyin.com/aweme/v1/play/?video_id={uri}&ratio=1080p&line=0"
    if not play:
        raise ParseError("未找到可播放地址")

    return ParseResult(
        platform="抖音",
        title=(item.get("desc") or "抖音视频").strip()[:80],
        video_url=play,
        author=((item.get("author") or {}).get("nickname") or ""),
        duration=int((item.get("duration") or 0) / 1000),
        headers={"User-Agent": UA_MOBILE, "Referer": "https://www.douyin.com/"},
    )


# ---------------- 快手 ----------------

def _walk_find(obj, key):
    """递归在任意层级 JSON 里找第一个指定字段的值。"""
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], str) and obj[key].startswith("http"):
            return obj[key]
        for v in obj.values():
            r = _walk_find(v, key)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _walk_find(v, key)
            if r:
                return r
    return None


async def parse_kuaishou(client: httpx.AsyncClient, url: str, cookie: str | None) -> ParseResult:
    headers = {"User-Agent": UA_DESKTOP}
    if cookie:
        headers["Cookie"] = cookie
    else:
        # 无 cookie 时给个随机 did,降低风控概率;正经 cookie 请在后台配置
        import random
        headers["Cookie"] = "did=web_" + "".join(random.choices("0123456789abcdef", k=32))
    r = await client.get(url, headers=headers, follow_redirects=True)
    html = r.text

    meta = None
    m = re.search(r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\})\s*</script>", html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            meta = _walk_find(data, "metaUrl")
        except json.JSONDecodeError:
            pass
    if not meta:
        m2 = re.search(r'"metaUrl"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
        if m2:
            meta = m2.group(1).encode().decode("unicode_escape")
    if not meta:
        m3 = re.search(r'"playUrl"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
        if m3:
            meta = m3.group(1).encode().decode("unicode_escape")
    if not meta:
        raise ParseError("快手页面未解析到视频地址(建议后台配置快手 Cookie)")

    title = ""
    mt = re.search(r'<meta name="description" content="([^"]*)"', html)
    if mt:
        title = mt.group(1).split("-")[0].strip()
    return ParseResult(
        platform="快手",
        title=(title or "快手视频")[:80],
        video_url=meta,
        headers={"User-Agent": UA_DESKTOP, "Referer": "https://www.kuaishou.com/"},
    )


# ---------------- yt-dlp 全网兜底 ----------------

def ytdlp_headers(url: str, cookie: str | None) -> dict:
    """yt-dlp 用的请求头:真实浏览器 UA;B 站加 Referer+buvid3(412 反爬);其余平台透传后台 cookie。"""
    import uuid
    h = {"User-Agent": UA_DESKTOP}
    if "bilibili.com" in url:
        h["Referer"] = "https://www.bilibili.com/"
        h["Cookie"] = cookie or f"buvid3={uuid.uuid4()}infoc"
    elif cookie:
        h["Cookie"] = cookie
    return h


async def parse_generic(source_url: str, cookie: str | None) -> ParseResult:
    import yt_dlp

    def work():
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            # 最高画质:最佳视频流+最佳音频流合并(下载阶段会 mp4 合并)
            "format": "bv*+ba/b",
            "http_headers": ytdlp_headers(source_url, cookie),
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source_url, download=False)
        return info

    info = await asyncio.to_thread(work)
    if info is None:
        raise ParseError("yt-dlp 未解析到信息")
    if "entries" in info:  # playlist 取第一条
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise ParseError("yt-dlp 解析列表为空")
        info = entries[0]

    return ParseResult(
        platform=info.get("extractor_key") or "其他",
        title=(info.get("title") or "视频")[:80],
        source_url=source_url,
        use_ytdlp=True,
        duration=int(info.get("duration") or 0),
        headers={"Cookie": cookie} if cookie else {},
    )


# ---------------- 入口路由 ----------------

async def parse(url: str, cookies: dict) -> ParseResult:
    cookie = cookie_for(url, cookies or {})
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": UA_MOBILE},
                                 follow_redirects=True) as client:
        if "douyin.com" in url or "iesdouyin.com" in url:
            return await parse_douyin(client, url, cookie)
        if "kuaishou.com" in url:
            return await parse_kuaishou(client, url, cookie)
    return await parse_generic(url, cookie)
