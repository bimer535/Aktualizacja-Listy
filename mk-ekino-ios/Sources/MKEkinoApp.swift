// SPDX-License-Identifier: GPL-3.0-only
import SwiftUI

@main struct MKEkinoApp: App {
    @StateObject private var library = LibraryStore()
    var body: some Scene {
        WindowGroup { CinemaView().environmentObject(library).preferredColorScheme(.dark).tint(Theme.cyan) }
    }
}
enum Theme {
    static let cyan = Color(red: 0.02, green: 0.85, blue: 0.93)
    static let purple = Color(red: 0.46, green: 0.29, blue: 0.88)
    static let panel = Color(red: 0.055, green: 0.083, blue: 0.16)
    static let background = LinearGradient(colors: [Color(red: 0.015, green: 0.025, blue: 0.065), Color(red: 0.055, green: 0.065, blue: 0.17)], startPoint: .topLeading, endPoint: .bottomTrailing)
}
struct CinemaView: View {
    @EnvironmentObject private var library: LibraryStore
    @State private var current = Entry(title: "Odkrywaj", action: "main")
    @State private var rows: [Entry] = Catalogue.home()
    @State private var stack: [(Entry, [Entry])] = []
    @State private var busy = false
    @State private var error: String?
    @State private var query = ""
    @State private var search = false
    @State private var info = false
    @State private var selected: Entry?
    @State private var playback: PlaybackRequest?
    @State private var loadTask: Task<Void, Never>?
    @State private var activeLoad = UUID()
    private let catalogue = Catalogue()
    var body: some View {
        GeometryReader { geometry in
            let wide = geometry.size.width >= 850
            HStack(alignment: .top, spacing: 0) {
                if wide { navigation(vertical: true).frame(width: 210).padding(.top, 25) }
                VStack(spacing: 0) {
                    header
                    if !wide { navigation(vertical: false).padding(.bottom, 14) }
                    HStack(alignment: .top, spacing: 20) {
                        ScrollViewReader { proxy in
                            ScrollView {
                                VStack(alignment: .leading, spacing: 20) {
                                    Color.clear.frame(height: 1).id("top")
                                    if current.action == "main" { hero }
                                    HStack {
                                        Text(current.title).font(.title2.bold())
                                        Spacer()
                                        if busy { ProgressView() }
                                        else { Text("\(rows.count) pozycji").font(.caption).foregroundStyle(.secondary) }
                                    }
                                    if rows.isEmpty && !busy { emptyState }
                                    if library.tiles {
                                        LazyVGrid(columns: [GridItem(.adaptive(minimum: wide ? 155 : 145), spacing: 14)], spacing: 22) {
                                            ForEach(rows) { entry in card(entry) }
                                        }
                                    } else {
                                        LazyVStack(spacing: 12) { ForEach(rows) { entry in listRow(entry) } }
                                    }
                                }.padding(.horizontal, 20).padding(.bottom, 30)
                            }
                            .onChange(of: current.id) { _ in proxy.scrollTo("top", anchor: .top) }
                        }
                        if wide, let selected { detail(selected).frame(width: 270).padding(.trailing, 24) }
                    }
                }
            }.background(Theme.background.ignoresSafeArea())
        }
        .sheet(isPresented: $search) {
            NavigationStack {
                VStack(spacing: 20) {
                    TextField("Tytuł filmu lub serialu", text: $query).textFieldStyle(.roundedBorder).submitLabel(.search).onSubmit { runSearch() }
                    Button("Szukaj", action: runSearch).buttonStyle(.borderedProminent).disabled(query.trimmingCharacters(in: .whitespaces).isEmpty)
                    Spacer()
                }.padding(24).navigationTitle("Wyszukaj").toolbar { ToolbarItem(placement: .cancellationAction) { Button("Wróć") { search = false } } }
            }.presentationDetents([.medium])
        }
        .sheet(isPresented: $info) { about }
        .sheet(item: $selected) { entry in
            NavigationStack { ScrollView { detail(entry).padding(24) }.background(Theme.background).toolbar { ToolbarItem(placement: .cancellationAction) { Button("Wróć") { selected = nil } } } }
        }
        .fullScreenCover(item: $playback) { request in
            SourcePlayer(request: request, catalogue: catalogue).environmentObject(library)
        }
        .alert("Nie udało się otworzyć", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) { Button("OK") { error = nil } } message: { Text(error ?? "") }
        .onDisappear { loadTask?.cancel() }
    }
    private var header: some View {
        HStack(spacing: 12) {
            if !stack.isEmpty { Button(action: back) { Image(systemName: "chevron.left").font(.title3.bold()).frame(width: 44, height: 44) }.accessibilityLabel("Wróć") }
            Image("Brand").resizable().scaledToFit().frame(width: 53, height: 53).clipShape(RoundedRectangle(cornerRadius: 13))
            VStack(alignment: .leading, spacing: 3) {
                Text("MK eKino").font(.title2.bold())
                Text("TWOJE KINO. TWÓJ WYBÓR.").font(.system(size: 9, weight: .semibold)).tracking(1.5).foregroundStyle(Theme.cyan)
            }
            Spacer(minLength: 0)
            Button { search = true } label: { Image(systemName: "magnifyingglass").font(.title3).frame(width: 44, height: 44) }.accessibilityLabel("Szukaj")
            Menu {
                Button(library.tiles ? "Widok listy" : "Widok kafelków", systemImage: "square.grid.2x2") { library.tiles.toggle() }
                Button("Odśwież", systemImage: "arrow.clockwise") { load(current, push: false) }
                Button("O aplikacji", systemImage: "info.circle") { info = true }
            } label: { Image(systemName: "ellipsis.circle").font(.title3).frame(width: 44, height: 44) }.accessibilityLabel("Opcje")
        }.padding(.horizontal, 16).padding(.vertical, 10)
    }
    private func navigation(vertical: Bool) -> some View {
        let menu = [Entry(title: "Odkrywaj", action: "main")] + Catalogue.home().filter { $0.action != "versions" }
        return Group {
            if vertical {
                VStack(alignment: .leading, spacing: 9) { ForEach(menu) { navButton($0) }; Spacer(); Text("MK • 1.0.0 beta").font(.caption).foregroundStyle(.secondary).padding() }.padding(.horizontal, 12)
            } else {
                ScrollView(.horizontal, showsIndicators: false) { HStack(spacing: 9) { ForEach(menu) { navButton($0) } }.padding(.horizontal, 20) }
            }
        }
    }
    private func navButton(_ entry: Entry) -> some View {
        Button { stack.removeAll(); load(entry, push: false) } label: {
            Label(entry.title, systemImage: symbol(entry.action)).font(.subheadline.weight(.semibold)).padding(.horizontal, 14).frame(minHeight: 44)
                .background(current.action == entry.action ? Theme.cyan.opacity(0.17) : Theme.panel, in: RoundedRectangle(cornerRadius: 13))
                .foregroundStyle(current.action == entry.action ? Theme.cyan : .white)
        }.buttonStyle(.plain)
    }
    private var hero: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 12) {
                Text("WIECZÓR NA TWOICH ZASADACH").font(.system(size: 9, weight: .bold)).tracking(1).foregroundStyle(Theme.cyan)
                Text("Kino po\nTwojemu.").font(.system(size: 32, weight: .bold, design: .rounded))
                Text("Odkrywaj filmy i seriale.\nWracaj do ulubionych historii.").font(.caption).foregroundStyle(.white.opacity(0.7))
                Button { load(Entry(title: "Filmy", action: "categories")) } label: { Label("Odkryj filmy", systemImage: "play.fill").font(.subheadline.bold()).padding(.horizontal, 15).frame(minHeight: 44).background(Theme.cyan, in: Capsule()).foregroundStyle(.black) }.buttonStyle(.plain)
            }
            Spacer(minLength: 0)
            Image("Brand").resizable().scaledToFit().frame(maxWidth: 170).clipShape(RoundedRectangle(cornerRadius: 20))
        }.padding(20).frame(maxWidth: .infinity, alignment: .leading).background(LinearGradient(colors: [Theme.purple.opacity(0.45), Theme.panel], startPoint: .topLeading, endPoint: .bottomTrailing), in: RoundedRectangle(cornerRadius: 25)).overlay(RoundedRectangle(cornerRadius: 25).stroke(.white.opacity(0.09)))
    }
    private func card(_ entry: Entry) -> some View {
        Button { choose(entry) } label: {
            VStack(alignment: .leading, spacing: 9) {
                if entry.isTitle { poster(entry).aspectRatio(2 / 3, contentMode: .fit).clipShape(RoundedRectangle(cornerRadius: 16)) }
                else { Image(systemName: symbol(entry.action)).font(.system(size: 28, weight: .medium)).foregroundStyle(Theme.cyan).frame(maxWidth: .infinity).frame(height: 75).background(Theme.panel, in: RoundedRectangle(cornerRadius: 16)) }
                Text(entry.title).font(.subheadline.weight(.semibold)).lineLimit(2).foregroundStyle(.white)
                if !entry.subtitle.isEmpty { Text(entry.subtitle).font(.caption).foregroundStyle(Theme.cyan) }
            }.frame(maxWidth: .infinity, alignment: .topLeading).contentShape(Rectangle())
        }.buttonStyle(.plain).contextMenu { if entry.isTitle { Button(library.contains(entry) ? "Usuń z ulubionych" : "Dodaj do ulubionych", systemImage: "heart") { library.toggle(entry) } } }
    }
    private func listRow(_ entry: Entry) -> some View {
        Button { choose(entry) } label: {
            HStack(spacing: 14) {
                if entry.isTitle { poster(entry).frame(width: 62, height: 92).clipped().clipShape(RoundedRectangle(cornerRadius: 9)) }
                else { Image(systemName: symbol(entry.action)).foregroundStyle(Theme.cyan).frame(width: 44, height: 44) }
                VStack(alignment: .leading, spacing: 7) { Text(entry.title).font(.headline).foregroundStyle(.white); Text(entry.subtitle).font(.caption).foregroundStyle(Theme.cyan) }
                Spacer(); Image(systemName: "chevron.right").foregroundStyle(.secondary)
            }.padding(12).background(Theme.panel, in: RoundedRectangle(cornerRadius: 15))
        }.buttonStyle(.plain)
    }
    private func poster(_ entry: Entry) -> some View {
        AsyncImage(url: URL(string: entry.icon)) { phase in
            if let image = phase.image { image.resizable().scaledToFill() }
            else { ZStack { Theme.panel; Image("Brand").resizable().scaledToFit().padding(22) } }
        }
    }
    private func detail(_ entry: Entry) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            poster(entry).aspectRatio(2 / 3, contentMode: .fit).clipShape(RoundedRectangle(cornerRadius: 20)).frame(maxWidth: 300).frame(maxWidth: .infinity)
            Text(entry.title).font(.title2.bold())
            Text(entry.subtitle).foregroundStyle(Theme.cyan)
            HStack {
                Button { selected = nil; load(entry) } label: { Label(entry.action == "seasons" ? "Odcinki" : "Wybierz źródło", systemImage: "play.fill").frame(minHeight: 44) }.buttonStyle(.borderedProminent)
                Button { library.toggle(entry) } label: { Image(systemName: library.contains(entry) ? "heart.fill" : "heart").frame(width: 44, height: 44) }.buttonStyle(.bordered).accessibilityLabel("Ulubione")
            }
            Text(entry.desc.isEmpty ? "Opis nie jest dostępny w katalogu." : entry.desc).font(.body).foregroundStyle(.white.opacity(0.8))
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
    private var emptyState: some View {
        VStack(spacing: 15) { Image(systemName: "film.stack").font(.largeTitle).foregroundStyle(Theme.cyan); Text(current.action == "continue" ? "Tutaj pojawią się rozpoczęte filmy." : current.action == "favourites" ? "Dodaj film do ulubionych przez przytrzymanie okładki." : "Brak pozycji. Spróbuj odświeżyć listę.").multilineTextAlignment(.center).foregroundStyle(.secondary) }.frame(maxWidth: .infinity).padding(35)
    }
    private var about: some View {
        NavigationStack {
            ScrollView { VStack(alignment: .leading, spacing: 22) {
                Image("Brand").resizable().scaledToFit().frame(height: 150).frame(maxWidth: .infinity)
                Text("MK eKino • iOS 1.0.0 beta").font(.title2.bold())
                Text("Autor wydania: MK")
                Link("Kontakt: bimer55@wp.pl", destination: URL(string: "mailto:bimer55@wp.pl")!)
                Text("Niezależne wydanie MK, z układem inspirowanym epremki. Wersja testowa: odtwarzacze źródłowe działają przez WebKit. Dostępność, jakość, napisy i reklamy zależą od źródła. Wznowienie wymaga odtwarzacza HTML5, który udostępnia postęp.")
                Text("Instalacja bezpłatna przez AltStore Classic wymaga odnawiania podpisu co 7 dni. Aktualizacja z GitHuba nie instaluje się samodzielnie na iOS.")
                Text("GPL-3.0-only. Katalog przeniesiony z MK eKino / epremki. SwiftSoup: MIT; pochodzenie i pełne licencje zawiera projekt źródłowy.").font(.caption).foregroundStyle(.secondary)
            }.padding(24) }.background(Theme.background).navigationTitle("O aplikacji").toolbar { ToolbarItem(placement: .confirmationAction) { Button("Gotowe") { info = false } } }
        }
    }
    private func symbol(_ action: String) -> String {
        switch action { case "main": return "sparkles"; case "categories", "movies": return "film"; case "series", "seasons", "episodes": return "tv"; case "continue": return "play.circle"; case "favourites": return "heart"; case "versions": return "waveform"; case "years": return "calendar"; case "play": return "play.fill"; case "page": return "arrow.right"; default: return "square.grid.2x2" }
    }
    private func choose(_ entry: Entry) {
        if entry.isTitle { selected = entry }
        else if entry.action == "play" {
            let parent = current
            let loadID = UUID(); activeLoad = loadID; loadTask?.cancel(); busy = true
            loadTask = Task { @MainActor in
                defer { if activeLoad == loadID { busy = false } }
                do {
                    let url = try await catalogue.playerURL(entry)
                    try Task.checkCancellation()
                    playback = PlaybackRequest(entry: parent, source: entry, url: url, resume: library.resume(parent))
                } catch { if !Task.isCancelled { self.error = error.localizedDescription } }
            }
        } else { load(entry) }
    }
    private func runSearch() {
        let term = query.trimmingCharacters(in: .whitespacesAndNewlines); guard !term.isEmpty else { return }
        search = false; load(Entry(title: "Szukaj: " + term, action: "search_results", query: String(term.prefix(200))))
    }
    private func back() {
        loadTask?.cancel(); activeLoad = UUID(); busy = false
        guard let last = stack.popLast() else { return }; current = last.0; rows = last.1
    }
    private func load(_ entry: Entry, push: Bool = true) {
        loadTask?.cancel(); let loadID = UUID(); activeLoad = loadID; busy = true
        loadTask = Task { @MainActor in
            defer { if activeLoad == loadID { busy = false } }
            do {
                let next: [Entry]
                if entry.action == "favourites" { next = library.favourites }
                else if entry.action == "continue" { next = library.records.filter { !$0.complete && $0.seconds > 10 }.map(\.entry) }
                else { next = try await catalogue.browse(entry) }
                try Task.checkCancellation()
                if push { stack.append((current, rows)) }
                current = entry; rows = next
            } catch { if !Task.isCancelled { self.error = error.localizedDescription } }
        }
    }
}
