import Foundation

// 表情角色（调度球 / 云宝 / 亮亮）：evo 的状态 → 表情编号。界面层用 WKWebView 跑 aora-bot 的表情引擎，这里只管映射，Linux 上也能测。
// 编号是引擎的对外契约（emotion-ball/js/emotions.js、mood-mates/src/data/emotions.js 两边同一张表，永不重排）：
//   00-09 生命周期 · 10-29 情绪反应 · 30-49 代理工作状态

/// 可选角色。调度球是默认（形象来自 aora-bot emotion-ball 的 blob 球）（只许自用，见 Resources/VENDOR-NOTICE.md）；云宝 / 亮亮来自 mood-mates，可买商业许可。
public enum MateCharacter: String, CaseIterable, Sendable {
    case ball      // 调度球（emotion-ball，blob 造型）
    case nimbo     // 云宝（mood-mates）
    case twinkle   // 亮亮（mood-mates）

    public static let `default` = MateCharacter.ball

    public var label: String {
        switch self {
        case .ball: return "调度球"
        case .nimbo: return "云宝"
        case .twinkle: return "亮亮"
        }
    }

    /// 宿主页参数：哪个引擎、哪个角色 / 造型。
    public var engine: String { self == .ball ? "ball" : "mates" }
    public var shapeOrCharacter: String {
        switch self {
        case .ball: return "blob"
        case .nimbo: return "nimbo"
        case .twinkle: return "twinkle"
        }
    }

    /// 能不能拿去分发（商用要另买许可；调度球的形象来自 emotion-ball，永远不行）。
    public var licensable: Bool { self != .ball }

    public static func from(_ raw: String?) -> MateCharacter { raw.flatMap(MateCharacter.init(rawValue:)) ?? .default }
}

/// 用到的表情（编号 = 引擎 emotionId）。
public enum MateEmotion: String, CaseIterable, Sendable {
    case sleep = "00"        // 睡眠
    case wake = "01"         // 唤醒
    case standby = "02"      // 待机放空
    case curious = "03"      // 好奇
    case happy = "10"        // 开心
    case thinking = "30"     // 思考中
    case received = "31"     // 接收任务
    case busy = "32"         // 处理中忙碌
    case done = "33"         // 任务完成（自带彩带 + 撒花）
    case error = "34"        // 出错
    case listening = "35"    // 等待输入（聆听）
    case replying = "39"     // 输出回复
    case searching = "40"    // 检索资料

    public var id: String { rawValue }

    public var name: String {
        switch self {
        case .sleep: return "睡眠"
        case .wake: return "唤醒"
        case .standby: return "待机"
        case .curious: return "好奇"
        case .happy: return "开心"
        case .thinking: return "思考中"
        case .received: return "接收任务"
        case .busy: return "忙碌"
        case .done: return "任务完成"
        case .error: return "出错"
        case .listening: return "等你"
        case .replying: return "回话"
        case .searching: return "检索"
        }
    }
}

/// 一次性的事件（几秒后回到常态表情）。
public enum MateEvent: Equatable, Sendable {
    case launch          // 应用刚启动
    case approved        // 你点了通过 / 做 / 上线
    case merged          // 有件合并了
    case rejected        // 你打回了
    case sending         // 输入框发出去了，等 evo 回话
    case replied         // evo 回话了
    case replyFailed     // evo 回话出错
}

public struct MateReaction: Equatable, Sendable {
    public var emotion: MateEmotion
    public var celebrate: Bool      // 额外撒花 + 弹一下
    public var seconds: Double      // 停留多久再回常态
}

public enum MateMap {
    /// 常态：跟着吉祥物心情走。
    ///   顺利 → 待机 02 · 干活 → 思考 30 · 等你 → 等待输入 35（聆听，最「在等你」的那个）
    ///   卡住 / 心跳过期 / 出错 → 出错 34 · 暂停 / 免打扰 → 睡眠 00
    public static func emotion(for mood: MascotMood) -> MateEmotion {
        switch mood {
        case .idle: return .standby
        case .working: return .thinking
        case .waiting: return .listening
        case .worried: return .error
        case .sleepy: return .sleep
        }
    }

