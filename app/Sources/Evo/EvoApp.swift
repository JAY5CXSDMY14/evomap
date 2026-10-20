#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

struct EvoApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @ObservedObject private var state = AppState.shared

    var body: some Scene {
        MenuBarExtra {
            MenuContent(state: state)
        } label: {
            MenuBarLabel(state: state)
        }
        .menuBarExtraStyle(.menu)
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        Notifier.shared.setup()
        AppState.shared.start()
        if !UserDefaults.standard.bool(forKey: "setupDone") { WindowManager.shared.showSetup() }
    }

    func applicationWillTerminate(_ notification: Notification) {
        PanelController.shared.stopOwnedPanel()
    }

    // 关掉最后一个窗口不退出：菜单栏应用常驻
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
}

/// 菜单栏图标：SF Symbol + 等你件数。接棒器停了换成警告图标，暂停时换暂停图标。
struct MenuBarLabel: View {
    @ObservedObject var state: AppState

    var symbol: String {
        if state.anyStale { return "exclamationmark.triangle" }
        if state.loopRunning == false { return "pause.circle" }
        return "arrow.triangle.2.circlepath"
    }

    var body: some View {
        if let t = Badge.text(state.badge) {
            Text("\(Image(systemName: symbol)) \(t)")
        } else {
            Image(systemName: symbol)
        }
    }
}

struct MenuContent: View {
    @ObservedObject var state: AppState

    private static let timeFmt: DateFormatter = {
        let f = DateFormatter(); f.dateFormat = "HH:mm:ss"; return f
    }()

    var body: some View {
        if let e = state.globalError {
            Text(e)
            Button("首次设置向导…") { WindowManager.shared.showSetup() }
        } else if state.snaps.isEmpty {
            Text(state.lastRefresh == nil ? "正在读取…" : "还没有项目（evo new / evo import）")
        }
        ForEach(state.snaps, id: \.code) { s in
            if let d = s.doc, !d.gates.isEmpty {
                Menu(Badge.menuLine(s)) {
                    ForEach(d.gates, id: \.id) { g in
                        Button("\(g.kindLabel)：\(g.question ?? g.id)") { PanelController.shared.open() }
                    }
                }
            } else {
                Text(Badge.menuLine(s))
            }
        }
        Divider()
        Button("打开面板") { PanelController.shared.open() }
            .keyboardShortcut("o")
        Button("立即 tick") { state.tickNow() }
            .disabled(state.busy != nil || state.snaps.isEmpty)
        if state.loopRunning != nil {
            Button(state.loopRunning == false ? "恢复循环" : "暂停循环") { state.togglePause() }
                .disabled(state.busy != nil)
        } else {
            Text("暂停/恢复：没装 launchd 常驻")
        }
        Menu(state.anyStale ? "看门狗状态 🔴" : "看门狗状态") {
            if state.beats.isEmpty { Text("（还没有心跳）") }
            ForEach(state.beats, id: \.project) { b in Text(b.line) }
            Divider()
            Text("超过 \(Int(state.config.heartbeatStaleMinutes)) 分钟算停")
            Button("立即跑一次 evo watchdog") { state.runWatchdog() }
                .disabled(state.busy != nil)
        }
        if let b = state.busy { Text(b) } else if let a = state.lastAction { Text(a) }
        Divider()
        Button("刷新") { state.refresh() }
            .keyboardShortcut("r")
        if let t = state.lastRefresh { Text("上次刷新 \(Self.timeFmt.string(from: t))") }
        Button("设置…") { WindowManager.shared.showSettings() }
            .keyboardShortcut(",")
        Divider()
        Button("退出 Evo") { NSApp.terminate(nil) }
            .keyboardShortcut("q")
    }
}
#endif
