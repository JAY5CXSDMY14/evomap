#if os(macOS)
import AppKit
import SwiftUI
import ServiceManagement
import EvoCore

/// 设置、向导这类 SwiftUI 窗口统一用 AppKit 开（菜单栏应用没有 Dock 图标，要手动把窗口拉到最前）。
@MainActor
final class WindowManager {
    static let shared = WindowManager()
    private var windows: [String: NSWindow] = [:]

    func show<V: View>(_ id: String, title: String, size: NSSize, @ViewBuilder content: () -> V) {
        if let w = windows[id] {
            w.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true); return
        }
        let w = NSWindow(contentRect: NSRect(origin: .zero, size: size),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        w.title = title
        w.isReleasedWhenClosed = false
        w.titlebarAppearsTransparent = true
        w.backgroundColor = NSColor(Theme.bg)
        w.contentViewController = NSHostingController(rootView: content())
        w.setContentSize(size)
        w.center()
        windows[id] = w
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func close(_ id: String) { windows[id]?.close() }

    func showSettings() {
        if MainWindowController.shared.isOpen {      // 窗口开着就在窗口里打开设置页
            AppState.shared.windowSelection = .settings
            MainWindowController.shared.show()
            return
        }
        show("settings", title: "Evo 设置", size: NSSize(width: 520, height: 700)) { SettingsView(state: AppState.shared) }
    }

    func showSetup() {
        show("setup", title: "欢迎使用 Evo", size: NSSize(width: 620, height: 720)) { SetupView() }
    }
}

// MARK: - 设置

/// 一组设置：象牙底上的白卡片，标题用 serif。
struct SettingsCard<Content: View>: View {
    let title: String
    let symbol: String
    @ViewBuilder var content: () -> Content
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(title, systemImage: symbol).font(Theme.title(14)).foregroundStyle(Theme.textPrimary)
                .accessibilityAddTraits(.isHeader)
            content()
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }
}

struct Hint: View {
    let text: String
    var color: Color = Theme.textSecondary
    var body: some View {
        Text(text).font(Theme.caption()).foregroundStyle(color).fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
    }
}

struct FieldBox: View {
    let placeholder: String
    @Binding var text: String
    var body: some View {
        ThemedField(placeholder: placeholder, text: $text)
            .padding(.horizontal, 10).padding(.vertical, 7)
            .background(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).fill(Theme.surfaceSunk))
            .overlay(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).strokeBorder(Theme.border))
    }
}

struct SettingsView: View {
    @ObservedObject var state: AppState
    @AppStorage("panelPort") private var panelPort = 8765
    @AppStorage("pythonPath") private var pythonPath = ""
    @AppStorage("evoPath") private var evoPath = ""
    @AppStorage("notificationsEnabled") private var notificationsEnabled = true
    @State private var loginItem = SMAppService.mainApp.status == .enabled
    @State private var loginError: String?
    @AppStorage("mateCharacter") private var mateCharacter = MateCharacter.default.rawValue
    var embedded = false
    @Environment(\.evoStatic) private var isStatic

    private var portText: Binding<String> {
        Binding(get: { String(panelPort) }, set: { v in if let n = Int(v.filter(\.isNumber)), (1...65535).contains(n) { panelPort = n } })
    }

