# iOS 端构建说明(必读)

## 这是原生 App,不是网页套壳

`WMFree/` 是纯 **SwiftUI 原生工程**:三个 Tab(下载/历史/设置)、原生输入框/列表/分享跳转、iOS 原生材质毛玻璃卡片。没有任何 WebView,不加载任何网页。后端只提供 `/api/parse` 和 `/api/health` 两个 JSON 接口。

```
ios/
├── project.yml          # XcodeGen 工程定义(自动生成 .xcodeproj)
├── build-ipa.yml        # GitHub Actions:macOS runner 自动出 ipa(不需要你有 Mac)
└── WMFree/
    ├── WMFreeApp.swift        # @main 入口
    ├── ContentView.swift      # TabView 根(下载/历史/设置)
    ├── Store.swift            # 历史持久化(UserDefaults,仅文字)+ 剪贴板链接提取
    ├── ApiService.swift       # /api/parse + /api/health 网络层
    └── views/
        ├── DownloadView.swift # 下载页:输入/剪贴板粘贴/解析进度/频道结果卡
        ├── HistoryView.swift  # 历史列表,点击直达 Telegram 频道消息
        └── SettingsView.swift # 服务器地址 + bot/频道连接状态检测
```

App 内默认服务器 `http://47.130.212.185:8081`,可在"设置"页随时改。

## 方式 A:没有 Mac(推荐,全程 Windows 可完成)

1. 把 `wmfree/` 推到你的 GitHub 仓库,**把 `ios/build-ipa.yml` 移到仓库根目录 `.github/workflows/build-ipa.yml`**(GitHub 只认这个位置)
2. Actions 页手动 Run(`workflow_dispatch`),或 push 触发,跑完在 Artifacts 下载 `WMFree-ipa`(内含未签名 `WMFree.ipa`)
3. Windows 上装 **Sideloadly**(sideloadly.io,免费)
4. iPhone 连电脑,Sideloadly 拖入 `WMFree.ipa`,填你的 **Apple ID 和密码**,点 Start —— 它会用免费开发者证书重新签名
5. iPhone 上:设置 → 通用 → VPN与设备管理 → 信任你的开发者证书,然后打开 App
6. 免费签名 7 天有效,到期重签一次(Sideloadly 一键);付费开发者账号($99/年)可走 TestFlight 长期安装

## 方式 B:有 Mac

```bash
brew install xcodegen
cd ios && xcodegen generate      # 生成 WMFree.xcodeproj
open WMFree.xcodeproj
```

选真机 → Run。签名用你自己的 Team。无需手工配置 ATS,`project.yml` 已声明 `NSAllowsArbitraryLoads`(IP 明文直连)。

## App 行为(与需求对应)

- 输入/粘贴链接 → `POST /api/parse` → 后端解析无水印 → 下载最高画质 → 上传频道 @dsfsfsdfwsdad
- App 只显示频道消息链接,提供"在 Telegram 频道中查看"直达按钮
- **本地不保存任何视频**,仅 UserDefaults 存最近 100 条文字历史
- 剪贴板检测:切回 App 时若剪贴板有链接,"从剪贴板粘贴"按钮立即可用(抖音分享文本也能提取)

## App Store 审核

该类 App 无法过 App Store 审核(第三方平台内容下载),分发只走:自签(Sideloadly/AltStore)、TestFlight(付费账号)、TrollStore(特定系统版本)。
