#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

/// 菜单栏弹窗（MenuBarExtra .window）。v0.3.0 起变紧凑：问候 + 状态、一行汇总、最前面两张闸门卡、「打开 Evo 窗口」。
/// 细看、项目、时间线、输入框都在主窗口里。
struct MainPopover: View {
    @ObservedObject var state: AppState
    /// 截图时固定时间；nil = 现在。
    var now: Date? = nil

    @Environment(\.evoStatic) private var isStatic
    @State private var hoveredCard: String?

    static let width = CGFloat(WindowSizing.popoverWidth)

    var body: some View {
        let cards = state.cards
        let shown = Array(cards.prefix(WindowSizing.popoverCards))
        VStack(spacing: 0) {
            HeaderView(state: state, now: now)
                .padding(.horizontal, 16).padding(.top, 16).padding(.bottom, 12)
                .staggeredAppear(0)
            VStack(alignment: .leading, spacing: 12) {
                SummaryStrip(state: state).staggeredAppear(1)
                if let f = state.focusedProject { FocusChip(code: f) { withAnimation(Motion.or(Motion.spring)) { state.focusedProject = nil } } }
                GatesSection(state: state, cards: shown, total: cards.count, focusedID: focusedID(shown), hovered: $hoveredCard)
                if cards.count > shown.count {
                    Button { MainWindowController.shared.show() } label: {
                        HStack(spacing: 4) { Text("还有 \(cards.count - shown.count) 件，去窗口里看"); Image(systemName: "arrow.right") }
                            .font(.system(size: 12, weight: .medium)).foregroundStyle(Theme.accent)
                    }
                    .buttonStyle(PressScale())
                    .frame(maxWidth: .infinity, alignment: .center)
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 14)
            VStack(spacing: 10) {
                Button { MainWindowController.shared.show() } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "macwindow")
                        Text("打开 Evo 窗口")
                        Spacer(minLength: 0)
                        Text("⌘0").font(.system(size: 11, weight: .medium, design: .rounded)).opacity(0.8)
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(BouncyStyle(kind: .primary))
                .uiProbe("pop-open-window")
                FooterView(state: state)
            }
            .padding(.horizontal, 16).padding(.vertical, 12)
            .background(Theme.bg.overlay(alignment: .top) { Rectangle().fill(Theme.border).frame(height: 1) })
        }
        .frame(width: Self.width)
        .background(Theme.bg)
        .animation(Motion.or(Motion.pop), value: cards.map(\.id))
        .background(shortcuts)
        .onAppear { if !isStatic { state.popoverShown = true } }
        .onDisappear { if !isStatic { state.popoverShown = false } }
    }

    private func focusedID(_ cards: [GateCard]) -> String? {
        if let h = hoveredCard, cards.contains(where: { $0.id == h }) { return h }
        return cards.first?.id
    }

    /// 看不见的按钮，只为挂快捷键：⌘0 打开窗口、⌘1…9 只看项目、⌘↩ 通过当前卡片、⌘K 命令面板、⌘R 刷新。
    private var shortcuts: some View {
        ZStack {
            Button("") { MainWindowController.shared.show() }.keyboardShortcut("0", modifiers: .command)
            ForEach(1..<10) { d in
                Button("") { withAnimation(Motion.or(Motion.spring)) { state.focus(digit: d) } }
                    .keyboardShortcut(KeyEquivalent(Character(String(d))), modifiers: .command)
            }
            Button("") {
                if let id = focusedID(Array(state.cards.prefix(WindowSizing.popoverCards))), let c = state.card(id: id) {
                    withAnimation(Motion.or(Motion.pop)) { state.approve(c) }
                }
            }
            .keyboardShortcut(.return, modifiers: .command)
            Button("") { PaletteController.shared.show() }.keyboardShortcut("k", modifiers: .command)
            Button("") { state.refresh() }.keyboardShortcut("r", modifiers: .command)
        }
        .opacity(0).frame(width: 0, height: 0).accessibilityHidden(true)
    }
}

