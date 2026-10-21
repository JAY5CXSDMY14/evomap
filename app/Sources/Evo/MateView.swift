#if os(macOS)
import AppKit
import SwiftUI
import WebKit
import EvoCore

// 表情角色：调度球（默认）/ 云宝 / 亮亮，跑 aora-bot 的表情引擎（Resources/vendor，版权见 vendor/NOTICE.md）。
// 透明 WKWebView 读本地宿主页 Resources/mate/index.html，不联网（规则表挡掉所有 http/https）。
// Swift 调 evoMate.set(编号, 撒花)、evoMate.look(x, y, 眼睛放大)、evoMate.blink(连眨)。
// v0.5.0「灵动」：表情交给引擎画，身体的呼吸 / 点击挤压回弹 / 状态弹跳 / 很近时一缩，以及眼睛跟鼠标的弹簧，
// 全部是 SwiftUI 原生弹簧（.spring / .interpolatingSpring）；目标值由 EvoCore 的 EyeFollow / MateMotion 算。

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
        // WebKit 的规则不支持「|」，一种协议一条
        let json = #"[{"trigger":{"url-filter":"^https?://"},"action":{"type":"block"}},{"trigger":{"url-filter":"^wss?://"},"action":{"type":"block"}},{"trigger":{"url-filter":"^ftp://"},"action":{"type":"block"}}]"#
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
            lastLook = ""
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

    /// 鼠标相对角色中心的位置（点，y 向下为正）；nil = 窗口不可见。由 SwiftUI 那边换算成注视目标。
    var onPointer: ((CGPoint?) -> Void)?
    private var globalMonitor: Any?
    private var lastLook = ""

    private func updateMonitor() {
        stopTracking()
        guard followMouse, !still, let w = window else { return }
        w.acceptsMouseMovedEvents = true
        // 本应用窗口里的移动走本地监听；鼠标在别的应用上方时走全局监听（鼠标移动不需要辅助功能权限）
        monitor = NSEvent.addLocalMonitorForEvents(matching: [.mouseMoved, .leftMouseDragged]) { [weak self] e in
            self?.track()
            return e
        }
        globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.mouseMoved, .leftMouseDragged]) { [weak self] _ in
            Task { @MainActor in self?.track() }
        }
        track()
    }

    private func track() {
        guard let w = window, Date().timeIntervalSince(lastGaze) > 1.0 / 60 else { return }
        lastGaze = Date()
        guard w.isVisible, w.occlusionState.contains(.visible) else { onPointer?(nil); return }
        let c = w.convertToScreen(convert(NSRect(x: bounds.midX, y: bounds.midY, width: 0, height: 0), to: nil)).origin
        let p = NSEvent.mouseLocation          // 屏幕坐标，y 向上
        onPointer?(CGPoint(x: p.x - c.x, y: c.y - p.y))
    }

    /// SwiftUI 弹簧每一帧的当前值 → 宿主页（相同就不发）。
    func look(_ x: Double, _ y: Double, boost: Double) {
        guard ready, !still else { return }
        let js = MateBridge.look(x, y, boost: boost)
        guard js != lastLook else { return }
        lastLook = js
        evaluateJavaScript(js, completionHandler: nil)
    }

    func blink(double: Bool) {
        guard ready, !still else { return }
        evaluateJavaScript(MateBridge.blink(double: double), completionHandler: nil)
    }

    func stopTracking() {
        if let m = monitor { NSEvent.removeMonitor(m); monitor = nil }
        if let m = globalMonitor { NSEvent.removeMonitor(m); globalMonitor = nil }
    }
}

struct MateWebRep: NSViewRepresentable {
    var character: MateCharacter
    var emotion: MateEmotion
    var celebrate: Int
    var size: CGFloat
    var still: Bool
    var followMouse: Bool
    var gazeX: Double = 0
    var gazeY: Double = 0
    var eyeBoost: Double = 1
    var blinkTick: Int = 0
    var onPointer: ((CGPoint?) -> Void)? = nil

    final class Coordinator { var celebrate = 0; var emotion: MateEmotion?; var blinkTick = 0 }
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> MateWebView {
        let w = MateWebView.make()
        w.load(character: character, emotion: emotion, size: size, still: still)
        w.onPointer = onPointer
        w.followMouse = followMouse
        context.coordinator.celebrate = celebrate
        context.coordinator.emotion = emotion
        context.coordinator.blinkTick = blinkTick
        return w
    }

