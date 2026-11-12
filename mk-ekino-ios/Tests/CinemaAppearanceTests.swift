// SPDX-License-Identifier: GPL-3.0-only
import XCTest
import SwiftUI
import UIKit
@testable import MKEkino
final class CinemaAppearanceTests: XCTestCase {
    @MainActor func testTouchControlsFitPortraitAndLandscape() throws {
        for size in [CGSize(width: 390, height: 844), CGSize(width: 844, height: 390)] {
            let root = VStack(alignment: .leading, spacing: 20) {
                HStack {
                    Text("MK KINO").font(.title2.bold())
                    Spacer()
                }
                HStack(spacing: 10) {
                    Button("Oglądaj teraz") {}.buttonStyle(CinemaButtonStyle(selected: true))
                    Button("Szczegóły") {}.buttonStyle(CinemaButtonStyle())
                }
                MoviePoster(entry: Entry(title: "Film", action: "sources")).frame(width: 140, height: 210)
            }.padding(20).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading).background(Theme.background).preferredColorScheme(.dark)
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
