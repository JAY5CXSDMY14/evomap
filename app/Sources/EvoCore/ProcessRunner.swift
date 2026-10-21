import Foundation

/// 第十九轮：跑子进程的唯一入口（App 里的 Shell.run 全走它）。
///
/// 第十八轮 CI 实机演示里，拨一个功能开关后 App 约 100 秒收不到 `evo feature off` 的结果（同一命令 0.17 秒）。
/// 老写法在 GCD 全局队列上 `waitUntilExit()` + 两个 `readDataToEndOfFile()` + `DispatchGroup.wait`，每条命令占住 3 个
/// GCD 线程直到子进程结束；状态刷新时几个项目一起跑，再加上 evo watch 的读回调也排在同一个全局队列上，线程一紧张，
/// 读回调和续体全都排队。新写法：
/// - 不调用 `waitUntilExit`、不 `wait` 任何东西：退出靠 `terminationHandler`，结果靠续体一次性交回；
/// - stdout / stderr 各一条专用读线程（不占 GCD 池、也不占 Swift 并发池），边出边读，管道永远不会塞满（>64KB 也不会死锁）；
/// - 超时先 SIGTERM，2 秒后还在就 SIGKILL，结果里 `timedOut = true`；
/// - 子进程退出后，继承了管道的孙进程可能还开着写端：最多再等 `drainGrace` 秒就交结果，不无限等 EOF。
public struct ProcessOutput: Sendable, Equatable {
    public var code: Int32
    public var out: String
    public var err: String
    public var timedOut: Bool
    public var seconds: Double

    public init(code: Int32, out: String, err: String, timedOut: Bool = false, seconds: Double = 0) {
        self.code = code; self.out = out; self.err = err; self.timedOut = timedOut; self.seconds = seconds
    }
}

public enum ProcessRunner {
    /// 输出上限（每条管道）：超过就只留开头这么多，后面照读照丢（不让管道塞住，也不让内存涨爆）。
    public static let maxCapture = 8 * 1024 * 1024

    public static func run(_ exe: String, _ args: [String], environment: [String: String]? = nil,
                           cwd: String? = nil, timeout: TimeInterval = 120, drainGrace: TimeInterval = 2) async -> ProcessOutput {
        await withCheckedContinuation { (cont: CheckedContinuation<ProcessOutput, Never>) in
            start(exe, args, environment: environment, cwd: cwd, timeout: timeout, drainGrace: drainGrace) { cont.resume(returning: $0) }
        }
    }

    /// 回调版（不阻塞调用线程；回调在任意线程上调一次）。
    public static func start(_ exe: String, _ args: [String], environment: [String: String]? = nil, cwd: String? = nil,
                             timeout: TimeInterval, drainGrace: TimeInterval = 2, done: @escaping @Sendable (ProcessOutput) -> Void) {
        let t0 = Date()
        let p = Process()
        p.executableURL = URL(fileURLWithPath: exe)
        p.arguments = args
        if let environment { p.environment = environment }
        if let cwd { p.currentDirectoryURL = URL(fileURLWithPath: cwd) }
        let o = Pipe(), e = Pipe()
        p.standardOutput = o
        p.standardError = e
        p.standardInput = FileHandle.nullDevice
        let job = Job(done: done, t0: t0)
        p.terminationHandler = { proc in job.exited(proc.terminationStatus, grace: drainGrace) }
        do {
            try p.run()
        } catch {
            job.finishNow(ProcessOutput(code: -1, out: "", err: "启动失败：\(exe) \(error.localizedDescription)"))
            return
        }
        // 父进程这边的写端 Foundation 在 run() 之后会关掉（两个平台都是），读线程能等到 EOF
        job.read(o.fileHandleForReading, isOut: true)
        job.read(e.fileHandleForReading, isOut: false)
        let pid = p.processIdentifier
        DispatchQueue.global().asyncAfter(deadline: .now() + timeout) {
            guard job.isRunning else { return }
            job.markTimedOut()
            kill(pid, SIGTERM)
            DispatchQueue.global().asyncAfter(deadline: .now() + 2) { if job.isRunning { kill(pid, SIGKILL) } }
        }
    }

    /// 一次运行的共享状态（锁保护）。结果只交一次。
    final class Job: @unchecked Sendable {
        private let lock = NSLock()
        private var out = Data(), err = Data()
        private var outEOF = false, errEOF = false
        private var code: Int32?
        private var timedOut = false
        private var delivered = false
        private let done: @Sendable (ProcessOutput) -> Void
        private let t0: Date

        init(done: @escaping @Sendable (ProcessOutput) -> Void, t0: Date) { self.done = done; self.t0 = t0 }

        var isRunning: Bool { lock.lock(); defer { lock.unlock() }; return code == nil && !delivered }

        func markTimedOut() { lock.lock(); timedOut = true; lock.unlock() }

        func read(_ h: FileHandle, isOut: Bool) {
            let th = Thread { [self] in
                while true {
                    let d = h.availableData          // 阻塞的只是这条专用线程
                    if d.isEmpty { break }
                    lock.lock()
                    if isOut { if out.count < ProcessRunner.maxCapture { out.append(d.prefix(ProcessRunner.maxCapture - out.count)) } }
                    else if err.count < ProcessRunner.maxCapture { err.append(d.prefix(ProcessRunner.maxCapture - err.count)) }
                    lock.unlock()
                }
                lock.lock()
                if isOut { outEOF = true } else { errEOF = true }
                lock.unlock()
                tryFinish()
            }
            th.name = isOut ? "evo-proc-out" : "evo-proc-err"
            th.start()
        }

        func exited(_ status: Int32, grace: TimeInterval) {
            lock.lock(); code = status; lock.unlock()
            tryFinish()
            // 孙进程拿着管道不放：退出后最多再等 grace 秒，收到多少交多少
            DispatchQueue.global().asyncAfter(deadline: .now() + grace) { [self] in tryFinish(force: true) }
        }

        func finishNow(_ r: ProcessOutput) {
            lock.lock()
            guard !delivered else { lock.unlock(); return }
            delivered = true
            lock.unlock()
            done(r)
        }

        private func tryFinish(force: Bool = false) {
            lock.lock()
            guard !delivered, let c = code, force || (outEOF && errEOF) else { lock.unlock(); return }
            delivered = true
            let r = ProcessOutput(code: c, out: String(decoding: out, as: UTF8.self), err: String(decoding: err, as: UTF8.self),
                                  timedOut: timedOut, seconds: Date().timeIntervalSince(t0))
            lock.unlock()
            done(r)
        }
    }
}