/// 一行汇总：等你 / 施工 / 验收 / 卡住 / 卡太久（跨项目）。
struct SummaryStrip: View {
    @ObservedObject var state: AppState
    var body: some View {
        let t = state.totals
        HStack(spacing: 0) {
            Metric(label: "等你", n: state.allCards.count, color: Theme.accent).frame(maxWidth: .infinity)
            Metric(label: "施工", n: t.building, color: Theme.textPrimary).frame(maxWidth: .infinity)
            Metric(label: "验收", n: t.verifying, color: Theme.textPrimary).frame(maxWidth: .infinity)
            Metric(label: "卡住", n: t.stuck, color: Theme.danger).frame(maxWidth: .infinity)
            Metric(label: "卡太久", n: t.tooLong, color: Theme.warning).frame(maxWidth: .infinity)
        }
        .padding(.vertical, 8)
        .background(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).fill(Theme.surfaceSunk))
        .accessibilityElement(children: .combine)
    }
}

/// 截图模式下 ScrollView 换成普通 VStack（离屏渲染时 ScrollView 的高度算不准）。
struct MaybeScroll<Content: View>: View {
    var maxHeight: CGFloat
    @ViewBuilder var content: () -> Content
    @Environment(\.evoStatic) private var isStatic
    var body: some View {
        if isStatic { content() } else {
            ScrollView(.vertical, showsIndicators: false) { content() }.frame(maxHeight: maxHeight).fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: - 头部

struct HeaderView: View {
    @ObservedObject var state: AppState
    var now: Date?
    @Environment(\.evoStatic) private var isStatic

    private static let hm: DateFormatter = { let f = DateFormatter(); f.dateFormat = "HH:mm"; return f }()

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .center, spacing: 12) {
                MateView(emotion: state.mateEmotion, celebrate: state.mateCelebrate, size: 50, followMouse: true)
                    .uiProbe("pop-mate")
                VStack(alignment: .leading, spacing: 2) {
                    if isStatic || now != nil { titleText(now ?? Date()) } else {
                        TimelineView(.everyMinute) { ctx in titleText(ctx.date) }
                    }
                }
                Spacer(minLength: 6)
                StatePill(state: state.loopState)
                    .animation(Motion.or(Motion.pop), value: state.loopState.label)
            }
            HStack(alignment: .bottom, spacing: 0) {
                Spacer().frame(width: 14)
                SpeechBubble(text: state.flash ?? state.busy ?? state.speech,
                             tone: state.flash?.hasPrefix("没成") == true ? .danger : state.loopState.tone)
                    .id(state.flash ?? state.busy ?? state.speech)
                    .transition(.scale(scale: 0.85, anchor: .bottomLeading).combined(with: .opacity))
                Spacer(minLength: 0)
            }
            .animation(Motion.or(Motion.pop), value: state.flash ?? state.busy ?? state.speech)
        }
    }

    private func titleText(_ d: Date) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("\(Greeting.text(at: d))，老板").font(Theme.title(19)).foregroundStyle(Theme.textPrimary)
                .accessibilityAddTraits(.isHeader)
            Text("\(Self.hm.string(from: d)) · \(state.snaps.count) 个项目").font(Theme.caption()).foregroundStyle(Theme.textSecondary)
        }
    }
}

struct FocusChip: View {
    let code: String
    let clear: () -> Void
    var body: some View {
        Button(action: clear) {
            HStack(spacing: 4) { Text("只看 \(code)"); Image(systemName: "xmark").font(.system(size: 9, weight: .bold)) }
        }
        .buttonStyle(BouncyStyle(kind: .chip, compact: true))
        .accessibilityLabel("只看 \(code)，点一下看全部")
    }
}

// MARK: - 等你处理

