// SPDX-License-Identifier: GPL-3.0-only
import XCTest
@testable import MKEkino
final class CatalogueTests: XCTestCase {
    func testCardsAndRating() throws {
        let html = """
        <div class="movies-list-item"><img src="/poster.jpg" alt="Film"><div class="title"><a href="/movie/show/123/test">Test &amp; film</a></div><div class="sum-vote"><div>4</div></div><div class="cates">2026</div><div class="movieDesc">Opis filmu</div></div>
        <div class="movies-list-item"><div class="title"><a href="/movie/show/123/test">Powtórka</a></div></div>
        <a href="/movie/cat/strona[2]+" title="Następna strona">Następna</a>
        """
        let rows = try Catalogue.cards(html, page: Catalogue.base)
        XCTAssertEqual(rows.count, 2)
        XCTAssertEqual(rows[0].title, "Test & film")
        XCTAssertEqual(rows[0].rating, "4")
        XCTAssertEqual(rows[0].year, "2026")
        XCTAssertEqual(rows[0].icon, "https://ekino.ws/poster.jpg")
        XCTAssertEqual(rows.last?.action, "page")
    }
    func testSourceOrderAndUnsupportedHidden() throws {
        let html = "ShowPlayer('mix','3'); ShowPlayer('player','1'); ShowPlayer('upzone','4'); ShowPlayer('voe','2'); ShowPlayer('player','1');"
        let rows = try Catalogue.sourceItems(html, parent: Entry(title: "Film", action: "sources", url: "https://ekino.ws/movie/show/1"))
        XCTAssertEqual(rows.map(\.provider), ["player", "voe", "mix"])
    }
    func testFilterValidation() throws {
        XCTAssertThrowsError(try Catalogue.movieURL(Entry(title: "", action: "movies", category: "../")))
        let url = try Catalogue.movieURL(Entry(title: "", action: "movies", year: "2026", category: "2,3", version: "1"))
        XCTAssertTrue(url.contains("rok[2026]")); XCTAssertTrue(url.contains("kategoria[2,3]"))
    }
    func testEpisodesInOrderAndParentPreserved() {
        let html = """
        <p>Sezon 2</p><ul class="list-series"><li><a href="/serie/watch/a+season[2]+episode[3]+">Trzeci</a></li><li><a href="/serie/watch/a+season[2]+episode[1]+">Pierwszy</a></li></ul>
        """
        let parent = Entry(title: "Serial", action: "seasons", url: "https://ekino.ws/serie/show/a", icon: "https://ekino.ws/p.jpg")
        let seasons = Catalogue.seasonItems(html, parent: parent)
        let episodes = Catalogue.episodeItems(html, parent: seasons[0])
        XCTAssertEqual(episodes.map(\.episode), [1, 3]); XCTAssertEqual(episodes[0].seriesURL, parent.url)
        XCTAssertEqual(episodes[0].icon, parent.icon)
    }
    func testURLRejectsNonWebSchemes() { XCTAssertEqual(absolute("javascript:alert(1)"), ""); XCTAssertEqual(absolute("file:///etc/passwd"), "") }
}
