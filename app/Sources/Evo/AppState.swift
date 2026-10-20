#if os(macOS)
import Foundation
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

    func start() {
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
        if Launchd.installed { loopRunning = await Launchd.isLoaded() } else { loopRunning = nil }
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
