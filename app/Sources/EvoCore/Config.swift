import Foundation

/// 解析 evo 写的 ISO 8601 时间（例 2026-10-20T12:00:00+08:00，可能带小数秒）。
public enum ISOTime {
    public static func parse(_ s: String?) -> Date? {
        guard let s = s?.trimmingCharacters(in: .whitespaces), !s.isEmpty else { return nil }
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        if let d = f.date(from: s) { return d }
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.date(from: s)
    }
}

/// 全局配置 ~/.evoloop/config.json 里应用关心的几项；缺省值与 kit/bin/evo 的 DEFAULTS 一致。
public struct GlobalConfig: Equatable, Sendable {
    public var quietHours: QuietHours?
    public var heartbeatStaleMinutes: Double
    public var magpieURL: String

    public static let `default` = GlobalConfig(
        quietHours: QuietHours(start: "00:00", end: "08:00", tz: "Asia/Shanghai"),
        heartbeatStaleMinutes: 10, magpieURL: "http://127.0.0.1:3425")

    public init(quietHours: QuietHours?, heartbeatStaleMinutes: Double, magpieURL: String) {
        self.quietHours = quietHours; self.heartbeatStaleMinutes = heartbeatStaleMinutes; self.magpieURL = magpieURL
    }

    /// 读不出（没有文件、不是 JSON）就用缺省值。
    public static func parse(_ data: Data?) -> GlobalConfig {
        var c = GlobalConfig.default
        guard let data, let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return c }
        if let m = obj["magpie_url"] as? String, !m.isEmpty { c.magpieURL = m }
        if let lim = obj["limits"] as? [String: Any], let n = lim["heartbeat_stale_minutes"] as? NSNumber {
            c.heartbeatStaleMinutes = n.doubleValue
        }
        if let n = obj["notify"] as? [String: Any], n.keys.contains("quiet_hours") {
            // 和 evo_notify.quiet_cfg 一样：写了 quiet_hours 但为空（null / {} / false）= 关掉免打扰
            if let q = n["quiet_hours"] as? [String: Any], !q.isEmpty {
                c.quietHours = QuietHours(start: q["start"] as? String ?? "00:00", end: q["end"] as? String ?? "08:00",
                                          tz: q["tz"] as? String ?? n["tz"] as? String ?? "Asia/Shanghai")
            } else {
                c.quietHours = nil
            }
        }
        return c
    }
}

/// 免打扰时段，[start, end)，end < start 表示跨午夜，start == end 表示关闭（同 evo_time.in_range）。
public struct QuietHours: Equatable, Sendable {
    public var start: String
    public var end: String
    public var tz: String

    public init(start: String, end: String, tz: String) {
        self.start = start; self.end = end; self.tz = tz
    }

    static func minutes(_ hm: String) -> Int? {
        let p = hm.trimmingCharacters(in: .whitespaces).split(separator: ":")
        guard p.count == 2, let h = Int(p[0]), let m = Int(p[1]) else { return nil }
        return h * 60 + m
    }

    public static func inRange(_ minute: Int, _ start: Int, _ end: Int) -> Bool {
        if start == end { return false }
        return start < end ? (start <= minute && minute < end) : (minute >= start || minute < end)
    }

    public func contains(_ date: Date) -> Bool {
        guard let s = Self.minutes(start), let e = Self.minutes(end) else { return false }
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: tz) ?? TimeZone(identifier: "Asia/Shanghai")!
        let c = cal.dateComponents([.hour, .minute], from: date)
        return Self.inRange((c.hour ?? 0) * 60 + (c.minute ?? 0), s, e)
    }
}

/// 看门狗：根据 last_tick 判断循环还活着没有。
public struct HeartbeatStatus: Equatable, Sendable {
    public enum Level: Equatable, Sendable { case ok, stale, never }
    public var project: String
    public var ageMinutes: Double?
    public var level: Level

    public init(project: String, ageMinutes: Double?, level: Level) {
        self.project = project; self.ageMinutes = ageMinutes; self.level = level
    }

