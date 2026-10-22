#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

/// evo 的吉祥物「小陶」：圆滚滚的陶土色小机器人，象牙色脸罩、两只椭圆眼、一根带球的小天线。
/// 全部矢量画（不需要图片资源）。姿态由 EvoCore.MascotPose 按时间算，这里只负责画。
struct EvoMascot: View {
    var mood: MascotMood
    var size: CGFloat = 44
    /// 固定时刻（截图用）；nil = 跟着时间动。
    var frozenAt: Double? = nil

    @Environment(\.evoStatic) private var isStatic
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Group {
            if isStatic || frozenAt != nil {
                MascotDrawing(pose: MascotPose.at(frozenAt ?? 0.4, mood: mood, reduceMotion: reduceMotion), size: size)
            } else {
                TimelineView(.animation(minimumInterval: 1.0 / 30)) { ctx in
                    MascotDrawing(pose: MascotPose.at(ctx.date.timeIntervalSinceReferenceDate, mood: mood, reduceMotion: reduceMotion), size: size)
                }
            }
        }
        .frame(width: size, height: size * 1.1)
        .accessibilityElement()
        .accessibilityLabel(Self.moodText(mood))
    }

    static func moodText(_ m: MascotMood) -> String {
        switch m {
        case .idle: return "小陶：一切顺利"
        case .working: return "小陶：正在干活"
        case .waiting: return "小陶：有事等你"
        case .worried: return "小陶：有点担心"
        case .sleepy: return "小陶：在睡觉"
        }
    }
}

/// 一帧。坐标以 size 为单位。
struct MascotDrawing: View {
    var pose: MascotPose
    var size: CGFloat
    var mono = false          // 菜单栏用的单色版

    var body: some View {
        let s = size
        let bodyColor = mono ? Color.black : Theme.mascotBody
        let face = mono ? Color.clear : Theme.mascotFace
        let ink = mono ? Color.black : Theme.mascotInk
        let bobY = CGFloat(pose.bob) * s * 0.06
        let sq = CGFloat(pose.squash)

        ZStack {
            // 地上的影子（跳起来变小）
            if !mono {
                Ellipse().fill(Color.black.opacity(0.10))
                    .frame(width: s * (0.62 + 0.1 * CGFloat(pose.bob)), height: s * 0.08)
                    .offset(y: s * 0.50)
            }
            ZStack {
                // 天线
                Capsule().fill(bodyColor).frame(width: s * 0.05, height: s * 0.16).offset(y: -s * 0.43)
                Circle().fill(mono ? Color.black : Theme.accentPressed).frame(width: s * 0.13).offset(y: -s * 0.52)
                if !mono { Circle().fill(.white.opacity(0.55)).frame(width: s * 0.04).offset(x: -s * 0.02, y: -s * 0.54) }
                // 耳朵
                Capsule().fill(bodyColor).frame(width: s * 0.12, height: s * 0.24).offset(x: -s * 0.43, y: s * 0.02)
                Capsule().fill(bodyColor).frame(width: s * 0.12, height: s * 0.24).offset(x: s * 0.43, y: s * 0.02)
                // 身体（圆角豆子）
                RoundedRectangle(cornerRadius: s * 0.32, style: .continuous).fill(bodyColor)
                    .frame(width: s * 0.84, height: s * 0.76)
                    .overlay(alignment: .topLeading) {
                        if !mono {
                            Capsule().fill(.white.opacity(0.22)).frame(width: s * 0.22, height: s * 0.07)
                                .rotationEffect(.degrees(-20)).offset(x: s * 0.12, y: s * 0.08)
                        }
                    }
                // 脸罩
                if mono {
                    RoundedRectangle(cornerRadius: s * 0.22, style: .continuous)
                        .fill(Color.black)
                        .frame(width: s * 0.66, height: s * 0.48)
                        .blendMode(.destinationOut)
                        .offset(y: s * 0.02)
                } else {
                    RoundedRectangle(cornerRadius: s * 0.22, style: .continuous).fill(face)
                        .frame(width: s * 0.66, height: s * 0.48).offset(y: s * 0.02)
                }
                faceFeatures(s: s, ink: ink)
                    .offset(y: s * 0.02)
            }
            .compositingGroup()
            .scaleEffect(x: 1 + sq * 0.12, y: 1 - sq * 0.10, anchor: .bottom)
            .rotationEffect(.degrees(pose.tilt))
            .offset(y: bobY)

            if pose.zzz > 0 && !mono {
                let z = CGFloat(pose.zzz)
                Text("z").font(.system(size: s * (0.16 + 0.1 * z), weight: .heavy, design: .rounded))
                    .foregroundStyle(Theme.textSecondary.opacity(Double(1 - z)))
                    .offset(x: s * (0.36 + 0.12 * z), y: -s * (0.30 + 0.25 * z))
            }
        }
        .frame(width: s, height: s * 1.1)
    }

