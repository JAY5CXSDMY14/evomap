#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

/// 设计令牌：暖象牙底、微微抬起的卡片、发丝暖灰边、陶土色强调（只用在主操作和角标）。浅色 / 深色自动切换。
enum Theme {
    static func dynamic(_ light: UInt32, _ dark: UInt32) -> Color {
        Color(nsColor: NSColor(name: nil) { ap in
            let isDark = ap.bestMatch(from: [.darkAqua, .aqua, .vibrantDark, .vibrantLight]).map { $0 == .darkAqua || $0 == .vibrantDark } ?? false
            return NSColor(hex: isDark ? dark : light)
        })
    }

    static let bg            = dynamic(0xFAF9F5, 0x262624)
    static let surface       = dynamic(0xFFFFFF, 0x30302E)
    static let surfaceSunk   = dynamic(0xF0EEE6, 0x1F1E1D)
    static let border        = dynamic(0xE5E1D6, 0x3E3D39)
    static let textPrimary   = dynamic(0x1F1E1D, 0xF5F4EE)
    static let textSecondary = dynamic(0x6B6862, 0xA8A49A)
    static let accent        = dynamic(0xD97757, 0xD97757)
    static let accentPressed = dynamic(0xC2613F, 0xE08A6C)
    static let accentSoft    = dynamic(0xF6E3DA, 0x4A3329)
    static let onAccent      = Color.white
    static let success       = dynamic(0x4F8A5B, 0x7FB88A)
    static let warning       = dynamic(0xB7791F, 0xE0B25C)
    static let danger        = dynamic(0xC0473A, 0xE8806F)
    static let sidebar       = dynamic(0xF0EEE6, 0x1F1E1D)
    static let sidebarSelected = dynamic(0xE3DED1, 0x353430)
    static let mascotBody    = dynamic(0xD97757, 0xDE8566)
    static let mascotFace    = dynamic(0xFBF6EE, 0xFBF6EE)
    static let mascotInk     = dynamic(0x2A2522, 0x2A2522)

    // 第十九轮：数字令牌只在 EvoCore/DesignTokens.swift 定义，这里换成 CGFloat 给 SwiftUI 用
    static let radius = CGFloat(Tokens.Radius.card)
    static let radiusSmall = CGFloat(Tokens.Radius.small)
    static let radiusField = CGFloat(Tokens.Radius.field)

    enum Space {
        static let xxs = CGFloat(Tokens.Space.xxs), xs = CGFloat(Tokens.Space.xs), s = CGFloat(Tokens.Space.s)
        static let m = CGFloat(Tokens.Space.m), l = CGFloat(Tokens.Space.l), xl = CGFloat(Tokens.Space.xl), xxl = CGFloat(Tokens.Space.xxl)
    }

    enum Size {
        static let micro = CGFloat(Tokens.FontSize.micro), caption = CGFloat(Tokens.FontSize.caption), body = CGFloat(Tokens.FontSize.body)
        static let bodyLarge = CGFloat(Tokens.FontSize.bodyLarge), section = CGFloat(Tokens.FontSize.section)
        static let pane = CGFloat(Tokens.FontSize.pane), hero = CGFloat(Tokens.FontSize.hero)
    }

    static func tone(_ t: LoopState.Tone) -> Color {
        switch t {
        case .success: return success
        case .warning: return warning
        case .danger: return danger
        case .neutral: return textSecondary
        }
    }

    // 字体：标题用 New York（serif），正文 SF
    static func title(_ size: CGFloat = Size.section) -> Font { .system(size: size, weight: .semibold, design: .serif) }
    static func body(_ size: CGFloat = Size.body) -> Font { .system(size: size) }
    static func caption(_ size: CGFloat = 11) -> Font { .system(size: size) }
}

extension NSColor {
    convenience init(hex: UInt32) {
        self.init(srgbRed: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
                  blue: CGFloat(hex & 0xFF) / 255, alpha: 1)
    }
}

// MARK: - 动效（QQ 弹弹）

/// 截图 / 预览时关掉入场动画和时间轴动画，直接画最终态。
private struct StaticRenderKey: EnvironmentKey { static let defaultValue = false }
extension EnvironmentValues {
    var evoStatic: Bool {
        get { self[StaticRenderKey.self] }
        set { self[StaticRenderKey.self] = newValue }
    }
}

