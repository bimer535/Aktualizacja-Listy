// SPDX-License-Identifier: GPL-3.0-only
import XCTest
import SwiftUI
import UIKit
@testable import MKEkino

final class CatalogueScrollTests: XCTestCase {
    @MainActor private func scroll(in view: UIView) -> UIScrollView? {
        if let view = view as? UIScrollView { return view }
        for child in view.subviews { if let result = scroll(in: child) { return result } }
        return nil
    }
    @MainActor private func page(_ revision: UUID) -> some View {
        CatalogueScrollView(revision: revision) {
            VStack { ForEach(0..<80, id: \.self) { Text("Source \($0)").frame(height: 44) } }
                .frame(maxWidth: .infinity)
        }
    }
    @MainActor func testCompletedNavigationResetsScrolledPageToTop() async throws {
        let window = UIWindow(frame: CGRect(x: 0, y: 0, width: 390, height: 844))
        let host = UIHostingController(rootView: page(UUID()))
        window.rootViewController = host; window.makeKeyAndVisible()
        defer { window.isHidden = true; window.rootViewController = nil }
        try await Task.sleep(nanoseconds: 300_000_000)
        host.view.setNeedsLayout(); host.view.layoutIfNeeded()
        let first = try XCTUnwrap(scroll(in: host.view))
        XCTAssertGreaterThan(first.contentSize.height, first.bounds.height + 500)
        first.setContentOffset(CGPoint(x: 0, y: 1000), animated: false)
        XCTAssertGreaterThan(first.contentOffset.y, 500)
        host.rootView = page(UUID())
        try await Task.sleep(nanoseconds: 300_000_000)
        host.view.setNeedsLayout(); host.view.layoutIfNeeded()
        let next = try XCTUnwrap(scroll(in: host.view))
        XCTAssertEqual(next.contentOffset.y, -next.adjustedContentInset.top, accuracy: 2)
    }
}
