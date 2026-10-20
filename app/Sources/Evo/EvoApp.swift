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
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        if let dir = Snapshots.requestedDir {          // make snapshots：画完图就退出，不碰 evo
            Snapshots.run(dir: dir)
            exit(0)
        }
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

/// 菜单栏图标：吉祥物的单色小脸（随心情变：等你 → 挑眉，停了 → 皱眉，暂停 → 闭眼）+ 等你件数。
struct MenuBarLabel: View {
    @ObservedObject var state: AppState

    var body: some View {
        let img = Image(nsImage: MenuBarIcon.image(state.mood))
        if let t = Badge.text(state.badge) {
            Text("\(img) \(t)")
                .accessibilityLabel("Evo，\(t) 件等你")
        } else {
            img.accessibilityLabel("Evo，\(state.loopState.label)")
        }
    }
}
#endif
