import Foundation

// 界面要用的数据映射，全部纯函数，Linux 上也能测。界面层（Sources/Evo）只负责画。

// MARK: - 问候

public enum Greeting {
    /// 按小时给一句问候（0–23）。
    public static func text(hour: Int) -> String {
        switch hour {
        case 0..<5: return "夜深了"
        case 5..<11: return "早上好"
        case 11..<13: return "中午好"
        case 13..<18: return "下午好"
        default: return "晚上好"
        }
    }

    public static func text(at date: Date, tz: TimeZone = .current) -> String {
        var cal = Calendar(identifier: .gregorian); cal.timeZone = tz
        return text(hour: cal.component(.hour, from: date))
    }
}

// MARK: - 总状态胶囊

public enum LoopState: Equatable, Sendable {
    case loading            // 还没读过
    case error(String)      // evo 跑不起来
    case stale              // 有项目心跳过期
    case paused             // launchd 常驻被暂停
    case running            // 正常
    case empty              // 还没有项目

    public static func derive(globalError: String?, loaded: Bool, projectCount: Int,
                              loopRunning: Bool?, anyStale: Bool) -> LoopState {
        if let e = globalError { return .error(e) }
        if !loaded { return .loading }
        if loopRunning == false { return .paused }
        if anyStale { return .stale }
        if projectCount == 0 { return .empty }
        return .running
    }

    public var label: String {
        switch self {
        case .loading: return "读取中"
        case .error: return "出错了"
        case .stale: return "心跳过期"
        case .paused: return "已暂停"
        case .running: return "运行中"
        case .empty: return "没有项目"
        }
    }

    /// 胶囊颜色语义：界面层映射到 Theme 的 success / warning / danger / secondary。
    public enum Tone: Equatable, Sendable { case success, warning, danger, neutral }
    public var tone: Tone {
        switch self {
        case .running: return .success
        case .paused: return .warning
        case .stale, .error: return .danger
        case .loading, .empty: return .neutral
        }
    }
}

// MARK: - 闸门卡片

public struct GateCard: Identifiable, Equatable, Sendable {
    public var id: String               // 「项目/闸门号」，和 GateTracker 的去重键一致
    public var project: String
    public var projectName: String
    public var gateID: String
    public var itemID: String?
    public var title: String
    public var kind: String?
    public var kindLabel: String
    public var approveChoice: String    // 传给 evo approve 的选项原文
    public var rejectChoice: String
    public var waitingSince: Date?

    /// 「打回」时要不要让老板写原话（看效果打回原话会进返工说明，最有用）。
    public var rejectAsksWords: Bool { kind == "look" || kind == "ask" || kind == "external" }

    public static let defaultChoices: [String: (String, String)] = [
        "do": ("做", "不做"), "look": ("通过", "打回"), "ship": ("上线", "再等等"),
        "ask": ("同意", "不同意"), "external": ("同意交决策岗", "拒绝"),
    ]

    public init(project: String, projectName: String, gate g: StatusDoc.Gate) {
        self.project = project
        self.projectName = projectName
        gateID = g.id
        id = GateTracker.key(project, g.id)
        itemID = g.item
        kind = g.kind
        kindLabel = g.kindLabel
        title = Self.cleanTitle(g.question ?? g.id)
        let d = Self.defaultChoices[g.kind ?? ""] ?? ("通过", "打回")
        approveChoice = g.options.first ?? d.0
        rejectChoice = g.options.count > 1 ? g.options[1] : d.1
        waitingSince = ISOTime.parse(g.waitingSince)
    }