    var body: some View {
        MaybeScroll(maxHeight: 2000) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 12) {
                    MateView(emotion: .standby, size: 44)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("设置").font(Theme.title(22)).foregroundStyle(Theme.textPrimary)
                        Text("Evo \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "dev")")
                            .font(Theme.caption()).foregroundStyle(Theme.textSecondary)
                    }
                    Spacer()
                }
                .staggeredAppear(0)
                SettingsCard(title: "角色和外观", symbol: "face.smiling") {
                    HStack(spacing: 8) {
                        ForEach(MateCharacter.allCases, id: \.self) { c in
                            Button { mateCharacter = c.rawValue; if MainWindowController.shared.isOpen { DockIcon.apply() } } label: {
                                Text(c.label)
                            }
                            .buttonStyle(BouncyStyle(kind: mateCharacter == c.rawValue ? .primary : .chip, compact: true))
                        }
                        Spacer()
                        MateView(emotion: .curious, size: 40)
                    }
                    Hint(text: mateCharacter == MateCharacter.ball.rawValue
                         ? "球球（emotion-ball）只许自用：个人学习研究、非商业，带着它的 Evo 不能公开分发。要分发就换云宝 / 亮亮并买商业许可。"
                         : "云宝 / 亮亮（mood-mates）：个人免费；商用或分发前要向作者买商业许可。", color: Theme.textSecondary)
                    HStack(spacing: 8) {
                        Text("外观").foregroundStyle(Theme.textPrimary)
                        ForEach([("system", "跟系统"), ("light", "浅色"), ("dark", "深色")], id: \.0) { k, t in
                            Button(t) { state.setAppearance(k) }
                                .buttonStyle(BouncyStyle(kind: state.appearance == k ? .primary : .chip, compact: true))
                        }
                        Spacer()
                    }
                }
                .staggeredAppear(1)
                SettingsCard(title: "开机", symbol: "power") {
                    Toggle("登录时自动打开 Evo", isOn: $loginItem).toggleStyle(PillToggleStyle())
                        .onChange(of: loginItem) { on in if !isStatic { setLoginItem(on) } }
                    if SMAppService.mainApp.status == .requiresApproval {
                        HStack {
                            Hint(text: "需要在系统设置里批准", color: Theme.warning)
                            Button("打开登录项设置") { SMAppService.openSystemSettingsLoginItems() }
                                .buttonStyle(BouncyStyle(kind: .secondary, compact: true))
                        }
                    }
                    if let loginError { Hint(text: loginError, color: Theme.danger) }
                }
                .staggeredAppear(1)
                SettingsCard(title: "通知", symbol: "bell") {
                    Toggle("新闸门、接棒器停了时发原生通知", isOn: $notificationsEnabled).toggleStyle(PillToggleStyle())
                    Hint(text: quietText)
                    Button("发一条测试通知") { Notifier.shared.test() }.buttonStyle(BouncyStyle(kind: .secondary, compact: true))
                }
                .staggeredAppear(2)
                SettingsCard(title: "面板", symbol: "rectangle.on.rectangle") {
                    HStack { Text("端口").foregroundStyle(Theme.textPrimary); FieldBox(placeholder: "8765", text: portText).frame(width: 110); Spacer() }
                    Hint(text: "应用会先找这个端口上正在跑的 evo panel，没有就自己起一个（退出 Evo 时一起关）。")
                }
                .staggeredAppear(3)
                SettingsCard(title: "evo", symbol: "terminal") {
                    FieldBox(placeholder: "python3 路径（留空自动找）", text: $pythonPath)
                    Hint(text: "现在用：\(isStatic ? "/opt/homebrew/bin/python3" : (EvoEnv.python ?? "没找到"))")
                    FieldBox(placeholder: "evo 路径（留空用应用自带的）", text: $evoPath)
                    Hint(text: "现在用：\(isStatic ? "Evo.app/Contents/Resources/evo/bin/evo" : (EvoEnv.evoScript ?? "没找到"))")
                    Hint(text: "心跳超过 \(Int(state.config.heartbeatStaleMinutes)) 分钟算停（全局配置 limits.heartbeat_stale_minutes）")
                }
                .staggeredAppear(4)
                HStack {
                    Button { WindowManager.shared.showSetup() } label: { Label("打开首次设置向导", systemImage: "wand.and.stars") }
                        .buttonStyle(BouncyStyle(kind: .primary))
                    Spacer()
                }
                .staggeredAppear(5)
            }
            .padding(20)
        }
        .frame(width: 520)
        .frame(minHeight: isStatic || embedded ? nil : 520)
        .background(embedded ? Color.clear : Theme.bg)
    }

    private var quietText: String {
        guard let q = state.config.quietHours else { return "免打扰：关（全局配置 notify.quiet_hours 为空）" }
        return "免打扰 \(q.start)–\(q.end)（\(q.tz)）：这段时间不弹，结束后补发。改全局配置 notify.quiet_hours。"
    }

    private func setLoginItem(_ on: Bool) {
        do {
            if on { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
            loginError = nil
        } catch {
            loginError = "没改成：\(error.localizedDescription)（先把 Evo.app 放进「应用程序」再试）"
        }
        loginItem = SMAppService.mainApp.status == .enabled
    }
}

