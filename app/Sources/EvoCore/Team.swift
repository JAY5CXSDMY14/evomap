import Foundation

// v0.4.0「团队」页要的纯逻辑：`evo team --json` 解码、状态灯、成绩一句话、换模型的意图（「把验收换成 X」）、
// 换模型确认卡、向导里的岗位卡片提案。evo 那边见 kit/bin/evo_team.py 和 docs/model-coordination.md。

/// `evo team --json`（schema_version 1，只加字段）。只认要用的字段；缺了不报错。
public struct TeamDoc: Decodable, Equatable, Sendable {
    public var project: String?
    public var cards: [TeamCard]
    public var magpieOK: Bool
    public var magpieURL: String?
    public var magpieModels: [String]
    public var groups: [String]
    public var suggestions: [String]
    public var projects: [TeamProject]
    public var thinkingLevels: [String]

    enum CodingKeys: String, CodingKey {
        case project, cards, magpie, suggestions, projects
        case thinkingLevels = "thinking_levels"
    }

    struct Magpie: Decodable {
        var ok: Bool?
        var url: String?
        var models: [String]?
        var groups: [String]?
    }

    struct Suggestion: Decodable { var model: String }

    public init(project: String? = nil, cards: [TeamCard] = [], magpieOK: Bool = false, magpieURL: String? = nil,
                magpieModels: [String] = [], groups: [String] = [], suggestions: [String] = [], projects: [TeamProject] = [],
                thinkingLevels: [String] = TeamDoc.defaultThinking) {
        self.project = project; self.cards = cards; self.magpieOK = magpieOK; self.magpieURL = magpieURL
        self.magpieModels = magpieModels; self.groups = groups; self.suggestions = suggestions; self.projects = projects
        self.thinkingLevels = thinkingLevels
    }

    public static let defaultThinking = ["off", "low", "medium", "high", "max"]

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        project = (try? c.decodeIfPresent(String.self, forKey: .project))
        cards = ((try? c.decode([Lenient.Maybe<TeamCard>].self, forKey: .cards)) ?? []).compactMap(\.value)
        let m = (try? c.decodeIfPresent(Magpie.self, forKey: .magpie))
        magpieOK = m?.ok ?? false
        magpieURL = m?.url
        magpieModels = m?.models ?? []
        groups = m?.groups ?? []
        suggestions = ((try? c.decode([Lenient.Maybe<Suggestion>].self, forKey: .suggestions)) ?? []).compactMap { $0.value?.model }
        projects = ((try? c.decode([Lenient.Maybe<TeamProject>].self, forKey: .projects)) ?? []).compactMap(\.value)
        let t = (try? c.decodeIfPresent([String].self, forKey: .thinkingLevels))
        thinkingLevels = (t?.isEmpty == false) ? t! : TeamDoc.defaultThinking
    }

    public static func decode(_ s: String) throws -> TeamDoc { try decode(Data(s.utf8)) }
    public static func decode(_ data: Data) throws -> TeamDoc { try JSONDecoder().decode(TeamDoc.self, from: data) }

    public func card(_ role: String) -> TeamCard? { cards.first { $0.role == role } }

    /// 下拉框的选项：卡片现在用的在最前，再是 magpie 列表、备用、成绩表里出现过的；去重、保持顺序。
    public func modelOptions(for card: TeamCard) -> [String] {
        var seen = Set<String>(), out: [String] = []
        for m in card.models + magpieModels + (card.fallback?.models ?? []) + card.stats.keys.sorted()
        where !m.isEmpty && !m.hasPrefix("(") && !seen.contains(m) {
            seen.insert(m); out.append(m)
        }
        return out
    }

    /// 某个项目在某个岗位上：跟随全局 / 本项目专用。
    public func badge(project: String, role: String) -> String {
        guard let p = projects.first(where: { $0.code == project }) else { return TeamCard.followGlobal }
        return p.overrides[role] == nil ? TeamCard.followGlobal : TeamCard.projectOnly
    }

    /// 侧栏角标：要老板动手的卡片数（停了的、没登录的）+ 新模型建议。
    public var attention: Int {
        cards.filter { TeamLight.of($0.status.code) == .red }.count + (suggestions.isEmpty ? 0 : 1)
    }
}

public struct TeamProject: Decodable, Equatable, Sendable {
    public var code: String
    public var name: String
    /// 岗位 → 本项目改了什么（模型、思考档位、试用…）；没有的岗位就是跟随全局。
    public var overrides: [String: Override]

