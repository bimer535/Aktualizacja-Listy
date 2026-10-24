// SPDX-License-Identifier: GPL-3.0-only
import XCTest
import WebKit
@testable import MKEkino
final class PlayerBrowserTests: XCTestCase {
    func testAllowedPageAndPopupSchemes() {
        XCTAssertTrue(ProviderNavigation.permits(URL(string: "https://example.org/verify")))
        XCTAssertTrue(ProviderNavigation.permits(URL(string: "about:blank")))
        XCTAssertTrue(ProviderNavigation.permits(nil))
        XCTAssertFalse(ProviderNavigation.permits(URL(string: "file:///etc/passwd")))
        XCTAssertFalse(ProviderNavigation.permits(URL(string: "javascript:alert(1)")))
        XCTAssertFalse(ProviderNavigation.permits(URL(string: "https://user:secret@example.org/")))
    }
    func testUnrelatedAdvertisingDestinationsAreRejected() {
        let policy = ProviderNavigationPolicy(player: URL(string: "https://mfw09.org/embed/film")!, source: "https://ekino.ws/movie/title", referer: "https://play.ekino.link/film")
        XCTAssertFalse(policy.permitsPopup(URL(string: "https://luugy.com/")))
        XCTAssertFalse(policy.permitsTopLevel(URL(string: "https://luugy.com/")))
        XCTAssertFalse(policy.permitsPopup(URL(string: "https://mfw09.org.evil.example/ad")))
        XCTAssertFalse(policy.permitsPopup(URL(string: "about:blank")))
        XCTAssertFalse(policy.permitsPopup(nil))
        XCTAssertTrue(policy.permitsPopup(URL(string: "https://mfw09.org/verify")))
        XCTAssertTrue(policy.permitsTopLevel(URL(string: "https://media.mfw09.org/player")))
        XCTAssertFalse(policy.permitsTopLevel(URL(string: "https://mfw09.org@luugy.com/")))
        XCTAssertFalse(policy.permitsTopLevel(URL(string: "blob:https://luugy.com/id")))
        XCTAssertTrue(policy.permitsTopLevel(URL(string: "blob:https://mfw09.org/id")))
    }
    @MainActor func testAdPopupIsNotPresented() async {
        let request = PlaybackRequest(entry: Entry(title: "Test", action: "sources"), source: Entry(title: "Player", action: "play"), url: URL(string: "https://mfw09.org/embed/test")!, resume: 0)
        let state = PlayerState()
        let coordinator = PlayerWebView(request: request, state: state, record: { _, _ in }).makeCoordinator()
        let presenter = UIViewController()
        XCTAssertNil(coordinator.openPopup(configuration: WKWebViewConfiguration(), address: URL(string: "https://luugy.com/"), presenter: presenter))
        XCTAssertTrue(coordinator.popups.isEmpty)
        XCTAssertNil(presenter.presentedViewController)
        XCTAssertTrue(state.message.contains("Zablokowano"))
        coordinator.stop()
    }
    @MainActor func testConfirmCompletionRunsExactlyOnce() async {
        let dialogs = ProviderDialogs(); var yes = 0; var no = 0
        let id = dialogs.insert { no += 1 }
        dialogs.finish(id, accepted: { yes += 1 }); dialogs.finish(id); dialogs.cancelAll()
        XCTAssertEqual(yes, 1); XCTAssertEqual(no, 0)
    }
    @MainActor func testPendingDialogsCancelOnExit() async {
        let dialogs = ProviderDialogs(); var count = 0
        _ = dialogs.insert { count += 1 }; _ = dialogs.insert { count += 1 }
        dialogs.cancelAll(); dialogs.cancelAll()
        XCTAssertEqual(count, 2)
    }
    @MainActor func testPopupUsesWebKitConfigurationAndStopsOnExit() async {
        let window = UIWindow(frame: UIScreen.main.bounds)
        let presenter = UIViewController(); window.rootViewController = presenter; window.makeKeyAndVisible()
        let request = PlaybackRequest(entry: Entry(title: "Test", action: "sources"), source: Entry(title: "Player", action: "play"), url: URL(string: "https://example.org/")!, resume: 0)
        let view = PlayerWebView(request: request, state: PlayerState(), record: { _, _ in })
        let coordinator = view.makeCoordinator()
        let config = WKWebViewConfiguration(); let pool = config.processPool
        let child = coordinator.openPopup(configuration: config, address: URL(string: "https://example.org/verify"), presenter: presenter)
        XCTAssertNotNil(child); XCTAssertEqual(coordinator.popups.count, 1)
        XCTAssertTrue(child?.configuration.processPool === pool)
        coordinator.stop()
        XCTAssertTrue(coordinator.popups.isEmpty); XCTAssertNil(child?.navigationDelegate); XCTAssertNil(child?.uiDelegate)
        XCTAssertNil(coordinator.openPopup(configuration: config, address: URL(string: "https://example.org/verify"), presenter: presenter))
        window.isHidden = true
    }
}
