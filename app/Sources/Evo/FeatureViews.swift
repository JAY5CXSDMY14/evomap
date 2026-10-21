#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

// v0.7.0（第十八轮）：功能开关 + 按 settings schema 自动画的设置表单 + evo watch 事件流 + 每页错误边界。
// 纯逻辑（解码、可见性、表单校验、重连退避、边界判断）都在 EvoCore/Features.swift，这里只接线和画。

// MARK: - AppState：功能列表 / 表单 / 错误边界

extension AppState {
    var registry: FeatureRegistry { FeatureRegistry(features) }

    /// 各页现在的错误（给 PageBoundary 判断这页画内容还是画错误卡片）。
    var pageErrors: PageErrors {
        PageErrors(team: team == nil ? teamError : nil,
                   projects: Dictionary(snaps.compactMap { s in s.error.map { (s.code, $0) } }, uniquingKeysWith: { a, _ in a }),
                   logs: logErrors,
                   features: featureNote)
    }

    /// `evo feature list --json`。老 evo 不认 feature 命令 → features = nil、不算错（界面照旧全显示）。
    func loadFeatures() async {
        if previewQuiet != nil { return }
        let r = await Shell.evo(FeatureCommand.list(), timeout: 30)
        if r.ok, let m = ContractCheck.check(r.out, command: .featureList).message {
            features = nil; featureNote = m; contractWarning = m; return
        }
        if r.ok, let l = try? FeatureList.decode(r.out) {
            features = l; featureNote = nil
            for f in l.features where featureForms[f.id] != nil { featureForms[f.id]?.sync(f) }
        } else if !r.ok && (r.err.contains("invalid choice") || r.err.contains("argument cmd")) {
            features = nil; featureNote = nil           // 老 evo：没有功能开关
        } else {
            features = nil
            featureNote = r.ok ? "看不懂 evo feature list 的回答：\(r.out.prefix(80))" : (r.tail.isEmpty ? "退出码 \(r.code)" : r.tail)
        }
        applyFeatureVisibility()
    }

    /// 页被关掉了：选着它就退回「等你处理」，它的数据也清掉（下次打开重读）。
    func applyFeatureVisibility() {
        let reg = registry
        let sel = windowSelection ?? .inbox
        let fb = reg.fallback(sel)
        if fb != sel { windowSelection = fb }
        if !reg.teamVisible { team = nil; teamError = nil }
        if !reg.pluginsVisible { plugins = nil; pluginNote = "功能「插件」关着（设置 → 功能里打开），第三方插件不跑。" }
    }

    func setFeatureEnabled(_ id: String, _ on: Bool) {
        guard !featureBusy.contains(id) else { return }
        featureBusy.insert(id)
        Task {
            let r = await Shell.evo(FeatureCommand.toggle(id, on: on), timeout: 30)
            featureBusy.remove(id)
            let name = features?.feature(id)?.name ?? id
            flash = r.ok ? "功能「\(name)」\(on ? "打开了" : "关掉了")" : "没成：\(r.tail.prefix(100))"
            await loadFeatures()
            if on { await loadTeam(); await loadPlugins() }
            clearFlash(containing: name)
        }
    }

    func form(_ f: FeatureInfo) -> FeatureForm { featureForms[f.id] ?? FeatureForm(f) }

    func editFeatureDraft(_ f: FeatureInfo, _ key: String, _ text: String) {
        var fm = form(f); fm.edit(key, text); featureForms[f.id] = fm
    }

    /// 文本 / 数字框：按 schema 校验，合格才跑 evo feature set。
    func commitFeatureField(_ f: FeatureInfo, _ field: SettingField) {
        var fm = form(f)
        let args = fm.commit(field)
        featureForms[f.id] = fm
        if let args { runFeatureSet(f, field, args) }
    }

    /// 开关 / 枚举按钮：点了就存。
    func chooseFeatureValue(_ f: FeatureInfo, _ field: SettingField, _ v: JSONValue) {
        var fm = form(f)
        let args = fm.choose(field, v)
        featureForms[f.id] = fm
        runFeatureSet(f, field, args)
    }

    private func runFeatureSet(_ f: FeatureInfo, _ field: SettingField, _ args: [String]) {
        let busyKey = "\(f.id)/\(field.key)"
        featureBusy.insert(busyKey)
        Task {
            let r = await Shell.evo(args, timeout: 30)
            featureBusy.remove(busyKey)
            if r.ok {
                flash = "「\(field.title)」存好了"
            } else {
                var fm = form(f); fm.reject(field.key, r.tail); featureForms[f.id] = fm
                flash = "没成：\(r.tail.prefix(100))"
            }
            await loadFeatures()
            clearFlash(containing: r.ok ? field.title : "没成")
        }
    }