enum Motion {
    // 第十九轮：弹簧参数来自 Tokens.Spring（阻尼 ≥ 0.6：QQ 弹弹但只过冲一点点）
    static func make(_ sp: Tokens.Spring) -> Animation { .spring(response: sp.response, dampingFraction: sp.damping) }
    static let spring = make(.press)        // 按下回弹
    static let pop = make(.pop)             // 卡片弹入、角标
    static let softSpring = make(.soft)     // 页切换、展开收起
    static let fade = Animation.easeInOut(duration: Tokens.Duration.fast)

    static let forceDemo = ProcessInfo.processInfo.environment["EVO_DEMO_MOTION"] == "1"
    static var policy: MotionPolicy {
        MotionPolicy.resolve(reduceMotion: NSWorkspace.shared.accessibilityDisplayShouldReduceMotion, forceDemo: forceDemo)
    }
    /// 系统开了「减弱动态效果」（CI 录屏 EVO_DEMO_MOTION=1 时照常动）。
    static var reduced: Bool { policy != .full }
    static var reduce: Bool { reduced }

    /// 尊重「减弱动态效果」：开了就只淡入淡出。
    static func or(_ a: Animation) -> Animation { reduced ? fade : a }
}

/// 按钮 / 小胶囊：按下压到 0.96，松手由弹簧带一点点过冲回到 1（不再手动弹到 1.04）。
struct BouncyStyle: ButtonStyle {
    enum Kind { case primary, secondary, ghost, chip, danger }
    var kind: Kind = .secondary
    var compact = false

    func makeBody(configuration: Configuration) -> some View {
        BouncyBody(configuration: configuration, kind: kind, compact: compact)
    }

    private struct BouncyBody: View {
        let configuration: ButtonStyleConfiguration
        let kind: Kind
        let compact: Bool
        @Environment(\.isEnabled) private var enabled
        private var reduceMotion: Bool { Motion.reduced }

        var body: some View {
            configuration.label
                .font(.system(size: compact ? 12 : Theme.Size.body, weight: kind == .primary ? .semibold : .medium))
                .padding(.horizontal, compact ? 10 : 14)
                .padding(.vertical, compact ? 5 : 7)
                .foregroundStyle(fg)
                .background(bgShape)
                .contentShape(Capsule())
                .scaleEffect(reduceMotion || !configuration.isPressed ? 1 : CGFloat(Tokens.pressScale))
                .opacity(enabled ? 1 : 0.45)
                .animation(reduceMotion ? nil : Motion.spring, value: configuration.isPressed)
        }

        private var fg: Color {
            switch kind {
            case .primary: return Theme.onAccent
            case .danger: return Theme.danger
            case .chip, .secondary, .ghost: return Theme.textPrimary
            }
        }

        @ViewBuilder private var bgShape: some View {
            switch kind {
            case .primary:
                Capsule().fill(configuration.isPressed ? Theme.accentPressed : Theme.accent)
                    .shadow(color: Theme.accent.opacity(0.28), radius: 6, y: 2)
            case .secondary, .danger:
                Capsule().fill(Theme.surface).overlay(Capsule().strokeBorder(Theme.border, lineWidth: 1))
            case .chip:
                Capsule().fill(configuration.isPressed ? Theme.accentSoft : Theme.surface)
                    .overlay(Capsule().strokeBorder(Theme.border, lineWidth: 1))
            case .ghost:
                Capsule().fill(configuration.isPressed ? Theme.surfaceSunk : Color.clear)
            }
        }
    }
}

/// 卡片底：白（深色时略亮）+ 发丝边 + 柔影。
struct CardBackground: ViewModifier {
    var highlighted = false
    func body(content: Content) -> some View {
        content
            .background(
                RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                    .fill(Theme.surface)
                    .shadow(color: .black.opacity(highlighted ? 0.10 : 0.05), radius: highlighted ? 10 : 6, y: highlighted ? 4 : 2)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                    .strokeBorder(highlighted ? Theme.accent.opacity(0.55) : Theme.border, lineWidth: 1)
            )
    }
}

extension View {
    func card(highlighted: Bool = false) -> some View { modifier(CardBackground(highlighted: highlighted)) }

