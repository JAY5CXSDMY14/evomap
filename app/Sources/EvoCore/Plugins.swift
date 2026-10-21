import Foundation

// 第十六轮：插件的纯逻辑。`evo plugin list --json` / `evo plugin run … --json` 解码、通用卡片模型、
// 输入框「/名字 参数」的匹配、要跑的 evo 命令行、插件页的三态（空 / 加载 / 报错）。
// 格式见 docs/app-contract.md 和 kit/schemas/（plugin-list、plugin-run、card）；写插件见 docs/plugins.md。

// MARK: - 任意 JSON（按钮的 payload 原样带回给插件）

public indirect enum JSONValue: Codable, Equatable, Sendable {
    case null, bool(Bool), number(Double), string(String), array([JSONValue]), object([String: JSONValue])

    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null; return }
        if let b = try? c.decode(Bool.self) { self = .bool(b); return }
        if let n = try? c.decode(Double.self) { self = .number(n); return }
        if let s = try? c.decode(String.self) { self = .string(s); return }
        if let a = try? c.decode([JSONValue].self) { self = .array(a); return }
        if let o = try? c.decode([String: JSONValue].self) { self = .object(o); return }
        throw DecodingError.dataCorruptedError(in: c, debugDescription: "不是 JSON 值")
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .null: try c.encodeNil()
        case .bool(let b): try c.encode(b)
        case .number(let n):
            if n == n.rounded(), abs(n) < 1e15 { try c.encode(Int64(n)) } else { try c.encode(n) }
        case .string(let s): try c.encode(s)
        case .array(let a): try c.encode(a)
        case .object(let o): try c.encode(o)
        }
    }

    /// 紧凑 JSON 文本（键排序），给 `--payload`。
    public var jsonText: String {
        let e = JSONEncoder()
        e.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return (try? e.encode(self)).map { String(decoding: $0, as: UTF8.self) } ?? "null"
    }
}

// MARK: - plugin list

public struct PluginList: Decodable, Equatable, Sendable {
    public var schemaVersion: Int
    public var evoAPI: String?
    public var pluginsDir: String?
    public var plugins: [PluginInfo]

    enum CodingKeys: String, CodingKey { case schemaVersion = "schema_version", evoAPI = "evo_api", pluginsDir = "plugins_dir", plugins }

    public init(plugins: [PluginInfo], pluginsDir: String? = nil) {
        schemaVersion = 1; evoAPI = "1.0"; self.pluginsDir = pluginsDir; self.plugins = plugins
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        schemaVersion = (try? c.decodeIfPresent(Int.self, forKey: .schemaVersion)) ?? 1
        evoAPI = try? c.decodeIfPresent(String.self, forKey: .evoAPI)
        pluginsDir = try? c.decodeIfPresent(String.self, forKey: .pluginsDir)
        plugins = ((try? c.decode([Lenient.Maybe<PluginInfo>].self, forKey: .plugins)) ?? []).compactMap(\.value)
    }

    public static func decode(_ text: String) throws -> PluginList { try JSONDecoder().decode(PluginList.self, from: Data(text.utf8)) }

    public var active: [PluginInfo] { plugins.filter(\.active) }

    /// 侧栏「插件」分组：打开了的插件的每个侧栏页，按插件名、页的顺序。
    public var sidebarPages: [PluginPageRef] {
        active.flatMap { p in p.contributes.sidebarPages.map { PluginPageRef(plugin: p.name, id: $0.id, title: $0.title, icon: $0.icon) } }
    }

    /// 输入框可用的 /命令（同名时先装的赢，evo 那边每个插件内不重名）。
    public var composerCommands: [PluginComposerRef] {
        var seen = Set<String>(), out: [PluginComposerRef] = []
        for p in active {
            for c in p.contributes.composerCommands where seen.insert(c.name).inserted {
                out.append(PluginComposerRef(plugin: p.name, id: c.id, name: c.name, title: c.title ?? c.name, usage: c.usage))
            }
        }
        return out
    }

    public var itemActions: [PluginItemActionRef] {
        active.flatMap { p in p.contributes.itemActions.map { PluginItemActionRef(plugin: p.name, id: $0.id, title: $0.title, icon: $0.icon) } }
    }

