// SPDX-License-Identifier: GPL-3.0-only
import SwiftUI

/// Replace the scroll container after a completed navigation so its old offset
/// cannot hide the new page. Re-rendering the same page preserves its offset.
struct CatalogueScrollView<Content: View>: View {
    let revision: UUID
    private let content: () -> Content
    init(revision: UUID, @ViewBuilder content: @escaping () -> Content) {
        self.revision = revision; self.content = content
    }
    var body: some View { ScrollView { content() }.id(revision) }
}