    func toggleFeatureExpanded(_ id: String) {
        withAnimation(Motion.or(Motion.softSpring)) { expandedFeature = expandedFeature == id ? nil : id }
        if expandedFeature == id {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { [weak self] in self?.scrollTarget = "feature-\(id)" }
        }
    }

    /// 错误卡片上的「重试」：只重读这一页要的东西。
    func retryPage(_ sel: SidebarItem) {
        pageRetrying = true
        Task {
            switch sel {
            case .team: await loadTeam()
            case .item(let p, let k): await loadLog(project: p, key: k)
            default:
                refresh()
                try? await Task.sleep(nanoseconds: 600_000_000)
            }
            pageRetrying = false
        }
    }

    func retryFeatures() {
        pageRetrying = true
        Task { await loadFeatures(); pageRetrying = false }
    }

    private func clearFlash(containing s: String) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 4) { [weak self] in
            if self?.flash?.contains(s) == true { self?.flash = nil }
        }
    }

    // MARK: 事件流

    func startWatch() {
        guard previewQuiet == nil, watchClient == nil else { return }
        let c = WatchClient()
        watchClient = c
        c.start()
        NotificationCenter.default.addObserver(forName: NSApplication.willTerminateNotification, object: nil, queue: .main) { _ in
            Task { @MainActor in AppState.shared.watchClient?.stop() }
        }
    }

    /// 30 秒定时器每次叫它：事件流活着就只做 2 分钟兜底；断了回到 30 秒轮询。
    func pollTick() {
        if WatchPolicy.shouldPoll(lastRefresh: lastRefresh, lastLine: watchLink.alive() ? watchLink.lastLine : nil) { refresh() }
    }
}

// MARK: - evo watch --json 子进程（断线自动重连；连不上时 AppState 照旧轮询）

@MainActor
final class WatchClient {
    private var proc: Process?
    private var parser = WatchParser()
    private var pending = Data()
    private var stopped = false
    private var debounce: DispatchWorkItem?

    func start() {
        guard proc == nil, !stopped else { return }
        let st = AppState.shared
        guard let py = EvoEnv.python, let script = EvoEnv.evoScript else {
            st.watchLink.started(); scheduleRestart(); return
        }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: py)
        p.arguments = [script, "watch", "--json", "--ping", "15"]
        p.environment = EvoEnv.environment
        p.currentDirectoryURL = URL(fileURLWithPath: EvoEnv.home)
        let out = Pipe()
        p.standardOutput = out
        p.standardError = FileHandle.nullDevice
        p.standardInput = FileHandle.nullDevice
        out.fileHandleForReading.readabilityHandler = { h in
            let d = h.availableData
            if d.isEmpty { h.readabilityHandler = nil; return }
            Task { @MainActor in AppState.shared.watchClient?.feed(d) }
        }
        p.terminationHandler = { _ in
            Task { @MainActor in AppState.shared.watchClient?.exited() }
        }
        parser = WatchParser(); pending = Data()
        st.watchLink.started()
        do { try p.run(); proc = p } catch { exited() }
    }

    func stop() {
        stopped = true
        debounce?.cancel()
        if let p = proc, p.isRunning { p.terminate() }
        proc = nil
    }

    /// 只把完整的行（以 \n 结尾）交给解析器，半个 UTF-8 字符留到下一块。
    func feed(_ d: Data) {
        pending.append(d)
        guard let nl = pending.lastIndex(of: 0x0A) else { return }
        let whole = pending[pending.startIndex...nl]
        pending = Data(pending[pending.index(after: nl)...])
        let text = String(decoding: whole, as: UTF8.self)
        let events = parser.feed(text)
        let st = AppState.shared
        st.watchLink.received(max(1, text.split(separator: "\n").count))
        guard events.contains(where: \.triggersRefresh) else { return }
        debounce?.cancel()
        let w = DispatchWorkItem { Task { @MainActor in AppState.shared.refresh() } }
        debounce = w
        DispatchQueue.main.asyncAfter(deadline: .now() + WatchPolicy.debounce, execute: w)
    }

    func exited() {
        proc = nil
        guard !stopped else { return }
        scheduleRestart()
    }

    private func scheduleRestart() {
        let delay = AppState.shared.watchLink.exited()
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            Task { @MainActor in AppState.shared.watchClient?.start() }
        }
    }
}

