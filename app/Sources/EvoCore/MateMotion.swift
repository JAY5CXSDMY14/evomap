import Foundation

// v0.5.0 调度球的「灵动」纯逻辑：眼睛跟鼠标的偏移、离得很近时的惊喜、随机眨眼间隔、状态切换时身体怎么弹。
// 界面层（Sources/Evo/MateView.swift）只拿这里算出的目标值，再交给 SwiftUI 原生弹簧（.spring / .interpolatingSpring）去追。

/// 眼睛跟鼠标：给定角色中心、球径和鼠标位置（同一坐标系，y 向下为正），算眼睛该往哪看。
public enum EyeFollow {
    /// 感应范围半径 = 球径 × 这个数。鼠标进了这个圈，眼睛开始跟。
    public static let rangeFactor = 3.0
    /// 「很近」半径 = 球径 × 这个数（差不多贴着球边）：眼睛微放大、身体轻轻一缩。
    public static let nearFactor = 0.85
    /// 离球心多远眼睛就看到底（球径 × 这个数）；再远方向照跟、幅度不再变大。
    public static let fullReachFactor = 1.2

    public struct Result: Equatable, Sendable {
        /// 归一化注视方向，x、y 各在 [-1, 1]，幅度（长度）≤ 1；不在范围里时是 (0, 0)。
        public var x: Double
        public var y: Double
        public var inRange: Bool
        public var near: Bool
        /// 鼠标到球心的距离（点）。
        public var distance: Double

        public static let rest = Result(x: 0, y: 0, inRange: false, near: false, distance: .infinity)
    }

    /// - Parameters:
    ///   - center: 角色中心
    ///   - diameter: 球径（点）
    ///   - pointer: 鼠标位置；nil 表示鼠标不在可感知的地方（例如离开了屏幕或窗口不可见）
    public static func compute(center: (x: Double, y: Double), diameter: Double, pointer: (x: Double, y: Double)?,
                               rangeFactor: Double = rangeFactor, nearFactor: Double = nearFactor,
                               fullReachFactor: Double = fullReachFactor) -> Result {
        guard let p = pointer, diameter > 0, p.x.isFinite, p.y.isFinite else { return .rest }
        let dx = p.x - center.x, dy = p.y - center.y
        let dist = (dx * dx + dy * dy).squareRoot()
        guard dist <= diameter * rangeFactor else { return Result(x: 0, y: 0, inRange: false, near: false, distance: dist) }
        let near = dist <= diameter * nearFactor
        // 正中心附近方向没意义：眼睛居中（但算「很近」）
        guard dist > 0.5 else { return Result(x: 0, y: 0, inRange: true, near: near, distance: dist) }
        let reach = max(1, diameter * fullReachFactor)
        let mag = min(1, dist / reach)
        return Result(x: dx / dist * mag, y: dy / dist * mag, inRange: true, near: near, distance: dist)
    }

    /// 两次目标差多少才值得重新起一次弹簧（免得鼠标抖一下就重设动画）。
    public static func changedEnough(_ a: Result, _ b: Result, threshold: Double = 0.03) -> Bool {
        a.inRange != b.inRange || a.near != b.near || abs(a.x - b.x) > threshold || abs(a.y - b.y) > threshold
    }
}

/// 身体动作：状态切换时怎么弹。
public enum MateKick: Equatable, Sendable {
    case none
    case hop(height: Double)          // 往上一跳再落回（开心 / 完成 / 唤醒）
    case perk                         // 竖起来一下（等你、好奇、接任务）
    case shake                        // 左右晃两下（出错）
    case sink                         // 往下一沉（睡觉）
    case nod                          // 轻轻点个头（开始思考 / 检索 / 回话）
}

public enum MateMotion {
    /// 待机呼吸：一次吸气（或呼气）多久；缩放幅度。
    public static let breathSeconds = 1.9
    public static let breathScale = 0.022

    /// 下一次眨眼隔多久（秒）：2.6～6.5 秒随机。r 是 [0, 1) 的随机数，测试时传固定值。
    public static func nextBlink(_ r: Double) -> Double {
        let t = min(max(r, 0), 1)
        return 2.6 + 3.9 * t
    }

    /// 偶尔连眨两下（概率约 18%）。
    public static func doubleBlink(_ r: Double) -> Bool { r < 0.18 }

    /// 点一下：按下时压扁（宽、矮），松手弹过头再回来。返回 (x 缩放, y 缩放)。
    public static let pressSquash = (x: 1.13, y: 0.84)
    public static let releaseStretch = (x: 0.94, y: 1.09)

    /// 很近时身体缩多少、眼睛放大多少。
    public static let nearShrink = 0.93
    public static let nearEyeBoost = 1.16

    /// 表情从 from 变成 to 时身体怎么弹。同一个表情不动。
    public static func kick(from: MateEmotion?, to: MateEmotion) -> MateKick {
        guard let from, from != to else { return .none }
        switch to {
        case .done, .happy: return .hop(height: 10)
        case .wake: return .hop(height: 6)
        case .error: return .shake
        case .listening, .curious, .received: return .perk
        case .sleep: return .sink
        case .thinking, .busy, .searching, .replying: return .nod
        case .standby: return from == .sleep ? .hop(height: 5) : .nod
        }
    }
}
