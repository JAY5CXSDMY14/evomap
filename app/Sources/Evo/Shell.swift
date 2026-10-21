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

enum Shell {
    /// 跑一个命令，收齐 stdout/stderr。第十九轮起全走 EvoCore.ProcessRunner：不 waitUntilExit、不占 GCD 线程，
    /// 两条专用读线程边出边读（输出再大管道也不会塞住），超时 SIGTERM → 2 秒后 SIGKILL。
    static func run(_ exe: String, _ args: [String], timeout: TimeInterval = 120) async -> RunResult {
        let r = await ProcessRunner.run(exe, args, environment: EvoEnv.environment, cwd: EvoEnv.home, timeout: timeout)
        if r.seconds > 5 { DemoLog.note("慢命令 \(String(format: "%.1f", r.seconds))s：\(([URL(fileURLWithPath: exe).lastPathComponent] + args.prefix(4)).joined(separator: " "))") }
        var err = r.err
        if r.timedOut { err += (err.isEmpty ? "" : "\n") + "超过 \(Int(timeout)) 秒没跑完，已停掉" }
        return RunResult(code: r.code, out: r.out, err: err)
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
