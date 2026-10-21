#if os(macOS)
import AppKit
import SwiftUI
import WebKit
import EvoCore

// 表情角色：球球（默认）/ 云宝 / 亮亮，跑 aora-bot 的表情引擎（Resources/vendor，版权见 vendor/NOTICE.md）。
// 透明 WKWebView 读本地宿主页 Resources/mate/index.html，不联网（规则表挡掉所有 http/https）。
// Swift 只调两个函数：evoMate.set(编号, 撒花) 和 evoMate.gaze(x, y)。

/// 宿主页和引擎文件在哪：打包后在 Evo.app/Contents/Resources/{mate,vendor}；`swift run` / make snapshots 时在 app/Resources。
enum MateAssets {
    static var resourcesRoot: URL? {
        let fm = FileManager.default
        if let r = Bundle.main.resourceURL, fm.fileExists(atPath: r.appendingPathComponent("mate/index.html").path) { return r }
        let dev = URL(fileURLWithPath: fm.currentDirectoryPath).appendingPathComponent("Resources")
        if fm.fileExists(atPath: dev.appendingPathComponent("mate/index.html").path) { return dev }
        let up = URL(fileURLWithPath: fm.currentDirectoryPath).appendingPathComponent("app/Resources")
        return fm.fileExists(atPath: up.appendingPathComponent("mate/index.html").path) ? up : nil
    }

    static func url(character: MateCharacter, emotion: MateEmotion, size: CGFloat, still: Bool) -> URL? {
        guard let root = resourcesRoot else { return nil }
        let q = MateBridge.query(character: character, emotion: emotion, size: Double(size), still: still)
        return URL(string: root.appendingPathComponent("mate/index.html").absoluteString + "?" + q)
    }

    /// 挡掉一切网络请求（宿主页和引擎本来就不联网，这里再加一道保险）。
    static var rules: WKContentRuleList?
    static func prepareRules() {
        guard rules == nil else { return }
        let json = #"[{"trigger":{"url-filter":"^(https?|wss?|ftp)://"},"action":{"type":"block"}}]"#
        WKContentRuleListStore.default()?.compileContentRuleList(forIdentifier: "evo-mate-offline", encodedContentRuleList: json) { list, err in
            if let err { NSLog("Evo 表情：规则表编译失败 \(err.localizedDescription)") }
            Task { @MainActor in MateAssets.rules = list }
        }
    }

    static var character: MateCharacter { MateCharacter.from(UserDefaults.standard.string(forKey: "mateCharacter")) }
}

/// JS → Swift 的消息转发（弱引用，免得 WKUserContentController 把协调器留住）。
final class MateMessageProxy: NSObject, WKScriptMessageHandler {
    weak var target: MateWebView?
    init(_ t: MateWebView) { target = t }
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        let body = m.body as? String ?? ""
        let t = target
        Task { @MainActor in t?.received(body) }
    }
}

/// 一个角色实例。不接鼠标点击（点击穿透给下面的 SwiftUI），但会跟着窗口里的鼠标转眼睛。
@MainActor
final class MateWebView: WKWebView, WKNavigationDelegate {
    var onReady: (() -> Void)?
    private(set) var ready = false
    private var desired: (MateEmotion, Bool)?
    private var loadedKey = ""
    private var monitor: Any?
    private var lastGaze = Date.distantPast
    var followMouse = false { didSet { updateMonitor() } }
    var still = false

    static func make() -> MateWebView {
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .nonPersistent()
        if let r = MateAssets.rules { cfg.userContentController.add(r) }
        let w = MateWebView(frame: NSRect(x: 0, y: 0, width: 64, height: 64), configuration: cfg)
        w.configuration.userContentController.add(MateMessageProxy(w), name: "evo")
        w.setValue(false, forKey: "drawsBackground")
        w.underPageBackgroundColor = .clear
        w.navigationDelegate = w
        w.allowsMagnification = false
        w.setAccessibilityElement(false)
        return w
    }

    /// 角色、静态与否、尺寸档变了才重新加载；表情变化走 JS。
    func load(character: MateCharacter, emotion: MateEmotion, size: CGFloat, still: Bool) {
        let key = "\(character.rawValue)|\(still)|\(size < 40 ? "s" : (size < 80 ? "m" : "l"))"
        guard key != loadedKey else { return }
        loadedKey = key
        self.still = still
        ready = false
        desired = (emotion, false)
        guard let url = MateAssets.url(character: character, emotion: emotion, size: size, still: still),
              let root = MateAssets.resourcesRoot else { return }
        loadFileURL(url, allowingReadAccessTo: root)
    }