    func updateNSView(_ w: MateWebView, context: Context) {
        w.load(character: character, emotion: emotion, size: size, still: still)
        w.onPointer = onPointer
        if w.followMouse != followMouse { w.followMouse = followMouse }
        w.look(gazeX, gazeY, boost: eyeBoost)
        let co = context.coordinator
        if co.blinkTick != blinkTick {
            co.blinkTick = blinkTick
            w.blink(double: MateMotion.doubleBlink(Double.random(in: 0..<1)))
        }
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

/// 把 SwiftUI 弹簧插出来的每一帧注视值交给 WKWebView（Animatable：动画期间每帧都会带着中间值重新算 body）。
struct MateLiveRep: View, Animatable {
    var rep: MateWebRep
    var gazeX: Double
    var gazeY: Double
    var eyeBoost: Double

    var animatableData: AnimatablePair<AnimatablePair<Double, Double>, Double> {
        get { AnimatablePair(AnimatablePair(gazeX, gazeY), eyeBoost) }
        set { gazeX = newValue.first.first; gazeY = newValue.first.second; eyeBoost = newValue.second }
    }

    var body: some View {
        var r = rep
        r.gazeX = gazeX; r.gazeY = gazeY; r.eyeBoost = eyeBoost
        return r
    }
}

/// 给 CI 演示看「眼睛真的在跟」：最近一次注视目标（UIProbe 写进几何 JSON 的 mate-gaze）。
enum MateGazeProbe {
    static var last: EyeFollow.Result = .rest
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

    // 眼睛：SwiftUI 弹簧追 EyeFollow 算出的目标
    @State private var gazeX = 0.0
    @State private var gazeY = 0.0
    @State private var eyeBoost = 1.0
    @State private var target = EyeFollow.Result.rest
    // 身体
    @State private var breathIn = false
    @State private var squash = CGSize(width: 1, height: 1)
    @State private var hop: CGFloat = 0
    @State private var tilt: Double = 0
    @State private var pressed = false
    @State private var isNear = false
    @State private var blinkTick = 0
    @State private var lastEmotion: MateEmotion?

    private var still: Bool { reduceMotion || forceStill }
    /// 小号实例（列表里的 26～30 点）不呼吸不弹，省得一屏都在动。
    private var lively: Bool { !still && size >= 40 }

    /// 眼睛跟随：偏「QQ 弹」的弹簧——响应快、有一点过冲。
    static let eyeSpring = Animation.interpolatingSpring(stiffness: 170, damping: 13)
    /// 回正：稍慢、更软。
    static let eyeHome = Animation.interpolatingSpring(stiffness: 90, damping: 9)
    static let squashSpring = Animation.spring(response: 0.22, dampingFraction: 0.42)
    static let releaseSpring = Animation.spring(response: 0.42, dampingFraction: 0.36)
    static let hopUp = Animation.spring(response: 0.20, dampingFraction: 0.7)
    static let hopDown = Animation.interpolatingSpring(stiffness: 210, damping: 9)

    var body: some View {
        let ch = MateCharacter.from(characterRaw)
        Group {
            if isStatic {
                MateStill(character: ch, emotion: emotion, size: size)
            } else {
                MateLiveRep(rep: MateWebRep(character: ch, emotion: emotion, celebrate: celebrate, size: size,
                                            still: still, followMouse: followMouse && !still,
                                            blinkTick: blinkTick, onPointer: { p in pointer(p) }),
                            gazeX: gazeX, gazeY: gazeY, eyeBoost: eyeBoost)
                    // 身体：呼吸（底部为锚，像坐着的软球）× 挤压 × 很近时一缩，再加跳和晃
                    .scaleEffect(x: bodyScaleX, y: bodyScaleY, anchor: .bottom)
                    .rotationEffect(.degrees(tilt), anchor: .bottom)
                    .offset(y: hop)
            }
        }
        .frame(width: size, height: size)
        .contentShape(Circle())
        .simultaneousGesture(pressGesture)
        .task(id: lively) { await liveLoop() }
        .onChange(of: emotion) { e in kick(to: e) }
        .onAppear { lastEmotion = emotion }
        .accessibilityElement()
        .accessibilityLabel("\(ch.label)：\(emotion.name)")
    }

    private var bodyScaleX: CGFloat {
        let breath = lively ? (breathIn ? 1 - MateMotion.breathScale * 0.5 : 1 + MateMotion.breathScale * 0.3) : 1
        let near = isNear && lively ? MateMotion.nearShrink + (1 - MateMotion.nearShrink) * 0.4 : 1
        return CGFloat(breath * near) * squash.width
    }
    private var bodyScaleY: CGFloat {
        let breath = lively ? (breathIn ? 1 + MateMotion.breathScale : 1 - MateMotion.breathScale * 0.4) : 1
        let near = isNear && lively ? MateMotion.nearShrink : 1
        return CGFloat(breath * near) * squash.height
    }

    // MARK: 鼠标 → 眼睛

    private func pointer(_ p: CGPoint?) {
        let r = EyeFollow.compute(center: (0, 0), diameter: Double(size), pointer: p.map { (Double($0.x), Double($0.y)) })
        guard EyeFollow.changedEnough(r, target) else { return }
        let wasNear = target.near
        target = r
        if followMouse { MateGazeProbe.last = r }
        guard !still else { return }
        withAnimation(r.inRange ? Self.eyeSpring : Self.eyeHome) {
            gazeX = r.x; gazeY = r.y
            eyeBoost = r.near ? MateMotion.nearEyeBoost : 1
        }
        if r.near != wasNear, lively {
            // 很近：身体轻轻一缩；离开再弹回
            withAnimation(Self.squashSpring) { isNear = r.near }
            if r.near { blinkTick += 1 }
        }
    }

    // MARK: 待机：呼吸 + 随机眨眼

    @MainActor private func liveLoop() async {
        guard lively else { return }
        var nextBlink = Date().addingTimeInterval(MateMotion.nextBlink(Double.random(in: 0..<1)))
        while !Task.isCancelled {
            withAnimation(.spring(response: MateMotion.breathSeconds, dampingFraction: 0.82)) { breathIn.toggle() }
            try? await Task.sleep(nanoseconds: UInt64(MateMotion.breathSeconds * 1_000_000_000))
            if Date() >= nextBlink {
                blinkTick += 1
                nextBlink = Date().addingTimeInterval(MateMotion.nextBlink(Double.random(in: 0..<1)))
            }
        }
    }

    // MARK: 点一下：压扁 → 弹过头 → 回来

    private var pressGesture: some Gesture {
        DragGesture(minimumDistance: 0)
            .onChanged { _ in
                guard lively, !pressed else { return }
                pressed = true
                withAnimation(Self.squashSpring) {
                    squash = CGSize(width: MateMotion.pressSquash.x, height: MateMotion.pressSquash.y)
                }
            }
            .onEnded { _ in
                guard lively else { return }
                pressed = false
                withAnimation(Self.releaseSpring) {
                    squash = CGSize(width: MateMotion.releaseStretch.x, height: MateMotion.releaseStretch.y)
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.13) {
                    withAnimation(Self.releaseSpring) { squash = CGSize(width: 1, height: 1) }
                }
                blinkTick += 1
            }
    }

    // MARK: 状态变化：弹一下

    private func kick(to e: MateEmotion) {
        let k = MateMotion.kick(from: lastEmotion, to: e)
        lastEmotion = e
        guard lively else { return }
        let unit = Double(size) / 58
        func later(_ s: Double, _ a: Animation, _ f: @escaping () -> Void) {
            DispatchQueue.main.asyncAfter(deadline: .now() + s) { withAnimation(a) { f() } }
        }
        switch k {
        case .none:
            return
        case .hop(let h):
            withAnimation(Self.squashSpring) { squash = CGSize(width: 1.10, height: 0.88) }
            later(0.10, Self.hopUp) { hop = -CGFloat(h * unit); squash = CGSize(width: 0.93, height: 1.10) }
            later(0.30, Self.hopDown) { hop = 0; squash = CGSize(width: 1.06, height: 0.94) }
            later(0.48, Self.releaseSpring) { squash = CGSize(width: 1, height: 1) }
        case .perk:
            withAnimation(Self.squashSpring) { squash = CGSize(width: 0.92, height: 1.10) }
            later(0.16, Self.releaseSpring) { squash = CGSize(width: 1, height: 1) }
        case .shake:
            withAnimation(.spring(response: 0.12, dampingFraction: 0.5)) { tilt = -9 }
            later(0.10, .spring(response: 0.12, dampingFraction: 0.5)) { tilt = 8 }
            later(0.20, .spring(response: 0.12, dampingFraction: 0.5)) { tilt = -5 }
            later(0.30, .interpolatingSpring(stiffness: 160, damping: 8)) { tilt = 0 }
        case .sink:
            withAnimation(.spring(response: 0.5, dampingFraction: 0.8)) { squash = CGSize(width: 1.07, height: 0.92) }
            later(0.55, .spring(response: 0.8, dampingFraction: 0.85)) { squash = CGSize(width: 1, height: 1) }
        case .nod:
            withAnimation(Self.squashSpring) { hop = CGFloat(2.5 * unit); squash = CGSize(width: 1.04, height: 0.96) }
            later(0.14, Self.releaseSpring) { hop = 0; squash = CGSize(width: 1, height: 1) }
        }
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
