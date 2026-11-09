// HistoryView.swift — 历史页:最近解析记录(仅文字),点击直达频道消息

import SwiftUI

struct HistoryView: View {
    @State private var items: [HistoryItem] = []

    var body: some View {
        NavigationStack {
            Group {
                if items.isEmpty {
                    // iOS 16 兼容空态(ContentUnavailableView 是 iOS 17+)
                    VStack(spacing: 10) {
                        Image(systemName: "clock")
                            .font(.system(size: 44))
                            .foregroundStyle(.secondary)
                        Text("暂无记录")
                            .font(.headline)
                        Text("解析过的链接会出现在这里(仅保存文字与频道地址)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(40)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List {
                        ForEach(items) { item in
                            Section {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(item.title.isEmpty ? item.url : item.title)
                                        .font(.subheadline)
                                        .lineLimit(2)
                                    HStack {
                                        if let u = URL(string: item.channelLink) {
                                            Link(item.channelLink, destination: u)
                                                .font(.caption)
                                                .lineLimit(1)
                                        }
                                        Spacer()
                                        Text(item.time, style: .date)
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                                .padding(.vertical, 2)
                            }
                        }
                    }
                }
            }
            .navigationTitle("历史")
            .toolbar {
                if !items.isEmpty {
                    Button("清空", role: .destructive) {
                        HistoryStore.shared.removeAll()
                        items = []
                    }
                }
            }
            .onAppear { items = HistoryStore.shared.load() }
        }
    }
}
