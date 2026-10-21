#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

// v0.6.0 插件：侧栏「插件」分组里的页、输入框「/命令」的回话卡片、件详情页的插件按钮、设置里的开关。
// 插件只输出卡片 JSON（标题、文字、列表、表格、按钮），这里用一个通用渲染器画，沿用现有的卡片样式和弹簧动效。
// 插件命令都由 evo 作为子进程跑（有超时、输出上限、环境变量白名单）；失败只在这一页显示错误。见 docs/plugins.md。

extension AppState {
    /// evo plugin list --json。老 evo 没有 plugin 命令：插件分组不出现，设置里说一句。
    func loadPlugins() async {
        if previewQuiet != nil { return }
        let r = await Shell.evo(PluginCLI.list(), timeout: 30)
        if r.ok, let m = ContractCheck.check(r.out, command: .pluginList).message {
            plugins = nil; pluginNote = m; contractWarning = m; return
        }
        if r.ok, let l = try? PluginList.decode(r.out) {
            plugins = l; pluginNote = nil
            // 关掉的插件：它的页不能再选着
            if case .plugin(let p, let id) = windowSelection ?? .inbox, l.page(p, id) == nil { windowSelection = .inbox }
        } else {
            plugins = nil
            pluginNote = r.ok ? "看不懂 evo plugin list 的回答" : "这版 evo 还没有插件功能（evo plugin），或读不出来：\(r.tail.prefix(120))"
        }
    }

    func setPluginEnabled(_ name: String, _ on: Bool) {
        guard !pluginBusy.contains(name) else { return }
        pluginBusy.insert(name)
        Task {
            let r = await Shell.evo(PluginCLI.setEnabled(name, on), timeout: 30)
            pluginBusy.remove(name)
            flash = r.ok ? "插件 \(name) \(on ? "打开了" : "关掉了")" : "没成：\(r.tail.prefix(100))"
            await loadPlugins()
            DispatchQueue.main.asyncAfter(deadline: .now() + 4) { [weak self] in
                if self?.flash?.contains(name) == true { self?.flash = nil }
            }
        }
    }

    /// 跑插件页（打开时、点刷新、点卡片上的按钮）。
    func runPluginPage(_ ref: PluginPageRef, action: String? = nil, payload: JSONValue? = nil) async {
        let k = ref.key
        if previewQuiet != nil { return }
        let keep = pluginPages[k]?.card
        if keep == nil || action == nil { pluginPages[k] = .loading }
        let r = await Shell.evo(PluginCLI.run(plugin: ref.plugin, kind: "sidebar_page", id: ref.id, action: action, payload: payload,
                                              project: focusedProject ?? codes.first), timeout: 75)
        withAnimation(Motion.or(Motion.softSpring)) {
            pluginPages[k] = CardViewState.from(code: r.code, out: r.out, err: r.err)
        }
    }

    /// 输入框「/名字 参数」，以及回话卡片上的按钮。
    func runComposerPlugin(_ c: PluginComposerRef, args: String, project: String, action: String?, payload: JSONValue?) {
        Task {
            let r = await Shell.evo(PluginCLI.run(plugin: c.plugin, kind: "composer_command", id: c.id, args: args, action: action,
                                                  payload: payload, project: project.isEmpty ? nil : project), timeout: 75)
            switch CardViewState.from(code: r.code, out: r.out, err: r.err) {
            case .loaded(let card):
                chat.append(ChatLine(text: card.title, mine: false, card: card, command: c))
                react(.replied)
            case .empty:
                chat.append(ChatLine(text: "/\(c.name) 跑完了（插件没回内容）", mine: false))
                react(.replied)
            case .failed(let e):
                chat.append(ChatLine(text: "/\(c.name) 出错：\(e)", mine: false, failed: true))
                react(.replyFailed)
            case .loading: break
            }
            trimChat()
        }
    }

    func runItemAction(_ a: PluginItemActionRef, project: String, key: String, action: String? = nil, payload: JSONValue? = nil) {
        let k = "\(project)/\(key)/\(a.key)"
        itemActionResults[k] = .loading
        Task {
            let r = await Shell.evo(PluginCLI.run(plugin: a.plugin, kind: "item_action", id: a.id, action: action, payload: payload,
                                                  project: project, item: key), timeout: 75)
            withAnimation(Motion.or(Motion.softSpring)) { itemActionResults[k] = CardViewState.from(code: r.code, out: r.out, err: r.err) }
        }
    }
}