    /// 常态，带「还在读」（loading → 检索 40）。
    public static func emotion(state: LoopState, mood: MascotMood) -> MateEmotion {
        if case .loading = state { return .searching }
        return emotion(for: mood)
    }

    public static func reaction(_ e: MateEvent) -> MateReaction {
        switch e {
        case .launch: return .init(emotion: .wake, celebrate: false, seconds: 2.6)
        case .approved: return .init(emotion: .done, celebrate: true, seconds: 3.0)
        case .merged: return .init(emotion: .done, celebrate: true, seconds: 3.0)
        case .rejected: return .init(emotion: .received, celebrate: false, seconds: 2.0)
        case .sending: return .init(emotion: .received, celebrate: false, seconds: 8.0)
        case .replied: return .init(emotion: .replying, celebrate: false, seconds: 2.4)
        case .replyFailed: return .init(emotion: .error, celebrate: false, seconds: 3.0)
        }
    }

    /// 合并数增加了吗（用来触发「任务完成」）：任何项目的 merged 计数比上一轮多。第一轮（旧表为空）不算。
    public static func mergedIncreased(old: [String: Int], new: [String: Int]) -> Bool {
        guard !old.isEmpty else { return false }
        return new.contains { k, v in v > (old[k] ?? v) }
    }
}

/// Swift → 宿主页 JS 的调用串（单独拿出来好测，避免把奇怪字符拼进 JS）。
public enum MateBridge {
    public static func set(_ e: MateEmotion, celebrate: Bool = false) -> String {
        "window.evoMate && window.evoMate.set('\(e.id)', \(celebrate ? "true" : "false"))"
    }

    /// 注视：归一化到 [-1, 1]，保留两位小数。
    public static func gaze(_ x: Double, _ y: Double) -> String {
        func c(_ v: Double) -> String { String(format: "%.2f", min(1, max(-1, v.isFinite ? v : 0))) }
        return "window.evoMate && window.evoMate.gaze(\(c(x)), \(c(y)))"
    }

    /// 直接设定注视（v0.5.0）：x、y 已经是 SwiftUI 弹簧追出来的当前值，宿主页不再自己平滑；
    /// boost 是眼睛放大倍数（很近时 1.16，平时 1）。
    public static func look(_ x: Double, _ y: Double, boost: Double = 1) -> String {
        func c(_ v: Double, _ lo: Double, _ hi: Double) -> String { String(format: "%.3f", min(hi, max(lo, v.isFinite ? v : 0))) }
        return "window.evoMate && window.evoMate.look(\(c(x, -1.2, 1.2)), \(c(y, -1.2, 1.2)), \(c(boost, 0.5, 1.6)))"
    }

    /// 眨一下眼（double = 连眨两下）。
    public static func blink(double: Bool = false) -> String {
        "window.evoMate && window.evoMate.blink(\(double ? "true" : "false"))"
    }

    /// 鼠标相对角色中心的位置 → 注视（v0.4 的老算法，范围 360 点、线性；v0.5.0 改用 EyeFollow）。dx/dy 是屏幕点距，reach 是「多远算看到底」（点）。y 向下为正（和 SVG 一致）。
    public static func gazeVector(dx: Double, dy: Double, reach: Double = 360) -> (Double, Double) {
        guard reach > 0 else { return (0, 0) }
        let x = min(1, max(-1, dx / reach)), y = min(1, max(-1, dy / reach))
        return (x, y)
    }

    /// 宿主页查询串。小号（< 80 点）放大眼睛、关粒子（引擎文档建议 eyeScale 1.5~1.8 + lite）。
    public static func query(character: MateCharacter, emotion: MateEmotion, size: Double, still: Bool) -> String {
        let small = size < 80
        var q = ["engine=\(character.engine)", "c=\(character.shapeOrCharacter)", "e=\(emotion.id)"]
        if small { q.append("eye=\(size < 40 ? "1.8" : "1.5")"); q.append("lite=1") }
        if still { q.append("still=1") }
        return q.joined(separator: "&")
    }
}
