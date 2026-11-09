// ChannelView.swift — 频道刷视频页:竖向全屏翻页,TikTok 式交互
// 数据来自后端 /api/videos(频道发布索引),播放走 /api/videos/{mid}/stream 代理流

import SwiftUI
import AVKit

struct ChannelVideo: Codable, Identifiable {
    let mid: Int
    let title: String
    let platform: String
    let sizeMB: Double
    let duration: Int
    let fileID: String
    let time: String
    // 后端下发:embed 直链路径不受 20MB 限制,默认可播
    let streamable: Bool?

    var id: Int { mid }
    var canStream: Bool { streamable ?? true }
    var durationText: String {
        let s = max(duration, 0)
        return String(format: "%d:%02d", s / 60, s % 60)
    }

    enum CodingKeys: String, CodingKey {
        case mid, title, platform, duration, time, streamable
        case sizeMB = "size_mb"
        case fileID = "file_id"
    }
}

struct ChannelView: View {
    @AppStorage("server") private var server = ApiService.defaultServer
    @State private var videos: [ChannelVideo] = []
    @State private var index = 0
    @State private var loading = false
    @State private var errMsg = ""

    var body: some View {
        GeometryReader { geo in
            if loading && videos.isEmpty {
                VStack(spacing: 10) {
                    ProgressView().controlSize(.large)
                    Text("加载频道视频…").font(.subheadline).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(.black)
            } else if videos.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "play.rectangle.on.rectangle")
                        .font(.system(size: 44)).foregroundStyle(.secondary)
                    Text("频道里还没有视频")
                        .font(.headline)
                    Text("去「下载」页解析一条链接,成功发布后这里就能刷了")
                        .font(.caption).foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                    if !errMsg.isEmpty { Text(errMsg).font(.caption).foregroundStyle(.red) }
                    Button("重新加载") { Task { await load() } }
                        .buttonStyle(.bordered)
                }
                .padding(40)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(.black)
            } else {
                // iOS 16 兼容竖向翻页:TabView 旋转 90° 尺寸互换
                TabView(selection: $index) {
                    ForEach(Array(videos.enumerated()), id: \.element.id) { i, v in
                        ChannelVideoPage(video: v, server: normalize(server), isActive: i == index)
                            .rotationEffect(.degrees(-90))
                            .frame(width: geo.size.height, height: geo.size.width)
                            .tag(i)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                .frame(width: geo.size.height, height: geo.size.width)
                .rotationEffect(.degrees(90))
                .offset(x: (geo.size.width - geo.size.height) / 2,
                        y: (geo.size.height - geo.size.width) / 2)
                .ignoresSafeArea()
                .overlay(alignment: .topTrailing) {
                    Button {
                        Task { await load() }
                    } label: {
                        Image(systemName: "arrow.clockwise.circle.fill")
                            .font(.title2).foregroundStyle(.white.opacity(0.85))
                            .padding(14)
                    }
                }
            }
        }
        .background(.black)
        .navigationTitle("")
        .navigationBarHidden(true)
        .task { await load() }
    }

    private func normalize(_ s: String) -> String {
        s.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    }

    private func load() async {
        loading = true
        errMsg = ""
        defer { loading = false }
        do {
            var req = URLRequest(url: URL(string: normalize(server) + "/api/videos")!)
            req.timeoutInterval = 20
            let (data, _) = try await URLSession.shared.data(for: req)
            let decoded = try JSONDecoder().decode(VideosResponse.self, from: data)
            videos = decoded.videos
            index = 0
        } catch {
            errMsg = "加载失败:\(error.localizedDescription)"
        }
    }
}

struct VideosResponse: Codable {
    let videos: [ChannelVideo]
}


// MARK: - 单页播放器(全屏 + 保持原比例 aspectFit)

/// AVPlayerLayer 宿主:支持 resizeAspect(等比不裁剪)+ frame 随布局更新
final class PlayerContainerView: UIView {
    override func layoutSubviews() {
        super.layoutSubviews()
        (layer.sublayers?.first as? AVPlayerLayer)?.frame = bounds
    }
}