    public struct Override: Decodable, Equatable, Sendable {
        public var models: [String]?
        public var thinking: String?
        public var tool: String?
        public var trialModel: String?
        enum CodingKeys: String, CodingKey { case models, thinking, tool, trial }
        struct Trial: Decodable { var model: String? }
        public init(models: [String]? = nil, thinking: String? = nil, tool: String? = nil, trialModel: String? = nil) {
            self.models = models; self.thinking = thinking; self.tool = tool; self.trialModel = trialModel
        }
        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            models = (try? c.decodeIfPresent([String].self, forKey: .models))
            thinking = (try? c.decodeIfPresent(String.self, forKey: .thinking))
            tool = (try? c.decodeIfPresent(String.self, forKey: .tool))
            trialModel = ((try? c.decodeIfPresent(Trial.self, forKey: .trial)) ?? nil)?.model
        }
    }

    enum CodingKeys: String, CodingKey { case code, name, overrides }

    public init(code: String, name: String, overrides: [String: Override] = [:]) {
        self.code = code; self.name = name; self.overrides = overrides
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        code = try c.decode(String.self, forKey: .code)
        name = (try? c.decodeIfPresent(String.self, forKey: .name)) ?? code
        overrides = (try? c.decodeIfPresent([String: Override].self, forKey: .overrides)) ?? [:]
    }
}

/// 一个模型在一个岗位上的成绩（施工和验收字段不同，都可缺）。
public struct ModelStats: Decodable, Equatable, Sendable {
    public var items: Int?
    public var runs: Int?
    public var verifyRejectRate: Double?
    public var reworkPerItem: Double?
    public var lookRejectRate: Double?
    public var minutesPerItem: Double?
    public var noLivePath: Int?
    public var passes: Int?
    public var rejects: Int?
    public var escaped: Int?
    public var escapeRate: Double?

    enum CodingKeys: String, CodingKey {
        case items, runs, passes, rejects, escaped
        case verifyRejectRate = "verify_reject_rate", reworkPerItem = "rework_per_item", lookRejectRate = "look_reject_rate"
        case minutesPerItem = "minutes_per_item", noLivePath = "no_live_path", escapeRate = "escape_rate"
    }

    public init(items: Int? = nil, runs: Int? = nil, verifyRejectRate: Double? = nil, reworkPerItem: Double? = nil,
                lookRejectRate: Double? = nil, minutesPerItem: Double? = nil, noLivePath: Int? = nil,
                passes: Int? = nil, rejects: Int? = nil, escaped: Int? = nil, escapeRate: Double? = nil) {
        self.items = items; self.runs = runs; self.verifyRejectRate = verifyRejectRate; self.reworkPerItem = reworkPerItem
        self.lookRejectRate = lookRejectRate; self.minutesPerItem = minutesPerItem; self.noLivePath = noLivePath
        self.passes = passes; self.rejects = rejects; self.escaped = escaped; self.escapeRate = escapeRate
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        func i(_ k: CodingKeys) -> Int? {
            if let v = (try? c.decodeIfPresent(Int.self, forKey: k)) ?? nil { return v }
            if let v = (try? c.decodeIfPresent(Double.self, forKey: k)) ?? nil { return Int(v) }
            return nil
        }
        func f(_ k: CodingKeys) -> Double? { (try? c.decodeIfPresent(Double.self, forKey: k)) ?? nil }
        items = i(.items); runs = i(.runs); passes = i(.passes); rejects = i(.rejects); escaped = i(.escaped); noLivePath = i(.noLivePath)
        verifyRejectRate = f(.verifyRejectRate); reworkPerItem = f(.reworkPerItem); lookRejectRate = f(.lookRejectRate)
        minutesPerItem = f(.minutesPerItem); escapeRate = f(.escapeRate)
    }

    static func pct(_ v: Double) -> String { "\(Int((v * 100).rounded()))%" }

    /// 一行大白话：施工看打回和返工，验收看漏放（放过去又被你打回）。
    public func line(role: String) -> String {
        var p: [String] = []
        if role == "verify" {
            if let r = runs { p.append("验了 \(r) 次") }
            if let r = rejects { p.append("打回 \(r)") }
            if let e = escaped { p.append("漏放 \(e)" + (escapeRate.map { "（\(Self.pct($0))）" } ?? "")) }
        } else {
            if let n = items { p.append("\(n) 件") }
            if let v = verifyRejectRate { p.append("验收打回 \(Self.pct(v))") }
            if let r = reworkPerItem { p.append("每件返工 \(r == r.rounded() ? String(Int(r)) : String(format: "%.1f", r)) 轮") }
            if let l = lookRejectRate { p.append("看效果打回 \(Self.pct(l))") }
            if let m = minutesPerItem { p.append("\(Int(m.rounded())) 分钟/件") }
            if let n = noLivePath, n > 0 { p.append("没活路 \(n) 次") }
        }
        return p.isEmpty ? "还没有数据" : p.joined(separator: " · ")
    }
}

