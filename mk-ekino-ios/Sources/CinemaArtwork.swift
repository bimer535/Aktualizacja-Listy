// SPDX-License-Identifier: GPL-3.0-only
import Foundation

/// Public artwork only. Catalogue/playback URLs remain the existing eKino URLs.
struct FilmArtwork: Equatable {
    let title: String
    let year: String
    let backdrop: String
    let synopsis: String
}
enum CinemaArtwork {
    static func titleKey(_ title: String) -> String {
        var value = title.components(separatedBy: " / ").first ?? title
        value = value.replacingOccurrences(of: #"\s*[-–·]\s*(?:HD|FHD|UHD|4K|1080p|720p)\s*$"#, with: "", options: [.regularExpression, .caseInsensitive])
        return value.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Locale(identifier: "pl_PL"))
            .components(separatedBy: CharacterSet.alphanumerics.inverted).filter { !$0.isEmpty }.joined(separator: " ")
    }
    static func wideURL(_ value: String?) -> URL? {
        guard let value, var parts = URLComponents(string: value), parts.scheme == "https",
              parts.host == "image.tmdb.org", parts.user == nil, parts.password == nil,
              parts.port == nil || parts.port == 443, parts.query == nil, parts.fragment == nil,
              parts.path.range(of: #"^/t/p/(original|w[0-9]+)/[A-Za-z0-9_-]+\.(jpg|png)$"#, options: .regularExpression) != nil else { return nil }
        parts.path = parts.path.replacingOccurrences(of: #"^/t/p/(original|w[0-9]+)/"#, with: "/t/p/w1280/", options: .regularExpression)
        return parts.url
    }
    static func parse(_ data: Data) throws -> [FilmArtwork] {
        let object = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let channel = object?["channel"] as? [String: Any]
        let content = channel?["content"] as? [String: Any]
        let rows = content?["data"] as? [[String: Any]] ?? []
        return rows.prefix(60).compactMap { row in
            guard row["is_series"] as? Bool != true, let title = row["name"] as? String,
                  let url = wideURL(row["backdrop"] as? String) else { return nil }
            let year = (row["year"] as? String) ?? (row["year"] as? Int).map { String($0) } ?? String((row["release_date"] as? String ?? "").prefix(4))
            return FilmArtwork(title: title, year: year, backdrop: url.absoluteString, synopsis: row["description"] as? String ?? "")
        }
    }
    static func enrich(_ entries: [Entry], with artwork: [FilmArtwork]) -> [Entry] {
        let groups = Dictionary(grouping: artwork) { titleKey($0.title) + "|" + $0.year }
        return entries.map { original in
            var entry = original
            for title in [entry.title, entry.originalTitle ?? ""] where !title.isEmpty {
                let candidates = groups[titleKey(title) + "|" + entry.year] ?? []
                if candidates.count == 1, let match = candidates.first, wideURL(match.backdrop) != nil {
                    entry.backdrop = match.backdrop
                    if entry.desc.isEmpty { entry.desc = clean(match.synopsis) }
                    break
                }
            }
            return entry
        }
    }
    static func slides(_ entries: [Entry]) -> [Entry] {
        var seen = Set<String>()
        return Array(entries.filter { $0.action == "sources" && $0.episode == 0 && $0.year == "2026" && wideURL($0.backdrop) != nil && seen.insert($0.url).inserted }.prefix(12))
    }
}
actor ArtworkService {
    static let shared = ArtworkService()
    private var cached: [FilmArtwork] = []
    private var fetchedAt = Date.distantPast
    private var lastAttempt = Date.distantPast
    private let session: URLSession = {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 8
        configuration.timeoutIntervalForResource = 12
        return URLSession(configuration: configuration)
    }()
    static var catalogueURL: URL {
        var parts = URLComponents(string: "https://premiumsmart.eu/api/v1/channel/filmy")!
        let rule: [[String: Any]] = [["key": "release_date", "operator": "between", "value": ["start": "2026-01-01T00:00:00.000Z", "end": "2026-12-31T23:59:59.999Z"]]]
        let data = try! JSONSerialization.data(withJSONObject: rule, options: [.sortedKeys])
        let encoded = data.base64EncodedString().addingPercentEncoding(withAllowedCharacters: .alphanumerics)!
        parts.queryItems = [URLQueryItem(name: "perPage", value: "60"), URLQueryItem(name: "order", value: "created_at:desc"), URLQueryItem(name: "page", value: "1"), URLQueryItem(name: "filters", value: encoded)]
        return parts.url!
    }
    func films() async -> [FilmArtwork] {
        if Date().timeIntervalSince(fetchedAt) < 1800 || Date().timeIntervalSince(lastAttempt) < 30 { return cached }
        lastAttempt = Date()
        var request = URLRequest(url: Self.catalogueURL)
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("https://premiumsmart.eu/", forHTTPHeaderField: "Referer")
        request.setValue("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1", forHTTPHeaderField: "User-Agent")
        do {
            let (data, response) = try await session.data(for: request)
            guard let response = response as? HTTPURLResponse, response.statusCode == 200, data.count < 2_000_000 else { return cached }
            let values = try CinemaArtwork.parse(data)
            if !values.isEmpty { cached = values; fetchedAt = Date() }
        } catch { /* Optional artwork never prevents use of the catalogue. */ }
        return cached
    }
}
