// SPDX-License-Identifier: GPL-3.0-only
import SwiftUI
import WebKit
import AVFoundation

struct PlaybackRequest: Identifiable {
    let id = UUID()
    var entry: Entry
    var source: Entry
    var url: URL
    var resume: Double
}
@MainActor final class PlayerState: ObservableObject {
    @Published var loading = true
    @Published var message = "Uruchamianie odtwarzacza źródłowego…"
    @Published var failed = false
    @Published var confirmed = false
    weak var webView: WKWebView?
    func retry() { failed = false; loading = true; webView?.reload() }
}
struct SourcePlayer: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var library: LibraryStore
    @StateObject private var state = PlayerState()
    @State var request: PlaybackRequest
    let catalogue: Catalogue
    @State private var nextBusy = false
    @State private var nextSources: [Entry] = []
    @State private var nextEntry: Entry?
    @State private var showNext = false
    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Button { dismiss() } label: { Label("Wróć", systemImage: "chevron.left").frame(minHeight: 44) }
                VStack(alignment: .leading) { Text(request.entry.title).font(.headline).lineLimit(1); Text(request.source.provider.capitalized).font(.caption).foregroundStyle(Theme.cyan) }
                Spacer()
                if !request.entry.seriesURL.isEmpty {
                    Button { Task { await nextEpisode() } } label: { Image(systemName: "forward.end.fill").frame(width: 44, height: 44) }.disabled(nextBusy).accessibilityLabel("Następny odcinek")
                }
                Button { state.retry() } label: { Image(systemName: "arrow.clockwise").frame(width: 44, height: 44) }.accessibilityLabel("Ponów")
            }.padding(.horizontal, 14).background(Theme.panel)
            if state.loading { ProgressView().padding(10) }
            if !state.confirmed {
                Text(state.message).font(.caption).foregroundStyle(state.failed ? .orange : .secondary).padding(12).frame(maxWidth: .infinity)
            }
            PlayerWebView(request: request, state: state) { seconds, duration in library.record(request.entry, seconds: seconds, duration: duration) }.id(request.id)
        }.background(.black).preferredColorScheme(.dark)
        .task {
            try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback)
            try? AVAudioSession.sharedInstance().setActive(true)
        }
        .onDisappear { state.webView?.stopLoading(); state.webView?.evaluateJavaScript("document.querySelectorAll('video').forEach(v=>v.pause())", completionHandler: nil) }
        .confirmationDialog("Następny odcinek — wybierz źródło", isPresented: $showNext, titleVisibility: .visible) {
            ForEach(nextSources) { source in Button(source.title) { Task { await playNext(source) } } }
            Button("Anuluj", role: .cancel) {}
        }
    }
    private func nextEpisode() async {
        nextBusy = true; defer { nextBusy = false }
        do {
            guard let next = try await catalogue.nextEpisode(request.entry) else { state.message = "Brak następnego odcinka w katalogu."; state.confirmed = false; return }
            nextEntry = next; nextSources = try await catalogue.browse(next)
            if nextSources.isEmpty { state.message = "Brak źródeł następnego odcinka."; state.confirmed = false }
            else { showNext = true }
        } catch { state.message = error.localizedDescription; state.confirmed = false }
    }
    private func playNext(_ source: Entry) async {
        nextBusy = true; defer { nextBusy = false }
        do {
            guard let entry = nextEntry else { return }
            let url = try await catalogue.playerURL(source)
            state.loading = true; state.confirmed = false; state.failed = false
            state.message = "Uruchamianie następnego odcinka…"
            request = PlaybackRequest(entry: entry, source: source, url: url, resume: library.resume(entry))
        } catch { state.message = error.localizedDescription; state.confirmed = false }
    }
}
struct PlayerWebView: UIViewRepresentable {
    let request: PlaybackRequest
    @ObservedObject var state: PlayerState
    let record: (Double, Double) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        config.allowsInlineMediaPlayback = false
        config.allowsAirPlayForMediaPlayback = true
        config.allowsPictureInPictureMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        config.userContentController.add(context.coordinator, name: "mkProgress")
        let start = request.resume.isFinite ? max(0, request.resume) : 0
        let script = """
        (()=>{const seen=new WeakSet();const attach=()=>{document.querySelectorAll('video').forEach(v=>{
          if(seen.has(v))return;seen.add(v);let last=0;let sought=false;
          const resume=()=>{if(!sought && v.duration>0){sought=true;const n=\(start);if(n>10&&n<v.duration-15){try{v.currentTime=n;}catch(e){}}}};
          v.addEventListener('loadedmetadata',resume);resume();
          const report=(force=false)=>{const now=Date.now();if(!force&&now-last<5000)return;last=now;
            if(Number.isFinite(v.currentTime)&&Number.isFinite(v.duration)&&v.duration>0){
              window.webkit.messageHandlers.mkProgress.postMessage({seconds:v.currentTime,duration:v.duration,playing:!v.paused});}};
          v.addEventListener('timeupdate',()=>report());v.addEventListener('pause',()=>report(true));
          v.addEventListener('ended',()=>report(true));v.addEventListener('playing',()=>report(true));
          v.addEventListener('error',()=>window.webkit.messageHandlers.mkProgress.postMessage({error:true}));
        });};attach();new MutationObserver(attach).observe(document.documentElement,{childList:true,subtree:true});})();
        """
        config.userContentController.addUserScript(WKUserScript(source: script, injectionTime: .atDocumentEnd, forMainFrameOnly: false))
        let view = WKWebView(frame: .zero, configuration: config)
        view.isOpaque = false; view.backgroundColor = .black
        view.navigationDelegate = context.coordinator; view.uiDelegate = context.coordinator
        view.scrollView.backgroundColor = .black
        state.webView = view
        var initial = URLRequest(url: request.url)
        initial.setValue(request.source.url, forHTTPHeaderField: "Referer")
        // Transfer catalogue cookies before the first player request.
        let cookies = HTTPCookieStorage.shared.cookies ?? []
        Task { @MainActor [weak view] in
            guard let view else { return }
            for cookie in cookies { await view.configuration.websiteDataStore.httpCookieStore.setCookie(cookie) }
            guard context.coordinator.active else { return }
            view.load(initial)
        }
        return view
    }
    func updateUIView(_ view: WKWebView, context: Context) {}
    static func dismantleUIView(_ view: WKWebView, coordinator: Coordinator) {
        coordinator.active = false
        view.evaluateJavaScript("document.querySelectorAll('video').forEach(v=>v.pause())", completionHandler: nil)
        view.stopLoading(); view.loadHTMLString("", baseURL: nil)
        view.configuration.userContentController.removeScriptMessageHandler(forName: "mkProgress")
        view.navigationDelegate = nil; view.uiDelegate = nil
    }
    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
        var parent: PlayerWebView
        var active = true
        init(_ parent: PlayerWebView) { self.parent = parent }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            guard active else { return }
            parent.state.loading = false
            parent.state.message = "Jeśli film nie ruszył, naciśnij ▶ w odtwarzaczu. Jakość i napisy wybierzesz w jego ustawieniach."
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { failed(error) }
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { failed(error) }
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            failed(CatalogueError.message("Odtwarzacz został zatrzymany przez system. Naciśnij Ponów lub wybierz inne źródło."))
        }
        private func failed(_ error: Error) {
            guard active, (error as NSError).code != NSURLErrorCancelled else { return }
            parent.state.loading = false; parent.state.failed = true; parent.state.confirmed = false; parent.state.message = error.localizedDescription
        }
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard active, let url = navigationAction.request.url, ["https", "about", "blob"].contains(url.scheme ?? "") else { decisionHandler(.cancel); return }
            decisionHandler(.allow)
        }
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            // Unsolicited pop-up windows are not opened. Provider media stays in its frame.
            return nil
        }
        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard active, let value = message.body as? [String: Any] else { return }
            if value["error"] as? Bool == true { failed(CatalogueError.message("Źródło zgłosiło błąd wideo. Wróć i wybierz inne źródło.")); return }
            guard let seconds = value["seconds"] as? Double, let duration = value["duration"] as? Double,
                  seconds.isFinite, duration.isFinite, seconds >= 0, duration > 0 else { return }
            parent.record(seconds, duration)
            if value["playing"] as? Bool == true { parent.state.confirmed = true; parent.state.loading = false }
        }
    }
}