/// 一张岗位卡片。
public struct TeamCard: Decodable, Equatable, Sendable, Identifiable {
    public static let followGlobal = "跟随全局"
    public static let projectOnly = "本项目专用"

    public var id: String { role }
    public var role: String
    public var name: String
    public var tool: String
    public var via: String
    public var models: [String]
    public var thinking: String?
    public var duty: String?
    public var account: String?
    public var configured: Bool
    public var fallback: Fallback?
    public var status: Status
    public var warnings: [String]
    public var stats: [String: ModelStats]
    public var recommendation: String
    public var switchTo: String?
    public var usageRuns: Int?
    public var usageMinutes: Double?
    public var badge: String?
    public var trial: Trial?

    public struct Fallback: Decodable, Equatable, Sendable {
        public var tool: String
        public var models: [String]
        public init(tool: String, models: [String]) { self.tool = tool; self.models = models }
        enum CodingKeys: String, CodingKey { case tool, models }
        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            tool = (try? c.decodeIfPresent(String.self, forKey: .tool)) ?? ""
            models = (try? c.decodeIfPresent([String].self, forKey: .models)) ?? []
        }
    }

    public struct Status: Decodable, Equatable, Sendable {
        public var code: String
        public var label: String
        public var until: String?
        public var why: String?
        public init(code: String, label: String, until: String? = nil, why: String? = nil) {
            self.code = code; self.label = label; self.until = until; self.why = why
        }
    }

    public struct Trial: Decodable, Equatable, Sendable {
        public var model: String
        public var base: String?
        public var needed: Int
        public var done: Int
        public init(model: String, base: String? = nil, needed: Int, done: Int) {
            self.model = model; self.base = base; self.needed = needed; self.done = done
        }
    }

    struct Recommendation: Decodable { var text: String?; var switch_to: String? }
    struct Usage: Decodable { var runs: Int?; var minutes: Double? }

    enum CodingKeys: String, CodingKey {
        case role, name, tool, via, models, thinking, duty, account, configured, fallback, status, warnings, stats, recommendation, badge, trial
        case usageWeek = "usage_week"
    }

    public init(role: String, name: String, tool: String, via: String = "cli", models: [String] = [], thinking: String? = nil,
                duty: String? = nil, account: String? = nil, configured: Bool = true, fallback: Fallback? = nil,
                status: Status = Status(code: "ok", label: "可用"), warnings: [String] = [], stats: [String: ModelStats] = [:],
                recommendation: String = "", switchTo: String? = nil, usageRuns: Int? = nil, usageMinutes: Double? = nil,
                badge: String? = nil, trial: Trial? = nil) {
        self.role = role; self.name = name; self.tool = tool; self.via = via; self.models = models; self.thinking = thinking
        self.duty = duty; self.account = account; self.configured = configured; self.fallback = fallback; self.status = status
        self.warnings = warnings; self.stats = stats; self.recommendation = recommendation; self.switchTo = switchTo
        self.usageRuns = usageRuns; self.usageMinutes = usageMinutes; self.badge = badge; self.trial = trial
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        role = try c.decode(String.self, forKey: .role)
        name = (try? c.decodeIfPresent(String.self, forKey: .name)) ?? TeamCard.roleName(role)
        tool = (try? c.decodeIfPresent(String.self, forKey: .tool)) ?? ""
        via = (try? c.decodeIfPresent(String.self, forKey: .via)) ?? "cli"
        models = (try? c.decodeIfPresent([String].self, forKey: .models)) ?? []
        thinking = (try? c.decodeIfPresent(String.self, forKey: .thinking))
        duty = (try? c.decodeIfPresent(String.self, forKey: .duty))
        account = (try? c.decodeIfPresent(String.self, forKey: .account))
        configured = (try? c.decodeIfPresent(Bool.self, forKey: .configured)) ?? true
        fallback = (try? c.decodeIfPresent(Fallback.self, forKey: .fallback))
        status = (try? c.decodeIfPresent(Status.self, forKey: .status)) ?? Status(code: "ok", label: "可用")
        warnings = (try? c.decodeIfPresent([String].self, forKey: .warnings)) ?? []
        let st = (try? c.decodeIfPresent([String: Lenient.Maybe<ModelStats>].self, forKey: .stats)) ?? [:]
        stats = st.compactMapValues(\.value)
        let r = (try? c.decodeIfPresent(Recommendation.self, forKey: .recommendation))
        recommendation = r?.text ?? ""
        switchTo = r?.switch_to
        let u = (try? c.decodeIfPresent(Usage.self, forKey: .usageWeek))
        usageRuns = u?.runs; usageMinutes = u?.minutes
        badge = (try? c.decodeIfPresent(String.self, forKey: .badge))
        trial = (try? c.decodeIfPresent(Trial.self, forKey: .trial))
    }

    public static func roleName(_ role: String) -> String {
        ["build": "施工", "verify": "验收", "decide": "决策"][role] ?? role
    }

    /// 「codex · gpt-5」「dsh · group/evo-build」；没写模型就是工具默认。
    public var modelLine: String {
        "\(tool.isEmpty ? "?" : tool) · " + (models.isEmpty ? "工具默认模型" : models.joined(separator: " / "))
    }

    public var fallbackLine: String? {
        guard let f = fallback else { return nil }
        return "备用：\(f.tool.isEmpty ? "?" : f.tool) · " + (f.models.isEmpty ? "工具默认模型" : f.models.joined(separator: " / "))
    }

    /// 本周用量一行（按订阅账号）。
    public var usageLine: String? {
        guard let r = usageRuns else { return nil }
        return "本周 \(r) 次 · \(Int((usageMinutes ?? 0).rounded())) 分钟" + (account.map { "（\($0)）" } ?? "")
    }
}

