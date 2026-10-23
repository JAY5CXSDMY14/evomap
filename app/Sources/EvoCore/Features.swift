import Foundation

// 第十八轮：功能注册表、按 settings schema 自动画的表单、evo watch 事件流、页的错误边界（纯逻辑，Linux 上也能 swift test）。
// 格式见 docs/app-contract.md 第十八轮小节、kit/schemas/feature-list.schema.json、kit/schemas/event.schema.json。

// MARK: - evo feature list --json

public struct FeatureList: Decodable, Equatable, Sendable {
    public var schemaVersion: Int
    public var api: String?
    public var preset: String
    public var fileError: String?
    public var features: [FeatureInfo]

    enum CodingKeys: String, CodingKey { case schemaVersion = "schema_version", api, preset, fileError = "file_error", features }

    public init(features: [FeatureInfo], preset: String = "all", fileError: String? = nil) {
        schemaVersion = 1; api = "1.0"; self.preset = preset; self.fileError = fileError; self.features = features
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        schemaVersion = (try? c.decodeIfPresent(Int.self, forKey: .schemaVersion)) ?? 1
        api = try? c.decodeIfPresent(String.self, forKey: .api)
        preset = (try? c.decodeIfPresent(String.self, forKey: .preset)) ?? "all"
        fileError = try? c.decodeIfPresent(String.self, forKey: .fileError)
        features = ((try? c.decode([Lenient.Maybe<FeatureInfo>].self, forKey: .features)) ?? []).compactMap(\.value)
    }

    public static func decode(_ text: String) throws -> FeatureList { try JSONDecoder().decode(FeatureList.self, from: Data(text.utf8)) }

    public func feature(_ id: String) -> FeatureInfo? { features.first { $0.id == id } }

    /// 设置区要列的：有设置的、或者能开关的（全部功能都能开关；精简必开的也能关，只有「在用」的关不掉）。
    public var settingsSections: [FeatureInfo] { features }
}

public struct FeaturePart: Decodable, Equatable, Sendable {
    public var slot: String
    public var key: String
    public var title: String?
    public var icon: String?
    public init(slot: String, key: String, title: String? = nil, icon: String? = nil) { self.slot = slot; self.key = key; self.title = title; self.icon = icon }
}

public struct FeatureInfo: Decodable, Equatable, Sendable, Identifiable {
    public var id: String
    public var name: String
    public var sub: String
    public var state: String          // off / pending / active / failed / disposed
    public var why: String
    public var enabled: Bool
    public var essential: Bool
    public var inUse: Int
    public var inUseText: String
    public var parts: [FeaturePart]
    public var settings: SettingsSchema?
    public var config: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case id, name, sub, state, why, enabled, essential, parts, settings, config
        case inUse = "in_use", inUseText = "in_use_text"
    }

    public init(id: String, name: String, sub: String = "", state: String = "active", why: String = "", enabled: Bool = true, essential: Bool = false,
                inUse: Int = 0, inUseText: String = "", parts: [FeaturePart] = [], settings: SettingsSchema? = nil, config: [String: JSONValue] = [:]) {
        self.id = id; self.name = name; self.sub = sub; self.state = state; self.why = why; self.enabled = enabled; self.essential = essential
        self.inUse = inUse; self.inUseText = inUseText; self.parts = parts; self.settings = settings; self.config = config
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = (try? c.decodeIfPresent(String.self, forKey: .name)) ?? id
        sub = (try? c.decodeIfPresent(String.self, forKey: .sub)) ?? ""
        state = (try? c.decodeIfPresent(String.self, forKey: .state)) ?? "active"
        why = (try? c.decodeIfPresent(String.self, forKey: .why)) ?? ""
        enabled = (try? c.decodeIfPresent(Bool.self, forKey: .enabled)) ?? true
        essential = (try? c.decodeIfPresent(Bool.self, forKey: .essential)) ?? false
        inUse = (try? c.decodeIfPresent(Int.self, forKey: .inUse)) ?? 0
        inUseText = (try? c.decodeIfPresent(String.self, forKey: .inUseText)) ?? ""
        parts = ((try? c.decode([Lenient.Maybe<FeaturePart>].self, forKey: .parts)) ?? []).compactMap(\.value)
        settings = (try? c.decodeIfPresent(SettingsSchema.self, forKey: .settings)) ?? nil
        config = (try? c.decodeIfPresent([String: JSONValue].self, forKey: .config)) ?? [:]
    }

    public var active: Bool { state == "active" }
    /// 关不掉：正在用。
    public var locked: Bool { inUse > 0 && enabled }
    public var hasPage: Bool { parts.contains { $0.slot == "page" } }

    /// 状态角标：「开着」「关着」「出错」「等服务」。
    public var badge: (text: String, tone: CardTone) {
        switch state {
        case "active": return ("开着", .success)
        case "failed": return ("出错", .danger)
        case "pending": return ("等服务", .warning)
        default: return ("关着", .neutral)
        }
    }

    /// 开关下面那行小字。
    public var note: String {
        if locked { return "正在用（\(inUseText)），关不掉" }
        if state == "failed" || state == "pending" { return why }
        return sub
    }

    public func value(_ field: SettingField) -> JSONValue { config[field.key] ?? field.defaultValue }
}