// MARK: - 首次设置向导

@MainActor
final class SetupModel: ObservableObject {
    struct Check: Identifiable {
        let id: String
        var ok: Bool?
        var detail: String
        var hint: String
        var required: Bool
    }

    @Published var checks: [Check] = []
    @Published var output = ""
    @Published var running: String?
    @Published var link = false
    @Published var step = 0            // 0 检查环境 → 1 安装常驻 → 2 完成
    var preset = false                 // 截图用：不真的去检查

    init() {}
    init(preset checks: [Check], step: Int = 0, output: String = "") {
        self.checks = checks; self.step = step; self.output = output; preset = true
    }

    var requiredOK: Bool { !checks.isEmpty && checks.allSatisfy { !$0.required || $0.ok == true } }

    func runChecks() async {
        if preset { return }
        running = "检查中…"
        var c: [Check] = []
        if let py = EvoEnv.python {
            let v = await Shell.run(py, ["--version"], timeout: 10)
            c.append(Check(id: "python3", ok: v.ok, detail: "\(py)  \((v.out + v.err).trimmingCharacters(in: .whitespacesAndNewlines))",
                           hint: "brew install python", required: true))
        } else {
            c.append(Check(id: "python3", ok: false, detail: "没找到", hint: "brew install python，或在设置里填路径", required: true))
        }
        for (name, hint, req) in [("git", "xcode-select --install", true),
                                  ("orca", "装 Orca 后在 设置 → CLI 安装命令行", true),
                                  ("gh", "brew install gh && gh auth login（没有也能跑，少 GitHub 入口）", false)] {
            let p = await Shell.which(name)
            c.append(Check(id: name, ok: p != nil, detail: p ?? "没找到", hint: hint, required: req))
        }
        let cfg = EvoEnv.loadConfig()
        let magpie = cfg.magpieURL.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/v1/models"
        let mOK = await Self.reachable(magpie)
        c.append(Check(id: "magpie", ok: mOK, detail: magpie, hint: "在 Mac mini 上启动 magpie 网关（岗位用到模型时才需要）", required: false))
        let root = EvoEnv.evoRoot.path
        c.append(Check(id: "~/.evoloop", ok: FileManager.default.fileExists(atPath: root), detail: root,
                       hint: "点下面「安装」会建好全局配置", required: true))
        c.append(Check(id: "launchd 常驻", ok: Launchd.installed, detail: Launchd.plist,
                       hint: "点下面「安装」会装 com.evoloop.autopilot", required: false))
        checks = c
        running = nil
    }

    nonisolated static func reachable(_ s: String) async -> Bool {
        guard let u = URL(string: s) else { return false }
        do {
            let (_, r) = try await URLSession.shared.data(for: URLRequest(url: u, timeoutInterval: 3))
            return (r as? HTTPURLResponse).map { (200..<500).contains($0.statusCode) } ?? false
        } catch { return false }
    }

