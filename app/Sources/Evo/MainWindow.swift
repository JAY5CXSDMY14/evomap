#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

// v0.3.0 主窗口：Claude 桌面版的样子。左边侧栏（角色 + 问候、等你处理、项目、卡太久、设置），
// 右边宽内容区（闸门卡片网格、项目概览、件的时间线），底部钉着「告诉 evo…」输入框；顶上统一标题栏 + 工具栏。
// 开着窗口时 Dock 里有图标（activation policy 切到 .regular），关掉回到纯菜单栏。

@MainActor
final class MainWindowController: NSObject, NSWindowDelegate {
    static let shared = MainWindowController()
    private(set) var window: NSWindow?

    var isOpen: Bool { window?.isVisible ?? false }

    func show() {
        if AppState.shared.popoverShown { MenuWindow.show() }     // 弹窗是开关式的：点一下状态栏按钮把它收起
        if window == nil { build() }
        if NSApp.activationPolicy() != .regular {
            NSApp.setActivationPolicy(.regular)
            DockIcon.apply()
        }
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func toggle() {
        if let w = window, w.isVisible, w.isKeyWindow { w.performClose(nil) } else { show() }
    }

    private func build() {
        let host = NSHostingController(rootView: MainWindowView(state: AppState.shared))
        host.sizingOptions = [.minSize]
        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 740),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                         backing: .buffered, defer: false)
        w.contentViewController = host
        w.title = "Evo"
        w.titleVisibility = .hidden
        w.toolbarStyle = .unified
        // 工具栏由 SwiftUI 的 .toolbar 提供（NavigationSplitView 会接管窗口工具栏，自己建的 NSToolbar 会被换掉）
        w.minSize = NSSize(width: WindowSizing.minWidth, height: WindowSizing.minHeight)
        w.isReleasedWhenClosed = false
        w.delegate = self
        w.acceptsMouseMovedEvents = true
        w.backgroundColor = NSColor(Theme.bg)
        w.tabbingMode = .disallowed
        w.collectionBehavior.insert(.fullScreenPrimary)
        // 记住位置和大小；第一次按屏幕可用区取一个舒服的尺寸
        if !w.setFrameUsingName("Evo.main") {
            let vis = (NSScreen.main ?? NSScreen.screens.first)?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
            let s = WindowSizing.initial(visibleWidth: Double(vis.width), visibleHeight: Double(vis.height))
            w.setFrame(NSRect(x: vis.midX - s.width / 2, y: vis.midY - s.height / 2, width: s.width, height: s.height), display: false)
        }
        w.setFrameAutosaveName("Evo.main")
        window = w
    }

    // 关窗：Dock 图标收起，回到纯菜单栏
    func windowWillClose(_ notification: Notification) {
        DispatchQueue.main.async {
            if !DockPolicy.showsDock(mainWindowOpen: self.isOpen) { NSApp.setActivationPolicy(.accessory) }
        }
    }
}

/// Dock 图标：v0.5.0 起用包里的 AppIcon.icns（调度球，scripts/make-icon.py 画的）——不再在运行时覆盖。
/// 只有 `swift run` 这种没有包图标的开发场景，才退回到「圆角方块上放角色静态帧」。
@MainActor
enum DockIcon {
    static var bundleHasIcon: Bool {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleIconFile") != nil
            && Bundle.main.url(forResource: "AppIcon", withExtension: "icns") != nil
    }

    static func apply() {
        if bundleHasIcon { NSApp.applicationIconImage = nil; return }   // nil = 用包里的图标
        let tile = ZStack {
            RoundedRectangle(cornerRadius: 186, style: .continuous)
                .fill(LinearGradient(colors: [Color(white: 0.30), Color(white: 0.06)], startPoint: .top, endPoint: .bottom))
                .frame(width: 824, height: 824)
                .shadow(color: .black.opacity(0.25), radius: 18, y: 10)
            MateStill(character: MateAssets.character, emotion: .standby, size: 560)
                .frame(width: 560, height: 560)
        }
        .frame(width: 1024, height: 1024)
        .environment(\.evoStatic, true)
        let r = ImageRenderer(content: tile)
        r.scale = 0.5
        if let img = r.nsImage { NSApp.applicationIconImage = img }
    }
}

// MARK: - 工具栏内容

struct ToolbarStatus: View {
    @ObservedObject var state: AppState
    var body: some View {
        HStack(spacing: 8) {
            StatePill(state: state.loopState).animation(Motion.or(Motion.pop), value: state.loopState.label)
            if let b = state.busy {
                HStack(spacing: 5) { Spinner(size: 11); Text(b).font(Theme.caption()).foregroundStyle(Theme.textSecondary) }
                    .transition(.opacity)
            }
        }
        .fixedSize()
        .padding(.leading, 4)
    }
}