// MARK: - 每页的错误边界卡片

struct PageErrorCard: View {
    let error: PageError
    var busy = false
    var back: (() -> Void)?
    let retry: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 10) {
                Image(systemName: "exclamationmark.triangle.fill").font(.system(size: 18)).foregroundStyle(Theme.danger)
                Text(error.title).font(Theme.title(17)).foregroundStyle(Theme.textPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }
            Text(error.message).font(.system(size: 12, design: .monospaced)).foregroundStyle(Theme.textPrimary)
                .fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
                .padding(10).frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).fill(Theme.surfaceSunk))
            Text("只有这一页坏了，别的页照常。修好原因后点重试；一直不行就看设置里的 evo 路径。")
                .font(Theme.caption(11.5)).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 8) {
                Button(action: retry) {
                    HStack(spacing: 6) {
                        if busy { Spinner(size: 11) } else { Image(systemName: "arrow.clockwise") }
                        Text("重试")
                    }
                }
                .buttonStyle(BouncyStyle(kind: .primary, compact: true))
                .disabled(busy)
                .uiProbe(PageBoundary.retryProbe)
                if let back {
                    Button(action: back) { Label("返回", systemImage: "chevron.left") }
                        .buttonStyle(BouncyStyle(kind: .secondary, compact: true))
                }
                Spacer()
            }
        }
        .padding(16)
        .frame(maxWidth: 640, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: Theme.radius, style: .continuous).fill(Theme.surface))
        .overlay(RoundedRectangle(cornerRadius: Theme.radius, style: .continuous).strokeBorder(Theme.danger.opacity(0.45), lineWidth: 1))
        .accessibilityElement(children: .contain)
        .accessibilityLabel("\(error.title)：\(error.message)")
        .uiProbe("page-error-card")
    }
}

// MARK: - 设置页「功能」卡片

struct FeatureSettingsCard: View {
    @ObservedObject var state: AppState

    var body: some View {
        SettingsCard(title: "功能", symbol: "square.stack.3d.up") {
            let reg = state.registry
            if let e = state.featureNote, state.features == nil {
                PageErrorCard(error: PageError(message: e, title: "功能列表读不出来"), busy: state.pageRetrying) { state.retryFeatures() }
            } else {
                Hint(text: reg.summary)
            }
            ForEach(reg.settingsRows) { f in
                FeatureRowView(state: state, feature: f)
                    .id("feature-\(f.id)")
                if f.id != reg.settingsRows.last?.id { Rectangle().fill(Theme.border).frame(height: 1) }
            }
            if state.features != nil {
                Hint(text: "开关和设置存在 ~/.evoloop/features.yml，下一轮生效；终端里 evo feature list / on / off / set 一样能改。「在用」的功能关不掉；推送渠道（Telegram / 邮件）不算在用，随时能关。")
            }
        }
    }
}

struct FeatureRowView: View {
    @ObservedObject var state: AppState
    let feature: FeatureInfo