    public func page(_ plugin: String, _ id: String) -> PluginPageRef? { sidebarPages.first { $0.plugin == plugin && $0.id == id } }
}

public struct PluginInfo: Decodable, Equatable, Sendable, Identifiable {
    public var id: String { name }
    public var name: String
    public var version: String?
    public var description: String?
    public var evoAPI: String?
    public var enabled: Bool
    public var valid: Bool
    public var compatible: Bool
    public var active: Bool
    public var errors: [String]
    public var contributes: Contributes

    public struct Contributes: Decodable, Equatable, Sendable {
        public var sidebarPages: [Entry]
        public var composerCommands: [Entry]
        public var notifyChannels: [Entry]
        public var itemActions: [Entry]
        enum CodingKeys: String, CodingKey {
            case sidebarPages = "sidebar_pages", composerCommands = "composer_commands", notifyChannels = "notify_channels", itemActions = "item_actions"
        }
        public init(sidebarPages: [Entry] = [], composerCommands: [Entry] = [], notifyChannels: [Entry] = [], itemActions: [Entry] = []) {
            self.sidebarPages = sidebarPages; self.composerCommands = composerCommands; self.notifyChannels = notifyChannels; self.itemActions = itemActions
        }
        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            func list(_ k: CodingKeys) -> [Entry] { ((try? c.decode([Lenient.Maybe<Entry>].self, forKey: k)) ?? []).compactMap(\.value) }
            sidebarPages = list(.sidebarPages); composerCommands = list(.composerCommands).filter { !$0.name.isEmpty }
            notifyChannels = list(.notifyChannels); itemActions = list(.itemActions)
        }
        /// 「侧栏页 1 · 输入框命令 1 · 通知渠道 1」
        public var summary: String {
            [("侧栏页", sidebarPages.count), ("输入框命令", composerCommands.count), ("通知渠道", notifyChannels.count), ("件按钮", itemActions.count)]
                .filter { $0.1 > 0 }.map { "\($0.0) \($0.1)" }.joined(separator: " · ")
        }
    }

    public struct Entry: Decodable, Equatable, Sendable {
        public var id: String
        public var title: String
        public var name: String
        public var icon: String?
        public var description: String?
        public var usage: String?
        public var events: String?
        enum CodingKeys: String, CodingKey { case id, title, name, icon, description, usage, events }
        public init(id: String, title: String, name: String = "", icon: String? = nil, description: String? = nil, usage: String? = nil, events: String? = nil) {
            self.id = id; self.title = title; self.name = name; self.icon = icon; self.description = description; self.usage = usage; self.events = events
        }
        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            id = try c.decode(String.self, forKey: .id)
            name = (try? c.decodeIfPresent(String.self, forKey: .name)) ?? ""
            title = (try? c.decodeIfPresent(String.self, forKey: .title)) ?? (name.isEmpty ? id : name)
            icon = try? c.decodeIfPresent(String.self, forKey: .icon)
            description = try? c.decodeIfPresent(String.self, forKey: .description)
            usage = try? c.decodeIfPresent(String.self, forKey: .usage)
            events = try? c.decodeIfPresent(String.self, forKey: .events)
        }
    }

    enum CodingKeys: String, CodingKey { case name, version, description, evoAPI = "evo_api", enabled, valid, compatible, active, errors, contributes }

    public init(name: String, version: String? = nil, description: String? = nil, enabled: Bool = false, valid: Bool = true,
                compatible: Bool = true, errors: [String] = [], contributes: Contributes = Contributes()) {
        self.name = name; self.version = version; self.description = description; self.evoAPI = "^1"
        self.enabled = enabled; self.valid = valid; self.compatible = compatible; self.active = enabled && valid && compatible
        self.errors = errors; self.contributes = contributes
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        name = try c.decode(String.self, forKey: .name)
        version = try? c.decodeIfPresent(String.self, forKey: .version)
        description = try? c.decodeIfPresent(String.self, forKey: .description)
        evoAPI = try? c.decodeIfPresent(String.self, forKey: .evoAPI)
        enabled = ((try? c.decodeIfPresent(Bool.self, forKey: .enabled)) ?? nil) ?? false
        valid = ((try? c.decodeIfPresent(Bool.self, forKey: .valid)) ?? nil) ?? false
        compatible = ((try? c.decodeIfPresent(Bool.self, forKey: .compatible)) ?? nil) ?? false
        // active 以 evo 说的为准；老格式没有就自己算
        active = ((try? c.decodeIfPresent(Bool.self, forKey: .active)) ?? nil) ?? (enabled && valid && compatible)
        errors = ((try? c.decodeIfPresent([String].self, forKey: .errors)) ?? nil) ?? []
        contributes = ((try? c.decodeIfPresent(Contributes.self, forKey: .contributes)) ?? nil) ?? Contributes()
    }

    /// 设置里开关下面那一行。
    public var statusLine: String {
        if !valid { return "plugin.json 不合格：" + (errors.first ?? "?") }
        if !compatible { return "和这版 evo 不兼容（插件要 evo_api \(evoAPI ?? "?")）" }
        let s = contributes.summary
        return [version.map { "v\($0)" }, s.isEmpty ? nil : s].compactMap { $0 }.joined(separator: " · ")
    }

    /// 开关能不能拨：坏的、不兼容的插件拨开也跑不了，只能关。
    public var canEnable: Bool { valid && compatible }
}