/// 状态灯颜色：绿 = 可用；黄 = 用备用 / 额度满（会自己恢复）；红 = 要你动手；灰 = 没配置。
public enum TeamLight: Equatable, Sendable {
    case green, amber, red, gray

    public static func of(_ code: String) -> TeamLight {
        switch code {
        case "ok": return .green
        case "fallback", "rate_limited": return .amber
        case "off": return .gray
        default: return .red      // not_installed / not_logged_in / retired / unknown_model / overlap / magpie_down
        }
    }

    /// 灯旁边那句：「额度满 · 17:00 恢复」。跨天写日期。
    public static func text(_ s: TeamCard.Status, now: Date = Date(), calendar: Calendar = .current) -> String {
        guard let u = s.until, let t = parseISO(u) else { return s.label }
        let f = DateFormatter()
        f.locale = Locale(identifier: "zh_CN")
        f.timeZone = calendar.timeZone
        f.dateFormat = calendar.isDate(t, inSameDayAs: now) ? "HH:mm" : "MM-dd HH:mm"
        return "\(s.label) · \(f.string(from: t)) 恢复"
    }

    static func parseISO(_ s: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: s)
    }
}

/// 一次换模型（或思考档位、或试用）：确认卡上的那句话 + 要跑的 evo 参数。
public struct TeamChange: Equatable, Sendable, Identifiable {
    public enum Kind: String, Equatable, Sendable { case model, thinking, trial }
    public var id: String { "\(kind.rawValue)/\(role)/\(value)/\(project ?? "*")" }
    public var role: String
    public var kind: Kind
    public var value: String
    public var project: String?

    public init(role: String, kind: Kind = .model, value: String, project: String? = nil) {
        self.role = role; self.kind = kind; self.value = value; self.project = project
    }

    /// 模型名只许字母数字和 . _ : / @ + -（会进工人命令行），和 evo 那边一致。
    public static func validModel(_ m: String) -> Bool {
        guard let f = m.unicodeScalars.first, m.count <= 128,
              CharacterSet.alphanumerics.contains(f), f.isASCII else { return false }
        let ok = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/@+-")
        return m.unicodeScalars.allSatisfy { ok.contains($0) }
    }

    public var args: [String] {
        switch kind {
        case .model: return ["team", "set", role, "--model", value] + (project.map { ["--project", $0] } ?? [])
        case .thinking: return ["team", "set", role, "--thinking", value] + (project.map { ["--project", $0] } ?? [])
        case .trial: return ["team", "trial", role, value, "--project", project ?? ""]
        }
    }