// MARK: - settings schema → 表单

public struct SettingsSchema: Decodable, Equatable, Sendable {
    public var fields: [SettingField]

    enum CodingKeys: String, CodingKey { case properties, order = "x-order" }

    public init(fields: [SettingField]) { self.fields = fields }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        let props = (try? c.decode([String: Lenient.Maybe<SettingField.Raw>].self, forKey: .properties)) ?? [:]
        let order = (try? c.decodeIfPresent([String].self, forKey: .order)) ?? nil
        let keys = (order ?? []).filter { props[$0] != nil } + props.keys.sorted().filter { !(order ?? []).contains($0) }
        fields = keys.compactMap { k in props[k]?.value.flatMap { SettingField(key: k, raw: $0) } }
    }
}

public struct SettingField: Equatable, Sendable, Identifiable {
    public enum Kind: String, Sendable { case boolean, integer, number, string }
    public var id: String { key }
    public var key: String
    public var kind: Kind
    public var title: String
    public var description: String?
    public var options: [JSONValue]?       // enum：画成一排按钮
    public var minimum: Double?
    public var maximum: Double?
    public var defaultValue: JSONValue

    struct Raw: Decodable {
        var type: String
        var title: String?
        var description: String?
        var `enum`: [JSONValue]?
        var minimum: Double?
        var maximum: Double?
        var `default`: JSONValue?
    }

    init?(key: String, raw: Raw) {
        guard let k = Kind(rawValue: raw.type) else { return nil }       // 画不出来的类型不画
        self.init(key: key, kind: k, title: raw.title ?? key, description: raw.description, options: raw.enum,
                  minimum: raw.minimum, maximum: raw.maximum, defaultValue: raw.default ?? .null)
    }

    public init(key: String, kind: Kind, title: String, description: String? = nil, options: [JSONValue]? = nil,
                minimum: Double? = nil, maximum: Double? = nil, defaultValue: JSONValue) {
        self.key = key; self.kind = kind; self.title = title; self.description = description; self.options = options
        self.minimum = minimum; self.maximum = maximum; self.defaultValue = defaultValue
    }

    /// 表单控件：开关 / 一排按钮（枚举）/ 数字框 / 文本框。
    public enum Control: Equatable, Sendable { case toggle, choice, number, text }
    public var control: Control {
        if options?.isEmpty == false { return .choice }
        switch kind {
        case .boolean: return .toggle
        case .integer, .number: return .number
        case .string: return .text
        }
    }

    /// 文本框里的字 → 值；不合 schema 返回原因（显示在框下面，红字）。
    public func parse(_ text: String) -> Result<JSONValue, SettingError> {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        switch kind {
        case .boolean:
            if ["true", "开", "1", "on"].contains(t.lowercased()) { return .success(.bool(true)) }
            if ["false", "关", "0", "off"].contains(t.lowercased()) { return .success(.bool(false)) }
            return .failure(SettingError(message: "要是开或关"))
        case .integer:
            guard let n = Int(t) else { return .failure(SettingError(message: "要是整数")) }
            return range(Double(n)).map { _ in .number(Double(n)) }
        case .number:
            guard let n = Double(t), n.isFinite else { return .failure(SettingError(message: "要是数字")) }
            return range(n).map { _ in .number(n) }
        case .string:
            if let o = options, !o.contains(.string(t)) { return .failure(SettingError(message: "只能是 " + o.map(Self.text).joined(separator: " / "))) }
            return .success(.string(t))
        }
    }

    private func range(_ n: Double) -> Result<Void, SettingError> {
        if let lo = minimum, n < lo { return .failure(SettingError(message: "不能小于 \(Self.text(.number(lo)))")) }
        if let hi = maximum, n > hi { return .failure(SettingError(message: "不能大于 \(Self.text(.number(hi)))")) }
        return .success(())
    }

