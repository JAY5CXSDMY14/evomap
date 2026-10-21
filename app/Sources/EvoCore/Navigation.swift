import Foundation

// 主窗口（v0.3.0）要的纯逻辑：侧栏条目、卡太久清单、闸门网格列数、窗口尺寸、演示脚本。

/// 侧栏选中的是什么。item = 某件的详情（时间线），不在侧栏里，但用同一个选择状态导航。
public enum SidebarItem: Hashable, Sendable {
    case inbox
    case project(String)
    case item(project: String, key: String)
    case stale
    case team             // v0.4.0：岗位卡片（工具·模型·思考档位·备用·成绩）
    case plugin(String, String)   // v0.6.0：插件的侧栏页（插件名, 页 id），内容由插件输出的卡片 JSON 画
    case settings

    /// 详情页标题。
    public func title(projectName: (String) -> String?) -> String {
        switch self {
        case .inbox: return "等你处理"
        case .project(let c): return projectName(c).map { "\(c) · \($0)" } ?? c
        case .item(_, let k): return k
        case .stale: return "卡太久"
        case .team: return "团队"
        case .plugin(_, let id): return id
        case .settings: return "设置"
        }
    }

    /// 选中件详情时，侧栏高亮它所属的项目。
    public var sidebarHighlight: SidebarItem {
        if case .item(let p, _) = self { return .project(p) }
        return self
    }

    /// 返回上一级：件 → 项目，其余回等你处理。
    public var parent: SidebarItem? {
        switch self {
        case .item(let p, _): return .project(p)
        case .inbox: return nil
        default: return .inbox
        }
    }
}

/// 卡太久 / 没活路的件（跨项目），给侧栏「卡太久」和它的详情页。
public struct StuckEntry: Identifiable, Equatable, Sendable {
    public enum Kind: Equatable, Sendable { case tooLong, noLivePath }
    public var id: String { "\(project)/\(key)/\(kind == .tooLong ? "s" : "n")" }
    public var project: String
    public var key: String
    public var title: String
    public var kind: Kind
    public var detail: String

    public static let reasons: [String: String] = [
        "dep_dead": "依赖的件没了", "no_decider": "没人能拍板", "stalled": "停着不动", "rate_limited": "额度满了",
    ]

    /// 没活路排前面，再按卡的时长从长到短。数字格式（老 evo）没有明细，就不列。
    public static func list(_ snaps: [ProjectSnapshot]) -> [StuckEntry] {
        var out: [(StuckEntry, Double)] = []
        for s in snaps {
            guard let d = s.doc else { continue }
            for f in d.noLivePathList {
                let why = f.reason.map { reasons[$0] ?? $0 } ?? "没有可走通的路"
                out.append((StuckEntry(project: s.code, key: f.key, title: f.title ?? "", kind: .noLivePath, detail: "没活路：\(why)"), 1e9 + (f.minutes ?? 0)))
            }
            for f in d.staleList {
                let h = f.hours ?? (f.minutes.map { $0 / 60 })
                let t = h.map { "同一状态 \(HeartbeatStatus.human($0 * 60))" } ?? "同一状态太久"
                out.append((StuckEntry(project: s.code, key: f.key, title: f.title ?? "", kind: .tooLong,
                                       detail: [f.state, t].compactMap { $0 }.joined(separator: " · ")), (h ?? 0) * 60))
            }
        }
        return out.sorted { $0.1 > $1.1 }.map(\.0)
    }
}

/// 闸门卡片网格：窗口内容区宽度 → 列数。卡片最窄 340 点，最多 3 列。
public enum GateGrid {
    public static let minCardWidth: Double = 340
    public static let spacing: Double = 14

    public static func columns(width: Double) -> Int {
        guard width.isFinite, width > 0 else { return 1 }
        let n = Int((width + spacing) / (minCardWidth + spacing))
        return min(3, max(1, n))
    }
}

/// 主窗口尺寸：最小 900×600；第一次打开取屏幕可用区的大部分（不超过 1240×820）。
public enum WindowSizing {
    public static let minWidth: Double = 900
    public static let minHeight: Double = 600

    public static func initial(visibleWidth: Double, visibleHeight: Double) -> (width: Double, height: Double) {
        let w = min(1240, max(minWidth, visibleWidth - 80))
        let h = min(820, max(minHeight, visibleHeight - 60))
        return (w, h)
    }

    /// 弹窗宽度（v0.3.0 起变宽变矮）。
    public static let popoverWidth: Double = 420
    /// 弹窗里最多放几张闸门卡，其余「还有 N 件」去窗口看。
    public static let popoverCards = 2
}

/// Dock 图标：主窗口开着时显示（.regular），关了回到纯菜单栏（.accessory）。
public enum DockPolicy {
    public static func showsDock(mainWindowOpen: Bool, otherWindowsOpen: Bool = false) -> Bool { mainWindowOpen }
}

/// 截图 / 录屏用的演示脚本（EVO_DEMO=1 时应用自己按顺序点；CI 里 UI 脚本走同一顺序）。
public enum DemoScript {
    public enum Step: String, CaseIterable, Sendable {
        case desktop          // 只有菜单栏
        case popover          // 点开菜单栏弹窗
        case openWindow       // 弹窗里「打开 Evo 窗口」
        case approve          // 通过第一张卡（飞走）
        case rejectWords      // 打回第二张，写原话
        case rejectSend
        case project          // 侧栏选项目
        case item             // 打开一件的时间线
        case team             // 侧栏「团队」：岗位卡片
        case pluginPage       // v0.6.0：侧栏「插件」分组里的页（示例插件 example-hello）
        case pluginCommand    // v0.6.0：输入框跑 /hello，回话是插件卡片
        case palette          // ⌘K
        case dark             // 命令面板里切深色
        case composer         // 输入框发一句，看回话
        case popoverDark      // 深色下再开弹窗
        case done
    }

    public static let steps: [Step] = Step.allCases

    /// 每步之后停多久（秒），给动画和录屏留时间。
    public static func pause(after s: Step) -> Double {
        switch s {
        case .desktop: return 1.2
        case .popover: return 2.0
        case .openWindow: return 2.5
        case .approve: return 2.2
        case .rejectWords: return 1.6
        case .rejectSend: return 2.0
        case .project: return 2.2
        case .item: return 2.6
        case .team: return 2.6
        case .pluginPage: return 2.6
        case .pluginCommand: return 3.0
        case .palette: return 1.8
        case .dark: return 2.4
        case .composer: return 3.2
        case .popoverDark: return 2.2
        case .done: return 0.5
        }
    }

    public static var totalSeconds: Double { steps.reduce(0) { $0 + pause(after: $1) } }

    /// 截图文件名：两位序号 + 步骤名。
    public static func shotName(_ s: Step) -> String {
        let i = (steps.firstIndex(of: s) ?? 0) + 1
        return (i < 10 ? "0" : "") + "\(i)-\(s.rawValue).png"
    }
}
