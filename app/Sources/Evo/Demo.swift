#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

// 给 CI 录屏用的两样东西，平时完全不起作用：
// 1) EVO_UITEST_GEOMETRY=<文件>：把带 .uiProbe("名字") 的控件在屏幕上的位置（左上角原点，和 cliclick 一样）
//    每 0.3 秒写成 JSON，外面的脚本据此用真鼠标点（cliclick c:x,y）。
// 2) EVO_DEMO=1：没有辅助功能权限、外面点不了的时候，应用自己按 DemoScript 的顺序演一遍，
//    每步用 screencapture 拍全屏（EVO_DEMO_SHOTS=<目录>）。

@MainActor
enum UIProbe {
    nonisolated static let path: String? = ProcessInfo.processInfo.environment["EVO_UITEST_GEOMETRY"]
    nonisolated static var enabled: Bool { path != nil }
    private static var views: [String: WeakView] = [:]
    private static var timer: Timer?

    final class WeakView { weak var view: NSView?; init(_ v: NSView) { view = v } }

    static func register(_ name: String, _ v: NSView) {
        views[name] = WeakView(v)
    }

    static func start() {
        guard enabled, timer == nil else { return }
        timer = Timer.scheduledTimer(withTimeInterval: 0.3, repeats: true) { _ in
            Task { @MainActor in UIProbe.write() }
        }
    }

    static func cgRect(_ r: NSRect) -> [String: Double] {
        let h = Double(NSScreen.screens.first?.frame.height ?? 0)
        let x = Double(r.minX), y = h - Double(r.maxY)
        return ["x": x, "y": y, "w": Double(r.width), "h": Double(r.height),
                "cx": (x + Double(r.width) / 2).rounded(), "cy": (y + Double(r.height) / 2).rounded()]
    }

    static func write() {
        guard let path else { return }
        var out: [String: Any] = [:]
        for (name, wv) in views {
            guard let v = wv.view, let w = v.window, w.isVisible, !v.isHiddenOrHasHiddenAncestor else { continue }
            let r = w.convertToScreen(v.convert(v.bounds, to: nil))
            guard r.width > 1, r.height > 1 else { continue }
            var d = cgRect(r)
            d["key"] = w.isKeyWindow ? 1 : 0
            out[name] = d
        }
        // 闸门卡按显示顺序起别名：win-gate-0-approve 永远是眼前第一张（探点按卡片 id 注册，卡片飞走后顺序会变）
        let st = AppState.shared
        for (prefix, list) in [("win-gate", st.windowCards), ("pop-gate", Array(st.cards.prefix(WindowSizing.popoverCards)))] {
            for (i, c) in list.enumerated() {
                for sfx in ["approve", "reject", "send", "timeline"] {
                    if let v = out["\(prefix)-\(c.id)-\(sfx)"] { out["\(prefix)-\(i)-\(sfx)"] = v }
                }
            }
        }
        if let b = MenuWindow.statusButton(), let w = b.window {
            out["status-item"] = cgRect(w.convertToScreen(b.convert(b.bounds, to: nil)))
        }
        if let w = MainWindowController.shared.window, w.isVisible { out["main-window"] = cgRect(w.frame) }
        if let s = NSScreen.screens.first { out["screen"] = ["w": Double(s.frame.width), "h": Double(s.frame.height)] }
        out["selection"] = String(describing: AppState.shared.windowSelection ?? .inbox)
        out["cards"] = AppState.shared.allCards.count
        out["active"] = NSApp.isActive ? 1 : 0
        let g = MateGazeProbe.last
        out["mate-gaze"] = ["x": (g.x * 100).rounded() / 100, "y": (g.y * 100).rounded() / 100,
                            "inRange": g.inRange ? 1 : 0, "near": g.near ? 1 : 0,
                            "distance": g.distance.isFinite ? g.distance.rounded() : -1,
                            "events": MateGazeProbe.events,
                            "reduceMotion": NSWorkspace.shared.accessibilityDisplayShouldReduceMotion ? 1 : 0,
                            "forceMotion": MateGazeProbe.forceMotion ? 1 : 0]
        out["dark"] = NSApp.effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? 1 : 0
        if let data = try? JSONSerialization.data(withJSONObject: out, options: [.sortedKeys, .prettyPrinted]) {
            try? data.write(to: URL(fileURLWithPath: path), options: .atomic)
        }
    }
}

final class ProbeNSView: NSView {
    var name = ""
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        let n = name, me = self
        Task { @MainActor in if !n.isEmpty { UIProbe.register(n, me) } }
    }
}