struct ToolbarActions: View {
    @ObservedObject var state: AppState
    var body: some View {
        HStack(spacing: 6) {
            Button { state.tickNow() } label: { Label("立即 tick", systemImage: "bolt") }
                .disabled(state.busy != nil || state.snaps.isEmpty)
                .help("每个项目马上转一轮（evo tick）")
                .uiProbe("win-toolbar-tick")
            Button { state.togglePause() } label: {
                Label(state.loopRunning == false ? "恢复" : "暂停", systemImage: state.loopRunning == false ? "play" : "pause")
            }
            .disabled(state.loopRunning == nil || state.busy != nil)
            .help(state.loopRunning == nil ? "没装 launchd 常驻" : "暂停 / 恢复常驻循环")
            Button { PanelController.shared.open() } label: { Label("打开面板", systemImage: "rectangle.on.rectangle") }
                .help("网页面板")
            Button { PaletteController.shared.show() } label: {
                HStack(spacing: 5) { Image(systemName: "magnifyingglass"); Text("⌘K") }
            }
            .help("命令面板")
            .uiProbe("win-toolbar-palette")
        }
        .labelStyle(.titleAndIcon)
        .buttonStyle(BouncyStyle(kind: .chip, compact: true))
        .lineLimit(1)
        .fixedSize()
        .padding(.trailing, 4)
    }
}

// MARK: - 窗口根视图

struct MainWindowView: View {
    @ObservedObject var state: AppState
    @State private var columns = NavigationSplitViewVisibility.all

    var body: some View {
        NavigationSplitView(columnVisibility: $columns) {
            SidebarView(state: state)
                .navigationSplitViewColumnWidth(min: 230, ideal: 256, max: 340)
        } detail: {
            DetailArea(state: state)
                .toolbar {
                    ToolbarItem(placement: .navigation) { ToolbarStatus(state: state) }
                    ToolbarItem(placement: .primaryAction) { ToolbarActions(state: state) }
                }
                .toolbarBackground(.hidden, for: .windowToolbar)     // 工具栏透出内容区的象牙底，不要一条白边
        }
        .navigationSplitViewStyle(.balanced)
        .frame(minWidth: WindowSizing.minWidth, minHeight: WindowSizing.minHeight)
        .background(WindowShortcuts(state: state))
        .tint(Theme.accent)
    }
}

/// 窗口里的快捷键：⌘1…9 选项目、⌘↩ 通过第一张卡、⌘K、⌘R、⌘[ 返回。
struct WindowShortcuts: View {
    @ObservedObject var state: AppState
    var body: some View {
        ZStack {
            ForEach(1..<10) { d in
                Button("") { withAnimation(Motion.or(Motion.softSpring)) { state.select(digit: d) } }
                    .keyboardShortcut(KeyEquivalent(Character(String(d))), modifiers: .command)
            }
            Button("") {
                if let c = state.windowCards.first { withAnimation(Motion.or(Motion.pop)) { state.approve(c) } }
            }
            .keyboardShortcut(.return, modifiers: .command)
            Button("") { PaletteController.shared.show() }.keyboardShortcut("k", modifiers: .command)
            Button("") { state.refresh() }.keyboardShortcut("r", modifiers: .command)
            Button("") { if let p = state.windowSelection?.parent { withAnimation(Motion.or(Motion.softSpring)) { state.windowSelection = p } } }
                .keyboardShortcut("[", modifiers: .command)
        }
        .opacity(0).frame(width: 0, height: 0).accessibilityHidden(true)
    }
}

extension AppState {
    /// 窗口里当前页的闸门卡：等你处理 = 全部；项目页 = 这个项目的。
    var windowCards: [GateCard] {
        switch windowSelection ?? .inbox {
        case .project(let c): return allCards.filter { $0.project == c }
        default: return allCards
        }
    }
}

// MARK: - 侧栏

struct SidebarView: View {
    @ObservedObject var state: AppState
    @Environment(\.evoStatic) private var isStatic