    func set(_ e: MateEmotion, celebrate: Bool) {
        desired = (e, celebrate)
        guard ready else { return }
        evaluateJavaScript(MateBridge.set(e, celebrate: celebrate), completionHandler: nil)
    }

    func received(_ body: String) {
        if body == "ready" {
            ready = true
            if let d = desired { evaluateJavaScript(MateBridge.set(d.0, celebrate: d.1), completionHandler: nil) }
            onReady?()
        } else if body.hasPrefix("error") {
            NSLog("Evo 表情：\(body)")
        }
    }

    // 只放行本地文件
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction) async -> WKNavigationActionPolicy {
        action.request.url?.isFileURL == true || action.request.url?.scheme == "about" ? .allow : .cancel
    }

    override func hitTest(_ point: NSPoint) -> NSView? { nil }
    override var acceptsFirstResponder: Bool { false }
    override func scrollWheel(with event: NSEvent) { nextResponder?.scrollWheel(with: event) }

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        updateMonitor()
    }

    private func updateMonitor() {
        if let m = monitor { NSEvent.removeMonitor(m); monitor = nil }
        guard followMouse, !still, let w = window else { return }
        w.acceptsMouseMovedEvents = true
        monitor = NSEvent.addLocalMonitorForEvents(matching: [.mouseMoved, .leftMouseDragged]) { [weak self] e in
            self?.track(e)
            return e
        }
    }

    private func track(_ e: NSEvent) {
        guard ready, let w = window, e.window === w, Date().timeIntervalSince(lastGaze) > 1.0 / 30 else { return }
        lastGaze = Date()
        let c = convert(NSPoint(x: bounds.midX, y: bounds.midY), to: nil)
        let p = e.locationInWindow
        let (x, y) = MateBridge.gazeVector(dx: Double(p.x - c.x), dy: Double(c.y - p.y))
        evaluateJavaScript(MateBridge.gaze(x, y), completionHandler: nil)
    }

    func stopTracking() { if let m = monitor { NSEvent.removeMonitor(m); monitor = nil } }
}

struct MateWebRep: NSViewRepresentable {
    var character: MateCharacter
    var emotion: MateEmotion
    var celebrate: Int
    var size: CGFloat
    var still: Bool
    var followMouse: Bool

    final class Coordinator { var celebrate = 0; var emotion: MateEmotion? }
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> MateWebView {
        let w = MateWebView.make()
        w.load(character: character, emotion: emotion, size: size, still: still)
        w.followMouse = followMouse
        context.coordinator.celebrate = celebrate
        context.coordinator.emotion = emotion
        return w
    }

    func updateNSView(_ w: MateWebView, context: Context) {
        w.load(character: character, emotion: emotion, size: size, still: still)
        if w.followMouse != followMouse { w.followMouse = followMouse }
        let co = context.coordinator
        let burst = celebrate != co.celebrate
        if burst || co.emotion != emotion {
            co.celebrate = celebrate; co.emotion = emotion
            w.set(emotion, celebrate: burst)
        }
    }

    static func dismantleNSView(_ w: MateWebView, coordinator: Coordinator) {
        w.stopTracking()
        w.configuration.userContentController.removeScriptMessageHandler(forName: "evo")
    }
}

/// 界面里用这个。截图（ImageRenderer 画不了 WKWebView）时换成预先拍好的静态图。
struct MateView: View {
    var emotion: MateEmotion
    var celebrate: Int = 0
    var size: CGFloat = 48
    var followMouse = false
    var forceStill = false
    @AppStorage("mateCharacter") private var characterRaw = MateCharacter.default.rawValue
    @Environment(\.evoStatic) private var isStatic
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let ch = MateCharacter.from(characterRaw)
        Group {
            if isStatic {
                MateStill(character: ch, emotion: emotion, size: size)
            } else {
                MateWebRep(character: ch, emotion: emotion, celebrate: celebrate, size: size,
                           still: reduceMotion || forceStill, followMouse: followMouse)
            }
        }
        .frame(width: size, height: size)
        .accessibilityElement()
        .accessibilityLabel("\(ch.label)：\(emotion.name)")
    }
}

