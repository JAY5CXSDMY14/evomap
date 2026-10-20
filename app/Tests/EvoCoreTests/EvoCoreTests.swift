import XCTest
@testable import EvoCore

func fixture(_ name: String) throws -> Data {
    let parts = name.split(separator: ".")
    guard let url = Bundle.module.url(forResource: String(parts[0]), withExtension: String(parts[1]), subdirectory: "Fixtures") else {
        throw NSError(domain: "fixture", code: 1, userInfo: [NSLocalizedDescriptionKey: "没有样例 \(name)"])
    }
    return try Data(contentsOf: url)
}

func snap(_ file: String) throws -> ProjectSnapshot {
    let d = try StatusDoc.decode(fixture(file))
    return ProjectSnapshot(code: d.project, doc: d)
}

final class StatusDocTests: XCTestCase {
    func testDecodeFullSchema1() throws {
        let d = try StatusDoc.decode(fixture("status_tb.json"))
        XCTAssertEqual(d.schemaVersion, 1)
        XCTAssertEqual(d.project, "TB")
        XCTAssertEqual(d.name, "土布")
        XCTAssertEqual(d.pendingCount, 2)
        XCTAssertEqual(d.buildingCount, 1)
        XCTAssertEqual(d.stuck, 1)
        XCTAssertEqual(d.gates[0].id, "gate_12")
        XCTAssertEqual(d.gates[0].kindLabel, "看效果")
        XCTAssertEqual(d.gates[0].options, ["通过", "打回"])
        XCTAssertNil(d.gates[1].waitingSince)
        XCTAssertEqual(d.items.count, 2)
        XCTAssertTrue(d.items[1].stalled)
        XCTAssertNotNil(ISOTime.parse(d.lastTick))
    }

    func testDecodeEmptyProjectWithNullLastTick() throws {
        let d = try StatusDoc.decode(fixture("status_ab.json"))
        XCTAssertNil(d.lastTick)
        XCTAssertEqual(d.pendingCount, 0)
        XCTAssertEqual(d.buildingCount, 0)
    }

    func testFutureSchemaIgnoresUnknownAndToleratesOddTypes() throws {
        let d = try StatusDoc.decode(fixture("status_future.json"))
        XCTAssertEqual(d.schemaVersion, 2)
        XCTAssertGreaterThan(d.schemaVersion, StatusDoc.supportedSchema)
        XCTAssertEqual(d.gates.first?.options, [])      // options 不是数组也不炸
        XCTAssertEqual(d.gates.first?.kindLabel, "上线")
        XCTAssertEqual(d.log, [])
        XCTAssertNotNil(ISOTime.parse(d.lastTick))     // 带小数秒、Z 结尾
    }

    func testGarbageThrows() {
        XCTAssertThrowsError(try StatusDoc.decode("接棒暂停中：状态文件损坏"))
        XCTAssertThrowsError(try StatusDoc.decode("{\"name\": \"缺 project\"}"))
    }

    func testProjectListParse() throws {
        let t = String(decoding: try fixture("projects.txt"), as: UTF8.self)
        XCTAssertEqual(ProjectList.parse(t), ["TB", "AB", "EV"])
        XCTAssertEqual(ProjectList.parse(""), [])
    }
}

final class BadgeTests: XCTestCase {
    func testCountSumsAllProjectsAndIgnoresErrors() throws {
        let snaps = [try snap("status_tb.json"), try snap("status_ab.json"), try snap("status_future.json"),
                     ProjectSnapshot(code: "XX", error: "读不出")]
        XCTAssertEqual(Badge.count(snaps), 3)
        XCTAssertEqual(Badge.text(3), "3")
        XCTAssertNil(Badge.text(0))
        XCTAssertEqual(Badge.text(150), "99+")
    }

    func testMenuLine() throws {
        XCTAssertEqual(Badge.menuLine(try snap("status_tb.json")), "TB 土布 · 等你 2 · 施工 1 · 卡住 1")
        XCTAssertEqual(Badge.menuLine(try snap("status_ab.json")), "AB 副业 · 等你 0")
        XCTAssertTrue(Badge.menuLine(ProjectSnapshot(code: "XX", error: "boom")).hasPrefix("XX  读不出状态"))
    }
}