    private var current: SidebarItem { (state.windowSelection ?? .inbox).sidebarHighlight }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SidebarHeader(state: state)
                .padding(.horizontal, 14).padding(.top, 6).padding(.bottom, 12)
            ScrollView(.vertical, showsIndicators: false) {
                VStack(alignment: .leading, spacing: 2) {
                    SidebarRow(symbol: "tray.full", title: "等你处理", badge: state.allCards.count, accentBadge: true,
                               selected: current == .inbox) { go(.inbox) }
                        .uiProbe("win-sidebar-inbox")
                    SidebarHeading(text: "项目")
                    ForEach(Array(state.rows.enumerated()), id: \.element.id) { i, r in
                        SidebarProjectRow(row: r, index: i, selected: current == .project(r.code)) { go(.project(r.code)) }
                            .uiProbe("win-sidebar-project-\(r.code)")
                    }
                    if state.rows.isEmpty {
                        Text("还没有项目").font(Theme.caption(12)).foregroundStyle(Theme.textSecondary).padding(.horizontal, 10).padding(.vertical, 6)
                    }
                    SidebarHeading(text: "留意")
                    SidebarRow(symbol: "hourglass", title: "卡太久", badge: state.stuckEntries.count, accentBadge: false,
                               selected: current == .stale) { go(.stale) }
                        .uiProbe("win-sidebar-stale")
                    // v0.7.0：侧栏跟着功能列表走：功能包 team 关了「团队」就不出现（老 evo 没有功能开关 → 照旧显示）
                    if state.registry.teamVisible {
                        SidebarRow(symbol: "person.3", title: "团队", badge: state.team?.attention ?? 0, accentBadge: false,
                                   selected: current == .team) { go(.team) }
                            .uiProbe("win-sidebar-team")
                            .transition(.move(edge: .leading).combined(with: .opacity))
                    }
                    // v0.6.0：插件分组（打开了的插件的侧栏页；没有就不出现）；v0.7.0：功能包 plugins 关了整组不出现
                    let pages = state.registry.pluginsVisible ? (state.plugins?.sidebarPages ?? []) : []
                    if !pages.isEmpty {
                        SidebarHeading(text: "插件")
                        ForEach(Array(pages.enumerated()), id: \.element.key) { i, pg in
                            SidebarRow(symbol: pg.symbol, title: pg.title, badge: 0, accentBadge: false,
                                       selected: current == .plugin(pg.plugin, pg.id)) { go(.plugin(pg.plugin, pg.id)) }
                                .uiProbe("win-sidebar-plugin-\(i)")
                                .transition(.move(edge: .leading).combined(with: .opacity))
                        }
                    }
                }
                .padding(.horizontal, 8)
                .animation(Motion.or(Motion.softSpring), value: state.plugins?.sidebarPages.map(\.key) ?? [])
                .animation(Motion.or(Motion.softSpring), value: state.registry.teamVisible)
            }
            Spacer(minLength: 0)
            Rectangle().fill(Theme.border).frame(height: 1).padding(.horizontal, 12)
            SidebarRow(symbol: "gearshape", title: "设置", badge: 0, accentBadge: false, selected: current == .settings) { go(.settings) }
                .uiProbe("win-sidebar-settings")
                .padding(.horizontal, 8).padding(.vertical, 8)
        }
        .frame(maxHeight: .infinity, alignment: .top)
        .background(Theme.sidebar.ignoresSafeArea())
    }

    private func go(_ s: SidebarItem) {
        withAnimation(Motion.or(Motion.softSpring)) { state.windowSelection = s }
    }
}

struct SidebarHeader: View {
    @ObservedObject var state: AppState
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .center, spacing: 10) {
                MateView(emotion: state.mateEmotion, celebrate: state.mateCelebrate, size: 58, followMouse: true)
                    .uiProbe("win-mate")
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(Greeting.text(at: Date()))，老板").font(Theme.title(17)).foregroundStyle(Theme.textPrimary)
                        .lineLimit(1).minimumScaleFactor(0.8)
                    Text("\(state.snaps.count) 个项目 · \(MateAssets.character.label)").font(Theme.caption()).foregroundStyle(Theme.textSecondary)
                }
                Spacer(minLength: 0)
            }
            SpeechBubble(text: state.flash ?? state.speech,
                         tone: state.flash?.hasPrefix("没成") == true ? .danger : state.loopState.tone)
                .id(state.flash ?? state.speech)
                .transition(.scale(scale: 0.85, anchor: .topLeading).combined(with: .opacity))
                .padding(.leading, 6)
                .animation(Motion.or(Motion.pop), value: state.flash ?? state.speech)
        }
    }
}

struct SidebarHeading: View {
    let text: String
    var body: some View {
        Text(text).font(.system(size: 11, weight: .semibold)).foregroundStyle(Theme.textSecondary)
            .padding(.horizontal, 10).padding(.top, 14).padding(.bottom, 4)
            .accessibilityAddTraits(.isHeader)
    }
}

struct SidebarRow: View {
    let symbol: String
    let title: String
    let badge: Int
    let accentBadge: Bool
    let selected: Bool
    let action: () -> Void
    @State private var hover = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 9) {
                Image(systemName: symbol).font(.system(size: 13, weight: .medium))
                    .foregroundStyle(selected ? Theme.accent : Theme.textSecondary).frame(width: 20)
                Text(title).font(.system(size: 13, weight: selected ? .semibold : .regular)).foregroundStyle(Theme.textPrimary)
                Spacer(minLength: 4)
                if badge > 0 {
                    if accentBadge { JiggleBadge(count: badge) } else {
                        Text("\(badge)").font(.system(size: 11, weight: .semibold, design: .rounded)).foregroundStyle(Theme.warning)
                            .padding(.horizontal, 6).frame(minHeight: 18).background(Capsule().fill(Theme.warning.opacity(0.14)))
                    }
                }
            }
            .padding(.horizontal, 10).padding(.vertical, 7)
            .background(RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(selected ? Theme.sidebarSelected : (hover ? Theme.sidebarSelected.opacity(0.5) : .clear)))
            .contentShape(Rectangle())
        }
        .buttonStyle(PressScale())
        .onHover { hover = $0 }
        .accessibilityLabel(badge > 0 ? "\(title)，\(badge) 件" : title)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

