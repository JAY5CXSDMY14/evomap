import Foundation

/// `evo -p <代号> status --json` 的输出（schema_version 1，见 docs/agent-interface.md）。
/// 规则：只认我们要用的字段，其余忽略；字段缺了不报错（evo 只加字段不删，但老版本可能没有新字段）。
public struct StatusDoc: Decodable, Equatable, Sendable {
    public var schemaVersion: Int
    public var project: String
    public var name: String
    public var generatedAt: String?
    public var lastTick: String?
    public var count: [String: Int]
    public var stuck: Int
    public var gates: [Gate]
    public var items: [Item]
    public var log: [String]
    /// 新字段（可能还没有）：没有可走通路径的件数。evo 可能给数字、数组或布尔，统一成件数；没给就是 nil。
    public var noLivePath: Int?
    /// 第十二轮新字段：卡太久（同一状态超过 limits.stale_hours）的件数；顶层 stale 是件列表，这里只数个数。
    public var staleItems: Int?
    /// 第十二轮新字段：岗位状态（施工/验收/决策 忙、闲、暂停、额度满）。
    public var roles: [Role]
    /// 顶层 stale / no_live_path 是件列表时的明细（数字或布尔的老格式就是空表，只有上面的件数）。
    public var staleList: [Flag]
    public var noLivePathList: [Flag]
    /// 第十七轮：项目暂停原因（evo status 只读，暂停时也照常返回）；没暂停为 nil。
    public var paused: String?

    /// 一件被点名的件：卡太久或没活路。
    public struct Flag: Decodable, Equatable, Sendable {
        public var key: String
        public var title: String?
        public var state: String?
        public var reason: String?
        public var hours: Double?
        public var minutes: Double?
        enum CodingKeys: String, CodingKey { case key, title, state, reason, hours, minutes }
        public init(key: String, title: String? = nil, state: String? = nil, reason: String? = nil, hours: Double? = nil, minutes: Double? = nil) {
            self.key = key; self.title = title; self.state = state; self.reason = reason; self.hours = hours; self.minutes = minutes
        }
        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            key = try c.decode(String.self, forKey: .key)
            title = try? c.decodeIfPresent(String.self, forKey: .title)
            state = try? c.decodeIfPresent(String.self, forKey: .state)
            reason = try? c.decodeIfPresent(String.self, forKey: .reason)
            hours = try? c.decodeIfPresent(Double.self, forKey: .hours)
            minutes = try? c.decodeIfPresent(Double.self, forKey: .minutes)
        }
    }

    public struct Role: Decodable, Equatable, Sendable {
        public var role: String
        public var name: String
        public var status: String
        public var label: String
        enum CodingKeys: String, CodingKey { case role, name, status, label }
        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            role = (try? c.decode(String.self, forKey: .role)) ?? ""
            name = (try? c.decode(String.self, forKey: .name)) ?? role
            status = (try? c.decode(String.self, forKey: .status)) ?? ""
            label = (try? c.decode(String.self, forKey: .label)) ?? status
        }
    }

    public struct Gate: Decodable, Equatable, Hashable, Sendable {
        public var id: String
        public var question: String?
        public var options: [String]
        public var kind: String?
        public var item: String?
        public var waitingSince: String?
        /// 第十七轮：在 Orca 端被点了「通过 / 上线」等、要老板在 evo 入口再确认的闸门（试运行）。
        public var confirm: Bool = false
        public var orcaChoice: String?

        enum CodingKeys: String, CodingKey {
            case id, question, options, kind, item, confirm
            case waitingSince = "waiting_since"
            case orcaChoice = "orca_choice"
        }

        public init(id: String, question: String? = nil, options: [String] = [], kind: String? = nil, item: String? = nil, waitingSince: String? = nil) {
            self.id = id; self.question = question; self.options = options; self.kind = kind; self.item = item; self.waitingSince = waitingSince
        }

        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            id = try c.decode(String.self, forKey: .id)
            question = try c.decodeIfPresent(String.self, forKey: .question)
            options = (try? c.decodeIfPresent([String].self, forKey: .options)) ?? []
            kind = try c.decodeIfPresent(String.self, forKey: .kind)
            item = try c.decodeIfPresent(String.self, forKey: .item)
            waitingSince = try c.decodeIfPresent(String.self, forKey: .waitingSince)
            confirm = (try? c.decodeIfPresent(Bool.self, forKey: .confirm)) ?? false
            orcaChoice = try? c.decodeIfPresent(String.self, forKey: .orcaChoice)
        }

        /// 给人看的种类名。
        public var kindLabel: String {
            switch kind {
            case "do": return "做不做"
            case "look": return "看效果"
            case "ship": return "上线"
            case "external": return "外部请求"
            case "ask": return "提问"
            case "budget": return "上限"
            default: return "待定"
            }
        }
    }

    public struct Item: Decodable, Equatable, Sendable {
        public var key: String
        public var title: String
        public var state: String
        public var raw: String?
        public var stalled: Bool
        public var noLivePath: Bool

        enum CodingKeys: String, CodingKey { case key, title, state, raw, stalled
            case noLivePath = "no_live_path" }

        public init(key: String, title: String, state: String, raw: String? = nil, stalled: Bool = false, noLivePath: Bool = false) {
            self.key = key; self.title = title; self.state = state; self.raw = raw; self.stalled = stalled; self.noLivePath = noLivePath
        }

        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            key = try c.decode(String.self, forKey: .key)
            title = (try c.decodeIfPresent(String.self, forKey: .title)) ?? ""
            state = (try c.decodeIfPresent(String.self, forKey: .state)) ?? ""
            raw = try c.decodeIfPresent(String.self, forKey: .raw)
            stalled = (try? c.decodeIfPresent(Bool.self, forKey: .stalled)) ?? false
            noLivePath = (Lenient.count(c, .noLivePath) ?? 0) > 0
        }
    }

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case project, name, count, stuck, gates, items, log
        case noLivePath = "no_live_path"
        case staleItems = "stale"
        case roles
        case generatedAt = "generated_at"
        case lastTick = "last_tick"
        case paused
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        schemaVersion = (try c.decodeIfPresent(Int.self, forKey: .schemaVersion)) ?? 1
        project = try c.decode(String.self, forKey: .project)
        name = (try c.decodeIfPresent(String.self, forKey: .name)) ?? project
        generatedAt = try c.decodeIfPresent(String.self, forKey: .generatedAt)
        lastTick = try c.decodeIfPresent(String.self, forKey: .lastTick)
        count = (try? c.decodeIfPresent([String: Int].self, forKey: .count)) ?? [:]
        stuck = (try? c.decodeIfPresent(Int.self, forKey: .stuck)) ?? 0
        gates = (try? c.decodeIfPresent([Gate].self, forKey: .gates)) ?? []
        items = (try? c.decodeIfPresent([Item].self, forKey: .items)) ?? []
        log = (try? c.decodeIfPresent([String].self, forKey: .log)) ?? []
        noLivePath = Lenient.count(c, .noLivePath)
        staleItems = Lenient.count(c, .staleItems)
        // roles 可能是列表（第十二轮）也可能是别的形状：只认列表里像样的条目
        roles = ((try? c.decodeIfPresent([Lenient.Maybe<Role>].self, forKey: .roles)) ?? nil)?.compactMap(\.value).filter { !$0.role.isEmpty } ?? []
        staleList = ((try? c.decodeIfPresent([Lenient.Maybe<Flag>].self, forKey: .staleItems)) ?? nil)?.compactMap(\.value) ?? []
        noLivePathList = ((try? c.decodeIfPresent([Lenient.Maybe<Flag>].self, forKey: .noLivePath)) ?? nil)?.compactMap(\.value) ?? []
        paused = (try? c.decodeIfPresent(String.self, forKey: .paused)) ?? nil
    }

    /// 这个版本的应用认得的最高 schema_version；更高的照样解析（只加字段），但界面上提示升级。
    public static let supportedSchema = 1

    public static func decode(_ data: Data) throws -> StatusDoc {
        try JSONDecoder().decode(StatusDoc.self, from: data)
    }

    public static func decode(_ text: String) throws -> StatusDoc {
        try decode(Data(text.utf8))
    }

    /// 等老板的件数（= 这个项目的待批闸门数）。
    public var pendingCount: Int { gates.count }
    public var buildingCount: Int { count["building", default: 0] }
    /// 验收这一段：待验收 + 验收中。
    public var verifyingCount: Int { count["built", default: 0] + count["verifying", default: 0] }
    /// 已合并可收菜。
    public var mergedCount: Int { count["merged", default: 0] }
    /// 卡住：有顶层 no_live_path（没活路超过阈值的件）时取 stuck 和它的较大值（同一件可能两边都算，取大不重复加）。
    /// items[].no_live_path 只是「正在计时」，不算卡住。
    public var stuckCount: Int {
        guard let n = noLivePath else { return stuck }
        return max(stuck, n)
    }
}