final class GateTrackerTests: XCTestCase {
    func testFirstRunPrimesSilently() throws {
        var t = GateTracker()
        XCTAssertEqual(t.diff([try snap("status_tb.json")], quiet: false), [])
        XCTAssertTrue(t.primed)
        XCTAssertEqual(t.seen, ["TB/gate_12", "TB/gate_13"])
    }

    func testNewGateNotifiesOnceThenDedupes() throws {
        var t = GateTracker(seen: ["TB/gate_12"], primed: true)
        let n = t.diff([try snap("status_tb.json")], quiet: false)
        XCTAssertEqual(n.map(\.id), ["TB/gate_13"])
        XCTAssertEqual(n.first?.title, "[TB] 等你点头：做不做")
        XCTAssertEqual(n.first?.body, "TB-FEAT-004 · 做不做：导出 PDF")
        XCTAssertEqual(t.diff([try snap("status_tb.json")], quiet: false), [])
    }

    func testQuietHoursDefersInsteadOfDropping() throws {
        var t = GateTracker(seen: [], primed: true)
        XCTAssertEqual(t.diff([try snap("status_tb.json")], quiet: true), [])
        XCTAssertEqual(t.diff([try snap("status_tb.json")], quiet: false).count, 2)
    }

    func testApprovedGatesArePrunedButFailedProjectsKept() throws {
        var t = GateTracker(seen: ["TB/old_gate", "AB/g9", "TB/gate_12"], primed: true)
        // AB 这轮读不出：它的 seen 保留；TB 读得出：old_gate 已批完被清掉
        _ = t.diff([try snap("status_tb.json"), ProjectSnapshot(code: "AB", error: "timeout")], quiet: false)
        XCTAssertTrue(t.seen.contains("AB/g9"))
        XCTAssertFalse(t.seen.contains("TB/old_gate"))
        XCTAssertTrue(t.seen.contains("TB/gate_13"))
    }

    func testGateComesBackAfterApprovalNotifiesAgain() throws {
        var t = GateTracker(seen: ["TB/gate_12", "TB/gate_13"], primed: true)
        _ = t.diff([try snap("status_ab.json"), ProjectSnapshot(code: "TB", doc: try StatusDoc.decode(fixture("status_ab.json").replacing("AB", "TB")))], quiet: false)
        XCTAssertEqual(t.seen, [])
        XCTAssertEqual(t.diff([try snap("status_tb.json")], quiet: false).count, 2)
    }
}

extension Data {
    func replacing(_ a: String, _ b: String) -> Data {
        Data(String(decoding: self, as: UTF8.self).replacingOccurrences(of: a, with: b).utf8)
    }
}

final class ConfigTests: XCTestCase {
    func testDefaultsWhenMissing() {
        XCTAssertEqual(GlobalConfig.parse(nil), .default)
        XCTAssertEqual(GlobalConfig.parse(Data("not json".utf8)), .default)
        XCTAssertEqual(GlobalConfig.parse(Data("{}".utf8)).quietHours?.start, "00:00")
    }

    func testParseValues() throws {
        let c = GlobalConfig.parse(try fixture("config_global.json"))
        XCTAssertEqual(c.magpieURL, "http://127.0.0.1:4000")
        XCTAssertEqual(c.heartbeatStaleMinutes, 20)
        XCTAssertEqual(c.quietHours, QuietHours(start: "23:00", end: "07:30", tz: "Asia/Tokyo"))
    }

    func testEmptyQuietHoursDisables() throws {
        XCTAssertNil(GlobalConfig.parse(try fixture("config_quiet_off.json")).quietHours)
    }

    func testQuietHoursAcrossMidnightInZone() {
        let q = QuietHours(start: "00:00", end: "08:00", tz: "Asia/Shanghai")
        // 2026-10-20T18:30:00Z = 上海 10-21 02:30（安静）；02:00Z = 上海 10:00（不安静）
        XCTAssertTrue(q.contains(ISOTime.parse("2026-10-20T18:30:00Z")!))
        XCTAssertFalse(q.contains(ISOTime.parse("2026-10-20T02:00:00Z")!))
        let wrap = QuietHours(start: "23:00", end: "07:30", tz: "Asia/Shanghai")
        XCTAssertTrue(wrap.contains(ISOTime.parse("2026-10-20T23:10:00+08:00")!))
        XCTAssertTrue(wrap.contains(ISOTime.parse("2026-10-21T07:29:00+08:00")!))
        XCTAssertFalse(wrap.contains(ISOTime.parse("2026-10-21T07:30:00+08:00")!))
        XCTAssertFalse(QuietHours(start: "08:00", end: "08:00", tz: "UTC").contains(Date()))
        XCTAssertFalse(QuietHours(start: "坏", end: "08:00", tz: "UTC").contains(Date()))
    }
}

