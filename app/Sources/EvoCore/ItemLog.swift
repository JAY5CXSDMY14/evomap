import Foundation

/// `evo -p <代号> log <件号> --json` 的输出：一件的现状 + 交卷 + 时间线（kit/bin/evo cmd_log）。
/// 和 status 一样宽松：只认要用的字段，缺了不炸，事件里的附加字段统一转成文字。
public struct ItemLog: Decodable, Equatable, Sendable {
    public var key: String
    public var title: String?
    public var state: String?
    public var raw: String?
    public var goal: String?
    public var summary: String?
    public var manualChecks: [String]
    public var changes: [Change]
    public var tests: [TestRun]
    public var notes: [String]
    public var hasDiff: Bool
    public var mergedSha: String?
    public var events: [Event]
    /// 产出物（本件工作区 artifacts/ 下的文件）。evo log 现在还不输出这个字段（只有面板 /api/artifacts 有）；
    /// 将来加了就直接显示，没有就是空表。
    public var artifacts: [Artifact]

    public struct Change: Decodable, Equatable, Sendable {
        public var path: String
        public var why: String
        enum CodingKeys: String, CodingKey { case path, why }
        public init(path: String, why: String) { self.path = path; self.why = why }
        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            path = (try? c.decode(String.self, forKey: .path)) ?? "?"
            why = (try? c.decode(String.self, forKey: .why)) ?? ""
        }
    }

    public struct TestRun: Decodable, Equatable, Sendable {
        public var command: String
        public var result: String
        enum CodingKeys: String, CodingKey { case command, result }
        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            command = (try? c.decode(String.self, forKey: .command)) ?? "?"
            result = (try? c.decode(String.self, forKey: .result)) ?? "not_run"
        }
    }

    public struct Artifact: Decodable, Equatable, Sendable, Identifiable {
        public var id: String { path }
        public var path: String
        public var kind: String       // image | html | file
        public var bytes: Int?
        public var tooBig: Bool
        enum CodingKeys: String, CodingKey { case path, kind, bytes, tooBig = "too_big" }
        public init(path: String, kind: String = "file", bytes: Int? = nil, tooBig: Bool = false) {
            self.path = path; self.kind = kind; self.bytes = bytes; self.tooBig = tooBig
        }
        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            path = try c.decode(String.self, forKey: .path)
            kind = (try? c.decode(String.self, forKey: .kind)) ?? "file"
            bytes = try? c.decodeIfPresent(Int.self, forKey: .bytes)
            tooBig = (try? c.decodeIfPresent(Bool.self, forKey: .tooBig)) ?? false
        }

        public var symbol: String {
            switch kind {
            case "image": return "photo"
            case "html": return "globe"
            default: return "doc"
            }
        }

        /// 「12 KB」「3.4 MB」。
        public var sizeText: String? {
            guard let b = bytes else { return nil }
            if b < 1024 { return "\(b) B" }
            if b < 1024 * 1024 { return "\(Int((Double(b) / 1024).rounded())) KB" }
            return String(format: "%.1f MB", Double(b) / 1024 / 1024)
        }
    }

    /// 时间线上的一条（{at, item, event, …其余字段}）。
    public struct Event: Decodable, Equatable, Sendable, Identifiable {
        public var id: String { "\(at)#\(event)#\(index)" }
        public var index = 0
        public var at: String
        public var event: String
        public var fields: [String: String]     // 其余字段转成文字

        struct AnyKey: CodingKey {
            var stringValue: String; var intValue: Int? { nil }
            init?(stringValue: String) { self.stringValue = stringValue }
            init?(intValue: Int) { nil }
        }

        public init(at: String, event: String, fields: [String: String] = [:]) {
            self.at = at; self.event = event; self.fields = fields
        }

        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: AnyKey.self)
            var f: [String: String] = [:]
            var at = "", ev = ""
            for k in c.allKeys {
                let v = (try? c.decode(JSONText.self, forKey: k))?.text ?? ""
                switch k.stringValue {
                case "at": at = v
                case "event": ev = v
                case "item": break
                default: if !v.isEmpty { f[k.stringValue] = v }
                }
            }
            self.at = at; event = ev.isEmpty ? "?" : ev; fields = f
        }

        public var date: Date? { ISOTime.parse(at) }

        /// 给人看的事件名。
        public var label: String { Self.labels[event] ?? event }

        public static let labels: [String: String] = [
            "add": "登记", "dispatch": "派活", "report": "交卷", "gate_open": "开闸门等你", "gate_approve": "你点了头",
            "gate_reject": "你打回了", "gate_superseded": "闸门作废", "feedback": "你的反馈", "rework": "返工",
            "merge": "合并", "push": "推送", "ship": "上线", "deploy_failed": "部署失败", "restart": "重启",
            "decision": "决策岗拍板", "drop": "放弃", "state": "状态变化", "no_live_path": "没活路",
        ]

        public var symbol: String {
            switch event {
            case "add": return "plus.circle"
            case "dispatch": return "paperplane"
            case "report": return "doc.text"
            case "gate_open": return "hand.raised"
            case "gate_approve": return "checkmark.circle"
            case "gate_reject", "rework": return "arrow.uturn.backward.circle"
            case "gate_superseded": return "xmark.circle"
            case "feedback": return "text.bubble"
            case "merge": return "arrow.triangle.merge"
            case "push", "ship": return "shippingbox"
            case "deploy_failed", "no_live_path": return "exclamationmark.triangle"
            case "decision": return "person.crop.circle.badge.checkmark"
            case "drop": return "trash"
            default: return "circle"
            }
        }

        public enum Tone: Equatable, Sendable { case neutral, accent, success, danger }
        public var tone: Tone {
            switch event {
            case "merge", "ship", "gate_approve": return .success
            case "gate_open", "feedback": return .accent
            case "deploy_failed", "no_live_path", "gate_reject", "drop": return .danger
            default: return .neutral
            }
        }

        /// 一行补充：挑常见字段，其余最多再带两个「键=值」。
        public var detail: String? {
            let prefer = ["choice", "words", "role", "state", "to", "reason", "why", "round", "sha", "summary", "body", "gate", "kind"]
            var parts: [String] = []
            for k in prefer { if let v = fields[k] { parts.append(k == "round" ? "第 \(v) 轮" : (k == "sha" ? String(v.prefix(7)) : v)) } }
            if parts.isEmpty {
                parts = fields.keys.sorted().prefix(2).map { "\($0)=\(fields[$0] ?? "")" }
            }
            let t = parts.prefix(3).joined(separator: " · ")
            return t.isEmpty ? nil : String(t.prefix(160))
        }
    }

    enum CodingKeys: String, CodingKey {
        case key, title, state, raw, goal, report, notes, events, artifacts
        case manualChecks = "manual_checks"
        case hasDiff = "has_diff"
        case mergedSha = "merged_sha"
    }

    struct Report: Decodable {
        var summary: String?
        var changes: [Lenient.Maybe<Change>]?
        var tests: [Lenient.Maybe<TestRun>]?
    }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        key = try c.decode(String.self, forKey: .key)
        title = try? c.decodeIfPresent(String.self, forKey: .title)
        state = try? c.decodeIfPresent(String.self, forKey: .state)
        raw = try? c.decodeIfPresent(String.self, forKey: .raw)
        goal = try? c.decodeIfPresent(String.self, forKey: .goal)
        let rep = (try? c.decodeIfPresent(Report.self, forKey: .report)) ?? nil
        summary = rep?.summary
        changes = rep?.changes?.compactMap(\.value) ?? []
        tests = rep?.tests?.compactMap(\.value) ?? []
        manualChecks = ((try? c.decodeIfPresent([JSONText].self, forKey: .manualChecks)) ?? nil)?.map(\.text).filter { !$0.isEmpty } ?? []
        // owner_notes 可能是字符串，也可能是 {at, words, source}：都转成一句
        notes = ((try? c.decodeIfPresent([JSONText].self, forKey: .notes)) ?? nil)?.map(\.text).filter { !$0.isEmpty } ?? []
        hasDiff = (try? c.decodeIfPresent(Bool.self, forKey: .hasDiff)) ?? false
        mergedSha = try? c.decodeIfPresent(String.self, forKey: .mergedSha)
        var evs = ((try? c.decodeIfPresent([Lenient.Maybe<Event>].self, forKey: .events)) ?? nil)?.compactMap(\.value) ?? []
        for i in evs.indices { evs[i].index = i }
        events = evs
        artifacts = ((try? c.decodeIfPresent([Lenient.Maybe<Artifact>].self, forKey: .artifacts)) ?? nil)?.compactMap(\.value) ?? []
    }

    public static func decode(_ text: String) throws -> ItemLog { try JSONDecoder().decode(ItemLog.self, from: Data(text.utf8)) }

    /// 新的在上面。
    public var timeline: [Event] { events.reversed() }
}

