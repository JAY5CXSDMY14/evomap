import XCTest
@testable import EvoCore

/// v0.6.0：接口定版本（ContractCheck、projects --json）+ 插件（plugin list / run 解码、卡片、/命令、命令行、三态）。
final class ContractTests: XCTestCase {
    func testPeekVersion() {
        XCTAssertEqual(ContractCheck.peekVersion(#"{"schema_version": 1, "x": 2}"#), 1)
        XCTAssertEqual(ContractCheck.peekVersion(#"{"schema_version": 3}"#), 3)
        XCTAssertEqual(ContractCheck.peekVersion(#"{"key": "TB-1", "events": []}"#), 1)     // 老 evo log 没有版本号：当 1
        XCTAssertEqual(ContractCheck.peekVersion(#"{"schema_version": "2"}"#), 2)
        XCTAssertNil(ContractCheck.peekVersion("TB 土布 ~/code/tb"))
        XCTAssertNil(ContractCheck.peekVersion("[1,2]"))
    }

    func testNewerMajorIsRejectedWithMessage() throws {
        let s = String(decoding: try fixture("status_future.json"), as: UTF8.self)
        let c = ContractCheck.check(s, command: .status)
        XCTAssertEqual(c, .evoNewer(found: 2, supported: 1, command: .status))
        XCTAssertFalse(c.isOK)
        XCTAssertTrue(c.message!.contains("evo 版本比 App 新"))
        XCTAssertTrue(c.message!.contains("请更新 Evo App"))
        // 解码本身不炸（宽松解码），只是 AppState 不用它
        XCTAssertNoThrow(try StatusDoc.decode(s))
    }

    func testOlderMajorAndMinorAdditions() throws {
        let old = ContractCheck.check(#"{"schema_version": 0, "project": "TB"}"#, command: .status)
        XCTAssertEqual(old, .evoOlder(found: 0, supported: 1, command: .status))
        XCTAssertTrue(old.message!.contains("evo 版本比 App 旧"))
        // 小版本：同一大版本多了字段 → ok，解码忽略
        let minor = #"{"schema_version": 1, "project": "TB", "name": "土布", "count": {}, "stuck": 0, "gates": [], "items": [], "log": [], "brand_new": {"a": [1]}}"#
        XCTAssertTrue(ContractCheck.check(minor, command: .status).isOK)
        XCTAssertEqual(try StatusDoc.decode(minor).project, "TB")
        XCTAssertTrue(ContractCheck.check("不是 JSON", command: .status).isOK)          // 交给解码报错
        XCTAssertNil(ContractCheck.ok.message)
    }

    func testProjectsJSONAndTextFallback() {
        let j = #"{"schema_version": 1, "projects": [{"code": "TB", "name": "土布", "repo": "/x"}, {"code": "AB"}, {"bad": 1}, {"code": "TB"}]}"#
        XCTAssertEqual(try ProjectList.parseAny(j).get(), ["TB", "AB"])
        XCTAssertEqual(try ProjectList.parseAny("TB    土布  ~/code/tb  JAY/tb\nAB 副业 ~/ab\n").get(), ["TB", "AB"])
        if case .failure(let m) = ProjectList.parseAny(#"{"schema_version": 2, "projects": []}"#) {
            XCTAssertTrue(m.message.contains("evo projects --json"))
        } else { XCTFail("大版本 2 应该拦下") }
    }
}

final class PluginTests: XCTestCase {
    func list() throws -> PluginList { try PluginList.decode(String(decoding: try fixture("plugin_list.json"), as: UTF8.self)) }

    func testPluginListDecodes() throws {
        let l = try list()
        XCTAssertEqual(l.schemaVersion, 1)
        XCTAssertEqual(l.plugins.count, 1)
        let p = l.plugins[0]
        XCTAssertEqual(p.name, "example-hello")
        XCTAssertTrue(p.active && p.canEnable)
        XCTAssertEqual(l.sidebarPages, [PluginPageRef(plugin: "example-hello", id: "hello", title: "你好", icon: "hand.wave")])
        XCTAssertEqual(l.sidebarPages[0].symbol, "hand.wave")
        XCTAssertEqual(l.composerCommands.map(\.name), ["hello"])
        XCTAssertEqual(l.itemActions.map(\.key), ["example-hello/hello-item"])
        XCTAssertEqual(p.contributes.summary, "侧栏页 1 · 输入框命令 1 · 通知渠道 1 · 件按钮 1")
        XCTAssertTrue(p.statusLine.hasPrefix("v0.1.0"))
        XCTAssertNotNil(l.page("example-hello", "hello"))
        XCTAssertNil(l.page("example-hello", "nope"))
    }

    func testInactivePluginsContributeNothing() throws {
        let j = #"""
        {"schema_version": 1, "plugins": [
          {"name": "off", "enabled": false, "valid": true, "compatible": true, "active": false, "errors": [],
           "contributes": {"sidebar_pages": [{"id": "a", "title": "A"}], "composer_commands": [{"id": "c", "name": "cmd"}]}},
          {"name": "future", "evo_api": "^2", "enabled": true, "valid": true, "compatible": false, "errors": [], "contributes": {}},
          {"name": "broken", "enabled": true, "valid": false, "compatible": true, "errors": ["没有 plugin.json"]},
          {"oops": true}]}
        """#
        let l = try PluginList.decode(j)
        XCTAssertEqual(l.plugins.map(\.name), ["off", "future", "broken"])      // 坏条目丢掉，不连累整张表
        XCTAssertTrue(l.sidebarPages.isEmpty && l.composerCommands.isEmpty)
        XCTAssertFalse(l.plugins[1].active)                                       // 没有 active 字段：自己算
        XCTAssertTrue(l.plugins[1].statusLine.contains("不兼容"))
        XCTAssertTrue(l.plugins[2].statusLine.contains("没有 plugin.json"))
        XCTAssertFalse(l.plugins[2].canEnable)
    }

    func testCardDecodingAllBlocksAndUnknownIgnored() throws {
        let r = try JSONDecoder().decode(PluginRunResult.self, from: try fixture("plugin_run_page.json"))
        XCTAssertTrue(r.ok)
        let c = try XCTUnwrap(r.card)
        XCTAssertEqual(c.title, "你好，老板 👋")
        XCTAssertEqual(c.subtitle, "example-hello 0.1.0")
        guard case .list(let items) = c.blocks[1] else { return XCTFail("第二块应该是 list") }
        XCTAssertEqual(items.count, 4)
        XCTAssertEqual(items[0].symbol, "sidebar.left")
        guard case .table(let cols, let rows) = c.blocks[2] else { return XCTFail("第三块应该是 table") }
        XCTAssertEqual(cols, ["项", "值"])
        XCTAssertEqual(rows[0], ["打开次数", "3"])                                // 数字转文字
        guard case .buttons(let bs) = c.blocks[3] else { return XCTFail("第四块应该是 buttons") }
        XCTAssertEqual(bs.map(\.action), ["again", "roll"])
        XCTAssertEqual(bs[0].style, "primary")
        XCTAssertEqual(bs[1].payload, .object(["sides": .number(6)]))
        XCTAssertEqual(bs[1].payload?.jsonText, #"{"sides":6}"#)
        // 以后的小版本加了新块：丢掉，其余照画
        let future = try PluginCard.decode(#"{"title": "t", "blocks": [{"type": "chart", "data": [1]}, {"type": "text", "text": "x", "tone": "rainbow"}, {"type": "table", "columns": ["a", "b"], "rows": [["1"], [true, null, "extra"]]}]}"#)
        XCTAssertEqual(future.blocks.count, 2)
        XCTAssertEqual(future.blocks[0], .text("x", style: "body", tone: .neutral))
        XCTAssertEqual(future.blocks[1], .table(columns: ["a", "b"], rows: [["1", ""], ["是", ""]]))
    }

    func testCardViewStates() throws {
        let ok = String(decoding: try fixture("plugin_run_page.json"), as: UTF8.self)
        XCTAssertEqual(CardViewState.from(code: 0, out: ok, err: "").card?.title, "你好，老板 👋")
        // 插件失败：evo 退出码 3，stdout 照样是信封
        let off = String(decoding: try fixture("plugin_run_off.json"), as: UTF8.self)
        guard case .failed(let e) = CardViewState.from(code: 3, out: off, err: "") else { return XCTFail() }
        XCTAssertTrue(e.contains("还没打开"))
        XCTAssertEqual(CardViewState.from(code: 0, out: #"{"schema_version": 1, "ok": true, "plugin": "p", "kind": "notify_channel", "id": "x", "card": null, "error": null}"#, err: ""), .empty)
        guard case .failed(let e2) = CardViewState.from(code: 2, out: "", err: "evo: error: argument cmd: invalid choice: 'plugin'") else { return XCTFail() }
        XCTAssertTrue(e2.contains("还没有插件功能"))
        guard case .failed(let e3) = CardViewState.from(code: 0, out: #"{"schema_version": 2, "ok": true}"#, err: "") else { return XCTFail() }
        XCTAssertTrue(e3.contains("evo 版本比 App 新"))
        guard case .failed = CardViewState.from(code: 0, out: "hello", err: "") else { return XCTFail() }
        guard case .failed(let e4) = CardViewState.from(code: -1, out: "", err: "启动失败") else { return XCTFail() }
        XCTAssertEqual(e4, "启动失败")
        XCTAssertTrue(CardViewState.loading.isLoading)
    }

    func testComposerCommandMatching() throws {
        let cmds = try list().composerCommands
        XCTAssertEqual(PluginCommandParser.match("/hello 老板", commands: cmds), PluginCommandMatch(command: cmds[0], args: "老板"))
        XCTAssertEqual(PluginCommandParser.match("  /hello  ", commands: cmds)?.args, "")
        XCTAssertEqual(PluginCommandParser.match("/HELLO 两 个词", commands: cmds)?.args, "两 个词")
        XCTAssertEqual(PluginCommandParser.match("/hello\u{3000}全角空格", commands: cmds)?.args, "全角空格")
        XCTAssertNil(PluginCommandParser.match("/api 路径不对", commands: cmds))       // 不认识的 /词：照旧当反馈
        XCTAssertNil(PluginCommandParser.match("hello", commands: cmds))
        XCTAssertNil(PluginCommandParser.match("/", commands: cmds))
        XCTAssertNil(PluginCommandParser.match("/hello 老板", commands: []))
        XCTAssertEqual(PluginCommandParser.hints("/he", commands: cmds), ["/hello 名字 · 打个招呼"])
        XCTAssertEqual(PluginCommandParser.hints("/", commands: cmds).count, 1)
        XCTAssertTrue(PluginCommandParser.hints("/hello x", commands: cmds).isEmpty)
    }

    func testCLIArgs() {
        XCTAssertEqual(PluginCLI.list(), ["plugin", "list", "--json"])
        XCTAssertEqual(PluginCLI.setEnabled("p", true), ["plugin", "enable", "p"])
        XCTAssertEqual(PluginCLI.setEnabled("p", false), ["plugin", "disable", "p"])
        XCTAssertEqual(PluginCLI.run(plugin: "p", kind: "sidebar_page", id: "x"), ["plugin", "run", "p", "sidebar_page", "x", "--json"])
        XCTAssertEqual(PluginCLI.run(plugin: "p", kind: "composer_command", id: "c", args: "a b", action: "roll",
                                     payload: .object(["n": .number(2), "s": .string("x")]), project: "TB", item: "TB-1"),
                       ["plugin", "run", "p", "composer_command", "c", "--json", "--args", "a b", "--action", "roll",
                        "--payload", #"{"n":2,"s":"x"}"#, "--project", "TB", "--item", "TB-1"])
        XCTAssertEqual(PluginCLI.run(plugin: "p", kind: "k", id: "i", args: "", payload: .null, project: ""), ["plugin", "run", "p", "k", "i", "--json"])
    }

    func testSidebarItemForPlugin() {
        let s = SidebarItem.plugin("example-hello", "hello")
        XCTAssertEqual(s.title(projectName: { _ in nil }), "hello")
        XCTAssertEqual(s.sidebarHighlight, s)
        XCTAssertEqual(s.parent, .inbox)
        XCTAssertNotEqual(s, SidebarItem.plugin("example-hello", "other"))
    }
}