final class HeartbeatTests: XCTestCase {
    let now = ISOTime.parse("2026-10-20T12:30:00+08:00")!

    func testLevels() {
        let ok = HeartbeatStatus.of(project: "TB", lastTick: "2026-10-20T12:25:00+08:00", staleMinutes: 10, now: now)
        XCTAssertEqual(ok.level, .ok)
        XCTAssertEqual(ok.line, "🟢 TB 5 分钟前转过")
        let stale = HeartbeatStatus.of(project: "TB", lastTick: "2026-10-20T11:48:00+08:00", staleMinutes: 10, now: now)
        XCTAssertEqual(stale.level, .stale)
        XCTAssertEqual(stale.line, "🔴 TB 已 42 分钟没转动")
        XCTAssertEqual(HeartbeatStatus.of(project: "AB", lastTick: nil, staleMinutes: 10, now: now).line, "⚪️ AB 从没转过")
        XCTAssertEqual(HeartbeatStatus.human(150), "2.5 小时")
        XCTAssertEqual(HeartbeatStatus.human(60 * 24 * 3), "3 天")
    }

    func testStaleAlertOnceUntilRecovered() {
        var t = StaleTracker()
        let stale = HeartbeatStatus(project: "TB", ageMinutes: 30, level: .stale)
        let ok = HeartbeatStatus(project: "TB", ageMinutes: 1, level: .ok)
        XCTAssertEqual(t.diff([stale], quiet: false).count, 1)
        XCTAssertEqual(t.diff([stale], quiet: false).count, 0)
        XCTAssertEqual(t.diff([ok], quiet: false).count, 0)
        XCTAssertEqual(t.diff([stale], quiet: true).count, 0)    // 免打扰：先不报
        XCTAssertEqual(t.diff([stale], quiet: false).count, 1)
    }
}

final class EnvTests: XCTestCase {
    func testPythonLocator() {
        let have: Set<String> = ["/usr/bin/python3", "/usr/local/bin/python3"]
        XCTAssertEqual(PythonLocator.pick(override: nil, isExecutable: have.contains, systemStubUsable: true), "/usr/local/bin/python3")
        XCTAssertEqual(PythonLocator.pick(override: nil, isExecutable: ["/usr/bin/python3"].contains, systemStubUsable: true), "/usr/bin/python3")
        XCTAssertNil(PythonLocator.pick(override: nil, isExecutable: ["/usr/bin/python3"].contains, systemStubUsable: false))
        XCTAssertEqual(PythonLocator.pick(override: "/x/py", isExecutable: { $0 == "/x/py" }, systemStubUsable: false), "/x/py")
        XCTAssertNil(PythonLocator.pick(override: "/missing", isExecutable: have.contains, systemStubUsable: true))
    }

    func testToolPath() {
        let p = ToolPath.augmented("/usr/bin:/bin:/usr/sbin:/sbin", home: "/Users/j")
        XCTAssertTrue(p.hasPrefix("/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/Users/j/.local/bin:"))
        XCTAssertEqual(p.split(separator: ":").count, Set(p.split(separator: ":")).count)
        XCTAssertTrue(ToolPath.augmented(nil, home: "/h").contains("/usr/bin"))
    }

    func testPanelTokenParse() {
        XCTAssertEqual(PanelToken.parseShowToken("面板口令：abc-DEF_123（存在 钥匙串）"), "abc-DEF_123")
        XCTAssertEqual(PanelToken.parseShowToken("第一次开面板，已生成口令：xyz\n存在 /x"), "xyz")
        XCTAssertNil(PanelToken.parseShowToken("面板：http://127.0.0.1:8765/"))
    }
}

// MARK: - v1.1 界面映射