    /// 值 → 框里 / 按钮上显示的字。
    public static func text(_ v: JSONValue) -> String {
        switch v {
        case .bool(let b): return b ? "true" : "false"
        case .number(let n): return n == n.rounded() && abs(n) < 1e15 ? String(Int64(n)) : String(n)
        case .string(let s): return s
        case .null: return ""
        default: return v.jsonText
        }
    }

    /// `evo feature set <id> key=value` 的 key=value。
    public func cliArg(_ v: JSONValue) -> String { "\(key)=\(Self.text(v))" }

    /// 范围说明（数字框旁边的小字）。
    public var rangeText: String? {
        switch (minimum, maximum) {
        case let (lo?, hi?): return "\(Self.text(.number(lo)))–\(Self.text(.number(hi)))"
        case let (lo?, nil): return "≥ \(Self.text(.number(lo)))"
        case let (nil, hi?): return "≤ \(Self.text(.number(hi)))"
        default: return nil
        }
    }
}

public struct SettingError: Error, Equatable, Sendable {
    public var message: String
    public init(message: String) { self.message = message }
}

// MARK: - 要跑的 evo 命令

public enum FeatureCommand {
    public static func list() -> [String] { ["feature", "list", "--json"] }
    public static func toggle(_ id: String, on: Bool) -> [String] { ["feature", on ? "on" : "off", id] }
    public static func set(_ id: String, _ field: SettingField, _ v: JSONValue) -> [String] { ["feature", "set", id, field.cliArg(v)] }
}

// MARK: - 功能注册表：侧栏页 / 设置区跟着 evo 返回的功能列表走

public struct FeatureRegistry: Equatable, Sendable {
    public var list: FeatureList?
    public init(_ list: FeatureList?) { self.list = list }

    /// 内置页（team…）显示不显示：老 evo 没有 feature 命令（list 为 nil）→ 照旧都显示；
    /// 有列表 → 声明了这个页的功能包开着才显示；没有功能包声明它 → 内核的页，一直显示。
    public func pageVisible(_ key: String) -> Bool {
        guard let l = list else { return true }
        let owners = l.features.filter { f in f.parts.contains { $0.slot == "page" && $0.key == key } }
        if owners.isEmpty { return true }
        return owners.contains { $0.active }
    }

    /// 某个功能开着吗（老 evo 一律当开着）。
    public func active(_ id: String) -> Bool { list?.feature(id)?.active ?? (list == nil) }
}

// MARK: - evo watch --json（行分隔 JSON 事件流）

public struct WatchEvent: Decodable, Equatable, Sendable {
    public var schemaVersion: Int
    public var event: String
    public var project: String?
    public var item: String?
    enum CodingKeys: String, CodingKey { case schemaVersion = "schema_version", event, project, item }
    public init(event: String, project: String? = nil, item: String? = nil) { schemaVersion = 1; self.event = event; self.project = project; self.item = item }
    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        schemaVersion = (try? c.decodeIfPresent(Int.self, forKey: .schemaVersion)) ?? 1
        event = try c.decode(String.self, forKey: .event)
        project = try? c.decodeIfPresent(String.self, forKey: .project)
        item = try? c.decodeIfPresent(String.self, forKey: .item)
    }

    /// 要不要因为它刷新：保活 ping、不认识的大版本不刷。
    public var triggersRefresh: Bool { event != "watch.ping" && schemaVersion == ContractCheck.supported }
    /// 要不要连功能列表一起重读。
    public var touchesFeatures: Bool { event.hasPrefix("feature.") || event == "self.upgraded" }
}

/// 把子进程 stdout 的字节流切成行、解成事件（半行留到下次）。
public struct WatchParser: Sendable {
    private var buffer = ""
    public init() {}

    public mutating func feed(_ chunk: String) -> [WatchEvent] {
        buffer += chunk
        var out: [WatchEvent] = []
        while let r = buffer.range(of: "\n") {
            let line = String(buffer[buffer.startIndex..<r.lowerBound]).trimmingCharacters(in: .whitespaces)
            buffer = String(buffer[r.upperBound...])
            if line.hasPrefix("{"), let e = try? JSONDecoder().decode(WatchEvent.self, from: Data(line.utf8)) { out.append(e) }
        }
        return out
    }
}