struct SectionTitle: View {
    let text: String
    var count: Int? = nil
    var body: some View {
        HStack(spacing: 6) {
            Text(text).font(Theme.title(14)).foregroundStyle(Theme.textPrimary).accessibilityAddTraits(.isHeader)
            if let count, count > 0 { JiggleBadge(count: count) }
            Spacer()
        }
    }
}

/// 数字变了就晃一下、弹一下。
struct JiggleBadge: View {
    let count: Int
    @State private var angle: Double = 0
    @State private var scale: CGFloat = 1
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Text("\(count)")
            .font(.system(size: 11, weight: .bold, design: .rounded))
            .foregroundStyle(Theme.onAccent)
            .padding(.horizontal, 6).frame(minWidth: 18, minHeight: 18)
            .background(Capsule().fill(Theme.accent))
            .rotationEffect(.degrees(angle)).scaleEffect(scale)
            .onChange(of: count) { _ in jiggle() }
            .accessibilityLabel("\(count) 件")
    }

    private func jiggle() {
        guard !reduceMotion else { return }
        let steps: [(Double, CGFloat)] = [(-14, 1.25), (11, 1.15), (-7, 1.05), (3, 1.0), (0, 1.0)]
        for (i, s) in steps.enumerated() {
            DispatchQueue.main.asyncAfter(deadline: .now() + Double(i) * 0.07) {
                withAnimation(.spring(response: 0.18, dampingFraction: 0.5)) { angle = s.0; scale = s.1 }
            }
        }
    }
}

struct GatesSection: View {
    @ObservedObject var state: AppState
    let cards: [GateCard]
    var total: Int? = nil
    let focusedID: String?
    @Binding var hovered: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionTitle(text: "等你处理", count: total ?? cards.count).staggeredAppear(1)
            if cards.isEmpty {
                EmptyState().staggeredAppear(2).transition(.scale(scale: 0.9).combined(with: .opacity))
            } else {
                ForEach(Array(cards.enumerated()), id: \.element.id) { i, c in
                    GateCardView(state: state, card: c, focused: c.id == focusedID, probe: "pop-gate-\(c.id)")
                        .onHover { h in hovered = h ? c.id : (hovered == c.id ? nil : hovered) }
                        .staggeredAppear(2 + i)
                        .transition(.asymmetric(
                            insertion: .scale(scale: 0.9, anchor: .top).combined(with: .opacity).combined(with: .offset(y: 10)),
                            removal: .scale(scale: 0.5, anchor: .trailing).combined(with: .opacity).combined(with: .offset(x: 140, y: -14))))
                }
            }
        }
    }
}

struct EmptyState: View {
    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                Circle().fill(Theme.accentSoft).frame(width: 54, height: 54)
                Image(systemName: "leaf").font(.system(size: 24, weight: .regular)).foregroundStyle(Theme.accent)
            }
            Text("一切顺利").font(Theme.title(16)).foregroundStyle(Theme.textPrimary)
            Text("没有要你点头的事，喝口茶吧").font(Theme.caption(12)).foregroundStyle(Theme.textSecondary)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 18)
        .card()
        .accessibilityElement(children: .combine)
    }
}

