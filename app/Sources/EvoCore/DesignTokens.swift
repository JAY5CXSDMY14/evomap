import Foundation

/// 第十九轮：设计令牌——间距、圆角、字号、动效时长和弹簧，**只在这一处定义**。
/// 颜色是动态色（浅/深自动换），要 AppKit，放在 Evo/Theme.swift，但也只在那一处；界面代码一律引用令牌，不写裸数字。
/// 这里是纯数字，Linux 上能测（比如「弹簧要克制」「时长从短到长」）。
public enum Tokens {
    /// 间距：4 的倍数。
    public enum Space {
        public static let xxs: Double = 2
        public static let xs: Double = 4
        public static let s: Double = 8
        public static let m: Double = 12
        public static let l: Double = 16
        public static let xl: Double = 24
        public static let xxl: Double = 32
        public static let all: [Double] = [xxs, xs, s, m, l, xl, xxl]
    }

    /// 圆角。
    public enum Radius {
        public static let chip: Double = 6
        public static let field: Double = 8
        public static let small: Double = 10
        public static let card: Double = 14
        public static let sheet: Double = 18
    }

    /// 字号（标题 New York serif，正文 SF）。
    public enum FontSize {
        public static let micro: Double = 10.5
        public static let caption: Double = 11.5
        public static let body: Double = 13
        public static let bodyLarge: Double = 14
        public static let section: Double = 17
        public static let pane: Double = 26
        public static let hero: Double = 30
    }

    /// 动效时长（秒）。
    public enum Duration {
        public static let instant: Double = 0.12     // 按下、悬停
        public static let fast: Double = 0.18        // 淡入淡出、Reduce Motion 下的替代
        public static let base: Double = 0.28        // 页切换、展开
        public static let slow: Double = 0.45        // 卡片飞走、庆祝
        public static let stagger: Double = 0.035    // 列表依次弹入，每项延迟
        public static let staggerMax: Int = 8        // 超过这么多项不再加延迟（长列表不拖）
    }

    /// 弹簧：QQ 弹弹但克制——阻尼 ≥ 0.6（只弹过头一点点），响应 0.25–0.5 秒。
    public struct Spring: Equatable, Sendable {
        public var response: Double
        public var damping: Double
        public init(response: Double, damping: Double) { self.response = response; self.damping = damping }

        public static let press = Spring(response: 0.26, damping: 0.66)    // 按钮按下 / 松手
        public static let pop = Spring(response: 0.34, damping: 0.64)      // 卡片弹入、角标晃
        public static let soft = Spring(response: 0.42, damping: 0.8)      // 页切换、展开收起
        public static let all: [Spring] = [press, pop, soft]

        /// 过冲比例（欠阻尼二阶系统的最大超调）：e^(-ζπ/√(1-ζ²))。
        public var overshoot: Double {
            guard damping < 1 else { return 0 }
            return exp(-damping * .pi / (1 - damping * damping).squareRoot())
        }
    }

    /// 按下缩放：压到 0.96，松手弹回（过冲由弹簧给，不再手动 1.04）。
    public static let pressScale: Double = 0.96
}

/// 动效怎么放：尊重系统「减弱动态效果」；CI 录屏用 EVO_DEMO_MOTION=1 强制照常动。
public enum MotionPolicy: Equatable, Sendable {
    case full      // 弹簧、位移、缩放
    case fade      // 只淡入淡出（Reduce Motion）
    case none      // 静态截图：直接画终态

    public static func resolve(reduceMotion: Bool, forceDemo: Bool, staticRender: Bool = false) -> MotionPolicy {
        if staticRender { return .none }
        if forceDemo { return .full }
        return reduceMotion ? .fade : .full
    }

    /// 列表第 i 项的入场延迟（Reduce Motion / 静态时不延迟）。
    public func staggerDelay(_ i: Int) -> Double {
        guard self == .full, i > 0 else { return 0 }
        return Double(min(i, Tokens.Duration.staggerMax)) * Tokens.Duration.stagger
    }
}
