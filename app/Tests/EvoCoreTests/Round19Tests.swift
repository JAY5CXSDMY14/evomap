import XCTest
@testable import EvoCore

/// 第十九轮：设计令牌、动效策略、首页三态、「为什么卡住」、⌘K 跳转。
final class DesignTokenTests: XCTestCase {
    func testSpacingIsOrderedAndOnGrid() {
        XCTAssertEqual(Tokens.Space.all, Tokens.Space.all.sorted())
        for v in Tokens.Space.all where v >= 4 { XCTAssertEqual(v.truncatingRemainder(dividingBy: 4), 0, "\(v) 不在 4 的格子上") }
    }

    func testRadiiAndDurationsOrdered() {
        XCTAssertLessThan(Tokens.Radius.chip, Tokens.Radius.field)
        XCTAssertLessThan(Tokens.Radius.small, Tokens.Radius.card)
        XCTAssertLessThan(Tokens.Duration.instant, Tokens.Duration.fast)
        XCTAssertLessThan(Tokens.Duration.fast, Tokens.Duration.base)
        XCTAssertLessThan(Tokens.Duration.base, Tokens.Duration.slow)
        XCTAssertLessThan(Tokens.FontSize.caption, Tokens.FontSize.body)
        XCTAssertLessThan(Tokens.FontSize.section, Tokens.FontSize.pane)
    }

    func testSpringsAreRestrained() {
        // QQ 弹弹但克制：过冲不超过 8%，响应在 0.2–0.5 秒
        for s in Tokens.Spring.all {
            XCTAssertGreaterThanOrEqual(s.damping, 0.6)
            XCTAssertLessThan(s.overshoot, 0.08, "过冲 \(s.overshoot)")
            XCTAssertTrue((0.2...0.5).contains(s.response))
        }
        XCTAssertGreaterThan(Tokens.Spring.press.overshoot, 0, "一点都不弹就不是 QQ 弹弹了")
        XCTAssertGreaterThan(Tokens.pressScale, 0.9)
    }

    func testMotionPolicy() {
        XCTAssertEqual(MotionPolicy.resolve(reduceMotion: true, forceDemo: false), .fade)
        XCTAssertEqual(MotionPolicy.resolve(reduceMotion: true, forceDemo: true), .full)     // CI：EVO_DEMO_MOTION=1
        XCTAssertEqual(MotionPolicy.resolve(reduceMotion: false, forceDemo: false), .full)
        XCTAssertEqual(MotionPolicy.resolve(reduceMotion: false, forceDemo: true, staticRender: true), .none)
        XCTAssertEqual(MotionPolicy.full.staggerDelay(0), 0)
        XCTAssertEqual(MotionPolicy.full.staggerDelay(100), MotionPolicy.full.staggerDelay(Tokens.Duration.staggerMax))
        XCTAssertEqual(MotionPolicy.fade.staggerDelay(3), 0)
    }
}

final class HomeSummaryTests: XCTestCase {
    func testThreeStatesAndAttention() throws {
        let tb = try snap("status_tb.json")
        let cards = GateCard.cards([tb]), rows = [ProjectRow(tb)]
        XCTAssertEqual(HomeSummary.derive(loaded: false, globalError: nil, cards: [], rows: [], stuck: 0, paused: false).phase, .loading)
        let err = HomeSummary.derive(loaded: true, globalError: "找不到 python3", cards: cards, rows: rows, stuck: 0, paused: false)
        XCTAssertEqual(err.phase, .error)
        XCTAssertEqual(err.detail, "找不到 python3")
        XCTAssertNil(err.backgroundLine)
        let clear = HomeSummary.derive(loaded: true, globalError: nil, cards: [], rows: rows, stuck: 0, paused: false)
        XCTAssertEqual(clear.phase, .clear)
        XCTAssertEqual(clear.headline, "没有要你处理的事")
        XCTAssertNotNil(clear.backgroundLine)
        let empty = HomeSummary.derive(loaded: true, globalError: nil, cards: [], rows: [], stuck: 0, paused: false)
        XCTAssertTrue(empty.detail?.contains("还没有项目") == true)
        let att = HomeSummary.derive(loaded: true, globalError: nil, cards: cards, rows: rows, stuck: 2, paused: false)
        XCTAssertEqual(att.phase, .attention)
        XCTAssertEqual(att.headline, "有 \(cards.count) 件等你处理")
        XCTAssertEqual(att.attentionCount, cards.count)
        XCTAssertTrue(att.stuckLine?.hasPrefix("2 件卡住了") == true)
        XCTAssertTrue(att.backgroundLine?.contains("1 个项目在转") == true)
    }