    /// 去掉问题里重复的种类前缀：「看效果（第 2 轮）：改版按钮」→「改版按钮」。
    public static func cleanTitle(_ q: String) -> String {
        let t = q.trimmingCharacters(in: .whitespaces)
        for p in ["看效果", "做不做", "上线"] where t.hasPrefix(p) {
            var rest = t.dropFirst(p.count)
            if rest.first == "（" || rest.first == "(" {
                guard let close = rest.firstIndex(where: { $0 == "）" || $0 == ")" }) else { break }
                rest = rest[rest.index(after: close)...]
            }
            if rest.first == "：" || rest.first == ":" {
                let r = rest.dropFirst().trimmingCharacters(in: .whitespaces)
                return r.isEmpty ? t : r
            }
        }
        return t
    }

    /// 等了多久：「刚刚」「12 分钟」「3.5 小时」「2 天」；没有时间就 nil。
    public func ageText(now: Date = Date()) -> String? {
        guard let w = waitingSince else { return nil }
        let m = max(0, now.timeIntervalSince(w) / 60)
        return m < 1 ? "刚刚" : HeartbeatStatus.human(m)
    }

    /// evo 命令参数：通过 / 打回（带原话）。
    public func approveArgs() -> [String] { ["-p", project, "approve", gateID, approveChoice] }
    public func rejectArgs(words: String?) -> [String] {
        let w = words?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return ["-p", project, "approve", gateID, rejectChoice] + (w.isEmpty ? [] : [w])
    }

    /// 读屏念的一句。
    public var accessibilityText: String {
        "\(projectName)，\(kindLabel)：\(title)" + (itemID.map { "，件号 \($0)" } ?? "")
    }

    public static func cards(_ snaps: [ProjectSnapshot], hidden: Set<String> = []) -> [GateCard] {
        snaps.flatMap { s -> [GateCard] in
            guard let d = s.doc else { return [] }
            return d.gates.map { GateCard(project: s.code, projectName: d.name, gate: $0) }
        }.filter { !hidden.contains($0.id) }
    }
}

// MARK: - 项目行

public struct ProjectRow: Identifiable, Equatable, Sendable {
    public var id: String { code }
    public var code: String
    public var name: String
    public var building: Int
    public var verifying: Int
    public var waiting: Int
    public var stuck: Int
    public var merged: Int
    public var tooLong: Int            // 卡太久（status JSON 顶层 stale 的件数）
    public var roleLine: String?       // 「施工 忙 · 验收 闲」
    public var error: String?
    public var heartbeat: HeartbeatStatus.Level?

    public init(_ s: ProjectSnapshot, beat: HeartbeatStatus? = nil) {
        code = s.code; name = s.name; error = s.error
        building = s.doc?.buildingCount ?? 0
        verifying = s.doc?.verifyingCount ?? 0
        waiting = s.doc?.pendingCount ?? 0
        stuck = s.doc?.stuckCount ?? 0
        merged = s.doc?.mergedCount ?? 0
        tooLong = s.doc?.staleItems ?? 0
        let roles = s.doc?.roles ?? []
        roleLine = roles.isEmpty ? nil : roles.map { "\($0.name) \($0.label)" }.joined(separator: " · ")
        if let p = s.doc?.paused, !p.isEmpty { roleLine = "暂停：\(p)" }      // 第十七轮：项目暂停时说清原因，不显示成出错
        heartbeat = beat?.level
    }

    public var isQuiet: Bool { error == nil && building + verifying + waiting + stuck == 0 }

    public var accessibilityText: String {
        if let e = error { return "\(code) \(name)，读不出状态：\(e)" }
        return "\(code) \(name)，施工 \(building)，验收 \(verifying)，等你 \(waiting)，卡住 \(stuck)"
    }
}

// MARK: - 吉祥物心情 + 说的话

public enum MascotMood: String, CaseIterable, Sendable {
    case idle       // 一切顺利：偶尔眨眼
    case working    // 有件在施工：东张西望、轻轻上下
    case waiting    // 有闸门等你：挑眉、轻轻弹
    case worried    // 心跳过期 / 出错 / 卡住
    case sleepy     // 暂停

