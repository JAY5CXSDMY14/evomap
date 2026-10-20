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

    public struct Gate: Decodable, Equatable, Hashable, Sendable {
        public var id: String
        public var question: String?
        public var options: [String]
        public var kind: String?
        public var item: String?
        public var waitingSince: String?

        enum CodingKeys: String, CodingKey {
            case id, question, options, kind, item
            case waitingSince = "waiting_since"
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
        }

        /// 给人看的种类名。
        public var kindLabel: String {
            switch kind {
            case "do": return "做不做"
            case "look": return "看效果"
            case "ship": return "上线"
            case "external": return "外部请求"
            case "ask": return "提问"
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

        enum CodingKeys: String, CodingKey { case key, title, state, raw, stalled }

        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            key = try c.decode(String.self, forKey: .key)
            title = (try c.decodeIfPresent(String.self, forKey: .title)) ?? ""
            state = (try c.decodeIfPresent(String.self, forKey: .state)) ?? ""
            raw = try c.decodeIfPresent(String.self, forKey: .raw)
            stalled = (try c.decodeIfPresent(Bool.self, forKey: .stalled)) ?? false
        }
    }

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case project, name, count, stuck, gates, items, log
        case generatedAt = "generated_at"
        case lastTick = "last_tick"
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        schemaVersion = (try c.decodeIfPresent(Int.self, forKey: .schemaVersion)) ?? 1
        project = try c.decode(String.self, forKey: .project)
        name = (try c.decodeIfPresent(String.self, forKey: .name)) ?? project
        generatedAt = try c.decodeIfPresent(String.self, forKey: .generatedAt)
        lastTick = try c.decodeIfPresent(String.self, forKey: .lastTick)
        count = (try? c.decodeIfPresent([String: Int].self, forKey: .count)) ?? [:]
        stuck = (try c.decodeIfPresent(Int.self, forKey: .stuck)) ?? 0
        gates = (try c.decodeIfPresent([Gate].self, forKey: .gates)) ?? []
        items = (try c.decodeIfPresent([Item].self, forKey: .items)) ?? []
        log = (try? c.decodeIfPresent([String].self, forKey: .log)) ?? []
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
