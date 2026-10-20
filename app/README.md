# Evo 菜单栏应用

evo 自动循环的 macOS 菜单栏外壳。SwiftUI 写的小壳：菜单栏弹窗里直接批闸门、跟 evo 说话；完整界面嵌现有网页面板；evo 本体（整套 kit）打包在应用里。

v0.2.0 起界面按 Claude 的样子重做（暖象牙底、陶土色强调、serif 标题），加了吉祥物「小陶」和 QQ 弹弹的弹簧动效，截图见 `docs/screenshots/`。

| 浅色 | 深色 |
|---|---|
| ![弹窗 浅色](docs/screenshots/popover-light.png) | ![弹窗 深色](docs/screenshots/popover-dark.png) |
**全部用命令行维护**：Swift Package Manager + Makefile，没有 Xcode 工程，不用打开 Xcode。

- 系统：macOS 13 及以上；本机要有 Xcode 命令行工具或 Xcode（提供 `swift`、`codesign`、`hdiutil`）
- 体积：Evo.app 约 1 MB、Evo.dmg 约 400 KB（python3 用系统/Homebrew 的，不打包）
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
| `make snapshots` | 用假数据把主要界面画成 PNG（`build/snapshots/`，浅色 + 深色，2 倍）；要在 Mac 上跑 |
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
  Sources/EvoCore/       纯逻辑，可单测：status JSON 解码、角标计数、闸门去重、免打扰、心跳、找 python3，
                         以及界面数据映射（ViewModels.swift：问候、状态胶囊、闸门卡片、项目行、吉祥物心情与台词、
                         模糊过滤、命令面板条目、输入框命令、收菜清单、快捷键；MascotPose.swift：吉祥物每一帧的姿态）
  Sources/Evo/           菜单栏外壳：
    Theme.swift          设计令牌（颜色、字体、圆角）+ 弹簧按钮、卡片、依次弹入、开关样式
    Mascot.swift         吉祥物「小陶」矢量画、菜单栏单色小脸、聊天气泡
    MainPopover.swift    菜单栏弹窗（头部、等你处理卡片、项目行、快捷胶囊、输入框）
    Palette.swift        ⌘K 命令面板
    Windows.swift        设置、首次向导
    Snapshots.swift      make snapshots 用的假数据和出图
    AppState / Panel / Notifier / Shell   轮询、面板窗口、通知、跑命令
  Tests/EvoCoreTests/    单元测试 + Fixtures/ 样例 JSON
  docs/screenshots/      CI 出的界面截图