    /// quiet = 正在免打扰时段：循环照转，但小家伙睡觉（不吵你）。
    public static func derive(state: LoopState, waiting: Int, building: Int, stuck: Int, quiet: Bool = false) -> MascotMood {
        switch state {
        case .error, .stale: return .worried
        case .paused: return .sleepy
        case .loading, .empty: return .idle
        case .running:
            if quiet { return .sleepy }
            if waiting > 0 { return .waiting }
            if stuck > 0 { return .worried }
            return building > 0 ? .working : .idle
        }
    }
}

public enum Speech {
    /// 吉祥物气泡里的一句状态。
    public static func status(state: LoopState, cards: [GateCard], rows: [ProjectRow], beats: [HeartbeatStatus]) -> String {
        switch state {
        case .loading: return "我去看看各个项目…"
        case .error(let e): return "evo 跑不起来：\(e.prefix(60))"
        case .empty: return "还没有项目。终端里 evo new 或 evo import 一个吧"
        case .paused: return "循环在睡觉。点「恢复」叫醒我"
        case .stale:
            if let b = beats.filter({ $0.level == .stale }).max(by: { ($0.ageMinutes ?? 0) < ($1.ageMinutes ?? 0) }) {
                return "\(b.project) 已 \(HeartbeatStatus.human(b.ageMinutes ?? 0))没转动，看看常驻和执行端（Multica / Orca）？"
            }
            return "有项目好久没转动了"
        case .running:
            if !cards.isEmpty {
                let kinds = Set(cards.map(\.kindLabel))
                if kinds.count == 1, let k = kinds.first { return "有 \(cards.count) 件等你\(k)" }
                return "有 \(cards.count) 件等你处理"
            }
            let stuck = rows.reduce(0) { $0 + $1.stuck }
            if stuck > 0 { return "\(stuck) 件卡住了，要不要去面板看看" }
            let b = rows.reduce(0) { $0 + $1.building }
            if b > 0 { return "正在施工 \(b) 件，你忙你的" }
            return "一切顺利"
        }
    }
}

// MARK: - 模糊过滤（⌘K）

public enum Fuzzy {
    /// 子序列匹配打分；不匹配返回 nil。连续命中、词首命中、开头命中加分，越短越靠前。不分大小写。
    public static func score(_ query: String, _ text: String) -> Int? {
        let q = Array(query.lowercased().filter { !$0.isWhitespace })
        if q.isEmpty { return 0 }
        let t = Array(text.lowercased())
        var qi = 0, score = 0, last = -2, first = -1
        for (i, ch) in t.enumerated() where qi < q.count && ch == q[qi] {
            if first < 0 { first = i }
            score += 10
            if i == last + 1 { score += 15 }
            if i == 0 || " -_/·：:".contains(t[i - 1]) { score += 10 }
            last = i; qi += 1
        }
        guard qi == q.count else { return nil }
        score -= first                       // 越早命中越好
        score -= max(0, t.count - q.count) / 4
        return score
    }

    public static func filter<T>(_ items: [T], query: String, text: (T) -> String) -> [T] {
        if query.trimmingCharacters(in: .whitespaces).isEmpty { return items }
        return items.enumerated()
            .compactMap { (i, x) in score(query, text(x)).map { (i, x, $0) } }
            .sorted { $0.2 != $1.2 ? $0.2 > $1.2 : $0.0 < $1.0 }
            .map(\.1)
    }
}

// MARK: - 命令面板条目

public enum PaletteDestination: String, Equatable, Sendable { case inbox, stale, team, settings }

public struct PaletteEntry: Identifiable, Equatable, Sendable {
    public enum Action: Equatable, Sendable {
        case tick, openPanel, togglePause, harvest, refresh, settings, setup, watchdog, openWindow, toggleAppearance
        case approve(String), reject(String)      // GateCard.id
        case focusProject(String)
        case openItem(project: String, key: String)    // 第十九轮：跳到件详情（时间线 + 为什么卡住）
        case go(PaletteDestination)                    // 第十九轮：跳页
    }
    public var id: String
    public var title: String
    public var subtitle: String
    public var symbol: String
    public var action: Action
    /// 第十九轮：只用来搜、不显示的词（英文别名、「时间线」之类）。
    public var keywords: String = ""