/// 宽松解码：数字 / 数组（取长度）/ 布尔（true=1）/ 字符串数字都认，其余当没有。
enum Lenient {
    /// 列表里某一条解不出就当 nil，不连累整张列表。
    struct Maybe<T: Decodable>: Decodable {
        var value: T?
        init(from decoder: Decoder) throws { value = try? T(from: decoder) }
    }

    static func count<K: CodingKey>(_ c: KeyedDecodingContainer<K>, _ k: K) -> Int? {
        guard c.contains(k) else { return nil }
        if let n = try? c.decode(Int.self, forKey: k) { return n }
        if let b = try? c.decode(Bool.self, forKey: k) { return b ? 1 : 0 }
        if let a = try? c.decode([AnyJSON].self, forKey: k) { return a.count }
        if let s = try? c.decode(String.self, forKey: k), let n = Int(s) { return n }
        if let d = try? c.decode([String: AnyJSON].self, forKey: k) { return d.count }
        return nil
    }
}

/// 只为数元素个数而解码的任意 JSON 值。
struct AnyJSON: Decodable {
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { return }
        if (try? c.decode(Bool.self)) != nil { return }
        if (try? c.decode(Double.self)) != nil { return }
        if (try? c.decode(String.self)) != nil { return }
        if (try? c.decode([AnyJSON].self)) != nil { return }
        if (try? c.decode([String: AnyJSON].self)) != nil { return }
        throw DecodingError.dataCorruptedError(in: c, debugDescription: "unknown")
    }
}

/// `evo projects` 的纯文本输出：每行「代号 名字 仓库 GitHub」，取第一列 2–4 个大写字母。
public enum ProjectList {
    public static func parse(_ text: String) -> [String] {
        var out: [String] = []
        for line in text.split(whereSeparator: \.isNewline) {
            guard let first = line.split(separator: " ", omittingEmptySubsequences: true).first else { continue }
            let code = String(first)
            if (2...4).contains(code.count), code.allSatisfy({ $0.isASCII && $0.isUppercase }), !out.contains(code) {
                out.append(code)
            }
        }
        return out
    }
}