```

改逻辑尽量放 EvoCore 并补测试；`Sources/Evo` 只做界面和系统调用。

## 应用做什么

- **菜单栏图标**：小陶的单色小脸（随心情变：有事等你挑眉、停了皱眉、暂停闭眼）+ 数字 = 所有项目「等你点头」件数之和。每 30 秒跑一遍 `evo projects` 和每个项目的 `evo -p 代号 status --json`。
- **弹窗**（点图标，`MenuBarExtra` 窗口样式）：
  - 头部：小陶 + 「晚上好，老板」+ 时间 + 状态胶囊（运行中 / 已暂停 / 心跳过期 / 出错了）；小陶用气泡说一句现状（「有 2 件等你看效果」），动作结果也从这里冒出来。
  - **等你处理**：每个闸门一张卡（项目、件号、标题、做不做 / 看效果 / 上线、等了多久），卡上直接点：
    第一个按钮 = 闸门第一个选项（通过 / 做 / 上线 / 同意），第二个 = 第二个选项（打回 / 不做 / 再等等 / 不同意）。
    看效果打回会先展开一行让你写原话。都是跑 `evo -p 代号 approve 闸门号 选项 [原话]`。点了卡片先弹走，evo 回话失败再弹回来。
  - **项目**：每个项目一行，施工 / 验收 / 等你 / 卡住 四个数（卡住 = `stuck`，有 `no_live_path` 时取两者较大），下面一行小字是卡太久件数和岗位状态（有这些字段时）；点一行只看这个项目的闸门。
  - **快捷胶囊**：立即 tick、打开面板、暂停 / 恢复、收菜清单（已合并待上线的件，一键 `evo ship` 建上线闸门）。
  - **输入框「告诉 evo…」**：选项目、选方式后回车。「反馈」= `evo -p 代号 feedback 原话`（进 GitHub issue，决策岗分拣）；「新件」= `evo -p 代号 add --title 标题 --scope .`（24 字内，可勾「要看效果」加 `--look`）。evo 的回话以小陶气泡显示。
  - 一切顺利时显示叶子空状态「一切顺利」。
- **快捷键**（弹窗里）：⌘1…⌘9 只看第几个项目（再按一次取消）、⌘↩ 通过当前卡片（鼠标停的那张，没有就第一张）、⌘K 命令面板、⌘R 刷新、⌘, 设置、⌘Q 退出。
- **⌘K 命令面板**：动作、每个闸门的通过 / 打回、每个项目都在里面，输入即模糊过滤（中文、英文都行），↑↓ 选、回车执行、Esc 关。
- **打开面板**：先从钥匙串（`evoloop-panel` / `evo`，和 `evo panel` 同一处）拿口令，探测 `http://127.0.0.1:端口`；没在跑就由应用起一个 `evo panel --port 端口`（日志 `~/.evoloop/logs/app-panel.log`，退出 Evo 时一起关），然后在内嵌窗口里打开。面板之外的链接交给默认浏览器。
- **原生通知**：新冒出的闸门（按「项目/闸门号」去重，重启也记得）和接棒器停了（停一次只报一次，恢复后再停再报）。读全局配置 `notify.quiet_hours`，免打扰时段不弹、结束后补发。面板窗口正在看时不弹横幅。点通知打开面板。
- **开机自启**：设置里开关，用 `SMAppService.mainApp`。
- **首次向导**：三步卡片（检查这台 Mac → 装好常驻 → 开始用）。检查 python3、git、orca、gh、magpie（`magpie_url/v1/models`）、`~/.evoloop`、launchd 常驻；一键跑包里的 `install.sh`（只检查）或 `install.sh --apply [--link]`，输出显示在窗口里。

### 动效和无障碍

- 按钮、胶囊按下压到 0.92、松手弹过头到 1.04 再回来（`spring(response: 0.3, dampingFraction: 0.55)`）；卡片依次弹入；批过的卡片缩小飞走；「等你处理」数字变了会晃一下；状态胶囊换状态时弹一下。
- 小陶五种心情：顺利（几秒眨一次眼）、干活（东张西望、轻轻上下）、等你（挑眉、弹弹）、卡住或出错（皱眉担心）、暂停（闭眼、冒 z）。
- 系统设置里开了「减弱动态效果」：不弹不跳，只淡入淡出，小陶不上下动。
- 卡片、项目行、按钮、小陶都有读屏标签（VoiceOver 念「土布，看效果：注册页按钮…，件号 TB-UX-003」这类整句）。

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

`.github/workflows/app.yml`：改动 `app/**` 时在 macos-14 上跑 `swift test` → `make dmg` → 检查包内容、用空的 `EVO_HOME` 跑一次包里的 evo → `make snapshots` → 上传构件 **Evo.dmg** 和 **snapshots**（界面截图，保留 30 天）。手动触发：Actions → app → Run workflow。

下载最新构件（要 gh 已登录）：

```bash
gh run download -R JAY5CXSDMY14/evomap -n Evo.dmg
gh run download -R JAY5CXSDMY14/evomap -n snapshots -D docs/screenshots   # 更新截图
```

## Linux 上跑 EvoCore 测试

`Sources/Evo` 全部包在 `#if os(macOS)` 里，Linux 上装了 Swift 工具链也能 `swift test`（只测 EvoCore）。
