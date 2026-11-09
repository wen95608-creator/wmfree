// Store.swift — 本地持久化:历史记录(仅文字,不存视频)+ 通用工具
// 历史存 UserDefaults,上限 100 条,含链接/标题/频道地址/时间

import Foundation
import UIKit

struct HistoryItem: Codable, Identifiable {
    var id = UUID()
    let url: String
    let title: String
    let channelLink: String
    let time: Date
}

final class HistoryStore {
    static let shared = HistoryStore()
    private let key = "wm_history"
    private let limit = 100

    func load() -> [HistoryItem] {
        guard let data = UserDefaults.standard.data(forKey: key),
              let list = try? JSONDecoder().decode([HistoryItem].self, from: data) else {
            return []
        }
        return list
    }

    func insert(_ item: HistoryItem) {
        var list = load()
        list.insert(item, at: 0)
        if list.count > limit { list = Array(list.prefix(limit)) }
        save(list)
    }

    func removeAll() {
        save([])
    }

    private func save(_ list: [HistoryItem]) {
        if let data = try? JSONEncoder().encode(list) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }
}

enum ClipboardUtil {
    /// 读取剪贴板,提取第一个 http(s) 链接;抖音分享文本也能解析出来
    static func extractLink() -> String? {
        let text = UIPasteboard.general.string ?? ""
        return LinkExtractor.firstURL(in: text)
    }
}

enum LinkExtractor {
    static func firstURL(in text: String) -> String? {
        let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue)
        let matches = detector?.matches(in: text, range: NSRange(text.startIndex..., in: text))
        return matches?.first?.url?.absoluteString
    }
}