struct GateCardView: View {
    @ObservedObject var state: AppState
    let card: GateCard
    let focused: Bool
    var probe: String? = nil                // UI 测试点位名前缀（pop-gate-0 / win-gate-0）
    var openItem: (() -> Void)? = nil       // 窗口里：打开这件的时间线
    @State private var rejecting = false
    @State private var words = ""
    @FocusState private var wordsFocused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Text(card.project)
                    .font(.system(size: 10.5, weight: .bold, design: .rounded))
                    .foregroundStyle(Theme.accent)
                    .padding(.horizontal, 7).padding(.vertical, 2)
                    .background(Capsule().fill(Theme.accentSoft))
                Label(card.kindLabel, systemImage: Self.symbol(card.kind))
                    .font(.system(size: 11, weight: .medium)).foregroundStyle(Theme.textSecondary)
                    .labelStyle(.titleAndIcon)
                Spacer()
                if let age = card.ageText() {
                    Label(age, systemImage: "clock").font(.system(size: 10.5)).foregroundStyle(Theme.textSecondary)
                }
            }
            VStack(alignment: .leading, spacing: 2) {
                if let item = card.itemID {
                    Text(item).font(.system(size: 10.5, design: .monospaced)).foregroundStyle(Theme.textSecondary)
                }
                Text(card.title).font(.system(size: 13.5, weight: .semibold)).foregroundStyle(Theme.textPrimary)
                    .lineLimit(2).fixedSize(horizontal: false, vertical: true)
            }
            if rejecting {
                HStack(spacing: 8) {
                    ThemedField(placeholder: "打回原话（会进返工说明）", text: $words) { sendReject() }
                        .focused($wordsFocused)
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(RoundedRectangle(cornerRadius: Theme.radiusSmall).fill(Theme.surfaceSunk))
                    Button("发送") { sendReject() }.buttonStyle(BouncyStyle(kind: .primary, compact: true))
                        .uiProbe(probe.map { "\($0)-send" })
                    Button { withAnimation(Motion.or(Motion.spring)) { rejecting = false } } label: { Image(systemName: "xmark") }
                        .buttonStyle(BouncyStyle(kind: .ghost, compact: true)).accessibilityLabel("取消打回")
                }
                .transition(.scale(scale: 0.95, anchor: .top).combined(with: .opacity))
            } else {
                HStack(spacing: 8) {
                    Button { withAnimation(Motion.or(Motion.pop)) { state.approve(card) } } label: {
                        Label(card.approveChoice, systemImage: "checkmark")
                    }
                    .buttonStyle(BouncyStyle(kind: .primary, compact: true))
                    .uiProbe(probe.map { "\($0)-approve" })
                    .accessibilityLabel("\(card.approveChoice)：\(card.title)")
                    .accessibilityHint(focused ? "快捷键 Command 回车" : "")
                    Button {
                        if card.rejectAsksWords {
                            withAnimation(Motion.or(Motion.spring)) { rejecting = true }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) { wordsFocused = true }
                        } else {
                            withAnimation(Motion.or(Motion.pop)) { state.reject(card, words: nil) }
                        }
                    } label: { Label(card.rejectChoice, systemImage: "arrow.uturn.backward") }
                    .buttonStyle(BouncyStyle(kind: .secondary, compact: true))
                    .uiProbe(probe.map { "\($0)-reject" })
                    .accessibilityLabel("\(card.rejectChoice)：\(card.title)")
                    if let openItem {
                        Button(action: openItem) { Label("时间线", systemImage: "clock.arrow.circlepath") }
                            .buttonStyle(BouncyStyle(kind: .ghost, compact: true))
                            .uiProbe(probe.map { "\($0)-timeline" })
                            .accessibilityLabel("看 \(card.itemID ?? "") 的时间线")
                    }
                    Spacer()
                    if focused {
                        Text("⌘↩").font(.system(size: 10.5, weight: .medium, design: .rounded)).foregroundStyle(Theme.textSecondary)
                            .accessibilityHidden(true)
                    }
                }
            }
        }
        .padding(12)
        .card(highlighted: focused)
        .animation(Motion.or(Motion.spring), value: focused)
        .onReceive(state.$demoReject) { d in
            guard let d, d.id == card.id else { return }
            withAnimation(Motion.or(Motion.spring)) { rejecting = true; words = d.words }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel(card.accessibilityText)
    }

    private func sendReject() {
        withAnimation(Motion.or(Motion.pop)) { state.reject(card, words: words) }
    }

    static func symbol(_ kind: String?) -> String {
        switch kind {
        case "look": return "eye"
        case "do": return "questionmark.circle"
        case "ship": return "paperplane"
        case "external": return "envelope.badge"
        case "ask": return "bubble.left"
        default: return "circle.dashed"
        }
    }
}

