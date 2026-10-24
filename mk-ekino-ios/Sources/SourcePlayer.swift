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
    var referer = ""
}
@MainActor final class PlayerState: ObservableObject {
    @Published var loading = true
    @Published var message = "Uruchamianie odtwarzacza źródłowego…"
    @Published var failed = false
    @Published var confirmed = false
    weak var webView: WKWebView?
    func startVideo() {
        webView?.evaluateJavaScript("window.postMessage({mkVideoAction:'play'}, '*')", completionHandler: nil)
    }
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
            if !state.confirmed {
                Button { state.startVideo() } label: { Label("Odtwórz wideo", systemImage: "play.fill").frame(minHeight: 44) }
            }
            if state.loading { ProgressView().frame(height: 24) }
            if !state.confirmed {
                Text(state.message).font(.caption).foregroundStyle(state.failed ? .orange : .secondary).lineLimit(3).padding(.horizontal, 12).frame(maxWidth: .infinity).frame(height: 66)
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
            let location = try await catalogue.playerURL(source)
            state.loading = true; state.confirmed = false; state.failed = false
            state.message = "Uruchamianie następnego odcinka…"
            request = PlaybackRequest(entry: entry, source: source, url: location.url, resume: library.resume(entry), referer: location.referer)
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
        config.allowsInlineMediaPlayback = true
        config.allowsAirPlayForMediaPlayback = true
        config.allowsPictureInPictureMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        config.preferences.javaScriptCanOpenWindowsAutomatically = false
        config.userContentController.add(context.coordinator, name: "mkProgress")
        let start = request.resume.isFinite ? max(0, request.resume) : 0
        let script = """
        (()=>{
          const reportUI=event=>window.webkit.messageHandlers.mkProgress.postMessage({event});
          document.addEventListener('click',e=>{if(e.isTrusted)reportUI('tap');},true);
          window.addEventListener('unhandledrejection',()=>reportUI('script_failure'));
          window.addEventListener('error',e=>{if(e.error)reportUI('script_failure');});
          const startVideo=()=>{ \(ProviderPlaybackScript.start); };
          window.addEventListener('message',e=>{
            if(e.data && e.data.mkVideoAction==='play'){
              startVideo(); document.querySelectorAll('iframe').forEach(f=>{try{f.contentWindow.postMessage({mkVideoAction:'play'},'*');}catch(_){}});
            }
          });
          let playbackStarted=false;
          document.addEventListener('click',e=>{if(e.isTrusted && !playbackStarted)startVideo();},false);
          const seen=new WeakSet();const attach=()=>{document.querySelectorAll('video').forEach(v=>{
          if(seen.has(v))return;seen.add(v);v.setAttribute('playsinline','');v.setAttribute('webkit-playsinline','');
          v.addEventListener('playing',()=>{playbackStarted=true;});let last=0;let sought=false;
          const resume=()=>{if(!sought && v.duration>0){sought=true;const n=\(start);if(n>10&&n<v.duration-15){try{v.currentTime=n;}catch(e){}}}};
          v.addEventListener('loadedmetadata',resume);resume();
          (\(ProviderPlaybackScript.autoStart))(v,startVideo);
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
        initial.setValue(request.referer.isEmpty ? request.source.url : request.referer, forHTTPHeaderField: "Referer")
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
        coordinator.stop()
        view.evaluateJavaScript("document.querySelectorAll('video').forEach(v=>v.pause())", completionHandler: nil)
        view.stopLoading(); view.loadHTMLString("", baseURL: nil)
        view.configuration.userContentController.removeScriptMessageHandler(forName: "mkProgress")
        view.navigationDelegate = nil; view.uiDelegate = nil
    }
    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
        var parent: PlayerWebView
        var active = true
        var popups: [ProviderWindowController] = []
        let dialogs = ProviderDialogs()
        let navigationPolicy: ProviderNavigationPolicy
        init(_ parent: PlayerWebView) {
            self.parent = parent
            navigationPolicy = ProviderNavigationPolicy(player: parent.request.url, source: parent.request.source.url, referer: parent.request.referer)
        }
        func blockedExternalWindow() {
            guard active else { return }
            parent.state.message = "Zablokowano dodatkowe okno spoza źródła filmu. Naciśnij ▶ w odtwarzaczu, aby kontynuować."
        }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            guard active else { return }
            parent.state.loading = false
            if popups.isEmpty { parent.state.message = "Naciśnij ▶ w odtwarzaczu źródłowym. Jeśli po kliknięciu nic nie rusza, sprawdź komunikat poniżej lub wybierz inne źródło." }
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
            guard active, ProviderNavigation.permits(navigationAction.request.url) else { decisionHandler(.cancel); return }
            if navigationAction.targetFrame?.isMainFrame != false,
               !navigationPolicy.permitsTopLevel(navigationAction.request.url) {
                decisionHandler(.cancel)
                blockedExternalWindow()
                if let popup = popups.first(where: { $0.browser === webView }) {
                    DispatchQueue.main.async { popup.closeWindow() }
                }
                return
            }
            decisionHandler(.allow)
        }
        func stop() {
            active = false
            dialogs.cancelAll()
            for popup in popups.reversed() { popup.shutdown(); popup.navigationController?.dismiss(animated: false) }
            popups.removeAll()
        }
        func presenter(for webView: WKWebView) -> UIViewController? {
            var controller = webView.window?.rootViewController
            while let next = controller?.presentedViewController, !next.isBeingDismissed { controller = next }
            return controller
        }
        func openPopup(configuration: WKWebViewConfiguration, address: URL?, presenter: UIViewController) -> WKWebView? {
            guard active else { return nil }
            guard navigationPolicy.permitsPopup(address) else { blockedExternalWindow(); return nil }
            guard popups.isEmpty, !(presenter is UIAlertController) else { return nil }
            // The supplied configuration keeps window.opener, cookies and process pool.
            let popup = ProviderWindowController(configuration: configuration, address: address)
            popup.browser.navigationDelegate = self; popup.browser.uiDelegate = self
            popup.onClose = { [weak self, weak popup] in
                guard let self, let popup else { return }
                popup.shutdown(); self.popups.removeAll { $0 === popup }
                if self.active { self.parent.state.message = "Wrócono do odtwarzacza. Jeśli film nie ruszył, naciśnij ponownie ▶." }
            }
            popups.append(popup)
            parent.state.message = "Źródło otworzyło dodatkowe okno. Po zakończeniu wróć przyciskiem Zamknij okno."
            let navigation = UINavigationController(rootViewController: popup)
            navigation.isModalInPresentation = true
            presenter.present(navigation, animated: true)
            return popup.browser
        }
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            guard let host = presenter(for: webView) else { return nil }
            return openPopup(configuration: configuration, address: navigationAction.request.url, presenter: host)
        }
        func webViewDidClose(_ webView: WKWebView) {
            guard let popup = popups.first(where: { $0.browser === webView }) else { return }
            popup.closeWindow()
        }
        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            guard active, let presenter = presenter(for: webView), !(presenter is UIAlertController) else { completionHandler(); return }
            let id = dialogs.insert { completionHandler() }
            let alert = UIAlertController(title: "Komunikat strony: " + (frame.request.url?.host ?? "źródło"), message: String(message.prefix(1000)), preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default) { [weak self] _ in self?.dialogs.finish(id) })
            presenter.present(alert, animated: true)
        }
        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            guard active, let presenter = presenter(for: webView), !(presenter is UIAlertController) else { completionHandler(false); return }
            let id = dialogs.insert { completionHandler(false) }
            let alert = UIAlertController(title: "Pytanie strony: " + (frame.request.url?.host ?? "źródło"), message: String(message.prefix(1000)), preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "Anuluj", style: .cancel) { [weak self] _ in self?.dialogs.finish(id) })
            alert.addAction(UIAlertAction(title: "OK", style: .default) { [weak self] _ in self?.dialogs.finish(id, accepted: { completionHandler(true) }) })
            presenter.present(alert, animated: true)
        }
        func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
            guard active, let presenter = presenter(for: webView), !(presenter is UIAlertController) else { completionHandler(nil); return }
            let id = dialogs.insert { completionHandler(nil) }
            let alert = UIAlertController(title: "Pole strony: " + (frame.request.url?.host ?? "źródło"), message: String(prompt.prefix(1000)), preferredStyle: .alert)
            alert.addTextField { $0.text = defaultText }
            alert.addAction(UIAlertAction(title: "Anuluj", style: .cancel) { [weak self] _ in self?.dialogs.finish(id) })
            alert.addAction(UIAlertAction(title: "OK", style: .default) { [weak self, weak alert] _ in self?.dialogs.finish(id, accepted: { completionHandler(alert?.textFields?.first?.text) }) })
            presenter.present(alert, animated: true)
        }
        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard active, let value = message.body as? [String: Any] else { return }
            if let event = value["event"] as? String, !parent.state.confirmed {
                if event == "tap" {
                    parent.state.message = "Dotknięcie odebrane przez stronę. Oczekiwanie na uruchomienie wideo…"
                    DispatchQueue.main.asyncAfter(deadline: .now() + 15) { [weak self] in
                        guard let self, self.active, !self.parent.state.confirmed, self.popups.isEmpty, !self.parent.state.failed else { return }
                        self.parent.state.message = "Źródło odebrało dotknięcie, ale nie uruchomiło wideo. Spróbuj innego źródła (VOE/Mix) lub ponów."
                    }
                } else if event == "script_failure" {
                    parent.state.message = "Strona źródła zgłosiła błąd skryptu. Jeśli film nie ruszy, wybierz VOE albo Mix."
                }
                return
            }
            if value["error"] as? Bool == true { failed(CatalogueError.message("Źródło zgłosiło błąd wideo. Wróć i wybierz inne źródło.")); return }
            guard let seconds = value["seconds"] as? Double, let duration = value["duration"] as? Double,
                  seconds.isFinite, duration.isFinite, seconds >= 0, duration > 0 else { return }
            parent.record(seconds, duration)
            if value["playing"] as? Bool == true { parent.state.confirmed = true; parent.state.loading = false }
        }
    }
}