    func install(apply: Bool) async {
        guard let sh = EvoEnv.installScript else { output = "找不到 install.sh（应用包里缺 Resources/evo/install.sh）"; return }
        running = apply ? "安装中…" : "检查中…"
        var args = [sh]
        if apply { args.append("--apply"); if link { args.append("--link") } }
        output = "$ bash \(args.joined(separator: " "))\n"
        let r = await Shell.run("/bin/bash", args, timeout: 600)
        output += r.out + (r.err.isEmpty ? "" : "\n" + r.err) + "\n（退出码 \(r.code)）"
        running = nil
        await runChecks()
        AppState.shared.refresh()
    }
}

struct SetupView: View {
    @StateObject private var model: SetupModel
    @Environment(\.evoStatic) private var isStatic

    @MainActor init(model: SetupModel? = nil) { let model = model ?? SetupModel()
        _model = StateObject(wrappedValue: model) }

    var body: some View {
        MaybeScroll(maxHeight: 2000) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .center, spacing: 14) {
                    MateView(emotion: model.running != nil ? .searching : (model.requiredOK ? .happy : .curious), size: 64, followMouse: true)
                    VStack(alignment: .leading, spacing: 6) {
                        Text("欢迎使用 Evo").font(Theme.title(24)).foregroundStyle(Theme.textPrimary).accessibilityAddTraits(.isHeader)
                        SpeechBubble(text: bubble)
                    }
                    Spacer(minLength: 0)
                }
                .staggeredAppear(0)
                StepCard(index: 1, title: "检查这台 Mac", current: model.step == 0, done: model.step > 0) {
                    VStack(spacing: 0) {
                        ForEach(Array(model.checks.enumerated()), id: \.element.id) { i, c in
                            if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 34) }
                            CheckRow(check: c, spinning: model.running != nil && c.ok == nil)
                        }
                        if model.checks.isEmpty {
                            HStack(spacing: 8) { Spinner(); Text("检查中…").foregroundStyle(Theme.textSecondary) }.padding(10)
                        }
                    }
                    HStack {
                        Button { Task { await model.runChecks() } } label: { Label("重新检查", systemImage: "arrow.clockwise") }
                            .buttonStyle(BouncyStyle(kind: .secondary, compact: true))
                        Spacer()
                        Button("下一步") { withAnimation(Motion.or(Motion.pop)) { model.step = 1 } }
                            .buttonStyle(BouncyStyle(kind: .primary))
                    }
                }
                .staggeredAppear(1)
                StepCard(index: 2, title: "装好常驻（launchd）", current: model.step == 1, done: model.step > 1) {
                    Hint(text: "「安装」会把常驻指向本应用里的 evo：先把 Evo.app 拖进「应用程序」再装，之后别挪位置。", color: Theme.warning)
                    Toggle("同时放 ~/.local/bin/evo 软链", isOn: $model.link).toggleStyle(PillToggleStyle())
                    ScrollOrText(text: model.output.isEmpty ? "（install.sh 的输出显示在这里）" : model.output)
                    HStack(spacing: 8) {
                        Button("只检查") { Task { await model.install(apply: false) } }
                            .buttonStyle(BouncyStyle(kind: .secondary, compact: true))
                        if let r = model.running { Spinner(); Text(r).font(Theme.caption()).foregroundStyle(Theme.textSecondary) }
                        Spacer()
                        Button("安装（--apply）") {
                            Task { await model.install(apply: true); withAnimation(Motion.or(Motion.pop)) { model.step = 2 } }
                        }
                        .buttonStyle(BouncyStyle(kind: .primary))
                    }
                    .disabled(model.running != nil)
                }
                .staggeredAppear(2)
                StepCard(index: 3, title: "开始用", current: model.step == 2, done: false) {
                    Hint(text: "点菜单栏上的小陶就能看到等你处理的事；⌘K 打开命令面板。")
                    HStack {
                        Spacer()
                        Button("开始使用") {
                            UserDefaults.standard.set(true, forKey: "setupDone")
                            WindowManager.shared.close("setup")
                        }
                        .buttonStyle(BouncyStyle(kind: .primary))
                        .keyboardShortcut(.defaultAction)
                    }
                }
                .staggeredAppear(3)
            }
            .padding(22)
        }
        .frame(width: 620)
        .frame(minHeight: isStatic ? nil : 600)
        .background(Theme.bg)
        .task { await model.runChecks() }
    }

    private var bubble: String {
        if model.running != nil { return "稍等，我在看…" }
        if model.checks.isEmpty { return "嗨，我是小陶。先看看这台 Mac 的环境" }
        let miss = model.checks.filter { $0.required && $0.ok != true }.map(\.id)
        if !miss.isEmpty { return "还差 \(miss.joined(separator: "、"))，装好再点重新检查" }
        return "必需的都齐了！可选项缺了只是少点功能"
    }
}