/// 静态一帧：先找拍好的图，没有就退回旧的矢量小陶。
struct MateStill: View {
    var character: MateCharacter
    var emotion: MateEmotion
    var size: CGFloat
    var body: some View {
        if let img = MateSnapshotCache.shared.image(character, emotion) {
            Image(nsImage: img).resizable().interpolation(.high).aspectRatio(contentMode: .fit)
        } else {
            EvoMascot(mood: Self.fallbackMood(emotion), size: size * 0.9)
        }
    }

    static func fallbackMood(_ e: MateEmotion) -> MascotMood {
        switch e {
        case .sleep: return .sleepy
        case .error: return .worried
        case .listening, .curious: return .waiting
        case .thinking, .busy, .searching, .received: return .working
        default: return .idle
        }
    }
}

/// 截图模式和 Dock 图标用：在屏幕外的小窗里把每个表情拍成透明 PNG。
@MainActor
final class MateSnapshotCache {
    static let shared = MateSnapshotCache()
    private var images: [String: NSImage] = [:]
    private var window: NSWindow?

    func image(_ c: MateCharacter, _ e: MateEmotion) -> NSImage? { images["\(c.rawValue)/\(e.id)"] }

    func prepare(_ c: MateCharacter, _ emotions: [MateEmotion], side: CGFloat = 200) async {
        for e in emotions where image(c, e) == nil {
            if let img = await shoot(c, e, side: side) { images["\(c.rawValue)/\(e.id)"] = img }
        }
        window?.orderOut(nil)
    }

    private func shoot(_ c: MateCharacter, _ e: MateEmotion, side: CGFloat) async -> NSImage? {
        guard MateAssets.resourcesRoot != nil else { return nil }
        let w = window ?? {
            let w = NSWindow(contentRect: NSRect(x: -4000, y: -4000, width: side, height: side),
                             styleMask: [.borderless], backing: .buffered, defer: false)
            w.isOpaque = false; w.backgroundColor = .clear; w.hasShadow = false
            w.isReleasedWhenClosed = false
            return w
        }()
        window = w
        let web = MateWebView.make()
        web.frame = NSRect(x: 0, y: 0, width: side, height: side)
        w.contentView = web
        w.setFrameOrigin(NSPoint(x: -4000, y: -4000))
        w.orderFrontRegardless()
        let once = OnceFlag()
        let ok: Bool = await withCheckedContinuation { cont in
            web.onReady = { if once.take() { cont.resume(returning: true) } }
            DispatchQueue.main.asyncAfter(deadline: .now() + 8) { if once.take() { cont.resume(returning: false) } }
            web.load(character: c, emotion: e, size: side, still: true)
        }
        guard ok else { NSLog("Evo 表情：\(c.rawValue) \(e.id) 没拍成（宿主页没回 ready）"); return nil }
        try? await Task.sleep(nanoseconds: 350_000_000)
        return await withCheckedContinuation { cont in
            let cfg = WKSnapshotConfiguration()
            cfg.afterScreenUpdates = true
            web.takeSnapshot(with: cfg) { img, err in
                if let err { NSLog("Evo 表情：截图失败 \(err.localizedDescription)") }
                cont.resume(returning: img)
            }
        }
    }
}

/// 只放行第一次（续体只能 resume 一次）。
final class OnceFlag: @unchecked Sendable {
    private let lock = NSLock()
    private var done = false
    func take() -> Bool { lock.lock(); defer { lock.unlock() }; if done { return false }; done = true; return true }
}

/// 设置 / 截图里的一排表情。
struct MateSheet: View {
    var character: MateCharacter
    static let shown: [MateEmotion] = [.standby, .thinking, .listening, .done, .error, .sleep, .wake]
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("\(character.label)的表情").font(Theme.title(17)).foregroundStyle(Theme.textPrimary)
            HStack(alignment: .bottom, spacing: 12) {
                ForEach(Self.shown, id: \.self) { e in
                    VStack(spacing: 6) {
                        MateView(emotion: e, size: 64)
                        Text(e.name).font(Theme.caption(11.5)).foregroundStyle(Theme.textSecondary)
                        Text(e.id).font(.system(size: 10, design: .monospaced)).foregroundStyle(Theme.textSecondary.opacity(0.7))
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            Text("顺利→待机 02 · 施工→思考 30 · 等你→等待输入 35 · 通过/合并→任务完成 33 · 卡住→出错 34 · 暂停/免打扰→睡眠 00 · 启动→唤醒 01")
                .font(Theme.caption()).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
        }
        .padding(20)
    }
}
#endif
