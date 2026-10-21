#if os(macOS)
import AppKit
import EvoCore

/// 应用的全部状态：每 30 秒跑一遍 `evo projects` + 每个项目 `evo -p X status --json`。
@MainActor
final class AppState: ObservableObject {
    static let shared = AppState()

    @Published var snaps: [ProjectSnapshot] = []
    @Published var beats: [HeartbeatStatus] = []
    @Published var config = GlobalConfig.default
    @Published var lastRefresh: Date?
    @Published var globalError: String?
    @Published var busy: String?           // 正在做的动作（立即 tick、暂停…），菜单里显示
    @Published var lastAction: String?     // 上一个动作的结果
    @Published var loopRunning: Bool?      // nil = 没装常驻 / 还不知道
    @Published var hiddenGates: Set<String> = []   // 刚点了通过/打回、等 evo 回话的卡片，先藏起来（乐观更新）
    @Published var resolving: Set<String> = []
    @Published var focusedProject: String?         // ⌘1…9 选中的项目：卡片只看它，输入框默认发给它
    @Published var chat: [ChatLine] = []           // 输入框发出去的话和 evo 的回话（最近几条）
    @Published var showHarvest = false
    @Published var flash: String?                  // 一句临时提示（通过成功、出错…）
    @Published var windowSelection: SidebarItem? = .inbox   // 主窗口侧栏 / 详情
    @Published var mateReaction: MateReaction?     // 一次性表情（通过 → 任务完成…），几秒后回常态
    @Published var mateCelebrate = 0               // 每 +1 撒一次花
    @Published var logs: [String: ItemLog] = [:]   // 「项目/件号」→ evo log --json
    @Published var logErrors: [String: String] = [:]
    @Published var appearance: String = UserDefaults.standard.string(forKey: "appearance") ?? "system"   // system / light / dark
    @Published var demoReject: (id: String, words: String)?   // 演示模式：让某张卡展开打回输入框并填好原话
    @Published var team: TeamDoc?                  // v0.4.0 团队页：evo team --json
    @Published var teamError: String?
    @Published var pendingTeam: TeamChange?        // 等你点「确认换」的换模型（卡片下拉框 / 输入框「把验收换成 X」）
    var popoverShown = false                       // 菜单栏弹窗开着吗（开主窗口时顺手收起）
    var previewQuiet: Bool?                        // 截图用：固定「是不是免打扰」
    private var reactionToken = UUID()
    private var mergedCounts: [String: Int] = [:]

    struct ChatLine: Identifiable, Equatable {
        let id = UUID()
        var text: String
        var mine: Bool
        var failed = false
    }

    static let pollSeconds: TimeInterval = 30
    private var timer: Timer?
    private var refreshing = false
    private var gates: GateTracker
    private var stale = StaleTracker()

    private init() {
        let d = UserDefaults.standard
        gates = GateTracker(seen: Set(d.stringArray(forKey: "seenGates") ?? []), primed: d.bool(forKey: "gatesPrimed"))
    }

    var badge: Int { Badge.count(snaps) }
    var anyStale: Bool { beats.contains { $0.level == .stale } }
    var codes: [String] { snaps.map(\.code) }

    // MARK: 界面要的数据（映射逻辑在 EvoCore，这里只是拼起来）
    var loopState: LoopState {
        LoopState.derive(globalError: globalError, loaded: lastRefresh != nil, projectCount: snaps.count,
                         loopRunning: loopRunning, anyStale: anyStale)
    }
    var allCards: [GateCard] { GateCard.cards(snaps, hidden: hiddenGates) }
    var cards: [GateCard] { allCards.filter { focusedProject == nil || $0.project == focusedProject } }
    var rows: [ProjectRow] {
        snaps.map { s in ProjectRow(s, beat: beats.first { $0.project == s.code }) }
    }
    var harvest: [HarvestItem] { HarvestItem.list(snaps) }
    var mood: MascotMood {
        let r = rows
        return MascotMood.derive(state: loopState, waiting: allCards.count,
                                 building: r.reduce(0) { $0 + $1.building }, stuck: r.reduce(0) { $0 + $1.stuck }, quiet: quietNow)
    }
    var quietNow: Bool { previewQuiet ?? (config.quietHours?.contains(Date()) ?? false) }
    /// 角色现在的表情：一次性反应优先，其余跟心情走。
    var mateEmotion: MateEmotion { mateReaction?.emotion ?? MateMap.emotion(state: loopState, mood: mood) }
    var stuckEntries: [StuckEntry] { StuckEntry.list(snaps) }
    var totals: (building: Int, verifying: Int, stuck: Int, tooLong: Int) {
        let r = rows
        return (r.reduce(0) { $0 + $1.building }, r.reduce(0) { $0 + $1.verifying }, r.reduce(0) { $0 + $1.stuck }, r.reduce(0) { $0 + $1.tooLong })
    }
    func snapshot(_ code: String) -> ProjectSnapshot? { snaps.first { $0.code == code } }
    func row(_ code: String) -> ProjectRow? { rows.first { $0.code == code } }
    func beat(_ code: String) -> HeartbeatStatus? { beats.first { $0.project == code } }