    /// 依次弹入：index 越大越晚（每个 Tokens.Duration.stagger，最多 8 个），从下面 6pt、0.98 倍弹到位。
    func staggeredAppear(_ index: Int) -> some View { modifier(StaggerIn(index: index)) }
}

struct StaggerIn: ViewModifier {
    let index: Int
    @State private var shown = false
    @Environment(\.evoStatic) private var isStatic

    func body(content: Content) -> some View {
        let on = shown || isStatic
        let policy = Motion.policy
        content
            .opacity(on ? 1 : 0)
            .offset(y: on || policy != .full ? 0 : 6)
            .scaleEffect(on || policy != .full ? 1 : 0.98, anchor: .top)
            .onAppear {
                guard !isStatic else { return }
                withAnimation(policy == .full ? Motion.pop.delay(policy.staggerDelay(index)) : Motion.fade) { shown = true }
            }
    }
}

/// 小开关（自己画，截图里也能显示；行为同 Toggle）。
struct PillToggleStyle: ToggleStyle {
    func makeBody(configuration: Configuration) -> some View {
        Button { configuration.isOn.toggle() } label: {
            HStack(spacing: 10) {
                configuration.label.foregroundStyle(Theme.textPrimary)
                Spacer(minLength: 8)
                ZStack(alignment: configuration.isOn ? .trailing : .leading) {
                    Capsule().fill(configuration.isOn ? Theme.accent : Theme.textSecondary.opacity(0.35)).frame(width: 34, height: 20)   // 关着的底色：深色卡片上也看得清（0.7.0）
                    Circle().fill(.white).frame(width: 16, height: 16).padding(2).shadow(color: .black.opacity(0.15), radius: 1, y: 1)
                }
                .animation(Motion.or(Motion.spring), value: configuration.isOn)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityValue(configuration.isOn ? "开" : "关")
    }
}

/// 圆点 + 文字的状态胶囊。
struct StatePill: View {
    let state: LoopState
    private var reduceMotion: Bool { Motion.reduced }   // 第十九轮：统一走 Motion.policy（CI 可强制动）

    var body: some View {
        let c = Theme.tone(state.tone)
        HStack(spacing: 5) {
            Circle().fill(c).frame(width: 6, height: 6)
            Text(state.label).font(.system(size: 11, weight: .medium)).foregroundStyle(c)
        }
        .padding(.horizontal, 9).padding(.vertical, 4)
        .background(Capsule().fill(c.opacity(0.12)))
        .id(state.label)
        .transition(.scale(scale: 0.8).combined(with: .opacity))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("循环状态：\(state.label)")
    }
}

/// 输入框外壳：截图模式下画成静态文字（离屏渲染画不出 AppKit 输入框光标等）。
struct ThemedField: View {
    let placeholder: String
    @Binding var text: String
    var onSubmit: () -> Void = {}
    @Environment(\.evoStatic) private var isStatic

    var body: some View {
        Group {
            if isStatic {
                Text(text.isEmpty ? placeholder : text)
                    .foregroundStyle(text.isEmpty ? Theme.textSecondary : Theme.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                TextField(placeholder, text: $text)
                    .textFieldStyle(.plain)
                    .foregroundStyle(Theme.textPrimary)
                    .onSubmit(onSubmit)
            }
        }
        .font(Theme.body())
    }
}

/// 自画的小转圈（离屏截图也能画）。
/// 转圈：用系统的 ProgressView（第十九轮起不再自己写 repeatForever 旋转——那种动画会顺着事务漏到同层布局上）。
/// 截图（静态渲染）时 ProgressView 画不出来，画一段静止的弧。
struct Spinner: View {
    var size: CGFloat = 12
    @Environment(\.evoStatic) private var isStatic
    var body: some View {
        Group {
            if isStatic {
                Circle().trim(from: 0.1, to: 0.8)
                    .stroke(Theme.accent, style: StrokeStyle(lineWidth: 2, lineCap: .round))
            } else {
                ProgressView().progressViewStyle(.circular).controlSize(.small)
                    .scaleEffect(size / 16)
            }
        }
        .frame(width: size, height: size)
        .accessibilityLabel("进行中")
    }
}
#endif
