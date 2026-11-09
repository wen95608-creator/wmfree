# WMFree — 全网去水印视频下载 → Telegram 频道自动发布

多平台(iOS App + Telegram 机器人 + 网页后台)无水印视频下载体系。
任何端发来链接 → 服务器解析无水印原画 → 下载最高画质 → 自动发布到 Telegram 频道 **@dsfsfsdfwsdad** → 返回频道消息链接。**视频不在任何端本地保存,发完即删。**

```
iOS App(SwiftUI) ──┐
TG 机器人私聊 ───────┤──> 解析后端 47.130.212.185:8081(Python FastAPI + yt-dlp)
网页后台 /admin ─────┘         │
                              ├─ engine.py   抖音/快手专用解析(无水印原画)+ yt-dlp 全网兜底
                              ├─ downloader  httpx 直链流式下载 / yt-dlp 下载+ffmpeg 合并
                              ├─ store.py    平台 Cookie 仓库 + 下载历史
                              └─ tg.py       Bot API sendVideo → 频道 + 私聊回复 + 轮询
```

## 当前部署(47.130.212.185,直连 IP 无隧道)

| 项 | 值 |
|---|---|
| 服务 | `wmfree.service`(systemd),端口 **8081** |
| 后端目录 | `/opt/wmfree/backend`(venv + Python 3.11 + yt-dlp 2026.10.26 + ffmpeg 5.1.9) |
| 数据目录 | `/opt/wmfree/data/`(cookies.json / history.json / admin_token.txt) |
| 网页后台 | `http://47.130.212.185:8081/admin` — Token:`33aaca90dc834912` |
| Bot | @shuiying78_bot(getUpdates 出站轮询,**不需要入站端口,现在已可用**) |
| 频道 | @dsfsfsdfwsdad(实测发帖成功,消息 293) |
| 修改密码 | 后台 Token 改法:`sudo rm /opt/wmfree/data/admin_token.txt && sudo systemctl restart wmfree` 重新随机生成 |

## ⚠️ 唯一待办:放行 8081(1 分钟)

AWS Lightsail 控制台 → 实例 → Networking → IPv4 Firewall → Add rule:
**TCP / 8081 / Anywhere**。App 端的 `/api/parse` 需要这个端口;**Telegram 机器人不受影响,现在就能私聊使用**。

## 平台适配策略

| 平台 | 方式 | 说明 |
|---|---|---|
| 抖音 | 专用解析(iesdouyin 分享页 `_ROUTER_DATA` → `playwm`→`play`) | 无水印原画,接口实测可达;失败自动提示重试/配 Cookie |
| 快手 | 专用解析(页面 `__APOLLO_STATE__` → `Photo.metaUrl`) | 无水印;建议后台配快手 Cookie 降风控 |
| YouTube / B站 / TikTok / Twitter/X / Instagram / Facebook | yt-dlp 兜底,最高画质 `bv*+ba` 合并 mp4 | 数据中心 IP 对 YouTube/B站 有登录风控——**在后台粘 Cookie 即解** |
| 其他任意平台 | yt-dlp 自动识别 | 引擎不认识的链接全部交给 yt-dlp |

## 需要登录的平台(网页后台操作)

1. 浏览器登录目标平台(如 YouTube/Instagram)
2. F12 → Network → 任意请求 → 复制请求头里的 `Cookie:` 整串
3. 打开后台 `/admin` → 平台 Cookie → 选平台 → 粘贴 → 保存
4. 之后该平台解析自动带上你的登录态(会员/年龄限制/私密内容同理)

## Bot 私聊用法

给 @shuiying78_bot 发任意视频链接(可直接转发抖音分享文本),机器人:
解析 → 下载 → 发频道 → **同时把视频直发给你** + 返回频道消息链接。
处理中显示"⏳ 解析中",完成/失败原地编辑消息。

## 50MB 限制说明

Telegram Bot API 单文件上传上限 50MB。超限时:yt-dlp 路径自动降画质重挑 <46MB 格式;抖音/快手直链无法降画质会明确报错。要发超大文件需要把视频切片或走本地 Bot API server,后续可加。

## iOS App

源码在 `ios/WMFree/`(SwiftUI):输链接 → 解析 → 显示频道消息链接,本地只存历史文字记录。
构建见 `ios/README-BUILD.md`(Xcode 工程三步拖入 + ATS 明文豁免 + 免费签名/TestFlight 路径)。
App 内默认服务器:`http://47.130.212.185:8081`,可随时在设置里改。

## 运维命令

```bash
sudo systemctl restart wmfree      # 重启(改代码/cookie 后)
sudo journalctl -u wmfree -f       # 看实时日志
sudo tail /opt/wmfree/data/history.json   # 下载历史
```

## 验证记录(2026-11-10)

- `/api/health` → bot=shuiying78_bot, channel_ok=true ✓
- ffmpeg 生成测试视频 → sendVideo 频道 → **消息 293 成功发布** ✓
- iesdouyin 分享页接口 SG IP 返回 200 ✓
- YouTube/B站数据中心 IP 登录风控 → 已知,后台 Cookie 解决(需求原生场景)
- 外网 8081 → Lightsail 安全组未放行(待你在控制台加规则)
