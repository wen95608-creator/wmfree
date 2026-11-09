// SettingsView.swift — 设置页:服务器地址 + 健康检查(bot/频道状态)

import SwiftUI

struct SettingsView: View {
    @AppStorage("server") private var server = ApiService.defaultServer
    @State private var checking = false
    @State private var health: HealthResponse?
    @State private var errMsg = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("后端服务器") {
                    TextField("http://47.130.212.185:8081", text: $server)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                    Text("视频不保存在本机,由服务器解析后自动发布到 Telegram 频道 @dsfsfsdfwsdad。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Section("连接状态") {
                    Button {
                        Task { await check() }
                    } label: {
                        if checking {
                            ProgressView().controlSize(.small)
                        } else {
                            Label("检测连接", systemImage: "antenna.radiowaves.left.and.right")
                        }
                    }
                    if let h = health {
                        LabeledContent("机器人", value: "@" + (h.bot ?? "-"))
                        LabeledContent("频道", value: h.channel ?? "-")
                        HStack {
                            Text("频道可达")
                            Spacer()
                            Image(systemName: (h.channelOK ?? false) ? "checkmark.circle.fill" : "xmark.circle.fill")
                                .foregroundStyle((h.channelOK ?? false) ? .green : .red)
                        }
                    }
                    if !errMsg.isEmpty {
                        Text(errMsg).font(.caption).foregroundStyle(.red)
                    }
                }

                Section("关于") {
                    LabeledContent("版本", value: "1.0.0")
                    LabeledContent("本地存储", value: "仅文字历史,不保存视频")
                }
            }
            .navigationTitle("设置")
        }
    }

    private func check() async {
        checking = true
        errMsg = ""
        health = nil
        defer { checking = false }
        do {
            health = try await ApiService.health(server: server)
        } catch {
            errMsg = "连接失败:\(error.localizedDescription)"
        }
    }
}