// MARK: - 项目

struct ProjectsSection: View {
    @ObservedObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            SectionTitle(text: "项目")
            VStack(spacing: 0) {
                ForEach(Array(state.rows.enumerated()), id: \.element.id) { i, r in
                    if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 12) }
                    ProjectRowView(row: r, index: i, selected: state.focusedProject == r.code) {
                        withAnimation(Motion.or(Motion.spring)) { state.focusedProject = state.focusedProject == r.code ? nil : r.code }
                    }
                }
            }
            .card()
        }
    }
}

struct ProjectRowView: View {
    let row: ProjectRow
    let index: Int
    let selected: Bool
    let tap: () -> Void

    var body: some View {
        Button(action: tap) {
            HStack(spacing: 10) {
                Circle().fill(dot).frame(width: 7, height: 7)
                VStack(alignment: .leading, spacing: 1) {
                    HStack(spacing: 5) {
                        Text(row.code).font(.system(size: 12, weight: .bold, design: .rounded)).foregroundStyle(Theme.textPrimary)
                        Text(row.name).font(Theme.body(12.5)).foregroundStyle(Theme.textPrimary).lineLimit(1)
                    }
                    if let e = row.error {
                        Text("读不出状态：\(e)").font(Theme.caption(10.5)).foregroundStyle(Theme.danger).lineLimit(1)
                    } else if let sub = subtitle {
                        Text(sub).font(Theme.caption(10.5)).foregroundStyle(row.tooLong > 0 ? Theme.warning : Theme.textSecondary).lineLimit(1)
                    }
                }
                Spacer(minLength: 4)
                if row.error == nil {
                    HStack(spacing: 8) {
                        Metric(label: "施工", n: row.building, color: Theme.textPrimary)
                        Metric(label: "验收", n: row.verifying, color: Theme.textPrimary)
                        Metric(label: "等你", n: row.waiting, color: Theme.accent)
                        Metric(label: "卡住", n: row.stuck, color: Theme.danger)
                    }
                }
                if index < 9 {
                    Text("⌘\(index + 1)").font(.system(size: 9.5, design: .rounded)).foregroundStyle(Theme.textSecondary.opacity(0.7))
                        .accessibilityHidden(true)
                }
            }
            .padding(.horizontal, 12).padding(.vertical, 9)
            .background(selected ? Theme.accentSoft.opacity(0.6) : Color.clear)
            .contentShape(Rectangle())
        }
        .buttonStyle(PressScale())
        .accessibilityLabel(row.accessibilityText)
        .accessibilityHint("只看这个项目的闸门，快捷键 Command \(index + 1)")
    }

    private var subtitle: String? {
        let parts = [row.tooLong > 0 ? "卡太久 \(row.tooLong)" : nil, row.roleLine].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    private var dot: Color {
        if row.error != nil { return Theme.danger }
        switch row.heartbeat {
        case .stale: return Theme.danger
        case .never: return Theme.border
        default: return Theme.success
        }
    }
}

/// 整行按下时轻轻缩一下再弹回。
struct PressScale: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed && !reduceMotion ? 0.97 : 1)
            .animation(reduceMotion ? nil : Motion.spring, value: configuration.isPressed)
    }
}

struct Metric: View {
    let label: String
    let n: Int
    let color: Color
    var body: some View {
        VStack(spacing: 0) {
            Text("\(n)").font(.system(size: 12.5, weight: .semibold, design: .rounded))
                .foregroundStyle(n == 0 ? Theme.textSecondary.opacity(0.55) : color)
            Text(label).font(.system(size: 9)).foregroundStyle(Theme.textSecondary)
        }
        .frame(minWidth: 24)
    }
}

// MARK: - 收菜清单