struct SidebarProjectRow: View {
    let row: ProjectRow
    let index: Int
    let selected: Bool
    let action: () -> Void
    @State private var hover = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 9) {
                Circle().fill(dot).frame(width: 8, height: 8).frame(width: 20)
                Text(row.code).font(.system(size: 12, weight: .bold, design: .rounded)).foregroundStyle(Theme.textPrimary)
                Text(row.name).font(.system(size: 13, weight: selected ? .semibold : .regular)).foregroundStyle(Theme.textPrimary)
                    .lineLimit(1).truncationMode(.tail)
                Spacer(minLength: 4)
                if row.waiting > 0 {
                    Text("\(row.waiting)").font(.system(size: 11, weight: .bold, design: .rounded)).foregroundStyle(Theme.accent)
                }
                if index < 9 {
                    Text("⌘\(index + 1)").font(.system(size: 10.5, design: .rounded)).foregroundStyle(Theme.textSecondary)
                        .accessibilityHidden(true)
                }
            }
            .padding(.horizontal, 10).padding(.vertical, 7)
            .background(RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(selected ? Theme.sidebarSelected : (hover ? Theme.sidebarSelected.opacity(0.5) : .clear)))
            .contentShape(Rectangle())
        }
        .buttonStyle(PressScale())
        .onHover { hover = $0 }
        .accessibilityLabel(row.accessibilityText)
        .accessibilityHint("快捷键 Command \(index + 1)")
    }

    private var dot: Color {
        if row.error != nil { return Theme.danger }
        switch row.heartbeat {
        case .stale: return Theme.danger
        case .never: return Theme.textSecondary.opacity(0.5)
        default: return row.stuck > 0 ? Theme.warning : Theme.success
        }
    }
}

// MARK: - 内容区

private struct WidthKey: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) { value = max(value, nextValue()) }
}

struct DetailArea: View {
    @ObservedObject var state: AppState
    @State private var width: CGFloat = 800

    private func backAction(_ sel: SidebarItem) -> (() -> Void)? {
        guard let p = sel.parent else { return nil }
        let st = state
        return { withAnimation(Motion.or(Motion.softSpring)) { st.windowSelection = p } }
    }

    var body: some View {
        let sel = state.windowSelection ?? .inbox
        VStack(spacing: 0) {
          ScrollViewReader { proxy in
            ScrollView(.vertical) {
                VStack(alignment: .leading, spacing: 0) {
                    if let w = state.contractWarning {      // v0.6.0：evo 的接口版本和 App 对不上
                        ContractBanner(text: w).padding(.bottom, 16)
                    }
                    Group {
                        // v0.7.0 错误边界：这页的数据读不出来 → 只这一页画「出错了 + 重试」卡片，侧栏和别的页照常
                        if let err = PageBoundary.error(for: sel, state.pageErrors) {
                            VStack(alignment: .leading, spacing: 0) {
                                PageTitleForError(sel: sel, state: state)
                                PageErrorCard(error: err, busy: state.pageRetrying, back: backAction(sel)) {
                                    state.retryPage(sel)
                                }
                            }
                        } else {
                        switch sel {
                        case .inbox: InboxPane(state: state, width: width)
                        case .project(let c): ProjectPane(state: state, code: c, width: width)
                        case .item(let p, let k): ItemPane(state: state, project: p, key: k, width: width)
                        case .stale: StalePane(state: state)
                        case .team: TeamPane(state: state, width: width)
                        case .plugin(let p, let id):
                            if let ref = state.plugins?.page(p, id) { PluginPane(state: state, ref: ref) }
                            else { Hint(text: "插件 \(p) 的页「\(id)」不在了（插件关掉或删掉了）", color: Theme.textSecondary) }
                        case .settings: SettingsView(state: state, embedded: true).frame(maxWidth: .infinity)
                        }
                        }
                    }
                    .id(sel)
                    .transition(.asymmetric(insertion: .opacity.combined(with: .offset(y: 8)), removal: .opacity))
                }
                .frame(maxWidth: 1080, alignment: .leading)
                .padding(.horizontal, 32).padding(.top, 22).padding(.bottom, 28)
                .frame(maxWidth: .infinity)
                .background(GeometryReader { g in Color.clear.preference(key: WidthKey.self, value: min(1080, g.size.width - 64)) })
            }
            .onPreferenceChange(WidthKey.self) { w in if abs(w - width) > 1 { width = w } }
            .animation(Motion.or(Motion.softSpring), value: sel)
            .onChange(of: state.scrollTarget) { t in
                guard let t else { return }
                withAnimation(Motion.or(Motion.softSpring)) { proxy.scrollTo(t, anchor: .top) }
                state.scrollTarget = nil
            }
          }
            if sel != .settings { ComposerDock(state: state) }
        }
        .background(Theme.bg.ignoresSafeArea())
    }
}

/// 错误卡片上面那行页标题（让人知道是哪一页坏了）。
struct PageTitleForError: View {
    let sel: SidebarItem
    @ObservedObject var state: AppState
    var body: some View {
        Text(sel.title { state.snapshot($0)?.name })
            .font(Theme.title(24)).foregroundStyle(Theme.textPrimary)
            .lineLimit(1).truncationMode(.tail)
            .padding(.bottom, 14)
    }
}