final class AdditiveFieldTests: XCTestCase {
    func testNoLivePathAndStaleDecodeLeniently() throws {
        let d = try StatusDoc.decode(fixture("status_v11.json"))
        XCTAssertEqual(d.noLivePath, 3)
        XCTAssertEqual(d.staleItems, 2)
        XCTAssertEqual(d.roles.map(\.role), ["build", "verify", "decide"])   // 坏条目跳过
        XCTAssertEqual(ProjectRow(ProjectSnapshot(code: "EV", doc: d)).roleLine, "施工 忙 · 验收 闲 · 决策 额度满")
        XCTAssertEqual(ProjectRow(ProjectSnapshot(code: "EV", doc: d)).tooLong, 2)
        XCTAssertEqual(try StatusDoc.decode(#"{"project":"X","roles":{"build":1}}"#).roles, [])
        XCTAssertNil(ProjectRow(try snap("status_tb.json")).roleLine)
        XCTAssertEqual(d.stuckCount, 3)
        XCTAssertEqual(d.verifyingCount, 3)
        XCTAssertEqual(d.mergedCount, 1)
        XCTAssertTrue(d.items[1].noLivePath)
        XCTAssertFalse(d.items[1].stalled)              // "yes" 不是布尔，当没有
        XCTAssertEqual(try StatusDoc.decode(#"{"project":"X","no_live_path":2}"#).noLivePath, 2)
        XCTAssertEqual(try StatusDoc.decode(#"{"project":"X","no_live_path":true}"#).noLivePath, 1)
        XCTAssertNil(try StatusDoc.decode(#"{"project":"X","no_live_path":null}"#).noLivePath)
        XCTAssertNil(try StatusDoc.decode(fixture("status_tb.json")).noLivePath)
        XCTAssertEqual(try StatusDoc.decode(fixture("status_tb.json")).stuckCount, 1)
    }
}

final class ViewModelTests: XCTestCase {
    func testGreeting() {
        XCTAssertEqual(Greeting.text(hour: 2), "夜深了")
        XCTAssertEqual(Greeting.text(hour: 8), "早上好")
        XCTAssertEqual(Greeting.text(hour: 12), "中午好")
        XCTAssertEqual(Greeting.text(hour: 15), "下午好")
        XCTAssertEqual(Greeting.text(hour: 21), "晚上好")
        let d = ISOTime.parse("2026-10-21T02:30:00+08:00")!
        XCTAssertEqual(Greeting.text(at: d, tz: TimeZone(identifier: "Asia/Shanghai")!), "夜深了")
    }

    func testLoopStatePriority() {
        XCTAssertEqual(LoopState.derive(globalError: "x", loaded: true, projectCount: 1, loopRunning: false, anyStale: true), .error("x"))
        XCTAssertEqual(LoopState.derive(globalError: nil, loaded: false, projectCount: 0, loopRunning: nil, anyStale: false), .loading)
        XCTAssertEqual(LoopState.derive(globalError: nil, loaded: true, projectCount: 2, loopRunning: false, anyStale: true), .paused)
        XCTAssertEqual(LoopState.derive(globalError: nil, loaded: true, projectCount: 2, loopRunning: true, anyStale: true), .stale)
        XCTAssertEqual(LoopState.derive(globalError: nil, loaded: true, projectCount: 0, loopRunning: nil, anyStale: false), .empty)
        let r = LoopState.derive(globalError: nil, loaded: true, projectCount: 1, loopRunning: nil, anyStale: false)
        XCTAssertEqual(r, .running); XCTAssertEqual(r.label, "运行中"); XCTAssertEqual(r.tone, .success)
        XCTAssertEqual(LoopState.paused.label, "已暂停")
        XCTAssertEqual(LoopState.stale.label, "心跳过期")
    }

    func testGateCards() throws {
        let cards = GateCard.cards([try snap("status_tb.json"), try snap("status_v11.json"), ProjectSnapshot(code: "XX", error: "e")])
        XCTAssertEqual(cards.map(\.id), ["TB/gate_12", "TB/gate_13", "EV/g7", "EV/g8", "EV/g9"])
        let look = cards[0]
        XCTAssertEqual(look.title, "改版注册页按钮")
        XCTAssertEqual(look.kindLabel, "看效果")
        XCTAssertEqual(look.approveArgs(), ["-p", "TB", "approve", "gate_12", "通过"])
        XCTAssertEqual(look.rejectArgs(words: "  按钮太小 "), ["-p", "TB", "approve", "gate_12", "打回", "按钮太小"])
        XCTAssertEqual(look.rejectArgs(words: ""), ["-p", "TB", "approve", "gate_12", "打回"])
        XCTAssertTrue(look.rejectAsksWords)
        let now = ISOTime.parse("2026-10-20T12:30:00+08:00")!
        XCTAssertEqual(look.ageText(now: now), "50 分钟")
        XCTAssertNil(cards[1].ageText(now: now))
        XCTAssertEqual(cards[1].approveChoice, "做"); XCTAssertEqual(cards[1].rejectChoice, "不做")
        XCTAssertEqual(cards[1].title, "导出 PDF")
        XCTAssertFalse(cards[1].rejectAsksWords)
        XCTAssertEqual(cards[2].title, "菜单栏换成弹窗")          // 带轮次前缀
        XCTAssertEqual(cards[3].approveChoice, "上线"); XCTAssertEqual(cards[3].rejectChoice, "再等等")
        XCTAssertEqual(cards[4].approveChoice, "同意交决策岗")    // 没给 options 用种类默认
        XCTAssertEqual(cards[4].title, "外部请求")
        XCTAssertEqual(GateCard.cards([try snap("status_tb.json")], hidden: ["TB/gate_12"]).map(\.gateID), ["gate_13"])
        XCTAssertEqual(GateCard.cleanTitle("看效果："), "看效果：")
        XCTAssertTrue(look.accessibilityText.contains("件号 TB-UX-003"))
    }

    func testProjectRowsAndHarvest() throws {
        let r = ProjectRow(try snap("status_v11.json"))
        XCTAssertEqual([r.building, r.verifying, r.waiting, r.stuck, r.merged], [1, 3, 3, 3, 1])
        XCTAssertFalse(r.isQuiet)
        XCTAssertTrue(ProjectRow(try snap("status_ab.json")).isQuiet)
        XCTAssertFalse(ProjectRow(ProjectSnapshot(code: "XX", error: "boom")).isQuiet)
        XCTAssertEqual(HarvestItem.list([try snap("status_v11.json"), try snap("status_tb.json")]).map(\.id), ["EV/EV-1"])
    }

    func testMoodAndSpeech() throws {
        XCTAssertEqual(MascotMood.derive(state: .running, waiting: 2, building: 1, stuck: 0), .waiting)
        XCTAssertEqual(MascotMood.derive(state: .running, waiting: 0, building: 1, stuck: 0), .working)
        XCTAssertEqual(MascotMood.derive(state: .running, waiting: 0, building: 0, stuck: 1), .worried)
        XCTAssertEqual(MascotMood.derive(state: .running, waiting: 0, building: 0, stuck: 0), .idle)
        XCTAssertEqual(MascotMood.derive(state: .paused, waiting: 3, building: 0, stuck: 0), .sleepy)
        XCTAssertEqual(MascotMood.derive(state: .stale, waiting: 0, building: 0, stuck: 0), .worried)
        let tb = try snap("status_tb.json")
        let looks = GateCard.cards([tb]).filter { $0.kind == "look" }
        XCTAssertEqual(Speech.status(state: .running, cards: looks, rows: [], beats: []), "有 1 件等你看效果")
        XCTAssertEqual(Speech.status(state: .running, cards: GateCard.cards([tb]), rows: [], beats: []), "有 2 件等你处理")
        XCTAssertEqual(Speech.status(state: .running, cards: [], rows: [], beats: []), "一切顺利")
        let beat = HeartbeatStatus(project: "TB", ageMinutes: 42, level: .stale)
        XCTAssertTrue(Speech.status(state: .stale, cards: [], rows: [], beats: [beat]).hasPrefix("TB 已 42 分钟没转动"))
    }

    func testFuzzy() {
        XCTAssertNotNil(Fuzzy.score("tk", "立即 tick"))
        XCTAssertNil(Fuzzy.score("xyz", "立即 tick"))
        XCTAssertEqual(Fuzzy.score("", "abc"), 0)
        XCTAssertNotNil(Fuzzy.score("收菜", "收菜清单"))
        XCTAssertNotNil(Fuzzy.score("TICK", "立即 tick"))
        // 连续命中 + 开头命中优先
        let items = ["打开面板 panel", "暂停循环 pause", "设置 settings", "立即 tick"]
        XCTAssertEqual(Fuzzy.filter(items, query: "pa", text: { $0 }).first, "打开面板 panel")
        XCTAssertEqual(Fuzzy.filter(items, query: "set", text: { $0 }), ["设置 settings"])
        XCTAssertEqual(Fuzzy.filter(items, query: " ", text: { $0 }), items)
        XCTAssertGreaterThan(Fuzzy.score("tick", "tick")!, Fuzzy.score("tick", "t-i-c-k")!)
    }

    func testPaletteEntries() throws {
        let tb = try snap("status_tb.json")
        let e = PaletteEntry.build(cards: GateCard.cards([tb]), rows: [ProjectRow(tb)], paused: true)
        XCTAssertTrue(e.contains { $0.action == .togglePause && $0.title == "恢复循环" })
        XCTAssertTrue(e.contains { $0.action == .approve("TB/gate_12") && $0.title == "通过：改版注册页按钮" })
        XCTAssertTrue(e.contains { $0.action == .focusProject("TB") })
        XCTAssertFalse(PaletteEntry.build(cards: [], rows: [], paused: nil).contains { $0.action == .togglePause })
        XCTAssertEqual(Fuzzy.filter(e, query: "收菜", text: \.searchText).first?.action, .harvest)
    }

    func testComposer() {
        XCTAssertEqual(try Composer.command(mode: .feedback, project: "TB", text: " 按钮太小了 ").get(), ["-p", "TB", "feedback", "按钮太小了"])
        XCTAssertEqual(try Composer.command(mode: .add, project: "TB", text: "加导出 PDF", look: true).get(),
                       ["-p", "TB", "add", "--title", "加导出 PDF", "--scope", ".", "--look"])
        if case .failure(let e) = Composer.command(mode: .add, project: "TB", text: String(repeating: "长", count: 25)) {
            XCTAssertTrue(e.message.contains("24"))
        } else { XCTFail() }
        XCTAssertThrowsError(try Composer.command(mode: .feedback, project: "TB", text: "  ").get())
        XCTAssertThrowsError(try Composer.command(mode: .feedback, project: "", text: "hi").get())
        XCTAssertEqual(Composer.reply(mode: .feedback, ok: true, out: "https://github.com/a/b/issues/42\n", err: ""), "收到！记成 issue #42，决策岗会分拣")
        XCTAssertTrue(Composer.reply(mode: .feedback, ok: false, out: "", err: "没建成：auth").hasPrefix("没成："))
    }

    func testShortcuts() {
        XCTAssertEqual(Shortcuts.project(forDigit: 2, codes: ["TB", "AB"]), "AB")
        XCTAssertNil(Shortcuts.project(forDigit: 3, codes: ["TB", "AB"]))
        XCTAssertNil(Shortcuts.project(forDigit: 0, codes: ["TB"]))
    }

    func testMascotPose() {
        XCTAssertEqual(MascotPose.blink(0, period: 3.6, phase: 0), 1, accuracy: 0.001)
        XCTAssertEqual(MascotPose.blink(0.08, period: 3.6, phase: 0), 0, accuracy: 0.01)
        XCTAssertEqual(MascotPose.blink(1.0, period: 3.6, phase: 0), 1)
        XCTAssertLessThan(MascotPose.at(1, mood: .sleepy).eyeOpen, 0.2)
        XCTAssertEqual(MascotPose.at(1, mood: .waiting).browRaise, 1)
        XCTAssertLessThan(MascotPose.at(1, mood: .worried).mouthCurve, 0)
        for m in MascotMood.allCases {             // 减弱动态效果：不上下跳
            XCTAssertEqual(MascotPose.at(0.37, mood: m, reduceMotion: true).bob, 0)
            XCTAssertEqual(MascotPose.at(0.37, mood: m, reduceMotion: true).squash, 0)
        }
        let w = (0..<40).map { MascotPose.at(Double($0) * 0.1, mood: .working).eyeDX }
        XCTAssertGreaterThan(w.max()!, 0.5); XCTAssertLessThan(w.min()!, -0.5)   // 真的在东张西望
    }
}
