// SPDX-License-Identifier: GPL-3.0-only
import Foundation
import Combine

struct Entry: Codable, Identifiable, Hashable {
    var title: String
    var action: String
    var url = ""
    var icon = ""
    var desc = ""
    var year = ""
    var rating = ""
    var category = ""
    var version = ""
    var query = ""
    var season = ""
    var episode = 0
    var seriesURL = ""
    var seriesTitle = ""
    var provider = ""
    var key = ""
    var section = 0
    var id: String { [action, url, title, category, version, year, key].joined(separator: "|") }
    var isTitle: Bool { action == "sources" || action == "seasons" }
    var subtitle: String { [rating.isEmpty ? "" : "★ \(rating)/10", year].filter { !$0.isEmpty }.joined(separator: " · ") }
}

struct WatchRecord: Codable {
    var entry: Entry
    var seconds: Double
    var duration: Double
    var updated: Date
    var complete: Bool { duration > 0 && seconds / duration > 0.95 }
}

@MainActor final class LibraryStore: ObservableObject {
    @Published private(set) var favourites: [Entry] = []
    @Published private(set) var records: [WatchRecord] = []
    @Published var tiles: Bool { didSet { UserDefaults.standard.set(tiles, forKey: "mk.tiles") } }
    private let defaults = UserDefaults.standard
    init() {
        tiles = defaults.object(forKey: "mk.tiles") as? Bool ?? true
        if let data = defaults.data(forKey: "mk.favourites") { favourites = (try? JSONDecoder().decode([Entry].self, from: data)) ?? [] }
        if let data = defaults.data(forKey: "mk.records") { records = (try? JSONDecoder().decode([WatchRecord].self, from: data)) ?? [] }
    }
    func toggle(_ entry: Entry) {
        if favourites.contains(where: { $0.url == entry.url }) { favourites.removeAll { $0.url == entry.url } }
        else { favourites.insert(entry, at: 0) }
        defaults.set(try? JSONEncoder().encode(favourites), forKey: "mk.favourites")
    }
    func contains(_ entry: Entry) -> Bool { favourites.contains { $0.url == entry.url } }
    func record(_ entry: Entry, seconds: Double, duration: Double) {
        guard seconds.isFinite, duration.isFinite, seconds >= 0, duration > 0 else { return }
        records.removeAll { $0.entry.url == entry.url }
        records.insert(WatchRecord(entry: entry, seconds: seconds, duration: duration, updated: Date()), at: 0)
        records = Array(records.prefix(150))
        defaults.set(try? JSONEncoder().encode(records), forKey: "mk.records")
    }
    func resume(_ entry: Entry) -> Double {
        guard let row = records.first(where: { $0.entry.url == entry.url }), !row.complete else { return 0 }
        return row.seconds
    }
}
