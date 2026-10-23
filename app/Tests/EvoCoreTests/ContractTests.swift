import XCTest
@testable import EvoCore

/// v0.6.0：接口定版本（ContractCheck、projects --json）。插件测试第二十四轮随插件一起删了（#16）。
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