    @ViewBuilder
    private func faceFeatures(s: CGFloat, ink: Color) -> some View {
        let eyeW = s * 0.12, eyeH = s * 0.17 * CGFloat(max(0.08, pose.eyeOpen))
        let dx = CGFloat(pose.eyeDX) * s * 0.035, dy = CGFloat(pose.eyeDY) * s * 0.03
        let eyeColor: Color = ink
        ZStack {
            // 眼睛
            ForEach([-1.0, 1.0], id: \.self) { side in
                ZStack {
                    Capsule().fill(eyeColor).frame(width: eyeW, height: max(eyeH, s * 0.025))
                    if pose.eyeOpen > 0.5 && !mono {
                        Circle().fill(.white).frame(width: eyeW * 0.38).offset(x: eyeW * 0.15, y: -eyeH * 0.22)
                    }
                }
                .offset(x: CGFloat(side) * s * 0.14 + dx, y: -s * 0.03 + dy)
                // 眉毛
                if abs(pose.browRaise) > 0.1 {
                    Capsule().fill(eyeColor).frame(width: s * 0.11, height: s * 0.028)
                        .rotationEffect(.degrees(side * (pose.browRaise > 0 ? -12.0 : 18.0)))
                        .offset(x: CGFloat(side) * s * 0.14, y: -s * (0.15 + 0.03 * CGFloat(pose.browRaise)))
                }
            }
            // 腮红
            if !mono {
                ForEach([-1.0, 1.0], id: \.self) { side in
                    Ellipse().fill(Theme.accent.opacity(0.35)).frame(width: s * 0.09, height: s * 0.05)
                        .offset(x: CGFloat(side) * s * 0.24, y: s * 0.07)
                }
            }
            // 嘴
            MouthShape(curve: pose.mouthCurve)
                .stroke(eyeColor, style: StrokeStyle(lineWidth: max(1, s * 0.032), lineCap: .round))
                .frame(width: s * 0.14, height: s * 0.06)
                .offset(y: s * 0.10)
        }
    }

    private var mono_: Bool { mono }
}

struct MouthShape: Shape {
    var curve: Double
    var animatableData: Double { get { curve } set { curve = newValue } }
    func path(in r: CGRect) -> Path {
        var p = Path()
        let mid = r.midY
        p.move(to: CGPoint(x: r.minX, y: mid - CGFloat(curve) * r.height * 0.3))
        p.addQuadCurve(to: CGPoint(x: r.maxX, y: mid - CGFloat(curve) * r.height * 0.3),
                       control: CGPoint(x: r.midX, y: mid + CGFloat(curve) * r.height))
        return p
    }
}

/// 菜单栏图标：彩色小调度球（10-22 老板要「跟应用图标一样的调度球」，不再用单色模板脸）。
/// 珊瑚橙软球 + 两只略斜的竖椭圆眼；随心情变：施工 → 眼睛往右看，等你 → 眼睛睁大上抬，
/// 出错 / 卡住 → 球变红、眼睛八字，暂停 → 球变淡、眼睛闭成弧线。浅色 / 深色菜单栏都看得清。
@MainActor
enum MenuBarIcon {
    private static var cache: [MascotMood: NSImage] = [:]

    static func image(_ mood: MascotMood) -> NSImage {
        if let i = cache[mood] { return i }
        let r = ImageRenderer(content: DispatchBallIcon(mood: mood).frame(width: 18, height: 18))
        r.scale = 2
        let img = r.nsImage ?? NSImage(systemSymbolName: "circle.fill", accessibilityDescription: nil)!
        img.isTemplate = false
        img.accessibilityDescription = "Evo"
        cache[mood] = img
        return img
    }
}

/// 小调度球本体（菜单栏 18pt；也可放大用）。纯 SwiftUI 形状，不用图片。
struct DispatchBallIcon: View {
    var mood: MascotMood

    private var colors: (Color, Color) {
        switch mood {
        case .worried: return (Color(red: 1.0, green: 0.47, blue: 0.39), Color(red: 0.78, green: 0.20, blue: 0.18))
        case .sleepy:  return (Color(red: 0.94, green: 0.63, blue: 0.53), Color(red: 0.77, green: 0.43, blue: 0.35))
        default:       return (Color(red: 1.0, green: 0.63, blue: 0.46), Color(red: 0.89, green: 0.34, blue: 0.22))
        }
    }

