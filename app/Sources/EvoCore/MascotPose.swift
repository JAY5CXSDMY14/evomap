import Foundation

/// 吉祥物在某一时刻的姿态（纯数学，界面用 TimelineView 每帧取一次；截图取固定时刻）。
/// 所有量都是相对值：眼睛偏移以眼宽为单位，弹跳以身高为单位。
public struct MascotPose: Equatable, Sendable {
    public var eyeOpen: Double        // 1 睁开，0 闭上
    public var eyeDX: Double          // 眼珠左右，-1…1
    public var eyeDY: Double          // 眼珠上下，-1…1
    public var bob: Double            // 身体上下，-1…1（负数往上）
    public var squash: Double         // 落地压扁，0…1
    public var browRaise: Double      // 眉毛，-1 皱眉 … 1 挑眉
    public var mouthCurve: Double     // 嘴，-1 撇嘴 … 1 笑
    public var tilt: Double           // 头歪，角度（度）
    public var zzz: Double            // 睡觉的 Z 出现进度 0…1（循环）

    public static let rest = MascotPose(eyeOpen: 1, eyeDX: 0, eyeDY: 0, bob: 0, squash: 0, browRaise: 0, mouthCurve: 0.6, tilt: 0, zzz: 0)

    /// 眨眼：每 `period` 秒眨一次，持续 0.16 秒（中间闭上）。
    public static func blink(_ t: Double, period: Double = 3.6, phase: Double = 0.7) -> Double {
        let x = (t + phase).truncatingRemainder(dividingBy: period)
        let d = 0.16
        guard x < d else { return 1 }
        return abs(x / d * 2 - 1)            // 1 → 0 → 1
    }

    /// 弹跳：|sin|，落地那一下压扁。
    static func bounce(_ t: Double, period: Double) -> (Double, Double) {
        let p = (t / period).truncatingRemainder(dividingBy: 1)
        let h = sin(p * .pi)                 // 0 → 1 → 0
        let squash = max(0, 1 - h * 6) * 0.6 // 只在落地附近压
        return (-h, squash)
    }

    public static func at(_ t: Double, mood: MascotMood, reduceMotion: Bool = false) -> MascotPose {
        var p = MascotPose.rest
        switch mood {
        case .idle:
            p.mouthCurve = 0.7
            p.bob = reduceMotion ? 0 : sin(t * 1.3) * 0.15
            p.eyeOpen = blink(t)
        case .working:
            p.mouthCurve = 0.3
            // 东张西望：左 → 中 → 右 → 中，4 秒一圈，平滑过渡
            let c = (t / 4).truncatingRemainder(dividingBy: 1)
            p.eyeDX = reduceMotion ? 0.5 : sin(c * 2 * .pi) * 0.8
            p.eyeDY = reduceMotion ? 0 : -abs(cos(c * 2 * .pi)) * 0.15
            p.bob = reduceMotion ? 0 : sin(t * 5) * 0.35
            p.tilt = reduceMotion ? 0 : sin(c * 2 * .pi) * 4
            p.eyeOpen = blink(t, period: 4.4)
        case .waiting:
            p.browRaise = 1
            p.mouthCurve = 0.9
            p.eyeDY = -0.3
            if !reduceMotion {
                let (b, s) = bounce(t, period: 1.1)
                p.bob = b * 0.8; p.squash = s
            }
            p.eyeOpen = blink(t, period: 3.0)
        case .worried:
            p.browRaise = -1
            p.mouthCurve = -0.7
            p.eyeDY = 0.2
            p.tilt = reduceMotion ? -4 : -4 + sin(t * 2.2) * 2
            p.eyeOpen = blink(t, period: 2.6) * 0.9
        case .sleepy:
            p.eyeOpen = 0.08
            p.mouthCurve = 0.1
            p.bob = reduceMotion ? 0 : sin(t * 0.9) * 0.25   // 慢慢呼吸
            p.tilt = 6
            p.zzz = reduceMotion ? 0.6 : (t / 2.4).truncatingRemainder(dividingBy: 1)
        }
        return p
    }
}