struct HarvestCard: View {
    @ObservedObject var state: AppState
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Label("收菜清单", systemImage: "basket").font(Theme.title(14)).foregroundStyle(Theme.textPrimary)
                Spacer()
                Button { withAnimation(Motion.or(Motion.softSpring)) { state.showHarvest = false } } label: { Image(systemName: "xmark") }
                    .buttonStyle(BouncyStyle(kind: .ghost, compact: true)).accessibilityLabel("收起收菜清单")
            }
            let items = state.harvest
            if items.isEmpty {
                Text("还没有已合并、等上线的件").font(Theme.caption(12)).foregroundStyle(Theme.textSecondary)
            } else {
                ForEach(items) { h in
                    HStack(spacing: 8) {
                        Text(h.key).font(.system(size: 10.5, design: .monospaced)).foregroundStyle(Theme.textSecondary)
                        Text(h.title).font(Theme.body(12.5)).foregroundStyle(Theme.textPrimary).lineLimit(1)
                        Spacer()
                    }
                }
                Button { state.shipHarvest() } label: { Label("建上线闸门", systemImage: "paperplane") }
                    .buttonStyle(BouncyStyle(kind: .primary, compact: true))
                    .disabled(state.busy != nil)
            }
        }
        .padding(12)
        .card()
    }
}

// MARK: - 对话

struct ChatSection: View {
    let lines: [AppState.ChatLine]
    let mood: MascotMood
    var liveEmotion: MateEmotion? = nil
    var state: AppState? = nil                     // v0.6.0：插件回话卡片上的按钮要再跑插件
    private var lastEvo: UUID? { lines.last { !$0.mine }?.id }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(lines) { l in
                HStack(alignment: .bottom, spacing: 6) {
                    if l.mine {
                        Spacer(minLength: 40)
                        SpeechBubble(text: l.text, side: .me)
                    } else {
                        if l.id == lastEvo, let live = liveEmotion {
                            MateView(emotion: live, size: 30)
                        } else {
                            MateView(emotion: l.failed ? .error : .happy, size: 26, forceStill: true)
                        }
                        if let c = l.card {
                            PluginCardView(card: c, compact: true, onAction: action(l), probePrefix: l.id == lines.last?.id ? "chat-card" : nil)
                                .padding(12)
                                .frame(maxWidth: 460, alignment: .leading)
                                .card()
                                .uiProbe(l.id == lines.last?.id ? "chat-card" : nil)
                        } else {
                            SpeechBubble(text: l.text, side: .evo, tone: l.failed ? .danger : .neutral)
                        }
                        Spacer(minLength: 40)
                    }
                }
                .transition(.asymmetric(insertion: .scale(scale: 0.6, anchor: l.mine ? .bottomTrailing : .bottomLeading).combined(with: .opacity),
                                        removal: .opacity))
            }
        }
    }
}

@MainActor
extension ChatSection {
    /// 回话卡片上的按钮：再跑同一个插件命令，带上按钮的 action / payload。
    func action(_ l: AppState.ChatLine) -> ((CardButton) -> Void)? {
        guard let st = state, let cmd = l.command else { return nil }
        return { b in st.runComposerPlugin(cmd, args: "", project: st.focusedProject ?? st.codes.first ?? "", action: b.action, payload: b.payload) }
    }
}

// MARK: - 快捷小胶囊（Grok 风格）