    /// 确认卡上那句。current = 这张卡现在的模型（或档位）。
    public func confirmText(current: String?) -> String {
        let r = TeamCard.roleName(role)
        let scope = project.map { "只改 \($0)（本项目专用）" } ?? "全局，所有跟随全局的项目一起换"
        switch kind {
        case .model:
            return "把\(r)" + (current.map { "从 \($0) " } ?? "") + "换成 \(value)？\(scope)。下一次派工生效，正在跑的不打断。"
        case .thinking:
            return "把\(r)的思考档位" + (current.map { "从 \($0) " } ?? "") + "调到 \(value)？\(scope)。下一次派工生效。"
        case .trial:
            return "在 \(project ?? "?") 让\(r)试用 \(value) 几件？满了给你对比，留不留你再点。"
        }
    }
}

/// 输入框里的「把验收换成 X」。认得：把施工/验收/决策（岗/模型）换成|改成|改用 X；前面可带「本项目」或项目代号。
public enum TeamIntent {
    public static let roles: [String: String] = ["施工": "build", "验收": "verify", "决策": "decide"]

    public static func parse(_ text: String, currentProject: String? = nil, projects: [String] = []) -> TeamChange? {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let pattern = #"^(本项目|这个项目|[A-Z]{2,4})?\s*(?:的|里)?\s*把?\s*(施工|验收|决策)(?:岗)?(?:的)?(?:模型)?\s*(?:换成|改成|改用|换到)\s*(\S+)\s*$"#
        guard let re = try? NSRegularExpression(pattern: pattern) else { return nil }
        let ns = NSRange(t.startIndex..<t.endIndex, in: t)
        guard let m = re.firstMatch(in: t, range: ns), m.numberOfRanges == 4 else { return nil }
        func g(_ i: Int) -> String? {
            guard let r = Range(m.range(at: i), in: t) else { return nil }
            return String(t[r])
        }
        guard let roleWord = g(2), let role = roles[roleWord], let model = g(3), TeamChange.validModel(model) else { return nil }
        var project: String? = nil
        if let p = g(1) {
            if p == "本项目" || p == "这个项目" {
                guard let c = currentProject else { return nil }
                project = c
            } else {
                guard projects.isEmpty || projects.contains(p) else { return nil }
                project = p
            }
        }
        return TeamChange(role: role, kind: .model, value: model, project: project)
    }
}

/// 向导「岗位卡片」一步：`evo team init --json` 给的提案。
public struct TeamProposal: Decodable, Equatable, Sendable {
    public var cards: [String: Card]
    public var notes: [String]
    public var magpieOK: Bool
    public var groups: [String]

    public struct Card: Decodable, Equatable, Sendable {
        public var tool: String
        public var models: [String]
        public var thinking: String?
        public var fallback: TeamCard.Fallback?
        public init(tool: String, models: [String] = [], thinking: String? = nil, fallback: TeamCard.Fallback? = nil) {
            self.tool = tool; self.models = models; self.thinking = thinking; self.fallback = fallback
        }
    }

    struct Magpie: Decodable { var ok: Bool?; var groups: [String]? }
    enum CodingKeys: String, CodingKey { case cards, notes, magpie }

    public init(cards: [String: Card], notes: [String] = [], magpieOK: Bool = false, groups: [String] = []) {
        self.cards = cards; self.notes = notes; self.magpieOK = magpieOK; self.groups = groups
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        cards = (try? c.decodeIfPresent([String: Card].self, forKey: .cards)) ?? [:]
        notes = (try? c.decodeIfPresent([String].self, forKey: .notes)) ?? []
        let m = (try? c.decodeIfPresent(Magpie.self, forKey: .magpie))
        magpieOK = m?.ok ?? false
        groups = m?.groups ?? []
    }

    public static func decode(_ s: String) throws -> TeamProposal { try JSONDecoder().decode(TeamProposal.self, from: Data(s.utf8)) }

    /// 按施工、验收、决策的顺序，一张卡一行。
    public var lines: [String] {
        ["build", "verify", "decide"].compactMap { r in
            guard let c = cards[r] else { return nil }
            var s = "\(TeamCard.roleName(r))：\(c.tool) · " + (c.models.isEmpty ? "工具默认模型" : c.models.joined(separator: " / "))
            if let t = c.thinking { s += " · 思考 \(t)" }
            if let f = c.fallback { s += "，备用 \(f.tool)" + (f.models.isEmpty ? "" : " · " + f.models.joined(separator: " / ")) }
            return s
        }
    }
}