/// 页标题：serif 大字 + 可选角标 + 右侧附加。
struct PaneTitle<Trailing: View>: View {
    let title: String
    var count: Int? = nil
    var subtitle: String? = nil
    @ViewBuilder var trailing: () -> Trailing
    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .center, spacing: 8) {
                    Text(title).font(Theme.title(26)).foregroundStyle(Theme.textPrimary).lineLimit(1).accessibilityAddTraits(.isHeader)
                    if let count, count > 0 { JiggleBadge(count: count) }
                }
                if let subtitle { Text(subtitle).font(Theme.body(13)).foregroundStyle(Theme.textSecondary) }
            }
            Spacer(minLength: 8)
            trailing()
        }
        .padding(.bottom, 18)
    }
}

extension PaneTitle where Trailing == EmptyView {
    init(title: String, count: Int? = nil, subtitle: String? = nil) {
        self.init(title: title, count: count, subtitle: subtitle) { EmptyView() }
    }
}

/// 闸门卡网格：宽了两列、三列。卡片通过时向右上飞走。
struct GateGridView: View {
    @ObservedObject var state: AppState
    let cards: [GateCard]
    let width: CGFloat

    var body: some View {
        let n = GateGrid.columns(width: Double(width))
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: CGFloat(GateGrid.spacing), alignment: .top), count: n),
                  alignment: .leading, spacing: CGFloat(GateGrid.spacing)) {
            ForEach(Array(cards.enumerated()), id: \.element.id) { i, c in
                GateCardView(state: state, card: c, focused: i == 0, probe: "win-gate-\(c.id)", openItem: opener(c))
                .staggeredAppear(i)
                .transition(.asymmetric(
                    insertion: .scale(scale: 0.9, anchor: .top).combined(with: .opacity),
                    removal: .scale(scale: 0.5, anchor: .topTrailing).combined(with: .opacity).combined(with: .offset(x: 220, y: -40))))
            }
        }
        .animation(Motion.or(Motion.pop), value: cards.map(\.id))
    }

    private func opener(_ c: GateCard) -> (() -> Void)? {
        guard let k = c.itemID else { return nil }
        let st = state, p = c.project
        return {
            withAnimation(Motion.or(Motion.softSpring)) { st.windowSelection = .item(project: p, key: k) }
        }
    }
}

struct InboxPane: View {
    @ObservedObject var state: AppState
    let width: CGFloat

    var body: some View {
        let cards = state.allCards
        VStack(alignment: .leading, spacing: 0) {
            PaneTitle(title: "等你处理", count: cards.count, subtitle: state.speech)
            if cards.isEmpty {
                EmptyState().frame(maxWidth: 520).padding(.bottom, 8)
            } else {
                GateGridView(state: state, cards: cards, width: width)
            }
            if state.showHarvest {
                HarvestCard(state: state).frame(maxWidth: 560).padding(.top, 18)
                    .transition(.scale(scale: 0.9, anchor: .top).combined(with: .opacity))
            }
            if !state.rows.isEmpty {
                Text("项目").font(Theme.title(17)).foregroundStyle(Theme.textPrimary).padding(.top, 30).padding(.bottom, 10)
                let n = max(1, min(3, Int((width + 14) / 274)))
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 14, alignment: .top), count: n), alignment: .leading, spacing: 14) {
                    ForEach(Array(state.rows.enumerated()), id: \.element.id) { i, r in
                        ProjectTile(row: r, beat: state.beat(r.code), index: i) {
                            withAnimation(Motion.or(Motion.softSpring)) { state.windowSelection = .project(r.code) }
                        }
                        .staggeredAppear(cards.count + i)
                    }
                }
            }
        }
        .animation(Motion.or(Motion.softSpring), value: state.showHarvest)
    }
}

struct ProjectTile: View {
    let row: ProjectRow
    let beat: HeartbeatStatus?
    let index: Int
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 6) {
                    Text(row.code).font(.system(size: 11, weight: .bold, design: .rounded)).foregroundStyle(Theme.accent)
                        .padding(.horizontal, 7).padding(.vertical, 2).background(Capsule().fill(Theme.accentSoft))
                    Text(row.name).font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.textPrimary).lineLimit(1)
                    Spacer(minLength: 0)
                    if index < 9 { Text("⌘\(index + 1)").font(.system(size: 10.5, design: .rounded)).foregroundStyle(Theme.textSecondary) }
                }
                HStack(spacing: 0) {
                    Metric(label: "施工", n: row.building, color: Theme.textPrimary).frame(maxWidth: .infinity)
                    Metric(label: "验收", n: row.verifying, color: Theme.textPrimary).frame(maxWidth: .infinity)
                    Metric(label: "等你", n: row.waiting, color: Theme.accent).frame(maxWidth: .infinity)
                    Metric(label: "卡住", n: row.stuck, color: Theme.danger).frame(maxWidth: .infinity)
                }
                Text(HeartbeatLine.text(beat, row: row)).font(Theme.caption(11)).foregroundStyle(row.tooLong > 0 ? Theme.warning : Theme.textSecondary)
                    .lineLimit(1)
            }
            .padding(14)
            .card()
            .contentShape(Rectangle())
        }
        .buttonStyle(PressScale())
        .accessibilityLabel(row.accessibilityText)
    }
}