public struct PluginPageRef: Hashable, Sendable, Identifiable {
    public var id: String
    public var plugin: String
    public var title: String
    public var icon: String?
    public init(plugin: String, id: String, title: String = "", icon: String? = nil) {
        self.plugin = plugin; self.id = id; self.title = title.isEmpty ? id : title; self.icon = icon
    }
    public var key: String { "\(plugin)/\(id)" }
    public var symbol: String { (icon?.isEmpty == false ? icon : nil) ?? "puzzlepiece.extension" }
}

public struct PluginComposerRef: Equatable, Sendable {
    public var plugin: String
    public var id: String
    public var name: String
    public var title: String
    public var usage: String?
}

public struct PluginItemActionRef: Equatable, Sendable, Identifiable {
    public var plugin: String
    public var id: String
    public var title: String
    public var icon: String?
    public var key: String { "\(plugin)/\(id)" }
    public var symbol: String { (icon?.isEmpty == false ? icon : nil) ?? "puzzlepiece.extension" }
}

// MARK: - 卡片

public struct PluginCard: Decodable, Equatable, Sendable {
    public var title: String
    public var subtitle: String?
    public var blocks: [CardBlock]

    enum CodingKeys: String, CodingKey { case title, subtitle, blocks }

    public init(title: String, subtitle: String? = nil, blocks: [CardBlock] = []) {
        self.title = title; self.subtitle = subtitle; self.blocks = blocks
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        title = ((try? c.decodeIfPresent(String.self, forKey: .title)) ?? nil) ?? ""
        subtitle = try? c.decodeIfPresent(String.self, forKey: .subtitle)
        // 不认识的块（以后的小版本新增）丢掉，不连累整张卡
        blocks = ((try? c.decode([Lenient.Maybe<CardBlock>].self, forKey: .blocks)) ?? []).compactMap(\.value).filter { $0 != .unknown }
    }

    public var isEmpty: Bool { blocks.isEmpty }

    public static func decode(_ text: String) throws -> PluginCard { try JSONDecoder().decode(PluginCard.self, from: Data(text.utf8)) }
}

public enum CardTone: String, Sendable { case neutral, accent, success, warning, danger }

public struct CardListItem: Decodable, Equatable, Sendable {
    public var title: String
    public var subtitle: String?
    public var badge: String?
    public var symbol: String?
    public var tone: CardTone
    enum CodingKeys: String, CodingKey { case title, subtitle, badge, symbol, tone }
    public init(title: String, subtitle: String? = nil, badge: String? = nil, symbol: String? = nil, tone: CardTone = .neutral) {
        self.title = title; self.subtitle = subtitle; self.badge = badge; self.symbol = symbol; self.tone = tone
    }
    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        title = try c.decode(String.self, forKey: .title)
        subtitle = try? c.decodeIfPresent(String.self, forKey: .subtitle)
        badge = try? c.decodeIfPresent(String.self, forKey: .badge)
        symbol = try? c.decodeIfPresent(String.self, forKey: .symbol)
        tone = CardTone(rawValue: ((try? c.decodeIfPresent(String.self, forKey: .tone)) ?? nil) ?? "") ?? .neutral
    }
}