// MARK: - 通用卡片渲染器

struct PluginCardView: View {
    let card: PluginCard
    var compact = false
    var busyAction: String? = nil
    var onAction: ((CardButton) -> Void)? = nil
    var probePrefix: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 8 : 12) {
            if compact {
                Text(card.title).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.textPrimary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if compact, let s = card.subtitle {
                Text(s).font(Theme.caption()).foregroundStyle(Theme.textSecondary)
            }
            ForEach(Array(card.blocks.enumerated()), id: \.offset) { i, b in
                block(b, index: i).staggeredAppear(i)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder private func block(_ b: CardBlock, index: Int) -> some View {
        switch b {
        case .text(let t, let style, let tone):
            Text(t).font(font(style)).foregroundStyle(style == "caption" ? Theme.textSecondary : color(tone))
                .fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
        case .list(let items):
            VStack(spacing: 0) {
                ForEach(Array(items.enumerated()), id: \.offset) { i, it in
                    if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, it.symbol == nil ? 12 : 40) }
                    HStack(spacing: 10) {
                        if let s = it.symbol {
                            Image(systemName: s).font(.system(size: 13, weight: .medium)).foregroundStyle(it.tone == .neutral ? Theme.accent : color(it.tone))
                                .frame(width: 20)
                        }
                        VStack(alignment: .leading, spacing: 1) {
                            Text(it.title).font(Theme.body(compact ? 12.5 : 13.5)).foregroundStyle(it.tone == .neutral ? Theme.textPrimary : color(it.tone))
                            if let st = it.subtitle {
                                Text(st).font(Theme.caption(11.5)).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        Spacer(minLength: 6)
                        if let bd = it.badge {
                            Text(bd).font(.system(size: 10.5, weight: .medium, design: .rounded)).foregroundStyle(Theme.textSecondary)
                                .padding(.horizontal, 7).padding(.vertical, 2).background(Capsule().fill(Theme.surfaceSunk))
                        }
                    }
                    .padding(.horizontal, 12).padding(.vertical, compact ? 6 : 9)
                }
            }
            .card()
        case .table(let cols, let rows):
            VStack(spacing: 0) {
                HStack(spacing: 0) {
                    ForEach(Array(cols.enumerated()), id: \.offset) { _, c in
                        Text(c).font(.system(size: 11.5, weight: .semibold)).foregroundStyle(Theme.textSecondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(.horizontal, 12).padding(.vertical, 7)
                .background(Theme.surfaceSunk)
                ForEach(Array(rows.enumerated()), id: \.offset) { i, r in
                    if i > 0 { Rectangle().fill(Theme.border).frame(height: 1) }
                    HStack(spacing: 0) {
                        ForEach(Array(r.enumerated()), id: \.offset) { _, cell in
                            Text(cell).font(Theme.body(12.5)).foregroundStyle(Theme.textPrimary)
                                .frame(maxWidth: .infinity, alignment: .leading).lineLimit(3).textSelection(.enabled)
                        }
                    }
                    .padding(.horizontal, 12).padding(.vertical, 7)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
            .card()
        case .buttons(let bs):
            HStack(spacing: 8) {
                ForEach(Array(bs.enumerated()), id: \.offset) { j, bt in
                    Button { onAction?(bt) } label: {
                        HStack(spacing: 5) {
                            if busyAction == bt.action { Spinner(size: 11) }
                            Text(bt.label)
                        }
                    }
                    .buttonStyle(BouncyStyle(kind: kind(bt.style), compact: true))
                    .disabled(onAction == nil || busyAction != nil)
                    .uiProbe(probePrefix.map { "\($0)-btn-\(j)" })
                }
                Spacer(minLength: 0)
            }
        case .unknown:
            EmptyView()
        }
    }

    private func font(_ style: String) -> Font {
        switch style {
        case "title": return Theme.title(compact ? 15 : 18)
        case "caption": return Theme.caption(11.5)
        case "mono": return .system(size: 12, design: .monospaced)
        default: return Theme.body(compact ? 12.5 : 13.5)
        }
    }

    private func color(_ t: CardTone) -> Color {
        switch t {
        case .neutral: return Theme.textPrimary
        case .accent: return Theme.accent
        case .success: return Theme.success
        case .warning: return Theme.warning
        case .danger: return Theme.danger
        }
    }

    private func kind(_ s: String) -> BouncyStyle.Kind {
        switch s {
        case "primary": return .primary
        case "danger": return .danger
        default: return .secondary
        }
    }
}

/// 三态外壳：空 / 加载 / 报错，加载完的卡片交给 PluginCardView。
struct CardStateView: View {
    let state: CardViewState?
    var compact = false
    var busyAction: String? = nil
    var onAction: ((CardButton) -> Void)? = nil
    var onRetry: (() -> Void)? = nil
    var probePrefix: String? = nil

    var body: some View {
        Group {
            switch state ?? .loading {
            case .loading:
                HStack(spacing: 8) {
                    Spinner()
                    Text("插件在跑…").font(Theme.body()).foregroundStyle(Theme.textSecondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(compact ? 10 : 16)
                .card()
                .transition(.opacity)
            case .failed(let e):
                VStack(alignment: .leading, spacing: 10) {
                    Label("插件出错了", systemImage: "exclamationmark.triangle.fill")
                        .font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.danger)
                    Text(e).font(Theme.body(12.5)).foregroundStyle(Theme.textPrimary).fixedSize(horizontal: false, vertical: true)
                        .textSelection(.enabled)
                    Text("只是这个插件出错，App 和 evo 循环不受影响。").font(Theme.caption()).foregroundStyle(Theme.textSecondary)
                    if let onRetry {
                        Button { onRetry() } label: { Label("再试一次", systemImage: "arrow.clockwise") }
                            .buttonStyle(BouncyStyle(kind: .secondary, compact: true))
                            .uiProbe(probePrefix.map { "\($0)-retry" })
                    }
                }
                .padding(compact ? 10 : 16)
                .frame(maxWidth: .infinity, alignment: .leading)
                .card()
                .transition(.scale(scale: 0.96, anchor: .top).combined(with: .opacity))
            case .empty:
                VStack(spacing: 8) {
                    Image(systemName: "tray").font(.system(size: 22)).foregroundStyle(Theme.textSecondary)
                    Text("插件这次没给内容").font(Theme.body()).foregroundStyle(Theme.textSecondary)
                }
                .frame(maxWidth: .infinity).padding(.vertical, compact ? 12 : 26)
                .card()
                .transition(.opacity)
            case .loaded(let c):
                PluginCardView(card: c, compact: compact, busyAction: busyAction, onAction: onAction, probePrefix: probePrefix)
                    .transition(.asymmetric(insertion: .scale(scale: 0.97, anchor: .top).combined(with: .opacity), removal: .opacity))
            }
        }
        .animation(Motion.or(Motion.softSpring), value: state)
    }
}

// MARK: - 插件页（侧栏「插件」分组）

struct PluginPane: View {
    @ObservedObject var state: AppState
    let ref: PluginPageRef
    @State private var busyAction: String?

    var body: some View {
        let st = state.pluginPages[ref.key]
        VStack(alignment: .leading, spacing: 0) {
            PaneTitle(title: st?.card?.title.isEmpty == false ? st!.card!.title : ref.title,
                      subtitle: st?.card?.subtitle ?? "插件 \(ref.plugin)") {
                HStack(spacing: 6) {
                    Text(ref.plugin).font(.system(size: 12, weight: .semibold, design: .rounded)).foregroundStyle(Theme.accent)
                        .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(Theme.accentSoft))
                    Button { reload(nil, nil) } label: { Image(systemName: "arrow.clockwise") }
                        .buttonStyle(BouncyStyle(kind: .ghost, compact: true))
                        .help("再跑一次插件")
                        .accessibilityLabel("刷新插件页")
                        .uiProbe("plugin-page-refresh")
                }
            }
            CardStateView(state: st, busyAction: busyAction, onAction: { b in reload(b.action, b.payload) },
                          onRetry: { reload(nil, nil) }, probePrefix: "plugin-page")
                .uiProbe("plugin-page")
        }
        .task(id: ref.key) {
            if state.pluginPages[ref.key]?.isLoading != true { await state.runPluginPage(ref) }     // 每次打开都重跑一次插件
        }
    }

    private func reload(_ action: String?, _ payload: JSONValue?) {
        busyAction = action
        Task {
            await state.runPluginPage(ref, action: action, payload: payload)
            busyAction = nil
        }
    }
}

// MARK: - 件详情页的插件按钮

struct ItemPluginActions: View {
    @ObservedObject var state: AppState
    let project: String
    let key: String

    var body: some View {
        let actions = state.plugins?.itemActions ?? []
        if !actions.isEmpty {
            InfoCard(title: "插件", symbol: "puzzlepiece.extension") {
                HStack(spacing: 6) {
                    ForEach(actions, id: \.key) { a in
                        Button { state.runItemAction(a, project: project, key: key) } label: { Label(a.title, systemImage: a.symbol) }
                            .buttonStyle(BouncyStyle(kind: .secondary, compact: true))
                    }
                    Spacer(minLength: 0)
                }
                ForEach(actions, id: \.key) { a in
                    let k = "\(project)/\(key)/\(a.key)"
                    if let r = state.itemActionResults[k] {
                        CardStateView(state: r, compact: true,
                                      onAction: { b in state.runItemAction(a, project: project, key: key, action: b.action, payload: b.payload) },
                                      onRetry: { state.runItemAction(a, project: project, key: key) })
                    }
                }
            }
        }
    }
}

// MARK: - 设置里的「插件」

struct PluginSettingsCard: View {
    @ObservedObject var state: AppState
    @Environment(\.evoStatic) private var isStatic

    var body: some View {
        SettingsCard(title: "插件", symbol: "puzzlepiece.extension") {
            let list = state.plugins?.plugins ?? []
            if list.isEmpty {
                Hint(text: state.pluginNote ?? "还没装插件。终端里 evo plugin install <插件文件夹>（示例：kit/plugins/example-hello），装好默认关着，在这里打开。")
            }
            ForEach(list) { p in
                VStack(alignment: .leading, spacing: 3) {
                    Toggle(isOn: Binding(get: { p.enabled }, set: { on in if !isStatic { state.setPluginEnabled(p.name, on) } })) {
                        HStack(spacing: 6) {
                            Text(p.name).foregroundStyle(Theme.textPrimary)
                            if state.pluginBusy.contains(p.name) { Spinner(size: 11) }
                        }
                    }
                    .toggleStyle(PillToggleStyle())
                    .disabled(!p.canEnable && !p.enabled)
                    .uiProbe("settings-plugin-\(p.name)")
                    if let d = p.description, !d.isEmpty {
                        Text(d).font(Theme.caption(11.5)).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
                    }
                    Hint(text: p.statusLine, color: p.canEnable ? Theme.textSecondary : Theme.danger)
                }
                .padding(.vertical, 2)
            }
            Hint(text: "插件放在 \(state.plugins?.pluginsDir ?? "~/.evoloop/plugins")/<名字>/plugin.json；新插件默认关着。插件作为子进程跑，20 秒超时，拿不到任何密钥。写法见 docs/plugins.md。")
            if !isStatic {
                Button { Task { await state.loadPlugins() } } label: { Label("重新读插件", systemImage: "arrow.clockwise") }
                    .buttonStyle(BouncyStyle(kind: .secondary, compact: true))
            }
        }
    }
}

// MARK: - 接口版本对不上时的横幅

struct ContractBanner: View {
    let text: String
    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "arrow.triangle.2.circlepath").foregroundStyle(Theme.warning)
            Text(text).font(Theme.body(12.5)).foregroundStyle(Theme.textPrimary).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).fill(Theme.warning.opacity(0.12)))
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).strokeBorder(Theme.warning.opacity(0.35), lineWidth: 1))
        .accessibilityElement(children: .combine)
        .uiProbe("contract-banner")
    }
}
#endif
