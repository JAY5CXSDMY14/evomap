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
        w.contentViewController = NSHostingController(rootView: content())
        w.setContentSize(size)
        w.center()
        windows[id] = w
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func close(_ id: String) { windows[id]?.close() }

    func showSettings() {
        show("settings", title: "Evo 设置", size: NSSize(width: 520, height: 520)) { SettingsView(state: AppState.shared) }
    }

    func showSetup() {
        show("setup", title: "欢迎使用 Evo", size: NSSize(width: 640, height: 620)) { SetupView() }
    }
}

// MARK: - 设置

struct SettingsView: View {
    @ObservedObject var state: AppState
    @AppStorage("panelPort") private var panelPort = 8765
    @AppStorage("pythonPath") private var pythonPath = ""
    @AppStorage("evoPath") private var evoPath = ""
    @AppStorage("notificationsEnabled") private var notificationsEnabled = true
    @State private var loginItem = SMAppService.mainApp.status == .enabled
    @State private var loginError: String?

    var body: some View {
        Form {
            Section("开机") {
                Toggle("登录时自动打开 Evo", isOn: $loginItem)
                    .onChange(of: loginItem) { on in setLoginItem(on) }
                if SMAppService.mainApp.status == .requiresApproval {
                    HStack {
                        Text("需要在系统设置里批准").foregroundStyle(.orange)
                        Button("打开登录项设置") { SMAppService.openSystemSettingsLoginItems() }
                    }
                }
                if let loginError { Text(loginError).foregroundStyle(.red).font(.caption) }
            }
            Section("通知") {
                Toggle("新闸门、接棒器停了时发原生通知", isOn: $notificationsEnabled)
                Text(quietText).font(.caption).foregroundStyle(.secondary)
                Button("发一条测试通知") { Notifier.shared.test() }
            }
            Section("面板") {
                TextField("端口", value: $panelPort, format: .number.grouping(.never))
                Text("应用会先找这个端口上正在跑的 evo panel，没有就自己起一个（退出 Evo 时一起关）。")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("evo") {
                TextField("python3 路径（留空自动找）", text: $pythonPath)
                Text("现在用：\(EvoEnv.python ?? "没找到")").font(.caption).foregroundStyle(.secondary)
                TextField("evo 路径（留空用应用自带的）", text: $evoPath)
                Text("现在用：\(EvoEnv.evoScript ?? "没找到")").font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                Text("心跳超过 \(Int(state.config.heartbeatStaleMinutes)) 分钟算停（全局配置 limits.heartbeat_stale_minutes）")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section {
                HStack {
                    Button("打开首次设置向导…") { WindowManager.shared.showSetup() }
                    Spacer()
                    Text("Evo \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "dev")")
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .frame(minWidth: 480, minHeight: 460)
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

    func runChecks() async {
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
    @StateObject private var model = SetupModel()

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Evo 是 evo 自动循环的菜单栏外壳").font(.title2).bold()
            Text("先确认这台 Mac 的环境。必需项打勾才能跑；可选项缺了只是少功能。")
                .foregroundStyle(.secondary)
            List(model.checks) { c in
                HStack(alignment: .top) {
                    Image(systemName: c.ok == true ? "checkmark.circle.fill" : (c.required ? "xmark.circle.fill" : "exclamationmark.circle"))
                        .foregroundStyle(c.ok == true ? .green : (c.required ? .red : .orange))
                    VStack(alignment: .leading) {
                        Text(c.id).bold()
                        Text(c.detail).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                        if c.ok != true { Text(c.hint).font(.caption) }
                    }
                }
            }
            .frame(minHeight: 200)
            Text("「安装」会把 launchd 常驻指向本应用里的 evo：请先把 Evo.app 拖进「应用程序」再装，之后别再挪位置。")
                .font(.caption).foregroundStyle(.orange)
            HStack {
                Button("重新检查") { Task { await model.runChecks() } }
                Button("运行 install.sh（只检查）") { Task { await model.install(apply: false) } }
                Button("安装（--apply）") { Task { await model.install(apply: true) } }
                Toggle("同时放 ~/.local/bin/evo 软链", isOn: $model.link)
                Spacer()
                if let r = model.running {
                    ProgressView().controlSize(.small)
                    Text(r)
                }
            }
            .disabled(model.running != nil)
            ScrollView {
                Text(model.output.isEmpty ? "（install.sh 的输出显示在这里）" : model.output)
                    .font(.system(.caption, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            }
            .frame(minHeight: 160)
            .background(Color(nsColor: .textBackgroundColor))
            HStack {
                Spacer()
                Button("完成") {
                    UserDefaults.standard.set(true, forKey: "setupDone")
                    WindowManager.shared.close("setup")
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(minWidth: 600, minHeight: 580)
        .task { await model.runChecks() }
    }
}
#endif