public struct CardButton: Decodable, Equatable, Sendable, Identifiable {
    public var id: String { action + "|" + label }
    public var label: String
    public var action: String
    public var style: String
    public var payload: JSONValue?
    enum CodingKeys: String, CodingKey { case label, action, style, payload }
    public init(label: String, action: String, style: String = "secondary", payload: JSONValue? = nil) {
        self.label = label; self.action = action; self.style = style; self.payload = payload
    }
    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        label = try c.decode(String.self, forKey: .label)
        action = try c.decode(String.self, forKey: .action)
        style = ((try? c.decodeIfPresent(String.self, forKey: .style)) ?? nil) ?? "secondary"
        payload = try? c.decodeIfPresent(JSONValue.self, forKey: .payload)
    }
}

public enum CardBlock: Decodable, Equatable, Sendable {
    case text(String, style: String, tone: CardTone)
    case list([CardListItem])
    case table(columns: [String], rows: [[String]])
    case buttons([CardButton])
    case unknown

    enum CodingKeys: String, CodingKey { case type, text, style, tone, items, columns, rows, buttons }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        let t = (try? c.decode(String.self, forKey: .type)) ?? ""
        switch t {
        case "text":
            let s = try c.decode(String.self, forKey: .text)
            let style = ((try? c.decodeIfPresent(String.self, forKey: .style)) ?? nil) ?? "body"
            let tone = CardTone(rawValue: ((try? c.decodeIfPresent(String.self, forKey: .tone)) ?? nil) ?? "") ?? .neutral
            self = .text(s, style: style, tone: tone)
        case "list":
            self = .list(((try? c.decode([Lenient.Maybe<CardListItem>].self, forKey: .items)) ?? []).compactMap(\.value))
        case "table":
            let cols = (try? c.decode([String].self, forKey: .columns)) ?? []
            let raw = (try? c.decode([[JSONValue]].self, forKey: .rows)) ?? []
            let rows = raw.map { r -> [String] in
                let cells = r.prefix(cols.count).map { v -> String in
                    switch v {
                    case .string(let s): return s
                    case .number(let n): return n == n.rounded() && abs(n) < 1e15 ? String(Int64(n)) : String(n)
                    case .bool(let b): return b ? "是" : "否"
                    case .null: return ""
                    default: return v.jsonText
                    }
                }
                return Array(cells) + Array(repeating: "", count: max(0, cols.count - cells.count))
            }
            self = cols.isEmpty ? .unknown : .table(columns: cols, rows: rows)
        case "buttons":
            let bs = ((try? c.decode([Lenient.Maybe<CardButton>].self, forKey: .buttons)) ?? []).compactMap(\.value)
            self = bs.isEmpty ? .unknown : .buttons(bs)
        default:
            self = .unknown
        }
    }
}

// MARK: - plugin run 的结果 → 页面三态

public struct PluginRunResult: Decodable, Equatable, Sendable {
    public var ok: Bool
    public var plugin: String
    public var kind: String
    public var id: String
    public var card: PluginCard?
    public var error: String?
    enum CodingKeys: String, CodingKey { case ok, plugin, kind, id, card, error }
    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        ok = (try? c.decode(Bool.self, forKey: .ok)) ?? false
        plugin = ((try? c.decodeIfPresent(String.self, forKey: .plugin)) ?? nil) ?? ""
        kind = ((try? c.decodeIfPresent(String.self, forKey: .kind)) ?? nil) ?? ""
        id = ((try? c.decodeIfPresent(String.self, forKey: .id)) ?? nil) ?? ""
        card = (try? c.decodeIfPresent(PluginCard.self, forKey: .card)) ?? nil
        error = (try? c.decodeIfPresent(String.self, forKey: .error)) ?? nil
    }
}

