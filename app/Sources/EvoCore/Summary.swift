import Foundation

/// 一个项目这一轮读到的结果：要么有状态，要么有错误（读不出也要显示在菜单里，不能悄悄消失）。
public struct ProjectSnapshot: Equatable, Sendable {
    public var code: String
    public var doc: StatusDoc?
    public var error: String?

    public init(code: String, doc: StatusDoc? = nil, error: String? = nil) {
        self.code = code; self.doc = doc; self.error = error
    }

    public var name: String { doc?.name ?? code }
    public var pending: Int { doc?.pendingCount ?? 0 }
}

/// 菜单栏角标与菜单行的计算。
public enum Badge {
    /// 角标 = 所有项目「等你点头」件数之和。
    public static func count(_ snaps: [ProjectSnapshot]) -> Int {
        snaps.reduce(0) { $0 + $1.pending }
    }

    /// 角标文字：0 不显示，超过 99 显示 99+。
    public static func text(_ n: Int) -> String? {
        n <= 0 ? nil : (n > 99 ? "99+" : String(n))
    }

    /// 菜单里每个项目一行。
    public static func menuLine(_ s: ProjectSnapshot) -> String {
        if let e = s.error { return "\(s.code)  读不出状态：\(e.prefix(60))" }
        guard let d = s.doc else { return "\(s.code)  …" }
        var parts = ["\(d.project) \(d.name)", "等你 \(d.pendingCount)"]
        if d.buildingCount > 0 { parts.append("施工 \(d.buildingCount)") }
        if d.stuck > 0 { parts.append("卡住 \(d.stuck)") }
        return parts.joined(separator: " · ")
    }
}

/// 一条要发的原生通知。id 用来去重（同一个闸门只提醒一次）。
public struct PlannedNotification: Equatable, Sendable {
    public var id: String
    public var title: String
    public var body: String
    public var project: String
    public var gate: String?

    public init(id: String, title: String, body: String, project: String, gate: String?) {
        self.id = id; self.title = title; self.body = body; self.project = project; self.gate = gate
    }
}

/// 闸门差异：哪些是新冒出来的、要提醒老板的。
/// 规则：
/// - 去重键 = 「项目/闸门号」，提醒过就记进 seen（应用重启也记得，存在 UserDefaults）。
/// - 第一次启动（seen 为空且 primed=false）只记录不提醒，免得一开应用就弹一屏旧闸门。
/// - 免打扰时段不提醒、也不记进 seen，等时段结束下一轮自然补发。
/// - 已经不在待批列表里的闸门从 seen 里清掉，seen 不会无限长。
public struct GateTracker: Equatable {
    public private(set) var seen: Set<String>
    public private(set) var primed: Bool

    public init(seen: Set<String> = [], primed: Bool = false) {
        self.seen = seen; self.primed = primed
    }

    public static func key(_ project: String, _ gate: String) -> String { "\(project)/\(gate)" }

    public mutating func diff(_ snaps: [ProjectSnapshot], quiet: Bool) -> [PlannedNotification] {
        var current: [(String, StatusDoc.Gate, StatusDoc)] = []
        var readable = Set<String>()
        for s in snaps {
            guard let d = s.doc else { continue }
            readable.insert(s.code)
            for g in d.gates { current.append((Self.key(s.code, g.id), g, d)) }
        }
        let liveKeys = Set(current.map { $0.0 })
        // 只清掉「读得出状态的项目」里已经消失的闸门；某个项目这一轮读失败，不能当成它的闸门都批完了
        seen = seen.filter { k in
            let proj = String(k.split(separator: "/", maxSplits: 1).first ?? "")
            return liveKeys.contains(k) || !readable.contains(proj)
        }
        if !primed {
            seen.formUnion(liveKeys); primed = true
            return []
        }
        if quiet { return [] }
        var out: [PlannedNotification] = []
        for (k, g, d) in current where !seen.contains(k) {
            seen.insert(k)
            let item = g.item.map { "\($0) · " } ?? ""
            out.append(PlannedNotification(id: k, title: "[\(d.project)] 等你点头：\(g.kindLabel)",
                                           body: item + (g.question ?? g.id), project: d.project, gate: g.id))
        }
        return out
    }
}