    public var searchText: String { "\(title) \(subtitle) \(keywords)" }

    /// 第十九轮：面板分组（没输入时按组显示小标题，像 Linear）。
    public var section: String {
        switch action {
        case .approve, .reject: return "等你处理"
        case .openItem: return "件"
        case .focusProject: return "项目"
        case .go: return "跳转"
        default: return "动作"
        }
    }

    /// 右侧显示的快捷键提示（没有就 nil）。
    public var shortcut: String? {
        switch action {
        case .openWindow: return "⌘0"
        case .refresh: return "⌘R"
        case .settings: return "⌘,"
        default: return nil
        }
    }

    /// 第十九轮：面板里能直接跳到的件（卡住的排前面，然后是其余件）。
    public struct ItemRef: Equatable, Sendable {
        public var project: String, key: String, title: String, note: String, stuck: Bool
        public init(project: String, key: String, title: String, note: String, stuck: Bool = false) {
            self.project = project; self.key = key; self.title = title; self.note = note; self.stuck = stuck
        }
    }

    public static func build(cards: [GateCard], rows: [ProjectRow], paused: Bool?,
                             items: [ItemRef] = [], teamVisible: Bool = false) -> [PaletteEntry] {
        var out: [PaletteEntry] = [
            .init(id: "window", title: "打开 Evo 窗口", subtitle: "主窗口", symbol: "macwindow", action: .openWindow, keywords: "window"),
            .init(id: "tick", title: "立即 tick", subtitle: "每个项目转一轮 tick", symbol: "bolt", action: .tick),
            .init(id: "panel", title: "打开面板", subtitle: "panel 网页面板", symbol: "rectangle.on.rectangle", action: .openPanel),
            .init(id: "harvest", title: "收菜清单", subtitle: "已合并可上线 harvest", symbol: "basket", action: .harvest),
            .init(id: "refresh", title: "刷新", subtitle: "重新读状态", symbol: "arrow.clockwise", action: .refresh, keywords: "refresh"),
            .init(id: "watchdog", title: "看门狗检查", subtitle: "evo watchdog", symbol: "heart.text.square", action: .watchdog),
            .init(id: "appearance", title: "切换深色 / 浅色", subtitle: "dark light appearance 外观", symbol: "circle.lefthalf.filled", action: .toggleAppearance),
            .init(id: "settings", title: "设置", subtitle: "settings", symbol: "gearshape", action: .settings),
            .init(id: "setup", title: "首次设置向导", subtitle: "setup install", symbol: "wand.and.stars", action: .setup),
        ]
        if let paused {
            out.insert(.init(id: "pause", title: paused ? "恢复循环" : "暂停循环", subtitle: paused ? "resume" : "pause",
                             symbol: paused ? "play" : "pause", action: .togglePause), at: 3)
        }
        for c in cards {
            let sub = "\(c.project) · \(c.kindLabel)" + (c.itemID.map { " · \($0)" } ?? "")
            out.append(.init(id: "ok/\(c.id)", title: "\(c.approveChoice)：\(c.title)", subtitle: sub, symbol: "checkmark.circle", action: .approve(c.id)))
            out.append(.init(id: "no/\(c.id)", title: "\(c.rejectChoice)：\(c.title)", subtitle: sub, symbol: "arrow.uturn.backward.circle", action: .reject(c.id)))
        }
        out.append(.init(id: "go/inbox", title: "去「等你处理」", subtitle: "首页", symbol: "tray", action: .go(.inbox), keywords: "home inbox"))
        out.append(.init(id: "go/stale", title: "去「卡太久」", subtitle: "没活路、同一状态太久的件", symbol: "hourglass", action: .go(.stale),
                         keywords: "卡住 stuck stale 为什么卡住"))
        if teamVisible {
            out.append(.init(id: "go/team", title: "去「团队」", subtitle: "施工 / 验收 / 决策用哪个模型", symbol: "person.3", action: .go(.team), keywords: "team model"))
        }
        for i in items.sorted(by: { $0.stuck && !$1.stuck }) {
            out.append(.init(id: "i/\(i.project)/\(i.key)", title: "\(i.key) \(i.title)",
                             subtitle: (i.stuck ? "卡住 · " : "") + "\(i.project) · \(i.note)",
                             symbol: i.stuck ? "exclamationmark.triangle" : "doc.text.magnifyingglass", action: .openItem(project: i.project, key: i.key),
                             keywords: "件 item 时间线 为什么卡住"))
        }
        for r in rows {
            out.append(.init(id: "p/\(r.code)", title: "\(r.code) \(r.name)", subtitle: "项目 project", symbol: "folder", action: .focusProject(r.code)))
        }
        return out
    }
}

