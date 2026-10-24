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