    // MARK: 表情反应

    func react(_ e: MateEvent) {
        let r = MateMap.reaction(e)
        let token = UUID()
        reactionToken = token
        mateReaction = r
        if r.celebrate { mateCelebrate += 1 }
        DispatchQueue.main.asyncAfter(deadline: .now() + r.seconds) { [weak self] in
            guard let self, self.reactionToken == token else { return }
            self.mateReaction = nil
        }
    }

    // MARK: 外观（深色 / 浅色 / 跟系统）

    func applyAppearance() {
        switch appearance {
        case "dark": NSApp.appearance = NSAppearance(named: .darkAqua)
        case "light": NSApp.appearance = NSAppearance(named: .aqua)
        default: NSApp.appearance = nil
        }
    }

    func setAppearance(_ a: String) {
        appearance = a
        UserDefaults.standard.set(a, forKey: "appearance")
        applyAppearance()
    }

    /// 命令面板「切换深色 / 浅色」：以眼前看到的为准取反。
    func toggleAppearance() {
        let dark = NSApp.effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
        setAppearance(dark ? "light" : "dark")
    }

    // MARK: 件的时间线（evo log <件号> --json）

    func loadLog(project: String, key: String) async {
        let k = "\(project)/\(key)"
        let r = await Shell.evo(["-p", project, "log", key, "--json"], timeout: 60)
        if r.ok, let l = try? ItemLog.decode(r.out) {
            logs[k] = l; logErrors[k] = nil
        } else {
            logErrors[k] = r.ok ? "不是 log JSON：\(r.out.prefix(80))" : (r.tail.isEmpty ? "退出码 \(r.code)" : r.tail)
        }
    }

    /// ⌘1…9：窗口里选中第几个项目（弹窗里是「只看」过滤）。
    func select(digit: Int) {
        guard let c = Shortcuts.project(forDigit: digit, codes: codes) else { return }
        windowSelection = .project(c)
    }
    var speech: String { Speech.status(state: loopState, cards: allCards, rows: rows, beats: beats) }
    var palette: [PaletteEntry] {
        PaletteEntry.build(cards: allCards, rows: rows, paused: loopRunning.map { !$0 })
    }

