#if os(macOS)
import Foundation
import EvoCore

struct RunResult {
    var code: Int32
    var out: String
    var err: String
    var ok: Bool { code == 0 }
    /// 出错时给人看的一句（取 stderr 末尾，没有就 stdout）。
    var tail: String {
        let t = (err.isEmpty ? out : err).trimmingCharacters(in: .whitespacesAndNewlines)
        return String(t.suffix(300))
    }
}

/// 应用里所有路径与环境：bundled evo 在 Evo.app/Contents/Resources/evo（整套 kit：bin、panel、roles、install.sh…）。
enum EvoEnv {
    static let defaults = UserDefaults.standard
    static var home: String { NSHomeDirectory() }
    static var evoRoot: URL { URL(fileURLWithPath: home).appendingPathComponent(".evoloop") }
    static var globalConfig: URL { evoRoot.appendingPathComponent("config.json") }

    /// 打包进应用的 kit 目录；`swift run` 开发时退回到仓库里的 ../kit。
    static var kitDir: URL? {
        if let r = Bundle.main.resourceURL?.appendingPathComponent("evo"),
           FileManager.default.fileExists(atPath: r.appendingPathComponent("bin/evo").path) { return r }
        let dev = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("../kit").standardized
        return FileManager.default.fileExists(atPath: dev.appendingPathComponent("bin/evo").path) ? dev : nil
    }

    /// 设置里填了 evo 路径就用它（比如想用自己 git 仓库里的 kit），否则用应用自带的。
    static var evoScript: String? {
        if let o = defaults.string(forKey: "evoPath")?.trimmingCharacters(in: .whitespaces), !o.isEmpty {
            return (o as NSString).expandingTildeInPath
        }
        return kitDir?.appendingPathComponent("bin/evo").path
    }

    static var installScript: String? {
        guard let s = evoScript else { return nil }
        let p = URL(fileURLWithPath: s).deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("install.sh").path
        return FileManager.default.fileExists(atPath: p) ? p : nil
    }

    static var python: String? {
        let fm = FileManager.default
        let clt = fm.fileExists(atPath: "/Library/Developer/CommandLineTools/usr/bin/python3")
            || fm.fileExists(atPath: "/Applications/Xcode.app/Contents/Developer/usr/bin/python3")
        return PythonLocator.pick(override: defaults.string(forKey: "pythonPath"),
                                  isExecutable: { fm.isExecutableFile(atPath: $0) }, systemStubUsable: clt)
    }

    static var environment: [String: String] {
        var e = ProcessInfo.processInfo.environment
        e["PATH"] = ToolPath.augmented(e["PATH"], home: home)
        e["PYTHONIOENCODING"] = "utf-8"
        e["PYTHONDONTWRITEBYTECODE"] = "1"      // 别往签过名的 .app 里写 __pycache__
        if e["LANG"] == nil { e["LANG"] = "zh_CN.UTF-8" }
        return e
    }

    static func loadConfig() -> GlobalConfig {
        GlobalConfig.parse(try? Data(contentsOf: globalConfig))
    }
}

private final class DataBox: @unchecked Sendable { var data = Data() }

enum Shell {
    /// 跑一个命令，收齐 stdout/stderr。超时就 terminate。不阻塞主线程。
    static func run(_ exe: String, _ args: [String], timeout: TimeInterval = 120) async -> RunResult {
        await withCheckedContinuation { cont in
            DispatchQueue.global(qos: .userInitiated).async {
                cont.resume(returning: runSync(exe, args, timeout: timeout))
            }
        }
    }

    static func runSync(_ exe: String, _ args: [String], timeout: TimeInterval) -> RunResult {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: exe)
        p.arguments = args
        p.environment = EvoEnv.environment
        p.currentDirectoryURL = URL(fileURLWithPath: EvoEnv.home)
        let o = Pipe(), e = Pipe()
        p.standardOutput = o; p.standardError = e; p.standardInput = FileHandle.nullDevice
        do { try p.run() } catch {
            return RunResult(code: -1, out: "", err: "启动失败：\(exe) \(error.localizedDescription)")
        }
        let ob = DataBox(), eb = DataBox(), g = DispatchGroup()
        g.enter(); DispatchQueue.global().async { ob.data = o.fileHandleForReading.readDataToEndOfFile(); g.leave() }
        g.enter(); DispatchQueue.global().async { eb.data = e.fileHandleForReading.readDataToEndOfFile(); g.leave() }
        let killer = DispatchWorkItem { if p.isRunning { p.terminate() } }
        DispatchQueue.global().asyncAfter(deadline: .now() + timeout, execute: killer)
        p.waitUntilExit()
        killer.cancel()
        // 子进程可能留下继承了管道的后台进程（比如 orca），退出后最多再等 2 秒收尾
        _ = g.wait(timeout: .now() + 2)
        return RunResult(code: p.terminationStatus, out: String(decoding: ob.data, as: UTF8.self),
                         err: String(decoding: eb.data, as: UTF8.self))
    }

    /// 用找到的 python3 跑 evo。
    static func evo(_ args: [String], timeout: TimeInterval = 120) async -> RunResult {
        guard let py = EvoEnv.python else {
            return RunResult(code: -1, out: "", err: "找不到 python3（设置里可以手动填路径；或 brew install python）")
        }
        guard let script = EvoEnv.evoScript else {
            return RunResult(code: -1, out: "", err: "找不到 evo（应用包里缺 Resources/evo，或设置里的路径不对）")
        }
        return await run(py, [script] + args, timeout: timeout)
    }

    /// 在补过的 PATH 里找命令。
    static func which(_ name: String) async -> String? {
        let r = await run("/usr/bin/which", [name], timeout: 5)
        let p = r.out.trimmingCharacters(in: .whitespacesAndNewlines)
        return r.ok && !p.isEmpty ? p : nil
    }
}

/// 常驻进程（install.sh 装的 launchd 任务 com.evoloop.autopilot）的暂停与恢复。
/// 暂停 = launchctl bootout（plist 留着）；恢复 = launchctl bootstrap。注意：plist 在 LaunchAgents 里，重新登录后会自动恢复。
enum Launchd {
    static let label = "com.evoloop.autopilot"
    static var plist: String { "\(EvoEnv.home)/Library/LaunchAgents/\(label).plist" }
    static var domain: String { "gui/\(getuid())" }
    static var installed: Bool { FileManager.default.fileExists(atPath: plist) }

    static func isLoaded() async -> Bool {
        await Shell.run("/bin/launchctl", ["print", "\(domain)/\(label)"], timeout: 10).ok
    }

    static func pause() async -> RunResult {
        await Shell.run("/bin/launchctl", ["bootout", "\(domain)/\(label)"], timeout: 20)
    }

    static func resume() async -> RunResult {
        await Shell.run("/bin/launchctl", ["bootstrap", domain, plist], timeout: 20)
    }
}
#endif
