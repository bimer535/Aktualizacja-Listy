// SPDX-License-Identifier: GPL-3.0-only
import SwiftUI

@main struct MKEkinoApp: App {
    @StateObject private var library = LibraryStore()
    var body: some Scene {
        WindowGroup { CinemaView().environmentObject(library).preferredColorScheme(.dark).tint(Theme.cyan) }
    }
}
enum Theme {
    // Android TV 0.6.5: #15102b background, #299dff accent.
    static let cyan = Color(red: 41/255, green: 157/255, blue: 1)
    static let purple = Color(red: 0.26, green: 0.18, blue: 0.44)
    static let ink = Color(red: 21/255, green: 16/255, blue: 43/255)
    static let panel = Color(red: 0.16, green: 0.27, blue: 0.35)
    static let background = LinearGradient(colors: [Color(red: 0.025, green: 0.06, blue: 0.14), ink, Color(red: 0.16, green: 0.08, blue: 0.32)], startPoint: .topLeading, endPoint: .bottomTrailing)
}
struct CinemaButtonStyle: ButtonStyle {
    var selected = false
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .foregroundStyle(Color.white)
            .padding(.horizontal, 15).frame(minHeight: 44)
            .background(Theme.panel.opacity(selected || configuration.isPressed ? 0.88 : 0.58), in: Capsule())
            .overlay(Capsule().stroke(selected || configuration.isPressed ? Theme.cyan : Color.white.opacity(0.6), lineWidth: selected || configuration.isPressed ? 2 : 1))
            .shadow(color: Theme.cyan.opacity(selected || configuration.isPressed ? 0.65 : 0), radius: 8)
    }
}
struct CinemaBackdrop: View {
    let address: String?
    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .top) {
                if let url = CinemaArtwork.wideURL(address) {
                    AsyncImage(url: url) { phase in
                        if let image = phase.image {
                            // Preserve the whole widescreen frame. Never magnify a vertical poster.
                            image.resizable().scaledToFit().frame(width: geometry.size.width, alignment: .top)
                        }
                    }
                }
                LinearGradient(colors: [.black.opacity(0.72), .black.opacity(0.25), .clear], startPoint: .leading, endPoint: .trailing)
                LinearGradient(stops: [.init(color: Theme.ink.opacity(0.02), location: 0), .init(color: Theme.ink.opacity(0.12), location: 0.35), .init(color: Theme.ink.opacity(0.85), location: 0.78), .init(color: Theme.ink, location: 1)], startPoint: .top, endPoint: .bottom)
            }.frame(width: geometry.size.width, height: geometry.size.height).clipped()
        }.allowsHitTesting(false).accessibilityHidden(true)
    }
}
struct MoviePoster: View {
    let entry: Entry
    var body: some View {
        ZStack {
            Theme.ink.opacity(0.45)
            AsyncImage(url: URL(string: entry.icon)) { phase in
                if let image = phase.image { image.resizable().scaledToFit() }
                else { Image(systemName: "film").font(.largeTitle).foregroundStyle(Theme.cyan.opacity(0.6)) }
            }
        }
    }
}
struct FilmBadges: View {
    let entry: Entry
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 7) {
                if !entry.year.isEmpty { badge(entry.year) }
                if !entry.rating.isEmpty { badge("★ " + entry.rating) }
                if let language = entry.language, !language.isEmpty { badge(language, accent: true) }
                if entry.action == "seasons" { badge("Serial") }
            }.padding(.vertical, 2)
        }
    }
    private func badge(_ value: String, accent: Bool = false) -> some View {
        Text(value).font(.system(size: 12, weight: .semibold)).foregroundStyle(accent ? Theme.cyan : .white)
            .padding(.horizontal, 10).padding(.vertical, 5)
            .background(Color.white.opacity(0.12), in: Capsule()).overlay(Capsule().stroke(.white.opacity(0.5)))
    }
}
struct CinemaView: View {
    @EnvironmentObject private var library: LibraryStore
    @Environment(\.scenePhase) private var scenePhase
    @State private var current = Entry(title: "Główna", action: "main")
    @State private var rows: [Entry] = []
    @State private var slides: [Entry] = []
    @State private var slideIndex = 0
    @State private var slideRevision = UUID()
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
    @State private var pageRevision = UUID()
    private let catalogue = Catalogue()
    private var activeSlide: Entry? { slides.indices.contains(slideIndex) ? slides[slideIndex] : nil }
    private var backdrop: String? { current.action == "main" ? activeSlide?.backdrop : current.backdrop }
    var body: some View {
        GeometryReader { geometry in
            let landscape = geometry.size.width > geometry.size.height
            ZStack(alignment: .top) {
                Theme.background.ignoresSafeArea()
                CinemaBackdrop(address: backdrop).frame(height: max(420, geometry.size.width * 9/16 + 200)).ignoresSafeArea(edges: .top)
                VStack(spacing: 8) {
                    header(compact: landscape)
                    navigation
                    CatalogueScrollView(revision: pageRevision) {
                        VStack(alignment: .leading, spacing: 20) {
                            if current.action == "main" { hero(width: geometry.size.width, landscape: landscape) }
                            else if current.action == "sources" || current.action == "seasons" || current.action == "episodes" {
                                pageDetails(landscape: landscape)
                            }
                            catalogueHeading
                            if rows.isEmpty && !busy { emptyState }
                            catalogueItems(width: geometry.size.width)
                        }.padding(.horizontal, landscape ? 24 : 18).padding(.bottom, 30)
                    }
                }
            }
        }
        .sheet(isPresented: $search) { searchSheet }
        .sheet(isPresented: $info) { about }
        .sheet(item: $selected) { entry in
            MovieDetails(entry: entry, catalogue: catalogue) { full in selected = nil; load(full) }.environmentObject(library)
        }
        .fullScreenCover(item: $playback) { request in
            SourcePlayer(request: request, catalogue: catalogue).environmentObject(library)
        }
        .alert("Nie udało się otworzyć", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
            Button("OK") { error = nil }
        } message: { Text(error ?? "") }
        .task { if rows.isEmpty && !busy { load(current, push: false) } }
        .task(id: slideRevision) { await rotateSlides() }
        .onDisappear { loadTask?.cancel() }
    }
    private func header(compact: Bool) -> some View {
        HStack(spacing: 10) {
            if !stack.isEmpty {
                Button(action: back) { Image(systemName: "chevron.left").frame(width: 44, height: 44) }.accessibilityLabel("Wróć")
            }
            Image("Brand").resizable().scaledToFit().frame(width: compact ? 30 : 38, height: compact ? 30 : 38).clipShape(RoundedRectangle(cornerRadius: 8))
            Text("MK KINO").font(.system(size: compact ? 17 : 21, weight: .bold))
            Spacer(minLength: 0)
            Text("1.1.0").font(.caption2).foregroundStyle(.white.opacity(0.6))
            optionsMenu
        }.foregroundStyle(.white).padding(.horizontal, 18).padding(.top, 4)
    }
    private var optionsMenu: some View {
        Menu {
            Button(library.tiles ? "Widok listy" : "Widok kafelków", systemImage: "square.grid.2x2") { library.tiles.toggle(); pageRevision = UUID() }
            Button("Odśwież", systemImage: "arrow.clockwise") { load(current, push: false) }
            Button("Autor i kontakt", systemImage: "info.circle") { info = true }
        } label: { Image(systemName: "ellipsis.circle").frame(width: 44, height: 44) }.accessibilityLabel("Opcje")
    }
    private var navigation: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                nav("Główna", action: "main", icon: "house.fill")
                nav("Filmy", action: "movies", icon: "film")
                nav("Seriale", action: "series", icon: "tv")
                Button { search = true } label: { Label("Szukaj", systemImage: "magnifyingglass").font(.system(size: 13, weight: .semibold)) }.buttonStyle(CinemaButtonStyle())
                nav("Ulubione", action: "favourites", icon: "heart")
                nav("Oglądaj dalej", action: "continue", icon: "play.circle")
                Button { info = true } label: { Text("Opcje").font(.system(size: 13, weight: .semibold)) }.buttonStyle(CinemaButtonStyle())
            }.padding(.horizontal, 18).padding(.vertical, 9)
        }.background(Theme.panel.opacity(0.35), in: Capsule()).padding(.horizontal, 10)
    }
    private func nav(_ title: String, action: String, icon: String) -> some View {
        Button { stack.removeAll(); load(Entry(title: title, action: action), push: false) } label: {
            Label(title, systemImage: icon).font(.system(size: 13, weight: .semibold))
        }.buttonStyle(CinemaButtonStyle(selected: current.action == action))
    }
    private func hero(width: CGFloat, landscape: Bool) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Spacer(minLength: landscape ? 18 : 80)
            if let entry = activeSlide {
                FilmBadges(entry: entry)
                Text(entry.title).font(.system(size: landscape ? 32 : 34, weight: .bold)).lineLimit(2).shadow(color: .black.opacity(0.7), radius: 2, y: 1)
                Text(entry.desc).font(.system(size: 15)).foregroundStyle(.white.opacity(0.9)).lineLimit(2)
                HStack(spacing: 10) {
                    Button { load(entry) } label: { Label("Oglądaj teraz", systemImage: "play.fill").font(.system(size: 14, weight: .semibold)) }.buttonStyle(CinemaButtonStyle(selected: true))
                    Button { selected = entry } label: { Text("Szczegóły").font(.system(size: 14, weight: .semibold)) }.buttonStyle(CinemaButtonStyle())
                }
            } else {
                Text("Filmy 2026").font(.system(size: 34, weight: .bold))
                Text(busy ? "Pobieranie panoram…" : "Filmy są dostępne poniżej. Brak szerokich zdjęć w aktualnie pobranym katalogu.").font(.subheadline).foregroundStyle(.white.opacity(0.8))
                Button("Odśwież") { load(current, push: false) }.buttonStyle(CinemaButtonStyle())
            }
            HStack {
                Spacer()
                Button { stepSlide(-1) } label: { Image(systemName: "chevron.left").frame(width: 44, height: 44) }.accessibilityLabel("Poprzedni film")
                Text(slides.isEmpty ? "00 / 00" : String(format: "%02d / %02d", slideIndex+1, slides.count)).font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.cyan).monospacedDigit()
                Button { stepSlide(1) } label: { Image(systemName: "chevron.right").frame(width: 44, height: 44) }.accessibilityLabel("Następny film")
            }.foregroundStyle(.white)
        }.frame(maxWidth: landscape ? width * 0.63 : .infinity, alignment: .leading)
            .frame(minHeight: landscape ? 250 : 400, alignment: .bottomLeading).padding(.bottom, 4)
    }
    private var catalogueHeading: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(current.action == "main" ? "Ostatnio dodane filmy · 2026" : current.action == "sources" ? "Wybierz hosting" : current.title).font(.title3.bold())
                Spacer()
                if busy { ProgressView() }
            }
            if current.action == "movies" || current.action == "page" {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        filter("Gatunek", action: "categories")
                        filter("Język", action: "versions")
                        filter("Rok", action: "years")
                    }.padding(.vertical, 3)
                }
            }
        }.foregroundStyle(.white)
    }
    private func filter(_ title: String, action: String) -> some View {
        Button { var entry = current; entry.title = title; entry.action = action; load(entry) } label: {
            Label(title, systemImage: "chevron.down").font(.system(size: 12, weight: .semibold))
        }.buttonStyle(CinemaButtonStyle())
    }
    @ViewBuilder private func catalogueItems(width: CGFloat) -> some View {
        if current.action == "main" {
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(alignment: .top, spacing: 15) {
                    ForEach(rows) { entry in card(entry).frame(width: width > 700 ? 155 : 140) }
                }.padding(.vertical, 7).padding(.horizontal, 3)
            }
        } else if library.tiles {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: current.action == "sources" ? 240 : 145), spacing: 14)], alignment: .leading, spacing: 20) {
                ForEach(rows) { card($0) }
            }.padding(.horizontal, 3)
        } else {
            LazyVStack(spacing: 12) { ForEach(rows) { listRow($0) } }
        }
    }
    private func card(_ entry: Entry) -> some View {
        Button { choose(entry) } label: {
            VStack(alignment: .leading, spacing: 9) {
                if entry.isTitle {
                    MoviePoster(entry: entry).aspectRatio(2/3, contentMode: .fit)
                        .overlay(alignment: .topLeading) {
                            if !entry.year.isEmpty {
                                Text(entry.year).font(.system(size: 12, weight: .bold)).padding(.horizontal, 8).padding(.vertical, 4)
                                    .background(.black.opacity(0.65), in: Capsule()).overlay(Capsule().stroke(.white.opacity(0.7))).padding(8)
                            }
                        }.clipShape(RoundedRectangle(cornerRadius: 17))
                } else {
                    Image(systemName: symbol(entry.action)).font(.system(size: entry.action == "page" ? 34 : 25)).foregroundStyle(Theme.cyan)
                        .frame(maxWidth: .infinity).frame(height: entry.action == "page" ? 140 : 56)
                }
                Text(entry.title).font(.system(size: 14, weight: .semibold)).lineLimit(2).frame(height: 36, alignment: .topLeading)
                if !entry.subtitle.isEmpty { Text(entry.subtitle).font(.system(size: 11)).foregroundStyle(Theme.cyan).lineLimit(1) }
            }.padding(entry.isTitle ? 7 : 14).frame(maxWidth: .infinity, alignment: .topLeading)
                .background(Theme.panel.opacity(0.55), in: RoundedRectangle(cornerRadius: 21))
                .overlay(RoundedRectangle(cornerRadius: 21).stroke(.white.opacity(0.45)))
        }.buttonStyle(PosterTouchStyle()).contextMenu {
            if entry.isTitle {
                Button(library.contains(entry) ? "Usuń z ulubionych" : "Dodaj do ulubionych", systemImage: "heart") { library.toggle(entry) }
            }
        }
    }
    private func listRow(_ entry: Entry) -> some View {
        Button { choose(entry) } label: {
            HStack(spacing: 14) {
                if entry.isTitle { MoviePoster(entry: entry).frame(width: 60, height: 90).clipShape(RoundedRectangle(cornerRadius: 10)) }
                VStack(alignment: .leading, spacing: 6) {
                    Text(entry.title).font(.headline).foregroundStyle(.white)
                    Text(entry.subtitle).font(.caption).foregroundStyle(Theme.cyan)
                }
                Spacer(); Image(systemName: "chevron.right").foregroundStyle(Theme.cyan)
            }.padding(12).frame(maxWidth: .infinity).background(Theme.panel.opacity(0.55), in: RoundedRectangle(cornerRadius: 18))
        }.buttonStyle(.plain)
    }
    private func pageDetails(landscape: Bool) -> some View {
        HStack(alignment: .top, spacing: 18) {
            if !current.icon.isEmpty { MoviePoster(entry: current).frame(width: landscape ? 105 : 85, height: landscape ? 158 : 128).clipShape(RoundedRectangle(cornerRadius: 14)) }
            VStack(alignment: .leading, spacing: 10) {
                FilmBadges(entry: current)
                Text(current.seriesTitle.isEmpty ? current.title : current.seriesTitle).font(.title2.bold()).foregroundStyle(.white)
                Text(current.desc).font(.system(size: 15)).foregroundStyle(.white.opacity(0.9)).fixedSize(horizontal: false, vertical: true)
            }
        }.padding(.top, 12)
    }
    private var emptyState: some View {
        VStack(spacing: 15) {
            Image(systemName: "film.stack").font(.largeTitle).foregroundStyle(Theme.cyan)
            Text(current.action == "continue" ? "Tutaj pojawią się rozpoczęte filmy." : current.action == "favourites" ? "Przytrzymaj okładkę, aby dodać film do ulubionych." : "Brak pozycji. Spróbuj odświeżyć katalog.").multilineTextAlignment(.center).foregroundStyle(.white.opacity(0.7))
        }.frame(maxWidth: .infinity).padding(30)
    }
    private var searchSheet: some View {
        NavigationStack {
            VStack(spacing: 20) {
                TextField("Tytuł filmu lub serialu", text: $query).textFieldStyle(.roundedBorder).submitLabel(.search).onSubmit { runSearch() }
                Button("Szukaj", action: runSearch).buttonStyle(CinemaButtonStyle(selected: true)).disabled(query.trimmingCharacters(in: .whitespaces).isEmpty)
                Spacer()
            }.padding(24).background(Theme.background).navigationTitle("Szukaj")
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Wróć") { search = false } } }
        }.presentationDetents([.medium, .large])
    }
    private var about: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Image("Brand").resizable().scaledToFit().frame(height: 110).frame(maxWidth: .infinity)
                    Text("MK Kino • iOS 1.1.0").font(.title2.bold())
                    Text("Wygląd wzorowany na MK Kino Android TV 0.6.5. Autor: MK.")
                    Link("bimer535@wp.pl", destination: URL(string: "mailto:bimer535@wp.pl")!)
                    Toggle("Widok kafelków", isOn: $library.tiles)
                    Button("Odśwież katalog") { info = false; load(current, push: false) }.buttonStyle(CinemaButtonStyle())
                    Text("Instaluj nowy plik IPA przez ten sam program i konto Apple co poprzednio. iOS nie instaluje aktualizacji samodzielnie z poziomu aplikacji.")
                    Text("Odtwarzanie przez WebKit; dostępność, jakość i napisy zależą od dostawcy. Ulubione i postęp są zapisane na urządzeniu.").font(.subheadline)
                    Text("GPL-3.0-only. Katalog MK eKino / epremki, SwiftSoup MIT. Szerokie zdjęcia pochodzą z publicznych metadanych PremiumSmart i TMDB; służą wyłącznie prezentacji filmów.").font(.caption).foregroundStyle(.secondary)
                }.padding(24)
            }.background(Theme.background).navigationTitle("Opcje")
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Gotowe") { info = false } } }
        }
    }
    private func symbol(_ action: String) -> String {
        switch action {
        case "categories", "movies": return "film"
        case "series", "seasons", "episodes": return "tv"
        case "continue": return "play.circle"
        case "favourites": return "heart"
        case "versions": return "waveform"
        case "years": return "calendar"
        case "play": return "play.fill"
        case "page": return "arrow.right.circle"
        default: return "square.grid.2x2"
        }
    }
    private func stepSlide(_ delta: Int) {
        guard !slides.isEmpty else { return }
        slideIndex = (slideIndex + delta + slides.count) % slides.count
        slideRevision = UUID()
    }
    @MainActor private func rotateSlides() async {
        while !Task.isCancelled {
            do { try await Task.sleep(nanoseconds: 5_000_000_000) } catch { return }
            guard current.action == "main", selected == nil, playback == nil, !search, !info, scenePhase == .active, slides.count > 1 else { continue }
            slideIndex = (slideIndex + 1) % slides.count
        }
    }
    private func choose(_ entry: Entry) {
        if entry.isTitle { selected = entry }
        else if entry.action == "play" {
            let parent = current
            let loadID = UUID(); activeLoad = loadID; loadTask?.cancel(); busy = true
            loadTask = Task { @MainActor in
                defer { if activeLoad == loadID { busy = false } }
                do {
                    let location = try await catalogue.playerURL(entry)
                    try Task.checkCancellation()
                    playback = PlaybackRequest(entry: parent, source: entry, url: location.url, resume: library.resume(parent), referer: location.referer)
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
        guard let last = stack.popLast() else { return }
        current = last.0; rows = last.1; pageRevision = UUID()
        if current.action == "main" { slides = CinemaArtwork.slides(rows); slideIndex = 0; slideRevision = UUID() }
    }
    private func load(_ entry: Entry, push: Bool = true) {
        loadTask?.cancel(); let loadID = UUID(); activeLoad = loadID; busy = true
        loadTask = Task { @MainActor in
            defer { if activeLoad == loadID { busy = false } }
            do {
                var next: [Entry]
                if entry.action == "main" { next = try await catalogue.homeFilms() }
                else if entry.action == "favourites" { next = library.favourites }
                else if entry.action == "continue" { next = library.records.filter { !$0.complete && $0.seconds > 10 }.map(\.entry) }
                else { next = try await catalogue.browse(entry) }
                try Task.checkCancellation()
                if push { stack.append((current, rows)) }
                var full = entry
                if entry.isTitle, let first = next.first, !first.desc.isEmpty { full.desc = first.desc }
                current = full; rows = next; pageRevision = UUID()
                if entry.action == "main" { slides = CinemaArtwork.slides(next); slideIndex = 0; slideRevision = UUID() }
            } catch { if !Task.isCancelled { self.error = error.localizedDescription } }
        }
    }
}
struct PosterTouchStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.overlay(RoundedRectangle(cornerRadius: 21).stroke(Theme.cyan.opacity(configuration.isPressed ? 1 : 0), lineWidth: 2))
            .shadow(color: Theme.cyan.opacity(configuration.isPressed ? 0.65 : 0), radius: 8)
    }
}
struct MovieDetails: View {
    @EnvironmentObject private var library: LibraryStore
    @Environment(\.dismiss) private var dismiss
    let entry: Entry
    let catalogue: Catalogue
    let watch: (Entry) -> Void
    @State private var full: Entry?
    @State private var descriptionError = false
    private var movie: Entry { full ?? entry }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    HStack(alignment: .top, spacing: 18) {
                        MoviePoster(entry: movie).frame(width: 110, height: 165).clipShape(RoundedRectangle(cornerRadius: 15))
                        VStack(alignment: .leading, spacing: 12) {
                            FilmBadges(entry: movie)
                            Text(movie.title).font(.title2.bold()).fixedSize(horizontal: false, vertical: true)
                            Button { watch(movie) } label: {
                                Label(movie.action == "seasons" ? "Wybierz sezon" : "Oglądaj teraz", systemImage: "play.fill").font(.system(size: 14, weight: .semibold))
                            }.buttonStyle(CinemaButtonStyle(selected: true))
                        }
                    }
                    Button { library.toggle(movie) } label: { Label(library.contains(movie) ? "Usuń z ulubionych" : "Dodaj do ulubionych", systemImage: library.contains(movie) ? "heart.fill" : "heart") }.buttonStyle(CinemaButtonStyle())
                    Text("Opis").font(.headline)
                    Text(movie.desc.isEmpty ? "Opis nie jest dostępny w katalogu." : movie.desc).font(.body).foregroundStyle(.white.opacity(0.9)).fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
                    if descriptionError { Text("Nie udało się pobrać pełnego opisu. Wyświetlono opis z katalogu.").font(.caption).foregroundStyle(.secondary) }
                }.padding(22)
            }.background { ZStack { Theme.background; CinemaBackdrop(address: movie.backdrop) } }
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Wróć") { dismiss() } } }
        }.task(id: entry.id) {
            do { let details = try await catalogue.details(entry); try Task.checkCancellation(); full = details }
            catch { if !Task.isCancelled { descriptionError = true } }
        }
    }
}
