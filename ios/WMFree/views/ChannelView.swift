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

    var id: Int { mid }
    // Bot API getFile 下载上限 20MB
    var streamable: Bool { fileID != "" && sizeMB <= 19.5 }
    var durationText: String {
        let s = max(duration, 0)
        return String(format: "%d:%02d", s / 60, s % 60)
    }

    enum CodingKeys: String, CodingKey {
        case mid, title, platform, duration, time
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

// MARK: - 单页播放器

struct ChannelVideoPage: View {
    let video: ChannelVideo
    let server: String
    let isActive: Bool

    @State private var player: AVPlayer?
    @State private var fileURL: URL?
    @State private var loadErr = ""
    @State private var muted = false
    @State private var playing = false
    @State private var loading = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            if let url = fileURL, let pl = player {
                VideoPlayer(player: pl)
                    .ignoresSafeArea()
                    .onTapGesture { togglePlay() }
            } else if !video.streamable {
                tooLargeView
            } else if !loadErr.isEmpty {
                VStack(spacing: 10) {
                    Image(systemName: "exclamationmark.triangle").font(.largeTitle)
                    Text(loadErr).font(.footnote).multilineTextAlignment(.center)
                    Button("重试") { Task { await prepare() } }.buttonStyle(.bordered)
                }
                .padding(30)
            } else {
                ProgressView().controlSize(.large)
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

    private var tooLargeView: some View {
        VStack(spacing: 12) {
            Image(systemName: "film.stack").font(.largeTitle).foregroundStyle(.secondary)
            Text("视频超过 20MB").font(.headline)
            Text("Telegram Bot API 无法流式播放大文件,点击下方飞机图标在频道内观看")
                .font(.caption).foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(30)
        .foregroundStyle(.white)
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

    private func prepare() async {
        if player != nil { player?.play(); playing = true; return }
        guard video.streamable, loading == false else { return }
        loading = true
        loadErr = ""
        defer { loading = false }
        do {
            var req = URLRequest(url: URL(string: server + "/api/videos/\(video.mid)/stream")!)
            req.timeoutInterval = 60
            let (data, resp) = try await URLSession.shared.data(for: req)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
                throw ApiError.server("HTTP \((resp as? HTTPURLResponse)?.statusCode ?? -1)")
            }
            let decoded = try JSONDecoder().decode(FileURLResponse.self, from: data)
            guard let u = URL(string: decoded.fileURL) else { throw ApiError.badURL }
            fileURL = u
            let pl = AVPlayer(url: u)
            pl.isMuted = muted
            pl.play()
            playing = true
            player = pl
        } catch {
            loadErr = error.localizedDescription
        }
    }
}

struct FileURLResponse: Codable {
    let fileURL: String
    enum CodingKeys: String, CodingKey {
        case fileURL = "file_url"
    }
}
