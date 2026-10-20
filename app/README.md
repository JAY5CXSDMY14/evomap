# Evo 菜单栏应用

evo 自动循环的 macOS 菜单栏外壳。SwiftUI 写的小壳，界面直接嵌现有网页面板，evo 本体（整套 kit）打包在应用里。
**全部用命令行维护**：Swift Package Manager + Makefile，没有 Xcode 工程，不用打开 Xcode。

- 系统：macOS 13 及以上；本机要有 Xcode 命令行工具或 Xcode（提供 `swift`、`codesign`、`hdiutil`）
- 体积：应用本身不到 5 MB（python3 用系统/Homebrew 的，不打包）
- 设计取舍见 `docs/app-packaging.md`

## 常用命令（都在 `app/` 目录下）

| 命令 | 做什么 |
|---|---|
| `make test` | 跑 EvoCore 单元测试（`swift test`） |
| `make build` | release 编译 |
| `make app` | 组装 `build/Evo.app`（Info.plist 带 `LSUIElement`，整套 kit 拷进 `Contents/Resources/evo`，ad-hoc 签名） |
| `make dmg` | 打 `build/Evo.dmg`（里面带「应用程序」快捷方式） |
| `make run` | 组装后直接打开 |
| `make install` | 拷进 `/Applications` 并打开 |
| `make clean` | 删 `.build` 和 `build` |
| `make version` | 显示版本号 |

可选变量：

- `SIGN="Developer ID Application: 名字 (TEAMID)" make dmg`：换正式证书；`SIGN= make app` 跳过签名
- `UNIVERSAL=1 make dmg`：出 arm64 + x86_64 通用包（默认只出本机架构）
- 改版本：编辑 `VERSION`（只写 `0.2.0` 这样的号），构建号自动取 git 提交数

## 目录

```
app/
  Package.swift          SwiftPM 清单（macOS 13+）
  VERSION                版本号
  Makefile               上面那些命令
  scripts/
    assemble-app.sh      组装 Evo.app、拷 kit、签名
    make-dmg.sh          打 dmg
  Resources/Info.plist.in  Info.plist 模板（__VERSION__ / __BUILD__ 构建时替换）
  Sources/EvoCore/       纯逻辑，可单测：status JSON 解码、角标计数、闸门去重、免打扰、心跳、找 python3
  Sources/Evo/           菜单栏外壳：菜单、面板窗口、通知、开机自启、设置、首次向导
  Tests/EvoCoreTests/    单元测试 + Fixtures/ 样例 JSON
```

改逻辑尽量放 EvoCore 并补测试；`Sources/Evo` 只做界面和系统调用。

## 应用做什么

- **菜单栏图标**：数字 = 所有项目「等你点头」件数之和。每 30 秒跑一遍 `evo projects` 和每个项目的 `evo -p 代号 status --json`。接棒器停了图标变成警告三角，循环暂停时变成暂停图标。
- **菜单**：每个项目一行（等你几件、施工几件、卡住几件），有闸门的项目可以展开看每个闸门；打开面板；立即 tick（每个项目 `evo -p 代号 tick`）；暂停/恢复循环；看门狗状态（每个项目上次转动多久前，超过 `limits.heartbeat_stale_minutes` 显示红点）；设置；退出。
- **打开面板**：先从钥匙串（`evoloop-panel` / `evo`，和 `evo panel` 同一处）拿口令，探测 `http://127.0.0.1:端口`；没在跑就由应用起一个 `evo panel --port 端口`（日志 `~/.evoloop/logs/app-panel.log`，退出 Evo 时一起关），然后在内嵌窗口里打开。面板之外的链接交给默认浏览器。
- **原生通知**：新冒出的闸门（按「项目/闸门号」去重，重启也记得）和接棒器停了（停一次只报一次，恢复后再停再报）。读全局配置 `notify.quiet_hours`，免打扰时段不弹、结束后补发。面板窗口正在看时不弹横幅。点通知打开面板。
- **开机自启**：设置里开关，用 `SMAppService.mainApp`。
- **首次向导**：检查 python3、git、orca、gh、magpie（`magpie_url/v1/models`）、`~/.evoloop`、launchd 常驻；一键跑包里的 `install.sh`（只检查）或 `install.sh --apply [--link]`，输出显示在窗口里。

### 和 evo 自己的提醒的关系

evo 配了 `notify.macos: true` 时会用 `osascript` 自己弹一条通知；装了 Evo 之后可以在 `~/.evoloop/config.json` 里把它改成 `false`，免得同一件弹两次。Telegram、邮件不受影响。

### 暂停/恢复是怎么做的

暂停 = `launchctl bootout gui/$UID/com.evoloop.autopilot`（plist 留着），恢复 = `launchctl bootstrap`。没装常驻时这一项显示为灰。plist 在 `~/Library/LaunchAgents` 里，**重新登录后会自动恢复**。

### 用应用自带的 evo 还是自己的

默认用 `Evo.app/Contents/Resources/evo/bin/evo`。在仓库里改 kit、想让应用直接用工作副本：设置 → evo 路径填 `~/…/evoloop/kit/bin/evo`。

向导里点「安装（--apply）」时，launchd 常驻会指向**应用里的** evo，所以要先把 Evo.app 拖进「应用程序」再装，之后别挪。升级应用（覆盖 `/Applications/Evo.app`）后路径不变，常驻下次重启就用新版。

包里 `Resources/evo/bin` 是只读的：常驻进程用包里的 evo 时 python 写不进 `__pycache__`，不会弄坏签名。

## 第一次打开（ad-hoc 签名）

1. 打开 `Evo.dmg`，把 Evo 拖进「应用程序」
2. 第一次在「应用程序」里**右键 Evo → 打开 → 打开**（没花 99 美元签名，Gatekeeper 会拦一次；macOS 15 起要去 系统设置 → 隐私与安全性 → 仍要打开）
3. 允许通知；第一次拿面板口令如果弹「Evo 想使用钥匙串」，点「始终允许」
4. 首次向导里看检查结果，需要的话点「安装」

## CI

`.github/workflows/app.yml`：改动 `app/**` 时在 macos-14 上跑 `swift test` → `make dmg` → 检查包内容、用空的 `EVO_HOME` 跑一次包里的 evo → 上传构件 **Evo.dmg**（保留 30 天）。手动触发：Actions → app → Run workflow。

下载最新构件（要 gh 已登录）：

```bash
gh run download -R JAY5CXSDMY14/evomap -n Evo.dmg
```

## Linux 上跑 EvoCore 测试

`Sources/Evo` 全部包在 `#if os(macOS)` 里，Linux 上装了 Swift 工具链也能 `swift test`（只测 EvoCore）。