// MARK: - 输入框（告诉 evo…）

public enum ComposerMode: String, CaseIterable, Sendable {
    case feedback   // evo feedback：原话进 GitHub issue，决策岗分拣
    case add        // evo add：直接登记一件（标题 24 字以内）

    public var label: String { self == .feedback ? "反馈" : "新件" }
    public var placeholder: String { self == .feedback ? "告诉 evo…（用户视角的意见）" : "新件标题，动作开头，24 字内" }
}

public enum Composer {
    /// 校验并给出 evo 参数；不合格返回错误句子。
    public static func command(mode: ComposerMode, project: String, text: String, look: Bool = false) -> Result<[String], ComposerError> {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { return .failure(.init("先写点什么")) }
        if project.isEmpty { return .failure(.init("先选一个项目")) }
        switch mode {
        case .feedback:
            return .success(["-p", project, "feedback", t])
        case .add:
            if t.count > 24 { return .failure(.init("新件标题超过 24 字（\(t.count)），改短一点，或切到「反馈」")) }
            if t.contains("\n") { return .failure(.init("标题只能一行")) }
            return .success(["-p", project, "add", "--title", t, "--scope", "."] + (look ? ["--look"] : []))
        }
    }

    /// evo 回的话转成吉祥物气泡里的一句。
    public static func reply(mode: ComposerMode, ok: Bool, out: String, err: String) -> String {
        let o = out.trimmingCharacters(in: .whitespacesAndNewlines)
        let e = (err.isEmpty ? out : err).trimmingCharacters(in: .whitespacesAndNewlines)
        if !ok { return "没成：\(String(e.suffix(120)))" }
        switch mode {
        case .feedback:
            if let n = o.split(separator: "/").last, o.contains("/issues/") { return "收到！记成 issue #\(n)，决策岗会分拣" }
            return "收到！交给决策岗分拣了"
        case .add:
            return o.isEmpty ? "登记好了，排进队里" : "登记好了：\(String(o.suffix(80)))"
        }
    }
}

public struct ComposerError: Error, Equatable, Sendable {
    public var message: String
    public init(_ m: String) { message = m }
}

// MARK: - 收菜清单

public struct HarvestItem: Identifiable, Equatable, Sendable {
    public var id: String { "\(project)/\(key)" }
    public var project: String
    public var key: String
    public var title: String

    /// 已合并可收菜（raw == merged）的件，跨项目。
    public static func list(_ snaps: [ProjectSnapshot]) -> [HarvestItem] {
        snaps.flatMap { s in
            (s.doc?.items ?? []).filter { $0.raw == "merged" }.map { HarvestItem(project: s.code, key: $0.key, title: $0.title) }
        }
    }
}

// MARK: - 快捷键

public enum Shortcuts {
    /// ⌘1…⌘9 对应第几个项目；超出返回 nil。
    public static func project(forDigit d: Int, codes: [String]) -> String? {
        guard (1...9).contains(d), d <= codes.count else { return nil }
        return codes[d - 1]
    }
}
