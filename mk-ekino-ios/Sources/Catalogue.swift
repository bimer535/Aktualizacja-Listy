// SPDX-License-Identifier: GPL-3.0-only
// Native port of MK / epremki public catalogue; no private E2iPlayer modules.
import Foundation
import SwiftSoup

func matches(_ pattern: String, _ text: String) -> [[String]] {
    guard let regex = try? NSRegularExpression(pattern: pattern, options: [.dotMatchesLineSeparators]) else { return [] }
    let ns = text as NSString
    return regex.matches(in: text, range: NSRange(location: 0, length: ns.length)).map { match in
        (1..<match.numberOfRanges).map { match.range(at: $0).location == NSNotFound ? "" : ns.substring(with: match.range(at: $0)) }
    }
}
func first(_ pattern: String, _ text: String) -> String { matches(pattern, text).first?.first ?? "" }
func clean(_ text: String) -> String { (try? SwiftSoup.parseBodyFragment(text).text()) ?? text }
func absolute(_ value: String, base: String = Catalogue.base) -> String {
    guard !value.isEmpty, let root = URL(string: base), let url = URL(string: value, relativeTo: root)?.absoluteURL,
          ["https", "http"].contains(url.scheme?.lowercased() ?? ""), url.user == nil, url.password == nil else { return "" }
    return url.absoluteString
}

enum CatalogueError: LocalizedError {
    case message(String)
    var errorDescription: String? { if case .message(let text) = self { return text }; return nil }
}

struct PlayerLocation {
    let url: URL
    let referer: String
}