    func start() {
        react(.launch)
        refresh()
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: Self.pollSeconds, repeats: true) { _ in
            Task { @MainActor in AppState.shared.refresh() }
        }
    }

    func refresh() {
        guard !refreshing else { return }
        refreshing = true
        Task {
            await doRefresh()
            refreshing = false
        }
    }

    private func doRefresh() async {
        config = EvoEnv.loadConfig()
        let list = await Shell.evo(["projects"], timeout: 30)
        guard list.ok else {
            globalError = "evo 跑不起来：\(list.tail)"
            snaps = []; beats = []; lastRefresh = Date()
            return
        }
        globalError = nil
        let codes = ProjectList.parse(list.out)
        var results: [String: ProjectSnapshot] = [:]
        await withTaskGroup(of: ProjectSnapshot.self) { group in
            for code in codes {
                group.addTask {
                    let r = await Shell.evo(["-p", code, "status", "--json"], timeout: 60)
                    guard r.ok else { return ProjectSnapshot(code: code, error: r.tail.isEmpty ? "退出码 \(r.code)" : r.tail) }
                    do { return ProjectSnapshot(code: code, doc: try StatusDoc.decode(r.out)) } catch {
                        return ProjectSnapshot(code: code, error: "不是 status JSON：\(r.out.prefix(80))")
                    }
                }
            }
            for await s in group { results[s.code] = s }
        }
        snaps = codes.compactMap { results[$0] }
        beats = snaps.compactMap { s in
            s.doc.map { HeartbeatStatus.of(project: s.code, lastTick: $0.lastTick, staleMinutes: config.heartbeatStaleMinutes) }
        }
        let quiet = config.quietHours?.contains(Date()) ?? false
        let notes = gates.diff(snaps, quiet: quiet) + stale.diff(beats, quiet: quiet)
        UserDefaults.standard.set(Array(gates.seen), forKey: "seenGates")
        UserDefaults.standard.set(gates.primed, forKey: "gatesPrimed")
        Notifier.shared.post(notes)
        pruneHidden()
        let merged = Dictionary(uniqueKeysWithValues: snaps.compactMap { s in s.doc.map { (s.code, $0.mergedCount) } })
        if MateMap.mergedIncreased(old: mergedCounts, new: merged) { react(.merged) }
        mergedCounts = merged
        if Launchd.installed { loopRunning = await Launchd.isLoaded() } else { loopRunning = nil }
        await loadTeam()
        lastRefresh = Date()
    }

    // MARK: 菜单动作

    /// 立即转一轮：每个项目 `evo -p X tick`（不等 30 秒的常驻节拍）。
    func tickNow() {
        guard busy == nil else { return }
        busy = "正在 tick…"
        Task {
            var bad: [String] = []
            for code in codes {
                let r = await Shell.evo(["-p", code, "tick"], timeout: 300)
                if !r.ok { bad.append("\(code)：\(r.tail.prefix(80))") }
            }
            lastAction = bad.isEmpty ? "tick 完成（\(codes.count) 个项目）" : "tick 出错 " + bad.joined(separator: "；")
            busy = nil
            refresh()
        }
    }

    func togglePause() {
        guard busy == nil, Launchd.installed else { return }
        let pausing = loopRunning != false
        busy = pausing ? "正在暂停…" : "正在恢复…"
        Task {
            let r: RunResult
            if pausing { r = await Launchd.pause() } else { r = await Launchd.resume() }
            lastAction = r.ok ? (pausing ? "循环已暂停（重新登录后会自动恢复）" : "循环已恢复") : "launchctl 出错：\(r.tail)"
            loopRunning = await Launchd.isLoaded()
            busy = nil
        }
    }

    // MARK: 闸门：通过 / 打回

    func approve(_ card: GateCard) { resolve(card, args: card.approveArgs(), verb: card.approveChoice) }

    func reject(_ card: GateCard, words: String?) { resolve(card, args: card.rejectArgs(words: words), verb: card.rejectChoice) }

    private func resolve(_ card: GateCard, args: [String], verb: String) {
        guard !resolving.contains(card.id) else { return }
        resolving.insert(card.id)
        // 先让卡片弹走（界面层带动画），evo 回话失败再弹回来
        hiddenGates.insert(card.id)
        Task {
            let r = await Shell.evo(args, timeout: 120)
            resolving.remove(card.id)
            if r.ok {
                flash = "\(verb)了：\(card.title)"
                react(verb == card.approveChoice ? .approved : .rejected)
                refresh()
            } else {
                hiddenGates.remove(card.id)
                flash = "没成：\(r.tail.prefix(100))"
            }
            clearFlashLater()
        }
    }

    func card(id: String) -> GateCard? { allCards.first { $0.id == id } }

    /// 刷新后 evo 已经不再列出的卡片，从「藏起来」里清掉，免得集合越来越大。
    private func pruneHidden() {
        let live = Set(GateCard.cards(snaps).map(\.id))
        hiddenGates = hiddenGates.filter { live.contains($0) && resolving.contains($0) }
    }

    private func clearFlashLater() {
        let f = flash
        DispatchQueue.main.asyncAfter(deadline: .now() + 4) { [weak self] in
            if self?.flash == f { self?.flash = nil }
        }
    }

    // MARK: 输入框

    func send(mode: ComposerMode, project: String, text: String, look: Bool) -> String? {
        // v0.4.0：「把验收换成 X」不发给 evo feedback，先出确认卡，点了才 evo team set
        if let ch = TeamIntent.parse(text, currentProject: project.isEmpty ? nil : project, projects: codes) {
            chat.append(ChatLine(text: text.trimmingCharacters(in: .whitespacesAndNewlines), mine: true))
            chat.append(ChatLine(text: ch.confirmText(current: team?.card(ch.role)?.models.first) + " 点下面确认。", mine: false))
            trimChat()
            pendingTeam = ch
            react(.replied)
            return nil
        }
        switch Composer.command(mode: mode, project: project, text: text, look: look) {
        case .failure(let e): return e.message
        case .success(let args):
            chat.append(ChatLine(text: text.trimmingCharacters(in: .whitespacesAndNewlines), mine: true))
            trimChat()
            react(.sending)
            Task {
                let r = await Shell.evo(args, timeout: 120)
                chat.append(ChatLine(text: Composer.reply(mode: mode, ok: r.ok, out: r.out, err: r.err), mine: false, failed: !r.ok))
                react(r.ok ? .replied : .replyFailed)
                trimChat()
                if r.ok { refresh() }
            }
            return nil
        }
    }

    func trimChat() { if chat.count > 6 { chat.removeFirst(chat.count - 6) } }

    func focus(digit: Int) {
        guard let c = Shortcuts.project(forDigit: digit, codes: codes) else { return }
        focusedProject = focusedProject == c ? nil : c
    }

    /// 收菜：给每个有已合并件的项目建一个「上线」闸门（evo ship）。
    func shipHarvest() {
        guard busy == nil else { return }
        let projects = Array(Set(harvest.map(\.project))).sorted()
        guard !projects.isEmpty else { return }
        busy = "正在建上线闸门…"
        Task {
            var bad: [String] = []
            for p in projects {
                let r = await Shell.evo(["-p", p, "ship"], timeout: 600)
                if !r.ok { bad.append("\(p)：\(r.tail.prefix(80))") }
            }
            lastAction = bad.isEmpty ? "上线闸门建好了，等你点「上线」" : "收菜出错 " + bad.joined(separator: "；")
            busy = nil
            refresh()
        }
    }

    func perform(_ a: PaletteEntry.Action) {
        switch a {
        case .tick: tickNow()
        case .openPanel: PanelController.shared.open()
        case .togglePause: togglePause()
        case .harvest: showHarvest = true; windowSelection = .inbox; MainWindowController.shared.show()
        case .refresh: refresh()
        case .settings: WindowManager.shared.showSettings()
        case .setup: WindowManager.shared.showSetup()
        case .watchdog: runWatchdog()
        case .approve(let id): if let c = card(id: id) { approve(c) }
        case .reject(let id): if let c = card(id: id) { reject(c, words: nil) }
        case .focusProject(let code): windowSelection = .project(code); MainWindowController.shared.show()
        case .openWindow: MainWindowController.shared.show()
        case .toggleAppearance: toggleAppearance()
        }
    }

    // MARK: 截图 / 预览用的假数据

    static func preview(snaps: [ProjectSnapshot], beats: [HeartbeatStatus] = [], loopRunning: Bool? = true,
                        chat: [ChatLine] = [], error: String? = nil) -> AppState {
        let s = AppState()
        s.snaps = snaps; s.beats = beats; s.loopRunning = loopRunning; s.chat = chat
        s.globalError = error; s.lastRefresh = Date()
        s.previewQuiet = false
        return s
    }

    func runWatchdog() {
        guard busy == nil else { return }
        busy = "看门狗检查中…"
        Task {
            let r = await Shell.evo(["watchdog"], timeout: 60)
            let out = r.out.trimmingCharacters(in: .whitespacesAndNewlines)
            lastAction = r.ok ? (out.isEmpty ? "看门狗：都在转" : "看门狗：\(out)") : "看门狗出错：\(r.tail)"
            busy = nil
            refresh()
        }
    }
}
#endif
