// SPDX-License-Identifier: GPL-3.0-only
import XCTest
@testable import MKEkino
final class CinemaArtworkTests: XCTestCase {
    private let wide = "https://image.tmdb.org/t/p/w1280/abc.jpg"
    func testOldSavedEntriesStillDecode() throws {
        let encoder = JSONEncoder()
        let data = try encoder.encode(Entry(title: "Zapisany", action: "sources", url: "https://ekino.ws/movie/show/1"))
        var json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        for key in ["backdrop", "originalTitle", "language"] { json.removeValue(forKey: key) }
        let old = try JSONDecoder().decode(Entry.self, from: JSONSerialization.data(withJSONObject: json))
        XCTAssertEqual(old.title, "Zapisany"); XCTAssertNil(old.backdrop)
    }
    func testSlidesExcludeOldFilmsEpisodesAndMissingWideImages() {
        let film = Entry(title: "A", action: "sources", url: "https://ekino.ws/movie/show/1", year: "2026", backdrop: wide)
        var old = film; old.year = "2025"
        var episode = film; episode.episode = 1
        var poster = film; poster.backdrop = nil; poster.icon = wide
        XCTAssertEqual(CinemaArtwork.slides([old, episode, poster, film, film]), [film])
    }
    func testExactYearAndTitleMatchOnly() {
        let rows = [Entry(title: "Film - HD", action: "sources", year: "2026"), Entry(title: "Film", action: "sources", year: "1999")]
        let result = CinemaArtwork.enrich(rows, with: [FilmArtwork(title: "Film", year: "2026", backdrop: wide, synopsis: "Opis")])
        XCTAssertEqual(result[0].backdrop, wide); XCTAssertNil(result[1].backdrop)
        let duplicate = FilmArtwork(title: "Film", year: "2026", backdrop: wide, synopsis: "Opis")
        XCTAssertNil(CinemaArtwork.enrich(rows, with: [duplicate, duplicate])[0].backdrop)
    }
    func testArtworkRejectsNonImageHostsAndPreservesHttps() {
        for value in ["http://image.tmdb.org/t/p/w1280/a.jpg", "https://example.com/p.jpg", wide + "?token=anything", "https://image.tmdb.org:8443/t/p/w1280/a.jpg"] {
            XCTAssertNil(CinemaArtwork.wideURL(value))
        }
        XCTAssertEqual(CinemaArtwork.wideURL("https://image.tmdb.org/t/p/original/abc.jpg")?.absoluteString, wide)
    }
    func testPublicMetadataShape() throws {
        let data = Data(#"{"channel":{"content":{"data":[{"name":"Film","year":2026,"backdrop":"https://image.tmdb.org/t/p/w1280/abc.jpg","description":"Pełny opis"},{"name":"Serial","is_series":true,"year":2026,"backdrop":"https://image.tmdb.org/t/p/w1280/abc.jpg"}]}}}"#.utf8)
        let values = try CinemaArtwork.parse(data)
        XCTAssertEqual(values.count, 1); XCTAssertEqual(values[0].year, "2026")
    }
    func testFullDescriptionIsNotTruncated() throws {
        let text = String(repeating: "Cały opis filmu bez obcinania. ", count: 200).trimmingCharacters(in: .whitespaces)
        let entry = Entry(title: "Film", action: "sources", desc: "Skrót…")
        let full = try Catalogue.detailedEntry(entry, html: "<div class='descriptionMovie'>" + text + "</div>")
        XCTAssertEqual(full.desc, text)
    }
    func testArtworkQueryContainsExplicit2026Range() throws {
        let parts = try XCTUnwrap(URLComponents(url: ArtworkService.catalogueURL, resolvingAgainstBaseURL: false))
        let filter = try XCTUnwrap(parts.queryItems?.first { $0.name == "filters" }?.value?.removingPercentEncoding)
        let data = try XCTUnwrap(Data(base64Encoded: filter))
        let text = String(decoding: data, as: UTF8.self)
        XCTAssertTrue(text.contains("2026-01-01")); XCTAssertTrue(text.contains("2026-12-31"))
    }
}
