import XCTest
@testable import EvoCore

/// 第十九轮：复现第十八轮「拨开关后卡 100 秒」那一类问题——子进程输出塞满管道、超时、孙进程拿着管道、并发很多条。
final class ProcessRunnerTests: XCTestCase {
    private let sh = "/bin/sh"

    func testBigOutputOnBothPipesDoesNotDeadlock() async {
        // 两条管道各 300KB（管道缓冲 64KB）：老写法只要有一条没人读就会互相等死
        let r = await ProcessRunner.run(sh, ["-c", "head -c 300000 /dev/zero | tr '\\0' a; head -c 200000 /dev/zero | tr '\\0' b >&2"], timeout: 20)
        XCTAssertEqual(r.code, 0)
        XCTAssertEqual(r.out.count, 300_000)
        XCTAssertEqual(r.err.count, 200_000)
        XCTAssertFalse(r.timedOut)
        XCTAssertLessThan(r.seconds, 10)
    }

    func testTimeoutKillsAndReports() async {
        let t0 = Date()
        let r = await ProcessRunner.run(sh, ["-c", "echo start; exec sleep 30"], timeout: 0.5)
        XCTAssertTrue(r.timedOut)
        XCTAssertNotEqual(r.code, 0)
        XCTAssertTrue(r.out.contains("start"))
        XCTAssertLessThan(Date().timeIntervalSince(t0), 6)
    }

    func testTimeoutEscalatesToKillWhenTermIgnored() async {
        let t0 = Date()
        let r = await ProcessRunner.run(sh, ["-c", "trap '' TERM; exec sleep 30"], timeout: 0.4, drainGrace: 0.5)
        XCTAssertTrue(r.timedOut)
        XCTAssertLessThan(Date().timeIntervalSince(t0), 8)
    }

    func testGrandchildHoldingPipeDoesNotHang() async throws {
        #if !os(macOS)
        // Linux 的 swift-corelibs Process 要等孙进程也退出才算「结束」（它的退出通知 fd 被孙进程继承了），
        // 和管道无关；真 App 只在 macOS 上跑，macOS 的 Process 按 waitpid 判退出。
        throw XCTSkip("只在 macOS 上有意义")
        #endif
        // 子进程退出了，后台孙进程还拿着 stdout：最多等 drainGrace 就交结果
        let t0 = Date()
        let r = await ProcessRunner.run(sh, ["-c", "sleep 20 & echo hi"], timeout: 30, drainGrace: 0.5)
        XCTAssertEqual(r.code, 0)
        XCTAssertTrue(r.out.contains("hi"))
        XCTAssertLessThan(Date().timeIntervalSince(t0), 5)
    }

    func testMissingExecutable() async {
        let r = await ProcessRunner.run("/nonexistent/evo-nope", [], timeout: 5)
        XCTAssertEqual(r.code, -1)
        XCTAssertTrue(r.err.contains("启动失败"))
    }

    func testManyConcurrentRunsAllFinish() async {
        // 状态刷新时几个项目 + feature / team / plugin 一起跑：40 条并发、每条 100KB 输出，全都要按时回来
        let t0 = Date()
        let codes = await withTaskGroup(of: Int.self) { g -> [Int] in
            for i in 0..<40 {
                g.addTask {
                    let r = await ProcessRunner.run(self.sh, ["-c", "head -c 100000 /dev/zero | tr '\\0' x; exit \(i % 3)"], timeout: 30)
                    return r.out.count == 100_000 ? Int(r.code) : -99
                }
            }
            var out: [Int] = []
            for await c in g { out.append(c) }
            return out
        }
        XCTAssertEqual(codes.count, 40)
        XCTAssertFalse(codes.contains(-99))
        XCTAssertEqual(codes.filter { $0 == 0 }.count, 14)
        XCTAssertLessThan(Date().timeIntervalSince(t0), 20)
    }

    func testEnvironmentAndCwd() async {
        let r = await ProcessRunner.run(sh, ["-c", "printf '%s|' \"$EVO_T\"; pwd"], environment: ["EVO_T": "老板", "PATH": "/usr/bin:/bin"],
                                        cwd: "/tmp", timeout: 5)
        XCTAssertTrue(r.out.hasPrefix("老板|"))
        XCTAssertTrue(r.out.contains("tmp"))
    }

    func testCallbackDeliveredExactlyOnce() {
        let exp = expectation(description: "done")
        exp.expectedFulfillmentCount = 1
        exp.assertForOverFulfill = true
        ProcessRunner.start(sh, ["-c", "echo ok"], timeout: 5, drainGrace: 0.2) { r in
            XCTAssertEqual(r.out, "ok\n")
            exp.fulfill()
        }
        wait(for: [exp], timeout: 5)
        // 再等过 grace，确认没有第二次回调（assertForOverFulfill 会炸）
        Thread.sleep(forTimeInterval: 0.5)
    }
}