actor Catalogue {
    static let base = "https://ekino.ws/"
    private let session: URLSession
    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 25
        config.httpCookieStorage = .shared
        config.httpShouldSetCookies = true
        session = URLSession(configuration: config)
    }
    func fetch(_ address: String, referer: String = base) async throws -> (String, String) {
        guard let url = URL(string: address), url.scheme == "https", url.host != nil else { throw CatalogueError.message("Nieprawidłowy adres serwisu.") }
        var request = URLRequest(url: url)
        request.setValue(referer, forHTTPHeaderField: "Referer")
        request.setValue("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else { throw CatalogueError.message("Serwis nie udostępnił strony. Spróbuj później.") }
        guard data.count < 8_000_000 else { throw CatalogueError.message("Odpowiedź serwisu jest zbyt duża.") }
        let body = String(data: data, encoding: .utf8) ?? String(data: data, encoding: .isoLatin1) ?? ""
        if body.contains("cf-chl-") || body.contains("Attention Required! | Cloudflare") { throw CatalogueError.message("Serwis wymaga weryfikacji w przeglądarce. Nie można teraz pobrać katalogu.") }
        return (body, http.url?.absoluteString ?? address)
    }
    static func home() -> [Entry] {
        [Entry(title: "Filmy", action: "categories"), Entry(title: "Seriale", action: "series"),
         Entry(title: "Kontynuuj oglądanie", action: "continue"), Entry(title: "Ulubione", action: "favourites"),
         Entry(title: "Dla dzieci", action: "versions", category: "2,3,5,6")]
    }
    static func movieURL(_ entry: Entry) throws -> String {
        var url = base + "movie/cat/strona[1]+sort[add]+method[desc]+"
        for (name, value) in [("kategoria", entry.category), ("wersja", entry.version), ("rok", entry.year)] where !value.isEmpty {
            guard value.range(of: "^[A-Za-z0-9,]{1,50}$", options: .regularExpression) != nil else { throw CatalogueError.message("Nieprawidłowy filtr.") }
            url += "\(name)[\(value)]+"
        }
        return url
    }
    static func cards(_ text: String, page: String) throws -> [Entry] {
        let document = try SwiftSoup.parse(text)
        var rows: [Entry] = []; var seen = Set<String>()
        for node in try document.select(".movies-list-item") {
            guard let link = try node.select("a[href*='/movie/show/'], a[href*='/serie/show/']").first() else { continue }
            let target = absolute(try link.attr("href"), base: page)
            guard !target.isEmpty, seen.insert(target).inserted else { continue }
            let titleNode = try node.select(".title a").first()
            let image = try node.select("img").first()
            let title = try titleNode?.text() ?? image?.attr("alt") ?? ""
            guard !title.isEmpty else { continue }
            var entry = Entry(title: title, action: target.contains("/movie/show/") ? "sources" : "seasons", url: target)
            entry.icon = absolute(try image?.attr("src") ?? "", base: page)
            entry.year = first("\\b([12][0-9]{3})\\b", try node.select(".cates").text())
            entry.desc = try node.select(".movieDesc").text()
            let score = try node.select(".sum-vote div").first()?.text() ?? ""
            if let number = Double(score.replacingOccurrences(of: ",", with: ".")), (0...10).contains(number) { entry.rating = score.replacingOccurrences(of: ".", with: ",") }
            rows.append(entry)
        }
        if let link = try document.select("a[title]").array().first(where: { (try? $0.attr("title").contains("pna strona")) == true }) {
            let next = absolute(try link.attr("href"), base: page)
            if !next.isEmpty && !rows.isEmpty { rows.append(Entry(title: "Następna strona", action: "page", url: next)) }
        }
        return rows
    }
    static func sourceItems(_ text: String, parent: Entry) throws -> [Entry] {
        let document = try SwiftSoup.parse(text)
        var labels: [String: String] = [:]
        for link in try document.select("ul.players a[href^='#']") {
            let key = String(try link.attr("href").dropFirst())
            labels[key] = try link.select("[title]").array().map { try $0.attr("title") }.joined(separator: " · ")
        }
        let providers = ["player", "voe", "mix"]
        var rows: [Entry] = []; var seen = Set<String>()
        for pair in matches("ShowPlayer\\(['\"]([^'\"]+)['\"],\\s*['\"]([^'\"]+)['\"]\\)", text) {
            let provider = pair[0], key = pair[1]
            guard providers.contains(provider), seen.insert(provider + key).inserted else { continue }
            var row = parent; row.action = "play"; row.provider = provider; row.key = key
            row.title = provider.capitalized + (labels[key + "-" + provider].map { $0.isEmpty ? "" : " — " + $0 } ?? "")
            rows.append(row)
        }
        return rows.sorted { providers.firstIndex(of: $0.provider)! < providers.firstIndex(of: $1.provider)! }
    }
    static func seasonItems(_ text: String, parent: Entry) -> [Entry] {
        matches("<p>Sezon (\\d+)</p>\\s*<ul class=\"list-series\">(.*?)</ul>", text).map { pair in
            var row = parent; row.action = "episodes"; row.title = "Sezon " + pair[0]; row.season = pair[0]
            row.seriesURL = parent.url; row.seriesTitle = parent.title
            return row
        }.sorted { (Int($0.season) ?? 0) < (Int($1.season) ?? 0) }
    }
    static func episodeItems(_ text: String, parent: Entry) -> [Entry] {
        var rows: [Entry] = []
        for pair in matches("<p>Sezon (\\d+)</p>\\s*<ul class=\"list-series\">(.*?)</ul>", text) where pair[0] == parent.season {
            for link in matches("<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", pair[1]) {
                let number = first("episode\\[(\\d+)\\]", link[0]); guard let episode = Int(number) else { continue }
                var row = parent; row.action = "sources"; row.episode = episode
                row.title = String(format: "S%02dE%02d", Int(parent.season) ?? 0, episode) + " — " + clean(link[1])
                row.url = absolute(link[0]); rows.append(row)
            }
        }
        return rows.sorted { $0.episode < $1.episode }
    }
    func nextEpisode(_ entry: Entry) async throws -> Entry? {
        guard entry.seriesURL.hasPrefix(Self.base + "serie/show/") else { return nil }
        let (text, _) = try await fetch(entry.seriesURL)
        var parent = entry; parent.url = entry.seriesURL; parent.title = entry.seriesTitle
        let episodes = Self.seasonItems(text, parent: parent).flatMap { Self.episodeItems(text, parent: $0) }
        return episodes.first { (Int($0.season) ?? 0, $0.episode) > (Int(entry.season) ?? 0, entry.episode) }
    }
    func browse(_ entry: Entry) async throws -> [Entry] {
        if entry.action == "main" { return Self.home() }
        if ["categories", "versions", "years"].contains(entry.action) {
            let (text, _) = try await fetch(Self.base + "movie/cat/+")
            let doc = try SwiftSoup.parse(text)
            var common = entry
            let next = entry.action == "categories" ? "versions" : entry.action == "versions" ? "years" : "movies"
            common.action = next; common.title = "Wszystkie"
            var rows = [common]
            let selector = entry.action == "categories" ? "ul.movieCategories a" : entry.action == "versions" ? "ul.quality li[data-id]" : "ul.filtyear [data-id]"
            for element in try doc.select(selector) {
                var row = common; row.title = try element.text()
                if entry.action == "categories" {
                    row.category = first("kategoria\\[(\\d+)\\]", try element.attr("href")); if row.category.isEmpty { continue }
                } else if entry.action == "versions" { row.version = try element.attr("data-id") }
                else { row.year = try element.attr("data-id"); row.title = row.year }
                rows.append(row)
            }
            guard rows.count > 1 else { throw CatalogueError.message("Nie udało się odczytać filtrów serwisu.") }
            return rows
        }
        if ["seasons", "episodes", "sources"].contains(entry.action) {
            let (text, _) = try await fetch(entry.url)
            if entry.action == "sources" { return try Self.sourceItems(text, parent: entry) }
            if entry.action == "episodes" { return Self.episodeItems(text, parent: entry) }
            return Self.seasonItems(text, parent: entry)
        }
        var url = entry.url
        if entry.action == "movies" { url = try Self.movieURL(entry) }
        if entry.action == "search_results" {
            var components = URLComponents(string: Self.base + "search/qf/")!
            components.queryItems = [URLQueryItem(name: "q", value: entry.query)]; url = components.url!.absoluteString
        }
        if entry.action == "series" || entry.action == "series_section" || entry.action == "series_az" {
            let (text, final) = try await fetch(Self.base + "serie/")
            if entry.action == "series" {
                let sections = text.components(separatedBy: "<h4")
                var rows: [Entry] = []
                for (index, section) in sections.dropFirst().enumerated() {
                    let title = clean(first("^[^>]*>(.*?)</h4>", section))
                    if !title.isEmpty { var row = Entry(title: title, action: "series_section"); row.section = index; rows.append(row) }
                }
                rows.append(Entry(title: "Seriale A–Z", action: "series_az")); return rows
            }
            let doc = try SwiftSoup.parse(text)
            if entry.action == "series_az" {
                return try doc.select("ul.serialsmenu a[href]").array().compactMap { link in
                    let title = try link.text(); let target = absolute(try link.attr("href"))
                    return target.isEmpty ? nil : Entry(title: title, action: "page", url: target)
                }
            }
            let sections = text.components(separatedBy: "<h4")
            guard sections.indices.contains(entry.section + 1) else { return [] }
            let section = sections[entry.section + 1]
            let cards = try Self.cards(section, page: final)
            if !cards.isEmpty { return cards }
            return matches("<a class=\"b\"\\s+href=\"([^\"]+)\">([^<]+)</a>", section).map { Entry(title: clean($0[1]), action: "seasons", url: absolute($0[0])) }
        }
        let (text, final) = try await fetch(url)
        return try Self.cards(text, page: final)
    }
    // Follows only the ordinary links provided by the website. The final provider
    // runs its own player in WebKit. No DRM, CAPTCHA or subscription bypass.
    func playerURL(_ source: Entry) async throws -> PlayerLocation {
        guard ["player", "voe", "mix"].contains(source.provider), !source.key.isEmpty else { throw CatalogueError.message("Nieprawidłowe źródło.") }
        let key = source.key.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? ""
        var url = Self.base + "watch/f/" + source.provider + "/" + key
        var parent = source.url; var visited = Set<String>()
        for _ in 0..<6 {
            guard visited.insert(url).inserted, let address = URL(string: url), let host = address.host else { break }
            let wrapper = host == "ekino.ws" || host == "ekino.link" || host.hasSuffix(".ekino.link")
            if !wrapper { return PlayerLocation(url: address, referer: parent) }
            let (text, final) = try await fetch(url, referer: parent)
            let doc = try SwiftSoup.parse(text)
            let frame = try doc.select("iframe[src]").first()?.attr("src") ?? ""
            let link = try doc.select("a[target][href]").first()?.attr("href") ?? ""
            let target = absolute(frame.isEmpty ? link : frame, base: final)
            guard !target.isEmpty else { throw CatalogueError.message("Serwis nie zwrócił odtwarzacza. Wybierz inne źródło.") }
            parent = final; url = target
        }
        throw CatalogueError.message("Nie udało się otworzyć odtwarzacza źródłowego.")
    }
}