/// 任意 JSON 值转成一句文字：字符串原样，数字去掉多余的 .0，布尔「是/否」，对象取 words/text/summary/title，否则紧凑 JSON。
struct JSONText: Decodable {
    var text: String
    struct K: CodingKey {
        var stringValue: String; var intValue: Int? { nil }
        init?(stringValue: String) { self.stringValue = stringValue }
        init?(intValue: Int) { nil }
    }
    init(from decoder: Decoder) throws {
        if let c = try? decoder.singleValueContainer() {
            if c.decodeNil() { text = ""; return }
            if let s = try? c.decode(String.self) { text = s; return }
            if let b = try? c.decode(Bool.self) { text = b ? "是" : "否"; return }
            if let i = try? c.decode(Int.self) { text = String(i); return }
            if let d = try? c.decode(Double.self) { text = d == d.rounded() && abs(d) < 1e12 ? String(Int(d)) : String(d); return }
            if let a = try? c.decode([JSONText].self) { text = a.map(\.text).joined(separator: "、"); return }
        }
        let o = try decoder.container(keyedBy: K.self)
        for name in ["words", "text", "summary", "title", "body", "why"] {
            if let k = K(stringValue: name), let v = try? o.decode(JSONText.self, forKey: k), !v.text.isEmpty { text = v.text; return }
        }
        text = o.allKeys.map(\.stringValue).sorted().prefix(3).compactMap { n in
            K(stringValue: n).flatMap { k in (try? o.decode(JSONText.self, forKey: k)).map { "\(n)=\($0.text)" } }
        }.joined(separator: " ")
    }
}
