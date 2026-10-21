import Foundation

// 第十六轮：App ↔ evo 的 JSON 接口定版本（docs/app-contract.md、kit/schemas/）。
// 规则：顶层 schema_version 是「大版本」。evo 只加字段不升版本（App 解码时忽略不认识的字段）；
// 不兼容的改动才升大版本。App 读到不认识的大版本：不解码、不崩溃，界面上显示一句「evo 比 App 新/旧，请更新」。

/// App 调的、带版本号的 evo 命令（用于提示里说是哪一个）。
public enum ContractCommand: String, Sendable, CaseIterable {
    case projects = "evo projects --json"
    case status = "evo status --json"
    case log = "evo log --json"
    case team = "evo team --json"
    case teamInit = "evo team init --json"
    case pluginList = "evo plugin list --json"
    case pluginRun = "evo plugin run --json"
}

public enum ContractCheck: Equatable, Sendable {
    case ok
    case evoNewer(found: Int, supported: Int, command: ContractCommand)
    case evoOlder(found: Int, supported: Int, command: ContractCommand)

    /// 这版 App 认得的大版本（所有命令目前都是 1）。
    public static let supported = 1

    /// 只看顶层 schema_version，不解码其余字段。没有这个字段（老版本的 evo log 等）当作 1；不是 JSON 对象返回 nil。
    public static func peekVersion(_ text: String) -> Int? {
        guard let d = text.data(using: .utf8),
              let o = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any] else { return nil }
        guard let v = o["schema_version"] else { return 1 }
        if let n = v as? Int { return n }
        if let n = v as? Double, n == n.rounded() { return Int(n) }
        if let s = v as? String, let n = Int(s) { return n }
        return 0
    }

    /// 不是 JSON 也算 ok（交给各自的解码报「不是 JSON」），只有认得出版本号又对不上时才拦。
    public static func check(_ text: String, command: ContractCommand, supported: Int = supported) -> ContractCheck {
        guard let v = peekVersion(text) else { return .ok }
        if v > supported { return .evoNewer(found: v, supported: supported, command: command) }
        if v < 1 { return .evoOlder(found: v, supported: supported, command: command) }
        return .ok
    }

    public var isOK: Bool { self == .ok }

    /// 给人看的一句。
    public var message: String? {
        switch self {
        case .ok: return nil
        case .evoNewer(let f, let s, let c):
            return "evo 版本比 App 新（\(c.rawValue) 是第 \(f) 版接口，这个 App 只认第 \(s) 版），请更新 Evo App。"
        case .evoOlder(let f, let s, let c):
            return "evo 版本比 App 旧（\(c.rawValue) 是第 \(f) 版接口，这个 App 要第 \(s) 版），请更新 evo（设置里的 evo 路径，或重新装 Evo App 自带的）。"
        }
    }
}

/// `evo projects --json`（第十六轮）。老版本 evo 没有 --json：退回读纯文本（ProjectList.parse）。
public struct ProjectsDoc: Decodable, Equatable, Sendable {
    public struct Project: Decodable, Equatable, Sendable {
        public var code: String
        public var name: String
        enum CodingKeys: String, CodingKey { case code, name }
        public init(from d: Decoder) throws {
            let c = try d.container(keyedBy: CodingKeys.self)
            code = try c.decode(String.self, forKey: .code)
            name = (try? c.decodeIfPresent(String.self, forKey: .name)) ?? code
        }
    }
    public var projects: [Project]
    enum CodingKeys: String, CodingKey { case projects }
    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        projects = ((try? c.decode([Lenient.Maybe<Project>].self, forKey: .projects)) ?? []).compactMap(\.value)
    }

    public static func decode(_ text: String) throws -> ProjectsDoc { try JSONDecoder().decode(ProjectsDoc.self, from: Data(text.utf8)) }
}

public extension ProjectList {
    /// 先当 JSON（projects --json），不是 JSON 再按纯文本读。版本对不上返回 .failure(提示)。
    static func parseAny(_ text: String) -> Result<[String], ContractMismatch> {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.hasPrefix("{") {
            let chk = ContractCheck.check(t, command: .projects)
            if let m = chk.message { return .failure(ContractMismatch(message: m)) }
            if let d = try? ProjectsDoc.decode(t) {
                var seen = Set<String>()
                return .success(d.projects.map(\.code).filter { seen.insert($0).inserted })
            }
        }
        return .success(parse(text))
    }
}

public struct ContractMismatch: Error, Equatable, Sendable {
    public var message: String
    public init(message: String) { self.message = message }
}