    var body: some View {
        GeometryReader { g in
            let d = min(g.size.width, g.size.height) * 0.92
            let u = d / 2                                   // 球半径
            let c = CGPoint(x: g.size.width / 2, y: g.size.height / 2)
            let ink = Color(red: 0.09, green: 0.086, blue: 0.11)
            let shift: CGFloat = mood == .working ? 0.14 : 0
            let lift: CGFloat = mood == .waiting ? -0.06 : 0
            let eyes = [CGPoint(x: -0.30 + shift, y: -0.08 + lift), CGPoint(x: 0.22 + shift, y: -0.18 + lift)]
            let (rx, ry): (CGFloat, CGFloat) = mood == .waiting ? (0.15, 0.29) : mood == .worried ? (0.12, 0.22) : (0.13, 0.26)
            ZStack {
                Circle()
                    .fill(RadialGradient(colors: [colors.0, colors.1], center: UnitPoint(x: 0.35, y: 0.28),
                                         startRadius: 0, endRadius: d * 0.75))
                    .frame(width: d, height: d)
                    .position(c)
                Ellipse()                                   // 左上一点高光
                    .fill(Color.white.opacity(0.38))
                    .frame(width: u * 0.52, height: u * 0.36)
                    .blur(radius: u * 0.06)
                    .position(x: c.x - u * 0.36, y: c.y - u * 0.60)
                ForEach(0..<2, id: \.self) { i in
                    let p = CGPoint(x: c.x + eyes[i].x * u, y: c.y + eyes[i].y * u)
                    if mood == .sleepy {
                        ClosedEye().stroke(ink, style: StrokeStyle(lineWidth: u * 0.13, lineCap: .round))
                            .frame(width: u * 0.34, height: u * 0.16)
                            .position(p)
                    } else {
                        Ellipse().fill(ink)
                            .frame(width: rx * 2 * u, height: ry * 2 * u)
                            .rotationEffect(.degrees(mood == .worried ? (i == 0 ? -14 : 14) : 20))
                            .position(p)
                        if mood != .worried {
                            Circle().fill(Color.white.opacity(0.9))
                                .frame(width: u * 0.08, height: u * 0.08)
                                .position(x: p.x - u * 0.04, y: p.y - u * 0.11)
                        }
                    }
                }
            }
        }
        .accessibilityHidden(true)
    }
}

/// 闭着的眼：往下弯的一道弧。
private struct ClosedEye: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: r.minX, y: r.minY))
        p.addQuadCurve(to: CGPoint(x: r.maxX, y: r.minY), control: CGPoint(x: r.midX, y: r.maxY * 1.6))
        return p
    }
}

/// 气泡：吉祥物说话（左）或你说的话（右）。
struct SpeechBubble: View {
    enum Side { case evo, me }
    var text: String
    var side: Side = .evo
    var tone: LoopState.Tone = .neutral

    // 两块形状先用不透明色画、合成后再整体调透明度，交叠处才不会更深
    private var fill: Color {
        side == .me ? Theme.accent : (tone == .danger ? Theme.danger : Theme.surfaceSunk)
    }
    private var fillOpacity: Double { side == .evo && tone == .danger ? 0.14 : 1 }

    var body: some View {
        Text(text)
            .font(Theme.body(12.5))
            .foregroundStyle(side == .me ? Theme.onAccent : Theme.textPrimary)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, 11).padding(.vertical, 7)
            .background(
                ZStack {
                    RoundedRectangle(cornerRadius: 12, style: .continuous).fill(fill)
                    BubbleShape(tailLeft: side == .evo).fill(fill)
                }
                .compositingGroup()
                .opacity(fillOpacity)
            )
            .accessibilityLabel(side == .evo ? "evo 说：\(text)" : "你说：\(text)")
    }
}

struct BubbleShape: Shape {
    var tailLeft: Bool
    func path(in r: CGRect) -> Path {
        // 只画小尾巴（闭合小三角）；圆角矩形单独画，两个同色叠在一起，避免绕向相反挖出洞
        var t = Path()
        if tailLeft {
            t.move(to: CGPoint(x: r.minX + 4, y: r.maxY - 12))
            t.addQuadCurve(to: CGPoint(x: r.minX - 4, y: r.maxY + 1), control: CGPoint(x: r.minX + 2, y: r.maxY - 3))
            t.addQuadCurve(to: CGPoint(x: r.minX + 14, y: r.maxY), control: CGPoint(x: r.minX + 5, y: r.maxY + 1))
        } else {
            t.move(to: CGPoint(x: r.maxX - 4, y: r.maxY - 12))
            t.addQuadCurve(to: CGPoint(x: r.maxX + 4, y: r.maxY + 1), control: CGPoint(x: r.maxX - 2, y: r.maxY - 3))
            t.addQuadCurve(to: CGPoint(x: r.maxX - 14, y: r.maxY), control: CGPoint(x: r.maxX - 5, y: r.maxY + 1))
        }
        t.closeSubpath()
        return t
    }
}
#endif