    private var expanded: Bool { state.expandedFeature == feature.id }
    private var fieldCount: Int { feature.settings?.fields.count ?? 0 }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Toggle(isOn: Binding(get: { feature.enabled }, set: { on in state.setFeatureEnabled(feature.id, on) })) {
                HStack(spacing: 7) {
                    Text(feature.name).font(.system(size: 13, weight: .medium)).foregroundStyle(Theme.textPrimary).lineLimit(1)
                    FeatureBadge(text: feature.badge.text, tone: feature.badge.tone)
                    if feature.essential {
                        Text("精简也开").font(.system(size: 10.5)).foregroundStyle(Theme.textSecondary)
                    }
                    if state.featureBusy.contains(feature.id) { Spinner(size: 11) }
                }
            }
            .toggleStyle(PillToggleStyle())
            .disabled(feature.locked || state.featureBusy.contains(feature.id))
            .uiProbe("settings-feature-\(feature.id)")
            .accessibilityHint(feature.note)
            if !feature.note.isEmpty {
                Text(feature.note).font(Theme.caption(11.5))
                    .foregroundStyle(feature.state == "failed" ? Theme.danger : Theme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if fieldCount > 0 {
                Button { state.toggleFeatureExpanded(feature.id) } label: {
                    Label(expanded ? "收起设置" : "设置（\(fieldCount) 项）", systemImage: expanded ? "chevron.up" : "slider.horizontal.3")
                }
                .buttonStyle(BouncyStyle(kind: .chip, compact: true))
                .uiProbe("feature-expand-\(feature.id)")
                if expanded {
                    FeatureFormView(state: state, feature: feature)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
        }
        .padding(.vertical, 3)
    }
}

struct FeatureBadge: View {
    let text: String
    let tone: CardTone
    var body: some View {
        let c = FeatureBadge.color(tone)
        Text(text).font(.system(size: 10.5, weight: .semibold)).foregroundStyle(c)
            .padding(.horizontal, 7).padding(.vertical, 2)
            .background(Capsule().fill(c.opacity(0.13)))
    }

    static func color(_ t: CardTone) -> Color {
        switch t {
        case .success: return Theme.success
        case .warning: return Theme.warning
        case .danger: return Theme.danger
        case .accent: return Theme.accent
        case .neutral: return Theme.textSecondary
        }
    }
}

/// 按 settings schema 画的表单：boolean → 开关；enum → 一排按钮；integer / number → 数字框（带范围）；string → 文本框。
struct FeatureFormView: View {
    @ObservedObject var state: AppState
    let feature: FeatureInfo

    var body: some View {
        let fm = state.form(feature)
        VStack(alignment: .leading, spacing: 12) {
            ForEach(feature.settings?.fields ?? []) { field in
                fieldView(field, fm)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).fill(Theme.surfaceSunk))
        .uiProbe("feature-form-\(feature.id)")
    }

    @ViewBuilder private func fieldView(_ field: SettingField, _ fm: FeatureForm) -> some View {
        let busy = state.featureBusy.contains("\(feature.id)/\(field.key)")
        VStack(alignment: .leading, spacing: 4) {
            switch field.control {
            case .toggle:
                Toggle(isOn: Binding(get: { feature.value(field) == .bool(true) },
                                     set: { on in state.chooseFeatureValue(feature, field, .bool(on)) })) {
                    HStack(spacing: 6) {
                        Text(field.title).font(Theme.body(12.5)).foregroundStyle(Theme.textPrimary).fixedSize(horizontal: false, vertical: true)
                        if busy { Spinner(size: 10) }
                    }
                }
                .toggleStyle(PillToggleStyle())
                .uiProbe("feature-field-\(feature.id)-\(field.key)")
            case .choice:
                title(field, busy)
                HStack(spacing: 6) {
                    ForEach(Array((field.options ?? []).enumerated()), id: \.offset) { _, opt in
                        Button(SettingField.text(opt)) { state.chooseFeatureValue(feature, field, opt) }
                            .buttonStyle(BouncyStyle(kind: feature.value(field) == opt ? .primary : .chip, compact: true))
                    }
                    Spacer(minLength: 0)
                }
            case .number, .text:
                title(field, busy)
                HStack(spacing: 8) {
                    ThemedField(placeholder: SettingField.text(field.defaultValue),
                                text: Binding(get: { state.form(feature).draft(field.key) },
                                              set: { state.editFeatureDraft(feature, field.key, $0) }),
                                onSubmit: { state.commitFeatureField(feature, field) })
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(RoundedRectangle(cornerRadius: 8, style: .continuous).fill(Theme.surface))
                        .overlay(RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .strokeBorder(fm.error(field.key) == nil ? Theme.border : Theme.danger, lineWidth: 1))
                        .frame(width: field.control == .number ? 120 : 200)
                        .uiProbe("feature-field-\(feature.id)-\(field.key)")
                    if let r = field.rangeText {
                        Text(r).font(Theme.caption(11)).foregroundStyle(Theme.textSecondary)
                    }
                    if fm.dirty(field, in: feature) {
                        Button("存") { state.commitFeatureField(feature, field) }
                            .buttonStyle(BouncyStyle(kind: .primary, compact: true))
                            .uiProbe("feature-save-\(feature.id)-\(field.key)")
                    }
                    Spacer(minLength: 0)
                }
            }
            if let e = fm.error(field.key) {
                Label(e, systemImage: "exclamationmark.circle.fill").font(Theme.caption(11.5)).foregroundStyle(Theme.danger)
                    .fixedSize(horizontal: false, vertical: true)
                    .uiProbe("feature-error-\(feature.id)-\(field.key)")
            } else if let d = field.description, !d.isEmpty {
                Text(d).font(Theme.caption(11)).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    @ViewBuilder private func title(_ field: SettingField, _ busy: Bool) -> some View {
        HStack(spacing: 6) {
            Text(field.title).font(Theme.body(12.5)).foregroundStyle(Theme.textPrimary).fixedSize(horizontal: false, vertical: true)
            if busy { Spinner(size: 10) }
        }
    }
}
#endif