enum HeartbeatLine {
    static func text(_ b: HeartbeatStatus?, row: ProjectRow) -> String {
        var parts: [String] = []
        if let e = row.error { return "读不出状态：\(e)" }
        switch b?.level {
        case .some(.stale): parts.append("已 \(HeartbeatStatus.human(b?.ageMinutes ?? 0))没转动")
        case .some(.never): parts.append("还没转过")
        default: if let m = b?.ageMinutes { parts.append(m < 1 ? "刚转过" : "\(HeartbeatStatus.human(m))前转过") }
        }
        if row.tooLong > 0 { parts.append("卡太久 \(row.tooLong)") }
        if let r = row.roleLine { parts.append(r) }
        return parts.joined(separator: " · ")
    }
}

// MARK: 项目页

struct ProjectPane: View {
    @ObservedObject var state: AppState
    let code: String
    let width: CGFloat

    var body: some View {
        let snap = state.snapshot(code)
        let row = state.row(code)
        let cards = state.allCards.filter { $0.project == code }
        VStack(alignment: .leading, spacing: 0) {
            PaneTitle(title: snap?.name ?? code, subtitle: row.map { HeartbeatLine.text(state.beat(code), row: $0) }) {
                Text(code).font(.system(size: 13, weight: .bold, design: .rounded)).foregroundStyle(Theme.accent)
                    .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(Theme.accentSoft))
            }
            if let row {
                HStack(spacing: 12) {
                    BigMetric(label: "施工", n: row.building, color: Theme.textPrimary)
                    BigMetric(label: "验收", n: row.verifying, color: Theme.textPrimary)
                    BigMetric(label: "等你", n: row.waiting, color: Theme.accent)
                    BigMetric(label: "卡住", n: row.stuck, color: Theme.danger)
                    BigMetric(label: "已合并", n: row.merged, color: Theme.success)
                }
                .padding(.bottom, 24)
            }
            if !cards.isEmpty {
                SectionTitle(text: "等你处理", count: cards.count).padding(.bottom, 10)
                GateGridView(state: state, cards: cards, width: width).padding(.bottom, 24)
            }
            let items = snap?.doc?.items ?? []
            SectionTitle(text: "件").padding(.bottom, 10)
            if items.isEmpty {
                Text("没有进行中的件").font(Theme.body()).foregroundStyle(Theme.textSecondary).padding(.bottom, 16)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(items.enumerated()), id: \.element.key) { i, it in
                        if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 14) }
                        ItemRowView(item: it) {
                            withAnimation(Motion.or(Motion.softSpring)) { state.windowSelection = .item(project: code, key: it.key) }
                        }
                        .uiProbe("win-item-\(i)")
                    }
                }
                .card()
                .padding(.bottom, 24)
            }
            let log = snap?.doc?.log ?? []
            if !log.isEmpty {
                SectionTitle(text: "最近动静").padding(.bottom, 10)
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(Array(log.suffix(8).reversed().enumerated()), id: \.offset) { _, l in
                        Text(l).font(.system(size: 11.5, design: .monospaced)).foregroundStyle(Theme.textSecondary)
                            .lineLimit(2).frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled)
                    }
                }
                .padding(14)
                .background(RoundedRectangle(cornerRadius: Theme.radius, style: .continuous).fill(Theme.surfaceSunk))
            }
            if let e = snap?.error {
                Hint(text: "读不出状态：\(e)", color: Theme.danger).padding(.top, 12)
            }
        }
    }
}

struct BigMetric: View {
    let label: String
    let n: Int
    let color: Color
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("\(n)").font(.system(size: 26, weight: .semibold, design: .rounded))
                .foregroundStyle(n == 0 ? Theme.textSecondary.opacity(0.6) : color)
                .contentTransition(.numericText())
            Text(label).font(Theme.caption(12)).foregroundStyle(Theme.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 14).padding(.vertical, 10)
        .card()
        .accessibilityElement(children: .combine)
    }
}

struct ItemRowView: View {
    let item: StatusDoc.Item
    let action: () -> Void
    @State private var hover = false
    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Text(item.key).font(.system(size: 11.5, design: .monospaced)).foregroundStyle(Theme.textSecondary)
                    .frame(minWidth: 96, alignment: .leading)
                Text(item.title).font(Theme.body(13.5)).foregroundStyle(Theme.textPrimary).lineLimit(1)
                Spacer(minLength: 8)
                if item.stalled || item.noLivePath {
                    Image(systemName: "exclamationmark.triangle.fill").font(.system(size: 11)).foregroundStyle(Theme.warning)
                }
                Text(item.state).font(.system(size: 11, weight: .medium)).foregroundStyle(Theme.textSecondary)
                    .padding(.horizontal, 8).padding(.vertical, 3).background(Capsule().fill(Theme.surfaceSunk))
                Image(systemName: "chevron.right").font(.system(size: 10, weight: .semibold)).foregroundStyle(Theme.textSecondary)
            }
            .padding(.horizontal, 14).padding(.vertical, 10)
            .background(hover ? Theme.surfaceSunk.opacity(0.6) : Color.clear)
            .contentShape(Rectangle())
        }
        .buttonStyle(PressScale())
        .onHover { hover = $0 }
        .accessibilityLabel("\(item.key) \(item.title)，\(item.state)")
    }
}