struct QuickChips: View {
    @ObservedObject var state: AppState
    var body: some View {
        HStack(spacing: 6) {
            Button { state.tickNow() } label: { Label("立即 tick", systemImage: "bolt") }
                .disabled(state.busy != nil || state.snaps.isEmpty)
            Button { PanelController.shared.open() } label: { Label("打开面板", systemImage: "rectangle.on.rectangle") }
            Button { state.togglePause() } label: {
                Label(state.loopRunning == false ? "恢复" : "暂停", systemImage: state.loopRunning == false ? "play" : "pause")
            }
            .disabled(state.loopRunning == nil || state.busy != nil)
            .help(state.loopRunning == nil ? "没装 launchd 常驻" : "")
            Button { withAnimation(Motion.or(Motion.softSpring)) { state.showHarvest.toggle() } } label: {
                Label(state.harvest.isEmpty ? "收菜" : "收菜 \(state.harvest.count)", systemImage: "basket")
            }
            .accessibilityLabel(state.harvest.isEmpty ? "收菜清单" : "收菜清单，\(state.harvest.count) 件")
        }
        .lineLimit(1)
        .fixedSize(horizontal: true, vertical: false)
        .labelStyle(.titleAndIcon)
        .buttonStyle(BouncyStyle(kind: .chip, compact: true))
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - 输入框（告诉 evo…）

struct ComposerView: View {
    @ObservedObject var state: AppState
    @AppStorage("composerMode") private var modeRaw = ComposerMode.feedback.rawValue
    @AppStorage("composerProject") private var savedProject = ""
    @State private var text = ""
    @State private var look = false
    @State private var error: String?
    @State private var sentPulse = false
    @Environment(\.evoStatic) private var isStatic

    private var mode: ComposerMode { ComposerMode(rawValue: modeRaw) ?? .feedback }
    private var project: String {
        if let f = state.focusedProject { return f }
        if state.codes.contains(savedProject) { return savedProject }
        return state.codes.first ?? ""
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            VStack(alignment: .leading, spacing: 8) {
                ThemedField(placeholder: mode.placeholder, text: $text) { send() }
                    .accessibilityLabel("告诉 evo")
                    .uiProbe("composer-field")
                HStack(spacing: 6) {
                    Group {
                        if isStatic {      // 离屏渲染画不出 Menu（会是黄块），截图时画成同样的胶囊
                            Label(project.isEmpty ? "选项目" : project, systemImage: "folder").labelStyle(.titleAndIcon)
                        } else {
                            Menu {
                                ForEach(state.codes, id: \.self) { c in Button(c) { savedProject = c; state.focusedProject = nil } }
                            } label: {
                                Label(project.isEmpty ? "选项目" : project, systemImage: "folder")
                            }
                            .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                        }
                    }
                    .modifier(ChipLook())
                    .accessibilityLabel("发给哪个项目：\(project)")
                    Button { modeRaw = (mode == .feedback ? ComposerMode.add : .feedback).rawValue } label: {
                        Label(mode.label, systemImage: mode == .feedback ? "text.bubble" : "plus.square")
                    }
                    .buttonStyle(BouncyStyle(kind: .chip, compact: true))
                    .accessibilityLabel("方式：\(mode.label)，点一下切换")
                    if mode == .add {
                        Button { look.toggle() } label: { Label("要看效果", systemImage: look ? "eye.fill" : "eye") }
                            .buttonStyle(BouncyStyle(kind: look ? .primary : .chip, compact: true))
                            .transition(.scale.combined(with: .opacity))
                    }
                    Spacer()
                    Button(action: send) {
                        Image(systemName: "arrow.up").font(.system(size: 13, weight: .bold)).foregroundStyle(Theme.onAccent)
                            .frame(width: 28, height: 28)
                            .background(Circle().fill(text.isEmpty ? Theme.border : Theme.accent))
                    }
                    .buttonStyle(PressBounce())
                    .scaleEffect(sentPulse ? 1.15 : 1)
                    .disabled(text.trimmingCharacters(in: .whitespaces).isEmpty)
                    .accessibilityLabel("发送")
                    .uiProbe("composer-send")
                }
            }
            .padding(10)
            .background(RoundedRectangle(cornerRadius: Theme.radius, style: .continuous).fill(Theme.surface)
                .shadow(color: .black.opacity(0.06), radius: 8, y: 2))
            .overlay(RoundedRectangle(cornerRadius: Theme.radius, style: .continuous).strokeBorder(Theme.border, lineWidth: 1))
            .animation(Motion.or(Motion.spring), value: mode)
            if let error {
                Text(error).font(Theme.caption()).foregroundStyle(Theme.danger).transition(.opacity)
            }
        }
    }

    private func send() {
        let t = text
        if let e = state.send(mode: mode, project: project, text: t, look: look) {
            withAnimation(Motion.or(Motion.spring)) { error = e }
            return
        }
        error = nil; text = ""; look = false
        withAnimation(Motion.or(Motion.pop)) { sentPulse = true }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { withAnimation(Motion.or(Motion.pop)) { sentPulse = false } }
    }
}

/// Menu 也画成小胶囊的样子。
struct ChipLook: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(.system(size: 12, weight: .medium))
            .foregroundStyle(Theme.textPrimary)
            .padding(.horizontal, 10).padding(.vertical, 5)
            .background(Capsule().fill(Theme.surface).overlay(Capsule().strokeBorder(Theme.border, lineWidth: 1)))
    }
}

