// ApiService.swift — 网络层:只发链接给后端,视频不在本机保存
// 后端下载无水印原画并自动发布到 Telegram 频道,返回频道消息链接

import Foundation

struct ParseResponse: Codable {
    let ok: Bool
    let platform: String?
    let title: String?
    let sizeMB: Double?
    let channelLink: String?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case ok, error
        case platform, title
        case sizeMB = "size_mb"
        case channelLink = "channel_link"
    }
}

struct HealthResponse: Codable {
    let ok: Bool
    let bot: String?
    let channel: String?
    let channelOK: Bool?

    enum CodingKeys: String, CodingKey {
        case ok, bot, channel
        case channelOK = "channel_ok"
    }
}

enum ApiError: LocalizedError {
    case badURL
    case server(String)

    var errorDescription: String? {
        switch self {
        case .badURL: return "服务器地址无效"
        case .server(let m): return m
        }
    }
}

final class ApiService {
    static let defaultServer = "http://47.130.212.185:8081"

    /// 规范化用户输入的服务器地址:去空格/去尾斜杠
    static func normalize(_ server: String) -> String {
        server.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    }

    private static func endpoint(_ server: String, _ path: String) throws -> URL {
        guard let url = URL(string: normalize(server) + path) else {
            throw ApiError.badURL
        }
        return url
    }

    /// 发送链接解析。视频由后端下载并直发频道,本机不留任何视频文件。
    /// 下载+上传大视频耗时,超时给足 10 分钟。
    static func parse(server: String, url: String) async throws -> ParseResponse {
        var req = URLRequest(url: try endpoint(server, "/api/parse"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 600
        req.httpBody = try JSONSerialization.data(withJSONObject: ["url": url])

        let (data, resp) = try await URLSession.shared.data(for: req)
        let decoded = try JSONDecoder().decode(ParseResponse.self, from: data)
        if !decoded.ok {
            throw ApiError.server(decoded.error ?? "HTTP \((resp as? HTTPURLResponse)?.statusCode ?? 0)")
        }
        return decoded
    }

    /// 后端健康检查:bot 是否有效、频道是否可达
    static func health(server: String) async throws -> HealthResponse {
        var req = URLRequest(url: try endpoint(server, "/api/health"))
        req.timeoutInterval = 20
        let (data, _) = try await URLSession.shared.data(for: req)
        return try JSONDecoder().decode(HealthResponse.self, from: data)
    }
}