/// 订阅事件流后的轮询策略：事件流活着（最近 45 秒内有过一行，含 ping）→ 只做 2 分钟一次的兜底轮询；死了 → 回到 30 秒轮询。
public enum WatchPolicy {
    public static let pollSeconds: Double = 30
    public static let fallbackSeconds: Double = 120
    public static let aliveWindow: Double = 45
    public static let debounce: Double = 1.2

    public static func alive(lastLine: Date?, now: Date = Date()) -> Bool {
        guard let l = lastLine else { return false }
        return now.timeIntervalSince(l) < aliveWindow
    }

    /// 定时器每 30 秒叫一次：这次要不要真刷新。
    public static func shouldPoll(lastRefresh: Date?, lastLine: Date?, now: Date = Date()) -> Bool {
        guard let r = lastRefresh else { return true }
        let gap = alive(lastLine: lastLine, now: now) ? fallbackSeconds : pollSeconds
        return now.timeIntervalSince(r) >= gap - 1
    }

    /// 子进程退了多久再起（5、10、20…最多 60 秒）。
    public static func restartDelay(failures: Int) -> Double { min(60, 5 * pow(2, Double(max(0, failures - 1)))) }
}

// MARK: - 页的错误边界（照 magpie 窗口内核：一页坏了只坏这一页，卡片上「这页出错了」+ 重试）

public struct PageError: Equatable, Sendable {
    public var title: String
    public var message: String
    public init(message: String, title: String = "这页出错了") {
        self.title = title
        let t = message.trimmingCharacters(in: .whitespacesAndNewlines)
        self.message = t.isEmpty ? "evo 没有回话（退出码非 0）" : String(t.suffix(400))
    }
}

// MARK: - 0.7.0：功能注册表补充（页可见性回退、设置分组）

public extension FeatureRegistry {
    /// 侧栏「团队」显示吗（功能包 team 声明了 page:team）。
    var teamVisible: Bool { pageVisible("team") }

    /// 选中的页被关掉了：退回「等你处理」；没关就原样。
    func fallback(_ sel: SidebarItem) -> SidebarItem {
        switch sel {
        case .team: return teamVisible ? sel : .inbox
        default: return sel
        }
    }

    /// 设置页「功能」卡片里的行：管侧栏页的排最前（开关一拨侧栏就变），再是有设置的（老板常改），其余按 id。老 evo 没有列表 → 空。
    var settingsRows: [FeatureInfo] {
        guard let l = list else { return [] }
        func rank(_ f: FeatureInfo) -> Int { f.hasPage ? 0 : (f.settings?.fields.isEmpty == false ? 1 : 2) }
        return l.features.enumerated().sorted { (rank($0.element), $0.offset) < (rank($1.element), $1.offset) }.map(\.element)
    }

    /// 给人看的一句汇总：「12 个功能，开着 11 个」。
    var summary: String {
        guard let l = list else { return "这版 evo 没有功能开关（evo feature），所有功能照旧都开着" }
        let on = l.features.filter(\.active).count
        var s = "\(l.features.count) 个功能，开着 \(on) 个 · 预设 \(l.preset == "essentials" ? "精简" : "全部")"
        if let e = l.fileError, !e.isEmpty { s += " · features.yml 坏了（\(e)），现在按全开跑" }
        return s
    }
}

// MARK: - 0.7.0：按 settings schema 画的表单的草稿状态

/// 一个功能的设置表单：文本框里的草稿、红字错误；提交得到要跑的 evo 命令。开关 / 枚举按钮不走草稿，点了就提交。
public struct FeatureForm: Equatable, Sendable {
    public let featureID: String
    public private(set) var drafts: [String: String] = [:]
    public private(set) var errors: [String: String] = [:]

    public init(_ f: FeatureInfo) {
        featureID = f.id
        for fld in f.settings?.fields ?? [] { drafts[fld.key] = SettingField.text(f.value(fld)) }
    }

    public func draft(_ key: String) -> String { drafts[key] ?? "" }
    public func error(_ key: String) -> String? { errors[key] }

    public mutating func edit(_ key: String, _ text: String) { drafts[key] = text; errors[key] = nil }

    /// 草稿和 evo 现在存的值不一样（显示「存」按钮）。
    public func dirty(_ field: SettingField, in f: FeatureInfo) -> Bool {
        guard let d = drafts[field.key] else { return false }
        if case .success(let v) = field.parse(d) { return v != f.value(field) }
        return d.trimmingCharacters(in: .whitespacesAndNewlines) != SettingField.text(f.value(field))
    }