    public static func of(project: String, lastTick: String?, staleMinutes: Double, now: Date = Date()) -> HeartbeatStatus {
        guard let t = ISOTime.parse(lastTick) else { return HeartbeatStatus(project: project, ageMinutes: nil, level: .never) }
        let age = max(0, now.timeIntervalSince(t) / 60)
        return HeartbeatStatus(project: project, ageMinutes: age, level: age > staleMinutes ? .stale : .ok)
    }

    /// 菜单里一行：🟢 TB 3 分钟前 / 🔴 TB 42 分钟没转动 / ⚪️ TB 从没转过
    public var line: String {
        switch level {
        case .never: return "⚪️ \(project) 从没转过"
        case .ok: return "🟢 \(project) \(Self.human(ageMinutes ?? 0))前转过"
        case .stale: return "🔴 \(project) 已 \(Self.human(ageMinutes ?? 0))没转动"
        }
    }

    public static func human(_ mins: Double) -> String {
        if mins < 1 { return "不到 1 分钟" }
        if mins < 60 { return "\(Int(mins)) 分钟" }
        if mins < 60 * 48 { return String(format: "%.1f 小时", mins / 60) }
        return "\(Int(mins / 60 / 24)) 天"
    }
}

/// 看门狗变红只提醒一次，恢复再停才再提醒（同 evo watchdog 的规则）。
public struct StaleTracker: Equatable {
    public private(set) var alerted: Set<String> = []
    public init(alerted: Set<String> = []) { self.alerted = alerted }

    public mutating func diff(_ beats: [HeartbeatStatus], quiet: Bool) -> [PlannedNotification] {
        var out: [PlannedNotification] = []
        for b in beats {
            if b.level == .stale {
                if !alerted.contains(b.project) && !quiet {
                    alerted.insert(b.project)
                    out.append(PlannedNotification(id: "stale/\(b.project)", title: "[\(b.project)] 接棒器停了",
                                                   body: "已 \(HeartbeatStatus.human(b.ageMinutes ?? 0))没转动。看看常驻进程、执行端（Multica / Orca）和这台 Mac 是否睡着了",
                                                   project: b.project, gate: nil))
                }
            } else if b.level == .ok {
                alerted.remove(b.project)
            }
        }
        return out
    }
}

/// 找 python3：用户设置优先，其次 Homebrew、python.org、系统自带。
/// /usr/bin/python3 在没装命令行工具的 Mac 上是个会弹安装框的占位程序，所以放最后，且要求命令行工具已装。
public enum PythonLocator {
    public static let candidates = [
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
        "/usr/bin/python3",
    ]

    public static func pick(override: String?, candidates: [String] = candidates,
                            isExecutable: (String) -> Bool, systemStubUsable: Bool) -> String? {
        if let o = override?.trimmingCharacters(in: .whitespaces), !o.isEmpty {
            let p = (o as NSString).expandingTildeInPath
            return isExecutable(p) ? p : nil
        }
        for c in candidates where isExecutable(c) {
            if c == "/usr/bin/python3" && !systemStubUsable { continue }
            return c
        }
        return nil
    }
}

/// GUI 应用的 PATH 很短（/usr/bin:/bin:/usr/sbin:/sbin），evo 要调 git、gh、orca、dsh，这里补上常见目录。
public enum ToolPath {
    public static func augmented(_ current: String?, home: String) -> String {
        let extra = ["/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin", "\(home)/.local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
        var parts = (current ?? "").split(separator: ":").map(String.init).filter { !$0.isEmpty }
        for e in extra where !parts.contains(e) { parts.append(e) }
        // 常用目录放前面，系统目录保持原顺序在后
        let front = ["/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin", "\(home)/.local/bin"]
        return (front + parts.filter { !front.contains($0) }).joined(separator: ":")
    }
}

/// `evo panel --show-token` 输出「面板口令：XXXX（存在 钥匙串）」，取出口令。
public enum PanelToken {
    public static func parseShowToken(_ text: String) -> String? {
        for line in text.split(whereSeparator: \.isNewline) {
            guard let r = line.range(of: "面板口令：") ?? line.range(of: "口令：") else { continue }
            var rest = line[r.upperBound...]
            if let p = rest.firstIndex(where: { $0 == "（" || $0 == "(" || $0 == " " }) { rest = rest[..<p] }
            let t = rest.trimmingCharacters(in: .whitespaces)
            if !t.isEmpty { return t }
        }
        return nil
    }
}