    func testOldestWaitAndPausedBackground() throws {
        let tb = try snap("status_tb.json")
        var cards = GateCard.cards([tb])
        let now = Date()
        cards[0].waitingSince = now.addingTimeInterval(-3 * 3600)
        let s = HomeSummary.derive(loaded: true, globalError: nil, cards: cards, rows: [ProjectRow(tb)], stuck: 0, paused: true, now: now)
        XCTAssertEqual(s.detail, "最久的一件等了 3.0 小时")
        XCTAssertTrue(s.backgroundLine?.contains("暂停中") == true)
        XCTAssertNil(s.stuckLine)
    }
}

final class ItemDiagnosisTests: XCTestCase {
    private func item(_ raw: String, state: String = "", stalled: Bool = false, nlp: Bool = false) -> StatusDoc.Item {
        StatusDoc.Item(key: "TB-1", title: "t", state: state, raw: raw, stalled: stalled, noLivePath: nlp)
    }
    private func log(_ events: [ItemLog.Event]) throws -> ItemLog {
        var l = try ItemLog.decode(#"{"key":"TB-1","events":[]}"#)
        l.events = events
        return l
    }

    func testNoLivePathReasons() {
        let now = Date()
        let d = ItemDiagnosis.explain(item: item("building", state: "施工中", nlp: true), log: nil, stale: nil,
                                      noLivePath: StatusDoc.Flag(key: "TB-1", reason: "dep_dead", minutes: 95), now: now)
        XCTAssertTrue(d.stuck)
        XCTAssertEqual(d.tone, .danger)
        XCTAssertEqual(d.headline, "它依赖的件没了，这件没人能接着做")
        XCTAssertEqual(d.because.first, "已经这样 1.6 小时")
        XCTAssertNotNil(d.next)
        let r = ItemDiagnosis.explain(item: nil, log: nil, stale: nil, noLivePath: StatusDoc.Flag(key: "X", reason: "rate_limited"))
        XCTAssertTrue(r.headline.contains("额度满"))
        let u = ItemDiagnosis.explain(item: nil, log: nil, stale: nil, noLivePath: StatusDoc.Flag(key: "X", reason: "weird"))
        XCTAssertTrue(u.headline.contains("weird"))
        // 只有 item.no_live_path 标记、没有明细
        XCTAssertTrue(ItemDiagnosis.explain(item: item("building", nlp: true), log: nil, stale: nil, noLivePath: nil).stuck)
    }

    func testWaitingOnBossIsNotStuck() {
        let look = ItemDiagnosis.explain(item: item("look", state: "等你看效果"), log: nil, stale: nil, noLivePath: nil)
        XCTAssertFalse(look.stuck)
        XCTAssertEqual(look.tone, .waitingOnYou)
        XCTAssertTrue(look.next?.contains("通过") == true)
        XCTAssertEqual(ItemDiagnosis.explain(item: item("proposed"), log: nil, stale: nil, noLivePath: nil).tone, .waitingOnYou)
        XCTAssertFalse(ItemDiagnosis.explain(item: item("merged"), log: nil, stale: nil, noLivePath: nil).stuck)
    }

    func testStaleByState() {
        let q = ItemDiagnosis.explain(item: item("queued", state: "排队", stalled: true), log: nil,
                                      stale: StatusDoc.Flag(key: "TB-1", state: "排队", hours: 9.5), noLivePath: nil)
        XCTAssertTrue(q.stuck)
        XCTAssertEqual(q.tone, .warning)
        XCTAssertEqual(q.headline, "排队 9.5 小时还没开工")
        XCTAssertEqual(q.because.first, "在「排队」待了 9.5 小时")
        let b = ItemDiagnosis.explain(item: item("building", state: "施工中"), log: nil,
                                      stale: StatusDoc.Flag(key: "TB-1", minutes: 200), noLivePath: nil)
        XCTAssertEqual(b.headline, "施工 3.3 小时没交卷")
        let v = ItemDiagnosis.explain(item: item("verifying", stalled: true), log: nil, stale: nil, noLivePath: nil)
        XCTAssertEqual(v.headline, "验收很久没出结果")
    }

    func testEventsDrivenReasons() throws {
        let now = Date()
        let iso = ISO8601DateFormatter().string(from: now.addingTimeInterval(-600))
        let failed = try log([ItemLog.Event(at: iso, event: "deploy_failed", fields: ["reason": "端口被占用"])])
        let d = ItemDiagnosis.explain(item: item("merged"), log: failed, stale: nil, noLivePath: nil, now: now)
        // 件还显示「已合并」，但最后一件事是部署失败：报失败，不说「等下一批上线」
        XCTAssertTrue(d.stuck)
        XCTAssertEqual(d.tone, .danger)
        let failed2 = ItemDiagnosis.explain(item: item("shipping"), log: failed, stale: nil, noLivePath: nil, now: now)
        XCTAssertEqual(failed2.headline, "上线时部署失败：端口被占用")
        XCTAssertTrue(failed2.because.contains { $0.hasPrefix("最后一件事：部署失败（10 分钟前）") })

        let blocked = try log([ItemLog.Event(at: iso, event: "report", fields: ["status": "blocked", "summary": "缺 API 密钥"])])
        let b = ItemDiagnosis.explain(item: item("building"), log: blocked, stale: nil, noLivePath: nil, now: now)
        XCTAssertTrue(b.stuck)
        XCTAssertEqual(b.headline, "施工交卷说做不下去：缺 API 密钥")

        let rework = try log([ItemLog.Event(at: iso, event: "gate_reject"), ItemLog.Event(at: iso, event: "dispatch")])
        let r = ItemDiagnosis.explain(item: item("building"), log: rework, stale: nil, noLivePath: nil, now: now)
        XCTAssertFalse(r.stuck)
        XCTAssertEqual(r.headline, "你打回过 1 次，正在按你的话返工")
        XCTAssertLessThanOrEqual(r.because.count, 3)
    }

    func testRealFixtureLog() throws {
        let l = try ItemLog.decode(String(decoding: fixture("log_tb_ux_003.json"), as: UTF8.self))
        let d = ItemDiagnosis.explain(item: nil, log: l, stale: nil, noLivePath: nil)
        XCTAssertFalse(d.headline.isEmpty)
    }
}

final class PaletteRound19Tests: XCTestCase {
    func testJumpEntriesAndSections() throws {
        let tb = try snap("status_tb.json")
        let items = [PaletteEntry.ItemRef(project: "TB", key: "TB-FIX-012", title: "修验证码", note: "施工中"),
                     PaletteEntry.ItemRef(project: "TB", key: "TB-DOC-007", title: "保养说明", note: "排队", stuck: true)]
        let e = PaletteEntry.build(cards: GateCard.cards([tb]), rows: [ProjectRow(tb)], paused: false, items: items, teamVisible: true)
        XCTAssertEqual(e.first?.action, .openWindow)                     // 老顺序不变
        XCTAssertEqual(e.firstIndex { $0.action == .togglePause }, 3)
        XCTAssertTrue(e.contains { $0.action == .go(.team) })
        XCTAssertFalse(PaletteEntry.build(cards: [], rows: [], paused: nil).contains { $0.action == .go(.team) })
        let its = e.filter { if case .openItem = $0.action { return true }; return false }
        XCTAssertEqual(its.first?.action, .openItem(project: "TB", key: "TB-DOC-007"))   // 卡住的排前面
        XCTAssertEqual(its.first?.section, "件")
        XCTAssertEqual(Fuzzy.filter(e, query: "卡太久", text: \.searchText).first?.action, .go(.stale))
        XCTAssertEqual(Fuzzy.filter(e, query: "TB-FIX", text: \.searchText).first?.action, .openItem(project: "TB", key: "TB-FIX-012"))
        XCTAssertEqual(e.first { $0.action == .refresh }?.shortcut, "⌘R")
        XCTAssertEqual(e.first { $0.action == .approve("TB/gate_12") }?.section, "等你处理")
    }
}
