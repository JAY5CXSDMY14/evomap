#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

struct EvoApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @ObservedObject private var state = AppState.shared

    var body: some Scene {
        MenuBarExtra {
            MainPopover(state: state)
        } label: {
            MenuBarLabel(state: state)
        }
        .menuBarExtraStyle(.window)
        .commands {
            CommandGroup(after: .windowArrangement) {
                Button("打开 Evo 窗口") { MainWindowController.shared.show() }.keyboardShortcut("0", modifiers: .command)
            }
            CommandMenu("Evo") {
                Button("立即 tick") { AppState.shared.tickNow() }.keyboardShortcut("t", modifiers: [.command, .shift])
                Button("刷新") { AppState.shared.refresh() }
                Button("命令面板…") { PaletteController.shared.show() }
                Divider()
                Button("切换深色 / 浅色") { AppState.shared.toggleAppearance() }
                Button("设置…") { WindowManager.shared.showSettings() }
            }
        }
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        MateAssets.prepareRules()
        if let dir = Snapshots.requestedDir {          // make snapshots：画完图就退出，不碰 evo
            Task { @MainActor in
                await Snapshots.run(dir: dir)
                exit(0)
            }
            return
        }
        AppState.shared.applyAppearance()
        Notifier.shared.setup()
        AppState.shared.start()
        UIProbe.start()
        DemoRunner.start()
        if !UserDefaults.standard.bool(forKey: "setupDone") { WindowManager.shared.showSetup() }
        // 先拍好角色静态帧（截图兜底用）；Dock 图标用包里的 AppIcon.icns，只有开发时没包图标才用角色帧
        Task { @MainActor in
            await MateSnapshotCache.shared.prepare(MateAssets.character, [.standby], side: 240)
            if MainWindowController.shared.isOpen { DockIcon.apply() }
        }
        if ProcessInfo.processInfo.environment["EVO_OPEN_WINDOW"] == "1" { MainWindowController.shared.show() }
    }

    func applicationWillTerminate(_ notification: Notification) {
        PanelController.shared.stopOwnedPanel()
    }

    // 关掉最后一个窗口不退出：菜单栏应用常驻
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    // 点 Dock 图标：重新打开主窗口
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        MainWindowController.shared.show()
        return true
    }
}

/// 菜单栏图标：吉祥物的单色小脸（随心情变：等你 → 挑眉，停了 → 皱眉，暂停 → 闭眼）+ 等你件数。
struct MenuBarLabel: View {
    @ObservedObject var state: AppState

    var body: some View {
        let img = Image(nsImage: MenuBarIcon.image(state.mood))
        if let t = Badge.text(state.badge) {
            // 菜单栏标签只认 Label / Image / Text；把图片插进 Text 里在真菜单栏上会被丢掉（CI 实机截图里只剩数字）
            Label { Text(t) } icon: { img }
                .labelStyle(.titleAndIcon)
                .accessibilityLabel("Evo，\(t) 件等你")
        } else {
            img.accessibilityLabel("Evo，\(state.loopState.label)")
        }
    }
}
#endif
