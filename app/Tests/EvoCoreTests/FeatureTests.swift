import XCTest
@testable import EvoCore

/// v0.7.0（第十八轮）：功能列表解码、侧栏显示/隐藏、settings schema 自动表单、evo watch 事件流与回退轮询、页错误边界。
final class FeatureTests: XCTestCase {
    private func list() throws -> FeatureList {
        try FeatureList.decode(String(decoding: try fixture("feature_list.json"), as: UTF8.self))   // 真 evo feature list --json（plugins 关着）
    }

    // MARK: 功能列表

    func testDecodeRealFeatureList() throws {
        let l = try list()
        XCTAssertEqual(l.schemaVersion, 1)
        XCTAssertEqual(l.features.count, 12)
        let caps = try XCTUnwrap(l.feature("item-caps"))
        XCTAssertTrue(caps.essential)
        XCTAssertEqual(caps.settings?.fields.map(\.key), ["decider_reworks", "item_hard_runs", "item_hard_hours"])   // 按 x-order
        XCTAssertEqual(caps.value(caps.settings!.fields[1]), .number(20))      // evo feature set 改过
        XCTAssertEqual(l.feature("plugins")?.state, "off")
        XCTAssertEqual(l.feature("plugins")?.badge.text, "关着")
        XCTAssertTrue(l.feature("team")?.hasPage == true)
        XCTAssertTrue(ContractCheck.check(String(decoding: try fixture("feature_list.json"), as: UTF8.self), command: .featureList).isOK)
    }