/// 一步：左边圆圈序号（做完变 ✓），当前这步展开、其余收起变淡。
struct StepCard<Content: View>: View {
    let index: Int
    let title: String
    let current: Bool
    let done: Bool
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                ZStack {
                    Circle().fill(done ? Theme.success : (current ? Theme.accent : Theme.surfaceSunk)).frame(width: 24, height: 24)
                    if done { Image(systemName: "checkmark").font(.system(size: 11, weight: .bold)).foregroundStyle(.white) }
                    else { Text("\(index)").font(.system(size: 12, weight: .bold, design: .rounded)).foregroundStyle(current ? .white : Theme.textSecondary) }
                }
                Text(title).font(Theme.title(15)).foregroundStyle(current ? Theme.textPrimary : Theme.textSecondary)
                Spacer()
            }
            if current { content().transition(.scale(scale: 0.96, anchor: .top).combined(with: .opacity)) }
        }
        .padding(14)
        .card(highlighted: current)
        .opacity(current || done ? 1 : 0.7)
        .animation(Motion.or(Motion.softSpring), value: current)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("第 \(index) 步：\(title)\(done ? "，已完成" : (current ? "，进行中" : ""))")
    }
}

struct CheckRow: View {
    let check: SetupModel.Check
    let spinning: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Group {
                if spinning { Spinner(size: 14) }
                else if check.ok == true { badge("checkmark", Theme.success) }
                else if check.required { badge("xmark", Theme.danger) }
                else { badge("exclamationmark", Theme.warning) }
            }
            .frame(width: 22, height: 22)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(check.id).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.textPrimary)
                    if !check.required { Text("可选").font(.system(size: 10)).foregroundStyle(Theme.textSecondary)
                        .padding(.horizontal, 5).padding(.vertical, 1).background(Capsule().fill(Theme.surfaceSunk)) }
                }
                Text(check.detail).font(.system(size: 11, design: .monospaced)).foregroundStyle(Theme.textSecondary)
                    .lineLimit(1).truncationMode(.middle).textSelection(.enabled)
                if check.ok != true { Text(check.hint).font(Theme.caption()).foregroundStyle(Theme.textPrimary.opacity(0.8)) }
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 8)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(check.id)：\(check.ok == true ? "通过" : (check.required ? "缺少，必需" : "缺少，可选"))。\(check.ok == true ? check.detail : check.hint)")
    }

    private func badge(_ symbol: String, _ c: Color) -> some View {
        ZStack {
            Circle().fill(c.opacity(0.15))
            Image(systemName: symbol).font(.system(size: 10, weight: .bold)).foregroundStyle(c)
        }
    }
}

struct ScrollOrText: View {
    let text: String
    @Environment(\.evoStatic) private var isStatic
    var body: some View {
        let t = Text(text).font(.system(size: 11, design: .monospaced)).foregroundStyle(Theme.textSecondary)
            .frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled).padding(10)
        Group {
            if isStatic { t } else { ScrollView { t }.frame(height: 130) }
        }
        .background(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).fill(Theme.surfaceSunk))
    }
}
#endif
