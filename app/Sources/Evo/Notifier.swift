#if os(macOS)
import Foundation
import AppKit
import UserNotifications
import EvoCore

/// 原生通知。去重和免打扰在 EvoCore.GateTracker / StaleTracker 里算好，这里只负责发和点。
/// 规则借 Todos：面板窗口正在看（前台且是 key 窗口）就不弹横幅。
final class Notifier: NSObject, UNUserNotificationCenterDelegate {
    static let shared = Notifier()

    /// UNUserNotificationCenter 只能在打包好的 .app 里用；`swift run` 时直接跳过，免得崩。
    var available: Bool {
        Bundle.main.bundleIdentifier != nil && Bundle.main.bundleURL.pathExtension == "app"
    }

    var enabled: Bool {
        UserDefaults.standard.object(forKey: "notificationsEnabled") as? Bool ?? true
    }

    func setup() {
        guard available else { return }
        let c = UNUserNotificationCenter.current()
        c.delegate = self
        c.requestAuthorization(options: [.alert, .sound, .badge]) { granted, err in
            if let err { NSLog("Evo 通知授权出错：\(err.localizedDescription)") }
            if !granted { NSLog("Evo 通知未授权：系统设置 → 通知 → Evo 打开") }
        }
    }

    func post(_ notes: [PlannedNotification]) {
        guard available, enabled, !notes.isEmpty else { return }
        let c = UNUserNotificationCenter.current()
        for n in notes {
            let content = UNMutableNotificationContent()
            content.title = n.title
            content.body = n.body
            content.sound = .default
            content.threadIdentifier = n.project
            content.userInfo = ["project": n.project, "gate": n.gate ?? ""]
            c.add(UNNotificationRequest(identifier: n.id, content: content, trigger: nil))
        }
    }

    func test() {
        post([PlannedNotification(id: "test/\(Date().timeIntervalSince1970)", title: "Evo 测试通知",
                                  body: "看到这条说明通知权限已打开", project: "Evo", gate: nil)])
    }

    // 应用在前台时也显示；但面板窗口正被看着就不弹
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        Task { @MainActor in
            completionHandler(PanelController.shared.isBeingWatched ? [] : [.banner, .sound, .list])
        }
    }

    // 点通知 → 打开面板
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        Task { @MainActor in
            PanelController.shared.open()
            completionHandler()
        }
    }
}
#endif