    func testLenientFeatureDecoding() throws {
        let l = try FeatureList.decode(#"{"features":[{"id":"a"},{"name":"没有 id"},{"id":"b","state":"failed","why":"缺服务 x","in_use":2,"in_use_text":"2 个项目在用"}]}"#)
        XCTAssertEqual(l.features.map(\.id), ["a", "b"])                  // 坏的一条丢掉，不连累整张
        XCTAssertEqual(l.features[0].name, "a")
        XCTAssertTrue(l.features[1].locked)
        XCTAssertEqual(l.features[1].note, "正在用（2 个项目在用），关不掉")
        XCTAssertEqual(l.features[1].badge.tone, .danger)
    }

    func testFutureFeatureListVersionIsCaught() {
        let c = ContractCheck.check(#"{"schema_version": 2, "features": []}"#, command: .featureList)
        XCTAssertEqual(c, .evoNewer(found: 2, supported: 1, command: .featureList))
        XCTAssertTrue(c.message!.contains("evo feature list --json"))
    }

    // MARK: 侧栏按功能列表显示 / 隐藏

    func testSidebarFollowsFeatureList() throws {
        let off = FeatureRegistry(try list())
        XCTAssertTrue(off.teamVisible)
        XCTAssertFalse(off.pluginsVisible)                          // plugins 关着 → 「插件」分组不出现
        XCTAssertEqual(off.fallback(.plugin("example-hello", "hello")), .inbox)
        XCTAssertEqual(off.fallback(.team), .team)
        XCTAssertEqual(off.fallback(.project("TB")), .project("TB"))
        XCTAssertTrue(off.pageVisible("inbox"))                     // 没有功能包声明 → 内核的页，一直显示

        var l = try list()
        l.features = l.features.map { f in var f = f; if f.id == "team" { f.state = "off"; f.enabled = false }; return f }
        let noTeam = FeatureRegistry(l)
        XCTAssertFalse(noTeam.teamVisible)
        XCTAssertEqual(noTeam.fallback(.team), .inbox)

        let old = FeatureRegistry(nil)                              // 老 evo 没有 feature 命令：照旧全显示
        XCTAssertTrue(old.teamVisible && old.pluginsVisible)
        XCTAssertTrue(old.active("team"))
        XCTAssertTrue(old.settingsRows.isEmpty)
        XCTAssertTrue(old.summary.contains("没有功能开关"))
    }

    func testSettingsRowsPutConfigurableFirst() throws {
        let r = FeatureRegistry(try list())
        let rows = r.settingsRows
        XCTAssertEqual(rows.count, 12)
        let firstPlain = rows.firstIndex { $0.settings?.fields.isEmpty != false }!
        XCTAssertTrue(rows[..<firstPlain].allSatisfy { $0.settings?.fields.isEmpty == false })
        XCTAssertTrue(rows[firstPlain...].allSatisfy { $0.settings?.fields.isEmpty != false })
        XCTAssertTrue(r.summary.hasPrefix("12 个功能，开着 11 个"))
    }

    // MARK: settings schema → 表单

    func testControlsFromSchema() throws {
        let l = try list()
        let caps = l.feature("item-caps")!.settings!.fields
        XCTAssertEqual(caps.map(\.control), [.number, .number, .number])
        XCTAssertEqual(caps[0].rangeText, "0–50")
        let deploy = l.feature("deploy")!.settings!.fields
        XCTAssertEqual(deploy.first { $0.key == "auto_ship_gate" }?.control, .toggle)
        XCTAssertEqual(deploy.first { $0.key == "ship_gate_at" }?.control, .text)
        let enumField = SettingField(key: "mode", kind: .string, title: "模式", options: [.string("a"), .string("b")], defaultValue: .string("a"))
        XCTAssertEqual(enumField.control, .choice)
        XCTAssertEqual(enumField.parse("c"), .failure(SettingError(message: "只能是 a / b")))
    }

    func testUnknownSchemaTypesAreSkipped() throws {
        let s = try JSONDecoder().decode(SettingsSchema.self, from: Data(#"{"x-order":["b","a"],"properties":{"a":{"type":"integer","default":1},"b":{"type":"string"},"c":{"type":"array"},"d":"坏的"}}"#.utf8))
        XCTAssertEqual(s.fields.map(\.key), ["b", "a"])
        XCTAssertEqual(s.fields[1].title, "a")                      // 没写 title 就用键名
    }

    func testFormDraftCommitAndErrors() throws {
        let caps = try list().feature("item-caps")!
        var form = FeatureForm(caps)
        let runs = caps.settings!.fields[1]
        XCTAssertEqual(form.draft("item_hard_runs"), "20")
        XCTAssertFalse(form.dirty(runs, in: caps))
        form.edit("item_hard_runs", "2000")
        XCTAssertTrue(form.dirty(runs, in: caps))
        XCTAssertNil(form.commit(runs))
        XCTAssertEqual(form.error("item_hard_runs"), "不能大于 1000")
        form.edit("item_hard_runs", "abc")
        XCTAssertNil(form.error("item_hard_runs"))                  // 一改就清红字
        XCTAssertNil(form.commit(runs))
        XCTAssertEqual(form.error("item_hard_runs"), "要是整数")
        form.edit("item_hard_runs", " 30 ")
        XCTAssertEqual(form.commit(runs), ["feature", "set", "item-caps", "item_hard_runs=30"])
        let hours = caps.settings!.fields[2]
        form.edit("item_hard_hours", "1.5")
        XCTAssertEqual(form.commit(hours), ["feature", "set", "item-caps", "item_hard_hours=1.5"])
        form.reject("item_hard_hours", "  item-caps 没有设置 x\n")
        XCTAssertEqual(form.error("item_hard_hours"), "item-caps 没有设置 x")
    }

    func testFormToggleAndSync() throws {
        let deploy = try list().feature("deploy")!
        var form = FeatureForm(deploy)
        let auto = deploy.settings!.fields.first { $0.key == "auto_ship_gate" }!
        XCTAssertEqual(form.choose(auto, .bool(false)), ["feature", "set", "deploy", "auto_ship_gate=false"])
        var newer = deploy
        newer.config["ship_gate_at"] = .string("09:00")
        form.edit("ship_gate_at", "07:")                            // 正在改的不被冲掉
        form.sync(newer, editing: "ship_gate_at")
        XCTAssertEqual(form.draft("ship_gate_at"), "07:")
        form.sync(newer)
        XCTAssertEqual(form.draft("ship_gate_at"), "09:00")
    }

    func testToggleCommands() {
        XCTAssertEqual(FeatureCommand.list(), ["feature", "list", "--json"])
        XCTAssertEqual(FeatureCommand.toggle("team", on: false), ["feature", "off", "team"])
        XCTAssertEqual(FeatureCommand.toggle("team", on: true), ["feature", "on", "team"])
    }

    // MARK: evo watch --json

    func testWatchParserSplitsLinesAndKeepsHalfLine() {
        var p = WatchParser()
        let a = p.feed(#"{"schema_version":1,"event":"watch.ping","project":null,"data":{"hello":true}}"# + "\n" + #"{"schema_version":1,"event":"gate.pend"#)
        XCTAssertEqual(a.map(\.event), ["watch.ping"])
        XCTAssertFalse(a[0].triggersRefresh)
        let b = p.feed(#"ing","project":"TB","item":"TB-1"}"# + "\n不是 JSON\n" + #"{"schema_version":2,"event":"tick"}"# + "\n")
        XCTAssertEqual(b.map(\.event), ["gate.pending", "tick"])
        XCTAssertEqual(b[0].project, "TB")
        XCTAssertTrue(b[0].triggersRefresh)
        XCTAssertFalse(b[1].triggersRefresh)                         // 不认识的大版本不刷
        XCTAssertTrue(WatchEvent(event: "feature.changed").touchesFeatures)
        XCTAssertFalse(WatchEvent(event: "item.merged").touchesFeatures)
    }

    func testWatchFallbackPolling() {
        let t0 = Date(timeIntervalSince1970: 1_000_000)
        // 没连上：30 秒轮询
        XCTAssertTrue(WatchPolicy.shouldPoll(lastRefresh: t0, lastLine: nil, now: t0.addingTimeInterval(30)))
        XCTAssertFalse(WatchPolicy.shouldPoll(lastRefresh: t0, lastLine: nil, now: t0.addingTimeInterval(10)))
        // 连着（最近有 ping）：只做 2 分钟兜底
        XCTAssertFalse(WatchPolicy.shouldPoll(lastRefresh: t0, lastLine: t0.addingTimeInterval(20), now: t0.addingTimeInterval(30)))
        XCTAssertTrue(WatchPolicy.shouldPoll(lastRefresh: t0, lastLine: t0.addingTimeInterval(110), now: t0.addingTimeInterval(120)))
        // ping 断了超过 45 秒 → 自动回到 30 秒轮询
        XCTAssertTrue(WatchPolicy.shouldPoll(lastRefresh: t0, lastLine: t0.addingTimeInterval(-60), now: t0.addingTimeInterval(30)))
        XCTAssertTrue(WatchPolicy.shouldPoll(lastRefresh: nil, lastLine: nil))
        XCTAssertEqual([1, 2, 3, 4, 5, 9].map { WatchPolicy.restartDelay(failures: $0) }, [5, 10, 20, 40, 60, 60])
    }

    func testWatchLinkReconnect() {
        let t0 = Date(timeIntervalSince1970: 2_000_000)
        var w = WatchLink()
        XCTAssertFalse(w.alive(t0))
        w.started(t0); w.received(at: t0.addingTimeInterval(1))
        XCTAssertTrue(w.alive(t0.addingTimeInterval(10)))
        XCTAssertTrue(w.statusText(t0.addingTimeInterval(10)).contains("已连上"))
        XCTAssertFalse(w.alive(t0.addingTimeInterval(60)))         // 45 秒没一行：当它死了
        XCTAssertEqual(w.exited(t0.addingTimeInterval(5)), 5)       // 刚起就退：退避
        w.started(t0.addingTimeInterval(10)); XCTAssertEqual(w.exited(t0.addingTimeInterval(11)), 10)
        w.started(t0.addingTimeInterval(20)); XCTAssertEqual(w.exited(t0.addingTimeInterval(21)), 20)
        XCTAssertTrue(w.statusText(t0.addingTimeInterval(22)).contains("连不上"))
        w.started(t0.addingTimeInterval(30)); XCTAssertEqual(w.exited(t0.addingTimeInterval(200)), 5)   // 活过 60 秒的断线：从头算
        XCTAssertFalse(w.alive(t0.addingTimeInterval(201)))
    }

    // MARK: 页错误边界

    func testPageBoundary() {
        let e = PageErrors(team: "功能 team 关着", projects: ["TB": "退出码 1"], logs: ["TB/TB-1": ""], features: "x")
        XCTAssertEqual(PageBoundary.error(for: .team, e)?.title, "团队页出错了")
        XCTAssertEqual(PageBoundary.error(for: .project("TB"), e)?.message, "退出码 1")
        XCTAssertNil(PageBoundary.error(for: .project("AB"), e))
        XCTAssertEqual(PageBoundary.error(for: .item(project: "TB", key: "TB-1"), e)?.message, "evo 没有回话（退出码非 0）")
        XCTAssertNil(PageBoundary.error(for: .inbox, e))            // 汇总页不整页挡住
        XCTAssertNil(PageBoundary.error(for: .settings, e))         // 设置页永远能开
        XCTAssertEqual(PageError(message: String(repeating: "长", count: 900)).message.count, 400)
    }
}