struct ProbeTag: NSViewRepresentable {
    let name: String
    func makeNSView(context: Context) -> ProbeNSView {
        let v = ProbeNSView(); v.name = name
        return v
    }
    func updateNSView(_ v: ProbeNSView, context: Context) {
        if v.name != name { v.name = name }
        if v.window != nil { UIProbe.register(name, v) }
    }
}

struct ProbeModifier: ViewModifier {
    let name: String?
    @ViewBuilder func body(content: Content) -> some View {
        if let name, UIProbe.enabled { content.background(ProbeTag(name: name)) } else { content }
    }
}

extension View {
    /// 给 UI 测试脚本标一个点位（只在 EVO_UITEST_GEOMETRY 设了时生效）。
    func uiProbe(_ name: String?) -> some View { modifier(ProbeModifier(name: name)) }
}

extension MenuWindow {
    static func statusButton() -> NSStatusBarButton? {
        for w in NSApp.windows where String(describing: type(of: w)).contains("NSStatusBarWindow") {
            if let b = findStatusButton(w.contentView) { return b }
        }
        return nil
    }

    private static func findStatusButton(_ v: NSView?) -> NSStatusBarButton? {
        guard let v else { return nil }
        if let b = v as? NSStatusBarButton { return b }
        for s in v.subviews { if let b = findStatusButton(s) { return b } }
        return nil
    }
}

// MARK: - 应用自己演（EVO_DEMO=1）

@MainActor
enum DemoRunner {
    static var enabled: Bool { ProcessInfo.processInfo.environment["EVO_DEMO"] == "1" }
    static var shotsDir: String? { ProcessInfo.processInfo.environment["EVO_DEMO_SHOTS"] }

    static func start() {
        guard enabled else { return }
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 5_000_000_000)     // 等第一轮 status 读完
            for step in DemoScript.steps {
                perform(step)
                let p = DemoScript.pause(after: step)
                try? await Task.sleep(nanoseconds: UInt64(p * 0.55 * 1_000_000_000))
                shoot(step)
                try? await Task.sleep(nanoseconds: UInt64(p * 0.45 * 1_000_000_000))
            }
            if let d = shotsDir { try? "done\n".write(toFile: d + "/DONE", atomically: true, encoding: .utf8) }
        }
    }

    static func perform(_ s: DemoScript.Step) {
        let st = AppState.shared
        switch s {
        case .desktop, .done: break
        case .popover, .popoverDark: MenuWindow.show()
        case .openWindow: MainWindowController.shared.show()
        case .approve:
            if let c = st.allCards.first { withAnimation(Motion.or(Motion.pop)) { st.approve(c) } }
        case .rejectWords:
            if let c = st.allCards.first(where: { $0.rejectAsksWords && !st.hiddenGates.contains($0.id) }) {
                st.demoReject = (c.id, "手机上按钮太挤，再大一圈")
            }
        case .rejectSend:
            if let d = st.demoReject, let c = st.card(id: d.id) {
                withAnimation(Motion.or(Motion.pop)) { st.reject(c, words: d.words) }
            }
            st.demoReject = nil
        case .project:
            if let c = st.rows.first(where: { ($0.building + $0.verifying + $0.waiting) > 0 })?.code ?? st.codes.first {
                withAnimation(Motion.or(Motion.softSpring)) { st.windowSelection = .project(c) }
            }
        case .item:
            if case .project(let c) = st.windowSelection ?? .inbox, let k = st.snapshot(c)?.doc?.items.first?.key {
                withAnimation(Motion.or(Motion.softSpring)) { st.windowSelection = .item(project: c, key: k) }
            }
        case .team:
            withAnimation(Motion.or(Motion.softSpring)) { st.windowSelection = .team }
        case .pluginPage:
            if let pg = st.plugins?.sidebarPages.first {
                withAnimation(Motion.or(Motion.softSpring)) { st.windowSelection = .plugin(pg.plugin, pg.id) }
            }
        case .pluginCommand:
            _ = st.send(mode: .feedback, project: st.codes.first ?? "", text: "/hello 老板", look: false)
        case .palette:
            PaletteController.shared.show()
            PaletteController.shared.model.query = "深色"
        case .dark:
            PaletteController.shared.runSelected()
        case .composer:
            withAnimation(Motion.or(Motion.softSpring)) { st.windowSelection = .inbox }
            MainWindowController.shared.show()
            _ = st.send(mode: .feedback, project: st.codes.first ?? "", text: "注册页在手机上按钮太挤了", look: false)
        }
    }

    static func shoot(_ s: DemoScript.Step) {
        guard let d = shotsDir else { return }
        try? FileManager.default.createDirectory(atPath: d, withIntermediateDirectories: true)
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
        p.arguments = ["-x", "-C", d + "/" + DemoScript.shotName(s)]
        try? p.run()
    }
}
#endif
