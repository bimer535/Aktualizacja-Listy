// SPDX-License-Identifier: GPL-3.0-only
import XCTest
import SwiftUI
import UIKit
@testable import MKEkino
final class CinemaAppearanceTests: XCTestCase {
    @MainActor func testTouchControlsFitPortraitAndLandscape() throws {
        for size in [CGSize(width: 390, height: 844), CGSize(width: 844, height: 390)] {
            let entry = Entry(title: "Przykładowy film", action: "sources", url: "https://ekino.ws/movie/show/test", desc: "Pełny opis filmu do sprawdzenia układu ekranu.", year: "2026", rating: "7,8", backdrop: "https://image.tmdb.org/t/p/w1280/test.jpg")
            let root = CinemaView(previewRows: [entry, Entry(title: "Następna strona", action: "page")]).environmentObject(LibraryStore()).preferredColorScheme(.dark)
            let controller = UIHostingController(rootView: root)
            let window = UIWindow(frame: CGRect(origin: .zero, size: size))
            window.rootViewController = controller; window.makeKeyAndVisible()
            defer { window.isHidden = true; window.rootViewController = nil }
            controller.view.setNeedsLayout(); controller.view.layoutIfNeeded()
            XCTAssertGreaterThan(controller.view.bounds.width, 0)
            let image = UIGraphicsImageRenderer(size: size).image { _ in controller.view.drawHierarchy(in: controller.view.bounds, afterScreenUpdates: true) }
            let attachment = XCTAttachment(image: image); attachment.name = "Cinema controls \(Int(size.width))x\(Int(size.height))"; attachment.lifetime = .keepAlways
            add(attachment)
        }
    }
}