struct PressBounce: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed && !reduceMotion ? 0.88 : 1)
            .animation(reduceMotion ? nil : Motion.spring, value: configuration.isPressed)
    }
}

// MARK: - 底栏

struct FooterView: View {
    @ObservedObject var state: AppState
    private static let hms: DateFormatter = { let f = DateFormatter(); f.dateFormat = "HH:mm:ss"; return f }()

    var body: some View {
        HStack(spacing: 6) {
            if let t = state.lastRefresh {
                Text("刷新于 \(Self.hms.string(from: t))").font(Theme.caption(10.5)).foregroundStyle(Theme.textSecondary)
            }
            if let a = state.lastAction, state.busy == nil {
                Text("· \(a)").font(Theme.caption(10.5)).foregroundStyle(Theme.textSecondary).lineLimit(1).truncationMode(.tail)
            }
            Spacer(minLength: 4)
            Button { state.tickNow() } label: { Image(systemName: "bolt") }
                .buttonStyle(BouncyStyle(kind: .ghost, compact: true)).accessibilityLabel("立即 tick").help("立即 tick")
                .disabled(state.busy != nil || state.snaps.isEmpty)
            Button { state.togglePause() } label: { Image(systemName: state.loopRunning == false ? "play" : "pause") }
                .buttonStyle(BouncyStyle(kind: .ghost, compact: true)).accessibilityLabel(state.loopRunning == false ? "恢复循环" : "暂停循环")
                .disabled(state.loopRunning == nil || state.busy != nil)
            Button { PaletteController.shared.show() } label: { Text("⌘K") }
                .buttonStyle(BouncyStyle(kind: .ghost, compact: true)).accessibilityLabel("命令面板")
            Button { WindowManager.shared.showSettings() } label: { Image(systemName: "gearshape") }
                .buttonStyle(BouncyStyle(kind: .ghost, compact: true)).accessibilityLabel("设置")
                .keyboardShortcut(",", modifiers: .command)
            Button { NSApp.terminate(nil) } label: { Image(systemName: "power") }
                .buttonStyle(BouncyStyle(kind: .ghost, compact: true)).accessibilityLabel("退出 Evo")
                .keyboardShortcut("q", modifiers: .command)
        }
        .foregroundStyle(Theme.textSecondary)
    }
}

/// 让菜单栏弹窗弹出来（命令面板里选「收菜清单」「项目」时用）。MenuBarExtra 没有公开接口，点一下状态栏按钮。
@MainActor
enum MenuWindow {
    static func show() {
        for w in NSApp.windows where String(describing: type(of: w)).contains("NSStatusBarWindow") {
            if let b = w.contentView?.subviews.first(where: { $0 is NSStatusBarButton }) as? NSStatusBarButton ?? findButton(w.contentView) {
                b.performClick(nil); return
            }
        }
    }

    private static func findButton(_ v: NSView?) -> NSStatusBarButton? {
        guard let v else { return nil }
        if let b = v as? NSStatusBarButton { return b }
        for s in v.subviews { if let b = findButton(s) { return b } }
        return nil
    }
}
#endif