struct PlayerLayerUIView: UIViewRepresentable {
    let player: AVPlayer

    func makeUIView(context: Context) -> UIView {
        let view = PlayerContainerView()
        let l = AVPlayerLayer()
        l.player = player
        l.videoGravity = .resizeAspect   // 保持原视频比例,不裁剪,全屏黑边
        view.layer.addSublayer(l)
        view.backgroundColor = .black
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        (uiView.layer.sublayers?.first as? AVPlayerLayer)?.frame = uiView.bounds
    }
}

struct ChannelVideoPage: View {
    let video: ChannelVideo
    let server: String
    let isActive: Bool

    @State private var player: AVPlayer?
    @State private var loadErr = ""
    @State private var muted = false
    @State private var playing = false
    @State private var loading = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            if let pl = player {
                PlayerLayerUIView(player: pl)
                    .ignoresSafeArea()
                    .contentShape(Rectangle())
                    .onTapGesture { togglePlay() }
            } else if !loadErr.isEmpty {
                VStack(spacing: 10) {
                    Image(systemName: "exclamationmark.triangle").font(.largeTitle)
                    Text(loadErr).font(.footnote).multilineTextAlignment(.center)
                    Button("重试") { Task { await prepare() } }.buttonStyle(.bordered)
                }
                .padding(30)
                .foregroundStyle(.white)
            } else {
                VStack(spacing: 10) {
                    ProgressView().controlSize(.large).tint(.white)
                    Text("连接服务器,准备播放…").font(.caption).foregroundStyle(.white.opacity(0.7))
                }
            }

            // 底部信息覆盖层(TikTok 式左下角)
            VStack {
                Spacer()
                HStack(alignment: .bottom) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(video.platform)
                            .font(.caption).bold()
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(.white.opacity(0.18), in: Capsule())
                        Text(video.title)
                            .font(.subheadline)
                            .lineLimit(3)
                        Text("\(video.durationText) · \(String(format: "%.1f", video.sizeMB))MB")
                            .font(.caption2).foregroundStyle(.white.opacity(0.7))
                    }
                    .foregroundStyle(.white)
                    Spacer()
                    VStack(spacing: 18) {
                        Button { toggleMute() } label: {
                            Image(systemName: muted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                                .font(.title3)
                        }
                        if let ch = telegramURL {
                            Link(destination: ch) {
                                Image(systemName: "paperplane.fill").font(.title3)
                            }
                        }
                    }
                    .foregroundStyle(.white)
                }
                .padding(16)
            }
            .padding(.bottom, 24)
        }
        .onChange(of: isActive) { active in
            if active {
                Task { await prepare() }
            } else {
                player?.pause()
                playing = false
            }
        }
        .onAppear {
            if isActive { Task { await prepare() } }
        }
        .onDisappear {
            player?.pause()
            playing = false
        }
    }

    private var telegramURL: URL? {
        URL(string: "https://t.me/dsfsfsdfwsdad/\(video.mid)")
    }

    private func togglePlay() {
        guard let pl = player else { return }
        if playing { pl.pause(); playing = false } else { pl.play(); playing = true }
    }

    private func toggleMute() {
        muted.toggle()
        player?.isMuted = muted
    }

    /// 直接让 AVPlayer 播服务器代理流(国内无法直连 Telegram,必须走服务器转发)。
    /// 后端是 Range 透传真流式,AVPlayer 边下边播,不做任何全量预取。
    private func prepare() async {
        if player != nil { player?.play(); playing = true; return }
        guard loading == false else { return }
        loading = true
        loadErr = ""
        defer { loading = false }
        let url = URL(string: server.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                       + "/api/videos/\(video.mid)/stream")
        guard let u = url else {
            loadErr = "服务器地址无效"
            return
        }
        let pl = AVPlayer(url: u)
        pl.isMuted = muted
        pl.play()
        playing = true
        player = pl
    }
}
