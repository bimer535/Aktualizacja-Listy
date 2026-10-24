// SPDX-License-Identifier: GPL-3.0-only
import UIKit
import WebKit

// Dialog completions must run exactly once, including teardown and cancellation.
@MainActor final class ProviderDialogs {
    private var pending: [UUID: () -> Void] = [:]
    @discardableResult func insert(_ cancel: @escaping () -> Void) -> UUID {
        let id = UUID(); pending[id] = cancel; return id
    }
    func finish(_ id: UUID, accepted: (() -> Void)? = nil) {
        guard let cancel = pending.removeValue(forKey: id) else { return }
        if let accepted { accepted() } else { cancel() }
    }
    func cancelAll() {
        let callbacks = Array(pending.values); pending.removeAll()
        callbacks.forEach { $0() }
    }
}
enum ProviderNavigation {
    static func permits(_ url: URL?) -> Bool {
        // window.open() may first create an empty about:blank context.
        guard let url else { return true }
        guard url.user == nil, url.password == nil else { return false }
        switch url.scheme?.lowercased() {
        case "https": return url.host != nil
        case "about": return ["about:blank", "about:srcdoc"].contains(url.absoluteString.lowercased())
        case "blob": return url.absoluteString.lowercased().hasPrefix("blob:https://")
        default: return false
        }
    }
}
/// Only the selected provider and its catalogue wrapper may replace the player
/// or open a visible auxiliary window. Resource/subframe loads are unaffected.
struct ProviderNavigationPolicy {
    let hosts: Set<String>
    init(player: URL, source: String, referer: String) {
        hosts = Set([player.host, URL(string: source)?.host, URL(string: referer)?.host]
            .compactMap { $0?.lowercased() })
    }
    func trustedHost(_ host: String?) -> Bool {
        guard let host = host?.lowercased() else { return false }
        return hosts.contains { host == $0 || host.hasSuffix("." + $0) }
    }
    func permitsTopLevel(_ url: URL?) -> Bool {
        guard let url, ProviderNavigation.permits(url) else { return false }
        if url.scheme?.lowercased() == "https" { return trustedHost(url.host) }
        if url.scheme?.lowercased() == "blob" {
            return trustedHost(URL(string: String(url.absoluteString.dropFirst(5)))?.host)
        }
        return ["about:blank", "about:srcdoc"].contains(url.absoluteString.lowercased())
    }
    func permitsPopup(_ url: URL?) -> Bool {
        // Empty/blank popups are commonly opened before their advertising
        // destination is assigned. Do not display an unclassified window.
        guard let url, url.scheme?.lowercased() == "https" else { return false }
        return ProviderNavigation.permits(url) && trustedHost(url.host)
    }
}
@MainActor final class ProviderWindowController: UIViewController {
    let browser: WKWebView
    var onClose: (() -> Void)?
    private var closed = false
    init(configuration: WKWebViewConfiguration, address: URL?) {
        browser = WKWebView(frame: .zero, configuration: configuration)
        super.init(nibName: nil, bundle: nil)
        title = address?.host.map { "Strona: " + $0 } ?? "Okno źródła"
        isModalInPresentation = true
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black; browser.isOpaque = false; browser.backgroundColor = .black
        browser.translatesAutoresizingMaskIntoConstraints = false; view.addSubview(browser)
        NSLayoutConstraint.activate([
            browser.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            browser.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            browser.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            browser.trailingAnchor.constraint(equalTo: view.trailingAnchor)
        ])
        navigationItem.rightBarButtonItem = UIBarButtonItem(title: "Zamknij okno", style: .done, target: self, action: #selector(closeWindow))
    }
    @objc func closeWindow() {
        guard !closed else { return }; closed = true
        onClose?(); navigationController?.dismiss(animated: true)
    }
    func shutdown() {
        browser.evaluateJavaScript("document.querySelectorAll('video').forEach(v=>v.pause())", completionHandler: nil)
        browser.stopLoading(); browser.navigationDelegate = nil; browser.uiDelegate = nil
        // The child and parent share userContentController; its handlers belong to
        // the parent and must not be removed while the parent is still playing.
        browser.loadHTMLString("", baseURL: nil)
    }
}

/// A playback request touches only video elements with media already attached.
/// It does not click overlays, verification controls, or advertising elements.
enum ProviderPlaybackScript {
    static let start = """
    (()=>{
      let started=0;
      document.querySelectorAll('video').forEach(v=>{
        if(v.currentSrc && v.readyState>0 && v.paused && !v.ended){
          try { const result=v.play(); if(result && result.catch)result.catch(()=>{}); started++; } catch(_){}
        }
      });
      return started;
    })()
    """
}