    /// 提交文本框：合 schema → 返回 `evo feature set` 的参数；不合 → 记下红字，返回 nil。
    public mutating func commit(_ field: SettingField) -> [String]? {
        switch field.parse(draft(field.key)) {
        case .success(let v): errors[field.key] = nil; return FeatureCommand.set(featureID, field, v)
        case .failure(let e): errors[field.key] = e.message; return nil
        }
    }

    /// 开关 / 枚举按钮：直接给值。
    public mutating func choose(_ field: SettingField, _ v: JSONValue) -> [String] {
        drafts[field.key] = SettingField.text(v); errors[field.key] = nil
        return FeatureCommand.set(featureID, field, v)
    }

    /// evo 拒了（比如范围是 evo 那边更严）：把 evo 的话挂到这个字段下面。
    public mutating func reject(_ key: String, _ message: String) {
        let t = message.trimmingCharacters(in: .whitespacesAndNewlines)
        errors[key] = t.isEmpty ? "evo 没存上" : String(t.suffix(200))
    }

    /// evo 重新读回来以后：没在改的字段跟上新值（正在改、或有红字的不动）。
    public mutating func sync(_ f: FeatureInfo, editing: String? = nil) {
        for fld in f.settings?.fields ?? [] where fld.key != editing && errors[fld.key] == nil {
            drafts[fld.key] = SettingField.text(f.value(fld))
        }
    }
}

// MARK: - 0.7.0：事件流连接状态（evo watch --json 子进程）

public struct WatchLink: Equatable, Sendable {
    public private(set) var connectedAt: Date?
    public private(set) var lastLine: Date?
    public private(set) var failures = 0
    public private(set) var events = 0

    public init() {}

    public mutating func started(_ now: Date = Date()) { connectedAt = now }

    public mutating func received(_ lines: Int = 1, at now: Date = Date()) {
        lastLine = now; events += lines
    }

    /// 子进程退了：返回几秒后重起。活过 60 秒才算「正常断线」，失败计数清零；起不来（老 evo 没有 watch）一路退避到 60 秒。
    public mutating func exited(_ now: Date = Date()) -> Double {
        if let c = connectedAt, now.timeIntervalSince(c) > 60 { failures = 0 }
        connectedAt = nil
        failures += 1
        return WatchPolicy.restartDelay(failures: failures)
    }

    public func alive(_ now: Date = Date()) -> Bool { connectedAt != nil && WatchPolicy.alive(lastLine: lastLine, now: now) }

    /// 设置页那一行。
    public func statusText(_ now: Date = Date()) -> String {
        if alive(now) { return "事件流已连上（evo watch --json）：有动静马上刷新，另外每 \(Int(WatchPolicy.fallbackSeconds / 60)) 分钟兜底轮询一次" }
        if failures >= 3 { return "事件流连不上（老版本 evo 没有 watch？）：每 \(Int(WatchPolicy.pollSeconds)) 秒轮询，不影响使用" }
        return "事件流没连上：先每 \(Int(WatchPolicy.pollSeconds)) 秒轮询，断线后自动重连"
    }
}

// MARK: - 0.7.0：每页的错误边界

/// 各页现在的错误（AppState 里收集来），决定这页画内容还是画「这页出错了 + 重试」卡片。
public struct PageErrors: Equatable, Sendable {
    public var team: String?
    public var projects: [String: String] = [:]     // 项目代号 → status 读不出来的原因
    public var logs: [String: String] = [:]         // 「项目/件号」→ log 读不出来的原因
    public var features: String?                    // feature list 读不出来（设置页里只坏「功能」这一块）
    public init(team: String? = nil, projects: [String: String] = [:], logs: [String: String] = [:], features: String? = nil) {
        self.team = team; self.projects = projects; self.logs = logs; self.features = features
    }
}

public enum PageBoundary {
    /// 这页要不要画错误卡片。等你处理 / 卡太久是跨项目汇总页，某个项目坏了只在它自己的格子里标红，不整页挡住；
    /// 设置页永远能打开（evo 路径填错了要靠它改回来）。
    public static func error(for sel: SidebarItem, _ e: PageErrors) -> PageError? {
        switch sel {
        case .team: return e.team.map { PageError(message: $0, title: "团队页出错了") }
        case .project(let c): return e.projects[c].map { PageError(message: $0, title: "项目 \(c) 读不出来") }
        case .item(let p, let k): return e.logs["\(p)/\(k)"].map { PageError(message: $0, title: "\(k) 的时间线读不出来") }
        default: return nil
        }
    }

    /// 卡片上的探点名（CI 截图脚本照它点「重试」）。
    public static let retryProbe = "page-error-retry"
}