// MARK: 件详情（时间线 + 产出物）

struct ItemPane: View {
    @ObservedObject var state: AppState
    let project: String
    let key: String
    let width: CGFloat

    private var k: String { "\(project)/\(key)" }
    private static let df: DateFormatter = { let f = DateFormatter(); f.dateFormat = "MM-dd HH:mm"; return f }()

    var body: some View {
        let log = state.logs[k]
        let item = state.snapshot(project)?.doc?.items.first { $0.key == key }
        VStack(alignment: .leading, spacing: 0) {
            Button { withAnimation(Motion.or(Motion.softSpring)) { state.windowSelection = .project(project) } } label: {
                Label("\(project) · \(state.snapshot(project)?.name ?? project)", systemImage: "chevron.left")
            }
            .buttonStyle(BouncyStyle(kind: .ghost, compact: true))
            .padding(.bottom, 8)
            PaneTitle(title: log?.title ?? item?.title ?? key, subtitle: key) {
                if let s = log?.state ?? item?.state {
                    Text(s).font(.system(size: 12, weight: .semibold)).foregroundStyle(Theme.accent)
                        .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(Theme.accentSoft))
                }
            }
            if let log {
                if width >= 760 {
                    HStack(alignment: .top, spacing: 18) {
                        timeline(log).frame(maxWidth: .infinity, alignment: .leading)
                        side(log).frame(width: min(360, width * 0.4))
                    }
                } else {
                    VStack(alignment: .leading, spacing: 18) { side(log); timeline(log) }
                }
            } else if let e = state.logErrors[k] {
                Hint(text: "读不出时间线：\(e)", color: Theme.danger)
            } else {
                HStack(spacing: 8) { Spinner(); Text("正在读 evo log \(key) …").font(Theme.body()).foregroundStyle(Theme.textSecondary) }
            }
        }
        .task(id: k) { await state.loadLog(project: project, key: key) }
    }

    @ViewBuilder private func timeline(_ log: ItemLog) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            SectionTitle(text: "时间线", count: nil).padding(.bottom, 12)
            if log.events.isEmpty {
                Text("还没有记录").font(Theme.body()).foregroundStyle(Theme.textSecondary)
            }
            ForEach(Array(log.timeline.enumerated()), id: \.element.id) { i, e in
                TimelineRow(event: e, time: e.date.map { Self.df.string(from: $0) } ?? String(e.at.prefix(16)),
                            last: i == log.timeline.count - 1)
                    .staggeredAppear(i)
            }
        }
        .padding(16)
        .card()
    }

    @ViewBuilder private func side(_ log: ItemLog) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            if let s = log.summary {
                InfoCard(title: "交卷说", symbol: "doc.text") {
                    Text(s).font(Theme.body()).foregroundStyle(Theme.textPrimary).fixedSize(horizontal: false, vertical: true)
                }
            }
            if !log.manualChecks.isEmpty {
                InfoCard(title: "看效果时看这几处", symbol: "eye") {
                    ForEach(log.manualChecks, id: \.self) { c in
                        Label(c, systemImage: "checkmark.circle").font(Theme.body(12.5)).foregroundStyle(Theme.textPrimary)
                    }
                }
            }
            InfoCard(title: "产出物", symbol: "photo.on.rectangle") {
                if log.artifacts.isEmpty {
                    Text("没有 artifacts/（或这版 evo log 还不给清单，去面板里看）").font(Theme.caption(11.5)).foregroundStyle(Theme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                ForEach(log.artifacts) { a in
                    HStack(spacing: 8) {
                        Image(systemName: a.symbol).foregroundStyle(Theme.accent).frame(width: 18)
                        Text(a.path).font(.system(size: 12, design: .monospaced)).foregroundStyle(Theme.textPrimary)
                            .lineLimit(1).truncationMode(.middle)
                        Spacer(minLength: 4)
                        if let s = a.sizeText { Text(s).font(Theme.caption(10.5)).foregroundStyle(a.tooBig ? Theme.warning : Theme.textSecondary) }
                    }
                }
                Button { PanelController.shared.open() } label: { Label("在面板里预览", systemImage: "rectangle.on.rectangle") }
                    .buttonStyle(BouncyStyle(kind: .secondary, compact: true))
            }
            if !log.changes.isEmpty {
                InfoCard(title: "改了哪些文件", symbol: "doc.on.doc") {
                    ForEach(Array(log.changes.enumerated()), id: \.offset) { _, c in
                        VStack(alignment: .leading, spacing: 1) {
                            Text(c.path).font(.system(size: 11.5, design: .monospaced)).foregroundStyle(Theme.textPrimary)
                                .lineLimit(1).truncationMode(.middle)
                            if !c.why.isEmpty { Text(c.why).font(Theme.caption(11)).foregroundStyle(Theme.textSecondary) }
                        }
                    }
                }
            }
            ItemPluginActions(state: state, project: project, key: key)     // v0.6.0：插件的件按钮
            if !log.notes.isEmpty {
                InfoCard(title: "你说过", symbol: "text.bubble") {
                    ForEach(Array(log.notes.enumerated()), id: \.offset) { _, n in
                        SpeechBubble(text: n, side: .me)
                    }
                }
            }
        }
    }
}

