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