/// 插件页 / 输入框回话 / 件按钮结果的样子。
public enum CardViewState: Equatable, Sendable {
    case empty                 // 跑完了，插件没给内容
    case loading
    case failed(String)
    case loaded(PluginCard)

    public var card: PluginCard? { if case .loaded(let c) = self { return c }; return nil }
    public var isLoading: Bool { self == .loading }

    /// evo plugin run --json 的输出 → 三态。插件失败时 evo 退出码 3，但 stdout 仍是信封，先读信封。
    public static func from(code: Int32, out: String, err: String) -> CardViewState {
        let t = out.trimmingCharacters(in: .whitespacesAndNewlines)
        if let m = ContractCheck.check(t, command: .pluginRun).message { return .failed(m) }
        if let r = try? JSONDecoder().decode(PluginRunResult.self, from: Data(t.utf8)), t.hasPrefix("{") {
            if !r.ok { return .failed(r.error ?? "插件出错了") }
            guard let c = r.card, !(c.isEmpty && c.title.isEmpty) else { return .empty }
            return .loaded(c)
        }
        let tail = (err.isEmpty ? out : err).trimmingCharacters(in: .whitespacesAndNewlines)
        if code == 0 { return .failed("evo 回的不是插件 JSON：\(String(t.prefix(80)))") }
        if tail.contains("invalid choice") || tail.contains("argument cmd") {
            return .failed("这版 evo 还没有插件功能（evo plugin），请更新 evo。")
        }
        return .failed(tail.isEmpty ? "退出码 \(code)" : String(tail.suffix(300)))
    }
}

// MARK: - 要跑的 evo 命令行

public enum PluginCLI {
    public static func list() -> [String] { ["plugin", "list", "--json"] }

    public static func setEnabled(_ name: String, _ on: Bool) -> [String] { ["plugin", on ? "enable" : "disable", name] }

    public static func run(plugin: String, kind: String, id: String, args: String? = nil, action: String? = nil,
                           payload: JSONValue? = nil, project: String? = nil, item: String? = nil) -> [String] {
        var a = ["plugin", "run", plugin, kind, id, "--json"]
        if let args, !args.isEmpty { a += ["--args", args] }
        if let action, !action.isEmpty { a += ["--action", action] }
        if let payload, payload != .null { a += ["--payload", payload.jsonText] }
        if let project, !project.isEmpty { a += ["--project", project] }
        if let item, !item.isEmpty { a += ["--item", item] }
        return a
    }
}

// MARK: - 输入框「/名字 参数」

public struct PluginCommandMatch: Equatable, Sendable {
    public var command: PluginComposerRef
    public var args: String
}

public enum PluginCommandParser {
    /// 「/hello 老板」→ 匹配到的插件命令 + 参数。不是 / 开头、或没有这个名字的插件命令 → nil（照旧当反馈发，免得吞掉「/api 路径不对」这种话）。
    public static func match(_ text: String, commands: [PluginComposerRef]) -> PluginCommandMatch? {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard t.hasPrefix("/"), t.count > 1 else { return nil }
        let body = t.dropFirst()
        let name: Substring, rest: Substring
        if let sp = body.firstIndex(where: { $0 == " " || $0 == "\u{3000}" || $0 == "\n" }) {
            name = body[..<sp]; rest = body[body.index(after: sp)...]
        } else {
            name = body; rest = ""
        }
        guard let c = commands.first(where: { $0.name == name.lowercased() }) else { return nil }
        return PluginCommandMatch(command: c, args: rest.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    /// 打了「/」但还没打完时的提示：「/hello 名字 · 打个招呼」。
    public static func hints(_ text: String, commands: [PluginComposerRef]) -> [String] {
        let t = text.trimmingCharacters(in: .whitespaces)
        guard t.hasPrefix("/"), !t.contains(" ") else { return [] }
        let p = t.dropFirst().lowercased()
        return commands.filter { p.isEmpty || $0.name.hasPrefix(p) }.map { c in
            "\(c.usage ?? "/" + c.name) · \(c.title)"
        }
    }
}
