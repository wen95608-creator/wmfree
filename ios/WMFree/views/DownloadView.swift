// DownloadView.swift — 下载页:输入链接 -> 解析 -> 频道结果
// 视频不落本机,只展示后端返回的频道消息链接

import SwiftUI
import UIKit

struct DownloadView: View {
    @AppStorage("server") private var server = ApiService.defaultServer
    @State private var link = ""
    @State private var busy = false
    @State private var result: ParseResponse?
    @State private var errMsg = ""
    @State private var clipboardHint = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    inputCard
                    if let r = result { resultCard(r) }
                    if !errMsg.isEmpty { errorCard }
                }
                .padding(16)
            }
            .background(Color(.systemGroupedBackground))
            .onTapGesture { hideKeyboard() }   // 点空白处收起键盘
            .navigationTitle("WMFree")
            .onAppear(perform: checkClipboard)
        }
    }

    // MARK: - 输入卡片

    private var inputCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("视频链接", systemImage: "link")
                .font(.headline)

            TextField("粘贴抖音/快手/YouTube 等分享链接", text: $link, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(2...4)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
                .submitLabel(.go)
                .onSubmit {
                    hideKeyboard()
                    Task { await go() }
                }

            HStack(spacing: 10) {
                Button {
                    if let l = ClipboardUtil.extractLink() {
                        link = l
                        clipboardHint = false
                    }
                } label: {
                    Label("从剪贴板粘贴", systemImage: "doc.on.clipboard")
                }
                .buttonStyle(.bordered)

                Spacer()

                Button {
                    Task { await go() }
                } label: {
                    if busy {
                        ProgressView().controlSize(.regular)
                            .frame(maxWidth: .infinity)
                    } else {
                        Text("解析并保存到频道")
                            .bold()
                            .frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(busy || normalizedLink.isEmpty)
            }

            if clipboardHint {
                Text("剪贴板里没有检测到链接")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text("视频不在本机保存,由服务器解析无水印原画后自动发布到 Telegram 频道。")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(16)
        .background(RoundedRectangle(cornerRadius: 14).fill(.ultraThinMaterial))
    }

    // MARK: - 结果卡片

    private func resultCard(_ r: ParseResponse) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("已发布到频道", systemImage: "checkmark.seal.fill")
                .foregroundStyle(.green)
                .font(.headline)
            Text(r.title ?? "")
                .font(.subheadline)
                .lineLimit(3)
            HStack(spacing: 8) {
                Text(r.platform ?? "")
                    .font(.caption).padding(6)
                    .background(.blue.opacity(0.15), in: Capsule())
                if let s = r.sizeMB {
                    Text(String(format: "%.1fMB", s))
                        .font(.caption).padding(6)
                        .background(.gray.opacity(0.15), in: Capsule())
                }
            }
            if let ch = r.channelLink, let u = URL(string: ch) {
                Link(destination: u) {
                    Label("在 Telegram 频道中查看", systemImage: "paperplane.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(RoundedRectangle(cornerRadius: 14).fill(.ultraThinMaterial))
    }

    private var errorCard: some View {
        Text(errMsg)
            .foregroundStyle(.red)
            .font(.footnote)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(RoundedRectangle(cornerRadius: 14).fill(.red.opacity(0.08)))
    }

    // MARK: - 逻辑

    private var normalizedLink: String {
        link.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // 收起键盘:解析开始、点空白处、键盘"前往"键三处都会触发
    private func hideKeyboard() {
        UIApplication.shared.sendAction(
            #selector(UIResponder.resignFirstResponder),
            to: nil, from: nil, for: nil)
    }

    private func checkClipboard() {
        // 进前台时检测剪贴板,有链接就提示用户(不自动读内容,避免 iOS 粘贴弹窗打扰)
        let text = UIPasteboard.general.string ?? ""
        if LinkExtractor.firstURL(in: text) != nil, link.isEmpty {
            clipboardHint = false
            // 不自动填充,仅把提示按钮点亮
        }
    }

    private func go() async {
        hideKeyboard()   // 解析一开始就收起键盘,结果卡直接可见
        busy = true
        errMsg = ""
        result = nil
        defer { busy = false }
        do {
            let r = try await ApiService.parse(server: server, url: normalizedLink)
            result = r
            if let ch = r.channelLink {
                HistoryStore.shared.insert(
                    HistoryItem(url: normalizedLink, title: r.title ?? "",
                                channelLink: ch, time: Date()))
            }
        } catch {
            errMsg = "失败:\(error.localizedDescription)"
        }
    }
}