struct InfoCard<Content: View>: View {
    let title: String
    let symbol: String
    @ViewBuilder var content: () -> Content
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(title, systemImage: symbol).font(.system(size: 12.5, weight: .semibold)).foregroundStyle(Theme.textPrimary)
            content()
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }
}

struct TimelineRow: View {
    let event: ItemLog.Event
    let time: String
    let last: Bool

    private var color: Color {
        switch event.tone {
        case .success: return Theme.success
        case .accent: return Theme.accent
        case .danger: return Theme.danger
        case .neutral: return Theme.textSecondary
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            ZStack {
                Circle().fill(Theme.surface).frame(width: 26, height: 26)
                Circle().fill(color.opacity(0.15)).frame(width: 26, height: 26)
                Image(systemName: event.symbol).font(.system(size: 11, weight: .semibold)).foregroundStyle(color)
            }
            .frame(width: 26)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 8) {
                    Text(event.label).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.textPrimary)
                    Text(time).font(.system(size: 11, design: .monospaced)).foregroundStyle(Theme.textSecondary)
                }
                if let d = event.detail {
                    Text(d).font(Theme.caption(12)).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(.bottom, last ? 0 : 14)
            Spacer(minLength: 0)
        }
        .background(alignment: .topLeading) {
            if !last { Rectangle().fill(Theme.border).frame(width: 2).padding(.top, 26).padding(.leading, 12) }
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: 卡太久

struct StalePane: View {
    @ObservedObject var state: AppState
    var body: some View {
        let list = state.stuckEntries
        VStack(alignment: .leading, spacing: 0) {
            PaneTitle(title: "卡太久", count: nil, subtitle: "没活路的件和同一状态待太久的件（status JSON 的 no_live_path / stale）")
            if list.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "checkmark.seal").font(.system(size: 26)).foregroundStyle(Theme.success)
                    Text("没有卡住的件").font(Theme.title(16)).foregroundStyle(Theme.textPrimary)
                }
                .frame(maxWidth: .infinity).padding(.vertical, 30).card()
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(list.enumerated()), id: \.element.id) { i, e in
                        if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 14) }
                        Button {
                            withAnimation(Motion.or(Motion.softSpring)) { state.windowSelection = .item(project: e.project, key: e.key) }
                        } label: {
                            HStack(spacing: 10) {
                                Image(systemName: e.kind == .noLivePath ? "exclamationmark.triangle.fill" : "hourglass")
                                    .foregroundStyle(e.kind == .noLivePath ? Theme.danger : Theme.warning).frame(width: 18)
                                Text(e.key).font(.system(size: 11.5, design: .monospaced)).foregroundStyle(Theme.textSecondary)
                                Text(e.title.isEmpty ? e.project : e.title).font(Theme.body(13.5)).foregroundStyle(Theme.textPrimary).lineLimit(1)
                                Spacer(minLength: 8)
                                Text(e.detail).font(Theme.caption(11.5)).foregroundStyle(Theme.textSecondary).lineLimit(1)
                            }
                            .padding(.horizontal, 14).padding(.vertical, 10).contentShape(Rectangle())
                        }
                        .buttonStyle(PressScale())
                    }
                }
                .card()
            }
        }
    }
}

// MARK: - 底部输入框（像 Claude 一样钉在内容区底部）

struct ComposerDock: View {
    @ObservedObject var state: AppState
    var body: some View {
        VStack(spacing: 10) {
            if !state.chat.isEmpty {
                ScrollView(.vertical, showsIndicators: false) {
                    ChatSection(lines: Array(state.chat.suffix(4)), mood: state.mood, liveEmotion: state.mateEmotion, state: state)
                        .padding(.top, 4)
                }
                .frame(maxHeight: state.chat.suffix(4).contains { $0.card != nil } ? 320 : 200)
                .fixedSize(horizontal: false, vertical: true)
            }
            if let ch = state.pendingTeam {
                TeamConfirmCard(state: state, change: ch)
            }
            ComposerView(state: state)
                .uiProbe("win-composer")
        }
        .frame(maxWidth: 760)
        .padding(.horizontal, 32).padding(.top, 12).padding(.bottom, 18)
        .frame(maxWidth: .infinity)
        .background(
            LinearGradient(colors: [Theme.bg.opacity(0), Theme.bg], startPoint: .top, endPoint: UnitPoint(x: 0.5, y: 0.25))
                .ignoresSafeArea()
        )
        .animation(Motion.or(Motion.softSpring), value: state.chat)
        .animation(Motion.or(Motion.pop), value: state.pendingTeam)
    }
}
#endif
