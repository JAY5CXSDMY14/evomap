#if os(macOS)
import Foundation
import AppKit
import WebKit
import Security
import EvoCore

/// 面板口令：和 kit/bin/evo 的 panel_token() 同一处（钥匙串 evoloop-panel / evo → ~/.evoloop/panel.token）。
enum PanelAuth {
    static let service = "evoloop-panel", account = "evo"

    static func token() async -> String? {
        // 1) /usr/bin/security：口令是 evo 用这个工具存的，钥匙串对它不弹授权框
        let r = await Shell.run("/usr/bin/security", ["find-generic-password", "-a", account, "-s", service, "-w"], timeout: 10)
        let t = r.out.trimmingCharacters(in: .whitespacesAndNewlines)
        if r.ok, !t.isEmpty { return t }
        // 2) Security.framework（别的工具存的条目会弹一次「Evo 想使用钥匙串」，点「始终允许」）
        if let t = keychainRead() { return t }
        // 3) 文件兜底（没有钥匙串时 evo 存这里，权限 600）
        let f = EvoEnv.evoRoot.appendingPathComponent("panel.token")
        if let s = try? String(contentsOf: f, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines), !s.isEmpty { return s }
        // 4) 都没有：让 evo 生成一个（--show-token 没有就生成并存进钥匙串）
        let g = await Shell.evo(["panel", "--show-token"], timeout: 30)
        return PanelToken.parseShowToken(g.out)
    }

    static func keychainRead() -> String? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                kSecAttrAccount as String: account, kSecReturnData as String: true,
                                kSecMatchLimit as String: kSecMatchLimitOne]
        var out: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        let s = String(decoding: d, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
        return s.isEmpty ? nil : s
    }
}

/// 「打开面板」：没在跑就由应用起一个 `evo panel --port N`（应用退出时一起关掉），然后用 WKWebView 打开。
@MainActor
final class PanelController: NSObject, WKNavigationDelegate, NSWindowDelegate {
    static let shared = PanelController()

    private var window: NSWindow?
    private var web: WKWebView?
    private var ownedPanel: Process?
    private var opening = false

    var port: Int {
        let p = UserDefaults.standard.integer(forKey: "panelPort")
        return (1...65535).contains(p) ? p : 8765
    }
    var baseURL: URL { URL(string: "http://127.0.0.1:\(port)/")! }

    var isBeingWatched: Bool { (window?.isVisible ?? false) && (window?.isKeyWindow ?? false) && NSApp.isActive }

    enum Probe { case ok, unauthorized, down }

    nonisolated static func probe(_ base: URL, token: String) async -> Probe {
        var req = URLRequest(url: base.appendingPathComponent("api/projects"), timeoutInterval: 2)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        do {
            let (_, resp) = try await URLSession.shared.data(for: req)
            switch (resp as? HTTPURLResponse)?.statusCode {
            case 200: return .ok
            case 401: return .unauthorized
            default: return .down
            }
        } catch { return .down }
    }

    func open() {
        showWindow()
        guard !opening else { return }
        opening = true
        Task {
            defer { opening = false }
            message("正在连接面板 \(baseURL.absoluteString) …")
            guard let token = await PanelAuth.token() else {
                return message("拿不到面板口令。终端里跑一次 evo panel --show-token 看看。", error: true)
            }
            var st = await Self.probe(baseURL, token: token)
            if st == .down {
                if let err = startPanel() { return message(err, error: true) }
                for _ in 0..<20 where st == .down {
                    try? await Task.sleep(nanoseconds: 400_000_000)
                    st = await Self.probe(baseURL, token: token)
                }
            }
            switch st {
            case .down:
                message("面板没起来（端口 \(port)）。日志：~/.evoloop/logs/app-panel.log；端口被占就在设置里换一个。", error: true)
            case .unauthorized:
                message("端口 \(port) 上的面板不认这个口令（可能是别的口令起的旧进程）。关掉它或换端口再试。", error: true)
            case .ok:
                await load(token: token)
            }
        }
    }

    /// 起一个 evo panel 子进程；返回错误文字或 nil。
    private func startPanel() -> String? {
        if let p = ownedPanel, p.isRunning { return nil }
        guard let py = EvoEnv.python else { return "找不到 python3" }
        guard let script = EvoEnv.evoScript else { return "找不到 evo" }
        let logs = EvoEnv.evoRoot.appendingPathComponent("logs")
        try? FileManager.default.createDirectory(at: logs, withIntermediateDirectories: true)
        let logURL = logs.appendingPathComponent("app-panel.log")
        if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil) }
        let log = try? FileHandle(forWritingTo: logURL)
        log?.seekToEndOfFile()
        let p = Process()
        p.executableURL = URL(fileURLWithPath: py)
        p.arguments = [script, "panel", "--host", "127.0.0.1", "--port", String(port)]
        p.environment = EvoEnv.environment
        p.standardOutput = log ?? FileHandle.nullDevice
        p.standardError = log ?? FileHandle.nullDevice
        p.standardInput = FileHandle.nullDevice
        do { try p.run() } catch { return "evo panel 起不来：\(error.localizedDescription)" }
        ownedPanel = p
        return nil
    }

    func stopOwnedPanel() {
        if let p = ownedPanel, p.isRunning { p.terminate() }
        ownedPanel = nil
    }

    private func showWindow() {
        if window == nil {
            let cfg = WKWebViewConfiguration()
            cfg.websiteDataStore = .default()
            let w = WKWebView(frame: NSRect(x: 0, y: 0, width: 1100, height: 760), configuration: cfg)
            w.navigationDelegate = self
            w.allowsBackForwardNavigationGestures = true
            let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 760),
                               styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
            win.title = "Evo 面板"
            win.isReleasedWhenClosed = false
            win.contentView = w
            win.delegate = self
            win.center()
            win.setFrameAutosaveName("Evo.panel")
            window = win; web = w
        }
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    /// 先放 cookie（面板网页里的 fetch 靠它），首个请求再带 Bearer。
    private func load(token: String) async {
        guard let web else { return }
        var props: [HTTPCookiePropertyKey: Any] = [.domain: "127.0.0.1", .path: "/", .name: "evo_panel", .value: token]
        props[.expires] = Date().addingTimeInterval(30 * 24 * 3600)
        let url = baseURL
        guard let cookie = HTTPCookie(properties: props) else { return }
        await web.configuration.websiteDataStore.httpCookieStore.setCookie(cookie)
        var req = URLRequest(url: url)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        web.load(req)
    }

    func reload() { web?.reload() }

    private func message(_ text: String, error: Bool = false) {
        let esc = text.replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;")
        let color = error ? "#c0392b" : "#555"
        web?.loadHTMLString("""
        <html><body style="font:15px -apple-system,'PingFang SC',sans-serif;background:#f6f5f2;display:flex;\
        height:100vh;align-items:center;justify-content:center;margin:0"><div style="max-width:520px;color:\(color)">\(esc)</div></body></html>
        """, baseURL: nil)
    }

    // 面板之外的链接（GitHub issue 等）交给默认浏览器
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction) async -> WKNavigationActionPolicy {
        if let u = navigationAction.request.url, let host = u.host, host != "127.0.0.1", host != "localhost",
           u.scheme == "http" || u.scheme == "https" {
            NSWorkspace.shared.open(u)
            return .cancel
        }
        return .allow
    }
}
#endif
