#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

/// `Evo --snapshots <目录>`：用假数据把主要界面画成 PNG（浅色 + 深色，2 倍），画完退出。
/// CI（macos-14）上 `make snapshots` 跑它，图上传成构件；也放进 app/docs/screenshots/。
@MainActor
enum Snapshots {
    static var requestedDir: String? {
        let a = CommandLine.arguments
        guard let i = a.firstIndex(of: "--snapshots") else { return nil }
        return i + 1 < a.count ? a[i + 1] : "build/snapshots"
    }

    static func iso(_ minutesAgo: Double) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.string(from: Date().addingTimeInterval(-minutesAgo * 60))
    }

    static func doc(_ json: String) -> StatusDoc { try! StatusDoc.decode(json) }

    static var sampleSnaps: [ProjectSnapshot] {
        let tb = doc("""
        {"project":"TB","name":"土布","last_tick":"\(iso(1))","count":{"building":2,"built":1,"merged":2},"stuck":0,
         "roles":[{"role":"build","name":"施工","status":"busy","label":"忙"},{"role":"verify","name":"验收","status":"idle","label":"闲"}],
         "gates":[{"id":"gate_12","question":"看效果：注册页按钮改成陶土色","options":["通过","打回"],"kind":"look","item":"TB-UX-003","waiting_since":"\(iso(50))"},
                  {"id":"gate_13","question":"做不做：订单导出 PDF","options":["做","不做"],"kind":"do","item":"TB-FEAT-004","waiting_since":"\(iso(190))"}],
         "items":[{"key":"TB-FIX-010","title":"修复验证码不刷新","state":"已合并·可收菜","raw":"merged"},
                  {"key":"TB-UX-002","title":"首页卡片加阴影","state":"已合并·可收菜","raw":"merged"}]}
        """)
        let ev = doc("""
        {"project":"EV","name":"Evo 应用","last_tick":"\(iso(3))","count":{"building":1,"verifying":1},"stuck":0,"no_live_path":[{"key":"EV-3","reason":"dep_dead"}],"stale":[{"key":"EV-5","hours":7}],
         "gates":[{"id":"g8","question":"上线这 2 件？菜单栏弹窗、命令面板","options":["上线","再等等"],"kind":"ship","waiting_since":"\(iso(8))"}],"items":[]}
        """)
        let ab = doc("""
        {"project":"AB","name":"副业","last_tick":"\(iso(4))","count":{"queued":1},"stuck":0,"gates":[],"items":[]}
        """)
        return [ProjectSnapshot(code: "TB", doc: tb), ProjectSnapshot(code: "EV", doc: ev), ProjectSnapshot(code: "AB", doc: ab)]
    }

    /// v0.7.0 截图用的功能列表（和 evo feature list --json 同形；team 关着）。
    static var sampleFeatures: FeatureList {
        let caps = SettingsSchema(fields: [
            SettingField(key: "decider_reworks", kind: .integer, title: "决策岗指导返工最多几次", description: "到了转老板「继续 / 不做」；0 = 不限", minimum: 0, maximum: 50, defaultValue: .number(2)),
            SettingField(key: "item_hard_runs", kind: .integer, title: "一件最多派工几次", description: "施工 + 验收都算；到了暂停等老板；0 = 不限", minimum: 0, maximum: 1000, defaultValue: .number(12)),
            SettingField(key: "item_hard_hours", kind: .number, title: "一件工人最多累计几小时", description: "到了暂停等老板；0 = 不限", minimum: 0, maximum: 1000, defaultValue: .number(6)),
        ])
        let deploy = SettingsSchema(fields: [
            SettingField(key: "auto_ship_gate", kind: .boolean, title: "每天自动攒一批建上线闸门", defaultValue: .bool(true)),
            SettingField(key: "ship_gate_at", kind: .string, title: "几点之后自动收菜", description: "24 小时制 HH:MM（上海时间）", defaultValue: .string("08:20")),
        ])
        return FeatureList(features: [
            FeatureInfo(id: "deploy", name: "上线", sub: "老板点「上线」后跑 deploy_cmd；每天早上自动攒一批建上线闸门", essential: true, settings: deploy),
            FeatureInfo(id: "item-caps", name: "每件上限", sub: "返工 / 派工次数 / 累计小时到了就暂停，问老板继续还是不做", essential: true, settings: caps,
                        config: ["item_hard_runs": .number(20)]),
            FeatureInfo(id: "github", name: "GitHub 来源", sub: "拉 issue 成件、回写评论、关 issue", essential: true, inUse: 2, inUseText: "2 个项目连着 GitHub"),
            FeatureInfo(id: "notify-telegram", name: "Telegram 推送", sub: "闸门和停摆推到 Telegram；关掉不影响别的渠道"),
            FeatureInfo(id: "plugins", name: "第三方插件", sub: "~/.evoloop/plugins 的外部插件（接口 evo_api 1.0）", parts: [FeaturePart(slot: "page", key: "plugins")]),
            FeatureInfo(id: "team", name: "团队 / 模型协调", sub: "你关了它", state: "off", enabled: false, essential: true, parts: [FeaturePart(slot: "page", key: "team")]),
        ])
    }

    static func beats(_ snaps: [ProjectSnapshot], stale: String? = nil) -> [HeartbeatStatus] {
        snaps.map { s in
            s.code == stale ? HeartbeatStatus(project: s.code, ageMinutes: 42, level: .stale)
                            : HeartbeatStatus.of(project: s.code, lastTick: s.doc?.lastTick, staleMinutes: 10)
        }
    }

    /// 截图里的「现在」：今天 21:10（晚上好）。
    static var evening: Date {
        Calendar.current.date(bySettingHour: 21, minute: 10, second: 0, of: Date()) ?? Date()
    }

    static func run(dir: String) async {
        let out = URL(fileURLWithPath: dir)
        try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
        // ImageRenderer 画不了 WKWebView：先在屏幕外把角色的各个表情拍成静态图，界面里换成图片
        let needed = Array(Set(MateSheet.shown + [MateEmotion.listening, .happy, .curious, .error, .replying, .searching, .sleep]))
        for c in MateCharacter.allCases {
            await MateSnapshotCache.shared.prepare(c, c == MateAssets.character ? needed : MateSheet.shown)
        }
        print("角色静态图：\(MateCharacter.allCases.map { c in "\(c.label) \(needed.filter { MateSnapshotCache.shared.image(c, $0) != nil }.count)" }.joined(separator: "、"))")
        let snaps = sampleSnaps
        let quiet = [snaps[2]]

        for dark in [false, true] {
            let sfx = dark ? "dark" : "light"
            // 1 主弹窗：有闸门
            let main = AppState.preview(snaps: snaps, beats: beats(snaps))
            render(MainPopover(state: main, now: evening), width: MainPopover.width, dark: dark, name: "popover-\(sfx)", out: out)
            // 2 一切顺利
            let calm = AppState.preview(snaps: quiet, beats: beats(quiet))
            render(MainPopover(state: calm, now: evening), width: MainPopover.width, dark: dark, name: "popover-empty-\(sfx)", out: out)
            // 3 命令面板
            let pm = PaletteModel(); pm.query = ""
            render(PaletteView(state: main, model: pm), width: 520, dark: dark, name: "palette-\(sfx)", out: out)
            // 4 设置
            render(SettingsView(state: main), width: 520, dark: dark, name: "settings-\(sfx)", out: out)
            // 4b 功能开关 + 自动表单（v0.7.0）：team 关着、item-caps 展开、填了超范围的数
            let fs = AppState.preview(snaps: snaps, beats: beats(snaps))
            fs.features = sampleFeatures
            fs.expandedFeature = "item-caps"
            if let f = sampleFeatures.feature("item-caps"), let fld = f.settings?.fields.first(where: { $0.key == "item_hard_runs" }) {
                var fm = FeatureForm(f); fm.edit(fld.key, "2000"); _ = fm.commit(fld)
                fs.featureForms[f.id] = fm
            }
            render(FeatureSettingsCard(state: fs).padding(20), width: 560, dark: dark, name: "features-\(sfx)", out: out)
            // 4c 页错误边界（v0.7.0）
            render(PageErrorCard(error: PageError(message: "evo log 读状态文件失败：state.json 被锁住（演示）", title: "TB-UX-003 的时间线读不出来"),
                                 back: {}) {}.padding(20), width: 680, dark: dark, name: "page-error-\(sfx)", out: out)
            // 5 向导
            render(SetupView(model: sampleSetup()), width: 620, dark: dark, name: "wizard-\(sfx)", out: out)
            // 5b 团队页（v0.4.0）：岗位卡片 + 各项目跟随全局 / 本项目专用 + 确认卡
            let tm = AppState.preview(snaps: snaps, beats: beats(snaps))
            tm.team = sampleTeam
            render(VStack(alignment: .leading, spacing: 14) {
                       TeamPane(state: tm, width: 900)
                       TeamConfirmCard(state: tm, change: TeamChange(role: "verify", value: "group/evo-verify"))
                   }.padding(24),
                   width: 948, dark: dark, name: "team-\(sfx)", out: out)
            // 5c 插件（v0.6.0）：插件页（通用卡片渲染）+ 输入框 /hello 的回话卡片 + 设置里的开关 + 接口版本横幅 + 报错态
            let pg = AppState.preview(snaps: snaps, beats: beats(snaps))
            pg.plugins = samplePlugins
            let ref = PluginPageRef(plugin: "example-hello", id: "hello", title: "你好", icon: "hand.wave")
            if let c = try? PluginCard.decode(samplePluginCardJSON) { pg.pluginPages[ref.key] = .loaded(c) }
            let reply = try? PluginCard.decode(#"{"schema_version":1,"title":"你好，老板！","blocks":[{"type":"text","text":"这是 /hello 的回话：插件收到的参数是「老板」，当前项目 TB。"},{"type":"buttons","buttons":[{"label":"掷骰子","action":"roll","style":"primary"}]}]}"#)
            render(VStack(alignment: .leading, spacing: 18) {
                       ContractBanner(text: ContractCheck.evoNewer(found: 2, supported: 1, command: .status).message ?? "")
                       PluginPane(state: pg, ref: ref)
                       ChatSection(lines: [.init(text: "/hello 老板", mine: true), .init(text: "你好，老板！", mine: false, card: reply)],
                                   mood: .idle, liveEmotion: .happy)
                       CardStateView(state: .failed("插件超时（20 秒），已停掉"), onRetry: {})
                       PluginSettingsCard(state: pg).frame(width: 520)
                   }.padding(24),
                   width: 900, dark: dark, name: "plugin-\(sfx)", out: out)
            // 6 角色表情（调度球 / 云宝 / 亮亮）+ 菜单栏小脸
            render(VStack(spacing: 0) {
                       ForEach(MateCharacter.allCases, id: \.self) { c in MateSheetStatic(character: c) }
                       MascotSheet()
                   },
                   width: 640, dark: dark, name: "mascot-\(sfx)", out: out)
        }
        // 7 暂停（深色）、心跳过期（浅色）、对话 + 收菜（浅色）
        let paused = AppState.preview(snaps: snaps, beats: beats(snaps), loopRunning: false)
        render(MainPopover(state: paused, now: evening), width: MainPopover.width, dark: true, name: "popover-paused-dark", out: out)
        let stale = AppState.preview(snaps: snaps, beats: beats(snaps, stale: "TB"))
        render(MainPopover(state: stale, now: evening), width: MainPopover.width, dark: false, name: "popover-stale-light", out: out)
        let chat = AppState.preview(snaps: quiet + [snaps[0]], beats: beats(snaps),
                                    chat: [.init(text: "注册页在手机上按钮太挤了", mine: true),
                                           .init(text: "收到！记成 issue #42，决策岗会分拣", mine: false)])
        chat.showHarvest = true
        chat.hiddenGates = ["TB/gate_13"]
        render(MainPopover(state: chat, now: evening), width: MainPopover.width, dark: false, name: "popover-chat-light", out: out)
        MainWindowController.shared.window?.close()
        print("snapshots → \(out.path)")
    }

    /// 插件样例（和 kit/plugins/example-hello 的输出同形）。
    static var samplePlugins: PluginList? {
        try? PluginList.decode(#"""
        {"schema_version": 1, "evo_api": "1.0", "plugins_dir": "~/.evoloop/plugins", "plugins": [
         {"name": "example-hello", "version": "0.1.0", "description": "示例插件：侧栏页「你好」、输入框命令 /hello、通知渠道（写本地文件）、件详情页按钮",
          "evo_api": "^1", "enabled": true, "valid": true, "compatible": true, "active": true, "errors": [],
          "contributes": {"sidebar_pages": [{"id": "hello", "title": "你好", "icon": "hand.wave"}],
                          "composer_commands": [{"id": "hello", "name": "hello", "title": "打个招呼", "usage": "/hello 名字"}],
                          "notify_channels": [{"id": "hello-log", "title": "写到本地文件", "events": "push"}],
                          "item_actions": [{"id": "hello-item", "title": "跟这件打招呼", "icon": "hand.wave"}]}},
         {"name": "future-thing", "version": "2.0.0", "description": "要 evo_api ^2 的插件", "evo_api": "^2", "enabled": false,
          "valid": true, "compatible": false, "active": false, "errors": [],
          "contributes": {"sidebar_pages": [], "composer_commands": [], "notify_channels": [], "item_actions": []}}]}
        """#)
    }

    static let samplePluginCardJSON = #"""
    {"schema_version": 1, "title": "你好，老板 👋", "subtitle": "example-hello 0.1.0", "blocks": [
     {"type": "text", "text": "🎲 掷出了 4", "style": "title", "tone": "accent"},
     {"type": "text", "text": "这页是 example-hello 插件画的：插件只输出一段卡片 JSON，App 用通用渲染器画出来。现在 21:10。"},
     {"type": "list", "items": [
       {"title": "侧栏页", "subtitle": "就是这一页", "symbol": "sidebar.left", "badge": "sidebar_pages"},
       {"title": "输入框命令", "subtitle": "在下面输入框打 /hello 老板", "symbol": "text.cursor", "badge": "composer_commands"},
       {"title": "通知渠道", "subtitle": "要推的事会追加到插件数据目录的 notify.log", "symbol": "bell", "badge": "notify_channels"},
       {"title": "件按钮", "subtitle": "件详情页多一个「跟这件打招呼」", "symbol": "hand.wave", "badge": "item_actions"}]},
     {"type": "table", "columns": ["项", "值"], "rows": [["打开次数", 3], ["插件接口", "1.0"], ["数据目录", "example-hello"]]},
     {"type": "buttons", "buttons": [{"label": "再打个招呼", "action": "again", "style": "primary"}, {"label": "掷骰子", "action": "roll", "payload": {"sides": 6}}]},
     {"type": "text", "text": "按钮点了会再跑一次插件命令（request.action = 按钮的 action）。", "style": "caption"}]}
    """#

    /// 团队页样例（和 Tests/EvoCoreTests/Fixtures/team.json、scripts/demo/team.json 同一份）。
    static var sampleTeam: TeamDoc? { try? TeamDoc.decode(teamJSON) }

    static let teamJSON = """
{"schema_version": 1, "generated_at": "2026-10-21T09:12:00+08:00", "project": null, "health_at": "2026-10-21T09:10:00+08:00",
 "magpie": {"ok": true, "url": "http://127.0.0.1:3425/v1/models",
            "models": ["group/evo-build", "group/evo-verify", "glm-5", "deepseek-v4", "kimi-k2", "qwen3-coder-plus"],
            "groups": ["group/evo-build", "group/evo-verify"], "retired": []},
 "clis": {"claude": {"installed": true, "path": "/opt/homebrew/bin/claude", "logged_in": true},
          "codex": {"installed": true, "path": "/opt/homebrew/bin/codex", "logged_in": true},
          "dsh": {"installed": true, "path": "/Users/boss/.local/bin/dsh", "logged_in": null},
          "pi": {"installed": false, "path": null, "logged_in": null}},
 "cards": [
  {"role": "build", "name": "施工", "tool": "codex", "via": "cli", "models": ["gpt-5-codex"], "thinking": "medium", "account": "codex",
   "duty": "按任务书写代码和测试，交 JSON 报告", "configured": true,
   "fallback": {"tool": "dsh", "via": "magpie", "models": ["group/evo-build"], "thinking": "medium", "account": "dsh"},
   "status": {"code": "fallback", "label": "用备用中", "why": "额度满", "until": "2026-10-21T13:00:00+08:00"},
   "warnings": [],
   "stats": {"gpt-5-codex": {"items": 14, "runs": 19, "merged": 12, "verify_reject_rate": 0.21, "rework_per_item": 0.36, "look_reject_rate": 0.1, "minutes_per_item": 22.4, "no_live_path": 1},
             "group/evo-build": {"items": 6, "runs": 11, "merged": 5, "verify_reject_rate": 0.45, "rework_per_item": 0.83, "look_reject_rate": 0.2, "minutes_per_item": 31.0, "no_live_path": 0}},
   "recommendation": {"text": "gpt-5-codex 目前成绩最好（或差别不大），不用换。", "switch_to": null},
   "usage_week": {"runs": 19, "minutes": 425.5}, "scope": "global"},
  {"role": "verify", "name": "验收", "tool": "claude", "via": "cli", "models": ["claude-sonnet-4.5"], "thinking": "high", "account": "claude",
   "duty": "换一个模型从头核对：跑命令、看证据、不过就打回", "configured": true,
   "fallback": {"tool": "dsh", "via": "magpie", "models": ["group/evo-verify"], "thinking": "high", "account": "dsh"},
   "status": {"code": "ok", "label": "可用"},
   "warnings": [],
   "stats": {"claude-sonnet-4.5": {"runs": 21, "passes": 15, "rejects": 6, "escaped": 3, "escape_rate": 0.2, "minutes_per_run": 6.5},
             "group/evo-verify": {"runs": 9, "passes": 7, "rejects": 2, "escaped": 0, "escape_rate": 0.0, "minutes_per_run": 8.1}},
   "recommendation": {"text": "建议验收换成 group/evo-verify：它放过去又被你看效果打回的只有 0%，现在的 claude-sonnet-4.5 是 20%（各验了 9 / 21 次）。点「换成 group/evo-verify」才生效。", "switch_to": "group/evo-verify"},
   "usage_week": {"runs": 23, "minutes": 160.0}, "scope": "global"},
  {"role": "decide", "name": "决策", "tool": "claude", "via": "cli", "models": ["claude-opus-4.1"], "thinking": "high", "account": "claude",
   "duty": "只做技术决定（重试、返工、拆分、问老板）；四类红线回老板", "configured": true, "fallback": null,
   "status": {"code": "ok", "label": "可用"}, "warnings": [], "stats": {},
   "recommendation": {"text": "决策岗不比成绩：用最强的模型。", "switch_to": null},
   "usage_week": {"runs": 23, "minutes": 160.0}, "scope": "global"}],
 "suggestions": [{"model": "qwen3-coder-plus", "at": "2026-10-21T08:40:00+08:00"}],
 "usage_week": {"codex": {"runs": 19, "minutes": 425.5}, "claude": {"runs": 23, "minutes": 160.0}, "dsh": {"runs": 4, "minutes": 88.0}},
 "thinking_levels": ["off", "low", "medium", "high", "max"],
 "projects": [{"code": "TB", "name": "土布", "overrides": {}},
              {"code": "ST", "name": "选股", "overrides": {"build": {"models": ["claude-opus-4.1"], "tool": "claude", "thinking": "max"}}},
              {"code": "EV", "name": "Evo 应用", "overrides": {"verify": {"models": ["kimi-k2"], "trial": {"model": "kimi-k2", "base": ["claude-sonnet-4.5"], "items": 5}}}}]}
"""

    static func sampleSetup() -> SetupModel {
        typealias C = SetupModel.Check
        return SetupModel(preset: [
            C(id: "python3", ok: true, detail: "/opt/homebrew/bin/python3  Python 3.12.6", hint: "", required: true),
            C(id: "git", ok: true, detail: "/usr/bin/git", hint: "", required: true),
            C(id: "orca", ok: true, detail: "/usr/local/bin/orca", hint: "", required: true),
            C(id: "gh", ok: false, detail: "没找到", hint: "brew install gh && gh auth login（没有也能跑，少 GitHub 入口）", required: false),
            C(id: "magpie", ok: true, detail: "http://127.0.0.1:3425/v1/models", hint: "", required: false),
            C(id: "~/.evoloop", ok: true, detail: "/Users/you/.evoloop", hint: "", required: true),
            C(id: "launchd 常驻", ok: false, detail: "~/Library/LaunchAgents/com.evoloop.autopilot.plist", hint: "点下面「安装」会装 com.evoloop.autopilot", required: false),
        ])
    }

    /// 画一张：ImageRenderer，2 倍像素。
    static func render<V: View>(_ view: V, width: CGFloat, dark: Bool, name: String, out: URL) {
        let ap = NSAppearance(named: dark ? .darkAqua : .aqua)!
        NSApp.appearance = ap
        let root = view
            .environment(\.evoStatic, true)
            .environment(\.colorScheme, dark ? .dark : .light)
            .frame(width: width)
            .fixedSize(horizontal: false, vertical: true)
            .background(Theme.bg)
        // 离屏 NSHostingView + cacheDisplay 试过：会糊、胶囊边被裁，Menu 画成黄块；ImageRenderer 是真矢量 2 倍，干净。
        let r = ImageRenderer(content: root)
        r.scale = 2
        if let cg = r.cgImage {
            let rep = NSBitmapImageRep(cgImage: cg)
            if let png = rep.representation(using: .png, properties: [:]) {
                try? png.write(to: out.appendingPathComponent("\(name).png"))
                print("  \(name)  \(cg.width / 2)×\(cg.height / 2)")
            }
        }
    }
}

/// 截图用：某个角色的表情表（不依赖 @AppStorage 当前角色）。
struct MateSheetStatic: View {
    let character: MateCharacter
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Text("\(character.label)").font(Theme.title(16)).foregroundStyle(Theme.textPrimary)
                Text(character.licensable ? "mood-mates · 可买商业许可" : "emotion-ball · 只许自用（默认）")
                    .font(Theme.caption()).foregroundStyle(Theme.textSecondary)
            }
            HStack(alignment: .bottom, spacing: 10) {
                ForEach(MateSheet.shown, id: \.self) { e in
                    VStack(spacing: 4) {
                        MateStill(character: character, emotion: e, size: 64).frame(width: 64, height: 64)
                        Text("\(e.name) \(e.id)").font(Theme.caption(10.5)).foregroundStyle(Theme.textSecondary)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(.horizontal, 20).padding(.top, 16)
    }
}

/// 吉祥物各心情一字排开 + 菜单栏小脸。
struct MascotSheet: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("菜单栏小脸（单色 template，沿用原来的矢量小脸）").font(Theme.title(13)).foregroundStyle(Theme.textPrimary)
            HStack(spacing: 14) {
                ForEach(MascotMood.allCases, id: \.self) { m in
                    HStack(spacing: 4) {
                        Image(nsImage: MenuBarIcon.image(m))
                            .foregroundStyle(Theme.textPrimary)
                        if m == .waiting { Text("2").font(.system(size: 13)).foregroundStyle(Theme.textPrimary) }
                    }
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(RoundedRectangle(cornerRadius: 5).fill(Theme.surfaceSunk))
                }
            }
        }
        .padding(20)
    }

    static func name(_ m: MascotMood) -> String {
        switch m {
        case .idle: return "顺利 · 眨眼"
        case .working: return "干活 · 东张西望"
        case .waiting: return "等你 · 挑眉弹弹"
        case .worried: return "卡住 · 担心"
        case .sleepy: return "暂停 · 睡觉"
        }
    }
}
#endif
