# Evo 菜单栏应用

evo 自动循环的 macOS 菜单栏外壳。SwiftUI 写的小壳：菜单栏弹窗里直接批闸门、跟 evo 说话；完整界面嵌现有网页面板；evo 本体（整套 kit）打包在应用里。

v0.6.0 起**能装插件**：丢一个文件夹进 `~/.evoloop/plugins/`，侧栏多一页、输入框多一个 `/命令`、通知多一个渠道，不用改 App（见下面 v0.6.0 和 `../docs/plugins.md`）；App 读 evo 的 JSON 接口都带版本号（`../docs/app-contract.md`）。

v0.3.0 起有了**真正的 Mac 窗口**（Claude 桌面版的样子：左侧栏、宽内容区、底部钉着输入框、统一标题栏和工具栏），菜单栏弹窗变成紧凑的速览；吉祥物换成 aora-bot 表情引擎的球形角色，v0.5.0 起叫 **调度球**（可切 云宝 / 亮亮）。实机截图和录屏见 `docs/mac-demo/`。

> **⚠️ 角色许可：只许自用。** 默认角色调度球的形象来自 sam70361/aora-bot 的 emotion-ball（固定版本 e3b6148）。它的**球形视觉形象只许个人学习研究、非商业使用，永远不给商业授权**，所以带调度球的 Evo **不得公开分发**（不发 Release、不放公开下载、不卖）。
> 哪天要分发：先在设置里换成 mood-mates 的云宝 / 亮亮并**向作者买商业许可**（1251579308@qq.com），或换成我们自己的角色。许可原文和 NOTICE 在 `Resources/vendor/`。

| 主窗口（浅色） | 主窗口（深色） |
|---|---|
| ![主窗口](docs/mac-demo/03-window.png) | ![深色](docs/mac-demo/11-dark-item.png) |

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
| `scripts/mac-demo.sh build/Evo.app build/mac-demo` | 在真桌面上用假 evo 把应用点一遍：全屏截图 + mp4 录屏（要 `brew install ffmpeg cliclick`，终端要有辅助功能和录屏权限） |
| `make clean` | 删 `.build` 和 `build` |
| `make version` | 显示版本号 |

可选变量：

- `SIGN="Developer ID Application: 名字 (TEAMID)" make dmg`：换正式证书；`SIGN= make app` 跳过签名
- `UNIVERSAL=1 make dmg`：出 arm64 + x86_64 通用包（默认只出本机架构）
- 改版本：编辑 `VERSION`（只写 `0.6.0` 这样的号），构建号自动取 git 提交数

## 目录

```
app/
  Package.swift          SwiftPM 清单（macOS 13+）
  VERSION                版本号
  Makefile               上面那些命令
  scripts/
    assemble-app.sh      组装 Evo.app、拷 kit、签名
    make-dmg.sh          打 dmg
    make-icon.py         画应用图标（numpy + Pillow，出 AppIcon.png / AppIcon.icns，结果提交进仓库，构建不依赖它）
  Resources/Info.plist.in  Info.plist 模板（__VERSION__ / __BUILD__ 构建时替换；CFBundleIconFile = AppIcon）
  Resources/AppIcon.icns   应用图标「调度球」（奶油底 + 珊瑚橙球从右下角探头，老板 10-21 选定）（AppIcon.png 是 1024 原图），scripts/make-icon.py 用代码画
  Resources/mate/index.html  表情角色宿主页（本地、不联网），Swift 调 evoMate.set(编号) / evoMate.gaze(x, y)
  Resources/vendor/      第三方表情引擎（aora-bot e3b6148）：emotion-ball/js（调度球）、mood-mates/src（云宝 / 亮亮）+ 许可 + NOTICE.md
  Sources/EvoCore/       纯逻辑，可单测：status JSON 解码、角标计数、闸门去重、免打扰、心跳、找 python3，
                         以及界面数据映射（ViewModels.swift：问候、状态胶囊、闸门卡片、项目行、吉祥物心情与台词、
                         模糊过滤、命令面板条目、输入框命令、收菜清单、快捷键；MascotPose.swift：菜单栏小脸的姿态；
                         MateMood.swift：evo 状态 → 表情编号；MateMotion.swift：眼睛跟鼠标的偏移、眨眼间隔、状态弹跳；ItemLog.swift：evo log --json；Navigation.swift：侧栏、
                         卡太久清单、网格列数、窗口尺寸、演示脚本）
  Sources/Evo/           菜单栏外壳：
    Theme.swift          设计令牌（颜色、字体、圆角）+ 弹簧按钮、卡片、依次弹入、开关样式
    MainWindow.swift     主窗口（NavigationSplitView 侧栏 + 详情、工具栏、闸门网格、项目页、件时间线、底部输入框）
    MateView.swift       表情角色：透明 WKWebView + JS 桥；眼睛跟鼠标、呼吸、眨眼、挤压回弹、状态弹跳（SwiftUI 弹簧）；截图用的静态帧
    Demo.swift           CI 录屏用：控件坐标导出（EVO_UITEST_GEOMETRY）、应用自演（EVO_DEMO=1）
    Mascot.swift         旧小陶矢量画（现在只用作菜单栏单色小脸和兜底）、聊天气泡
    MainPopover.swift    菜单栏弹窗（紧凑：问候、汇总、前两张闸门卡、打开窗口）
    Palette.swift        ⌘K 命令面板
    Windows.swift        设置、首次向导
    PluginViews.swift    v0.6.0 插件：通用卡片渲染器（三态）、插件页、件按钮、设置里的开关、接口版本横幅
    Snapshots.swift      make snapshots 用的假数据和出图
    AppState / Panel / Notifier / Shell   轮询、面板窗口、通知、跑命令
  Tests/EvoCoreTests/    单元测试 + Fixtures/ 样例 JSON
  scripts/mac-demo.sh    实机演示：真鼠标点一遍 + 截图 + 录屏；scripts/demo/ 是假 evo 和假状态
  docs/screenshots/      make snapshots 出的组件截图
  docs/mac-demo/         CI 在真 macOS 桌面上拍的整屏截图（mp4 不进仓库，在构件 mac-demo 里）
```

改逻辑尽量放 EvoCore 并补测试；`Sources/Evo` 只做界面和系统调用。

## 应用做什么

- **菜单栏图标**：单色小脸（沿用原来的矢量小陶，template 图）+ 数字 = 所有项目「等你点头」件数之和。每 30 秒跑一遍 `evo projects` 和每个项目的 `evo -p 代号 status --json`。
- **主窗口**（弹窗里「打开 Evo 窗口」、⌘0、点 Dock 图标、命令面板）：开着时 Dock 里有图标（activation policy 切到 regular），关掉回到纯菜单栏。最小 900×600，记住位置大小，统一标题栏，跟随深色模式。
  - **侧栏**：顶部角色 + 「晚上好，老板」+ 气泡说现状；「等你处理」带件数；项目列表（心跳圆点、等你件数、⌘1…⌘9）；「卡太久」（no_live_path / stale 明细）；最下面「设置」。
  - **等你处理**：闸门卡片网格，宽了两列、三列（每列至少 340 点）；卡上通过 / 打回（看效果打回先写原话）/ 时间线；通过的卡往右上飞走，角色「任务完成」撒花。下面是项目小卡。
  - **项目页**：施工 / 验收 / 等你 / 卡住 / 已合并五个大数字、这个项目的闸门、件列表（点进去看时间线）、最近动静。
  - **件详情**：`evo -p 代号 log 件号 --json` 的时间线（新的在上：登记、派活、交卷、返工、开闸门、你点了头…），右边是交卷说、看效果要看的几处、产出物、改了哪些文件、你说过的话。产出物清单：evo log 现在还不输出（只有面板 /api/artifacts 有），应用已经认 `artifacts` 字段，没有时提示去面板看。
  - **底部输入框**「告诉 evo…」：像 Claude 一样钉在内容区底部，上面是最近几句对话，evo 的回话旁边是角色（回话 / 出错表情）。
  - **工具栏**：状态胶囊（+ 正在做的事）、立即 tick、暂停 / 恢复、打开面板、⌘K。
- **弹窗**（点图标）：宽 420、更矮：问候 + 状态胶囊 + 角色气泡、一行汇总（等你 / 施工 / 验收 / 卡住 / 卡太久）、最前面两张闸门卡（多的「还有 N 件，去窗口里看」）、「打开 Evo 窗口 ⌘0」大按钮、底栏（刷新时间、tick、暂停、⌘K、设置、退出）。
- **表情角色**（调度球 / 云宝 / 亮亮，设置里切）：透明 WKWebView 跑本地宿主页，规则表挡掉所有网络请求，不加载任何网络字体。表情跟着 evo 走：

  | evo 状态 | 表情编号 |
  |---|---|
  | 顺利 | 02 待机 |
  | 施工中 / 还在读 | 30 思考 / 40 检索 |
  | 有闸门等你 | 35 等待输入（聆听） |
  | 你点了通过、有件合并 | 33 任务完成 + 撒花 |
  | 你打回、输入框发出去 | 31 接收任务 |
  | evo 回话 / 出错 | 39 输出回复 / 34 出错 |
  | 卡住、没活路、心跳过期、evo 跑不起来 | 34 出错 |
  | 暂停、免打扰时段 | 00 睡眠 |
  | 应用刚启动 | 01 唤醒 |

  鼠标进到调度球周围（约 3 倍球径）眼睛跟着看，见下面 v0.5.0；小号实例眼睛放大 1.5～1.8 倍、关粒子（lite）；开了「减弱动态效果」只画静态一帧。映射表在 EvoCore（MateMap），有单元测试。
- **快捷键**（窗口里）：⌘1…⌘9 选第几个项目、⌘↩ 通过第一张卡、⌘K 命令面板、⌘R 刷新、⌘[ 返回上一级。菜单栏「窗口 → 打开 Evo 窗口」⌘0，「Evo」菜单里有 tick、刷新、命令面板、切换深色 / 浅色、设置。
- **快捷键**（弹窗里）：⌘0 打开窗口、⌘1…⌘9 只看第几个项目（再按一次取消）、⌘↩ 通过当前卡片（鼠标停的那张，没有就第一张）、⌘K 命令面板、⌘R 刷新、⌘, 设置、⌘Q 退出。
- **⌘K 命令面板**：动作、每个闸门的通过 / 打回、每个项目都在里面，输入即模糊过滤（中文、英文都行），↑↓ 选、回车执行、Esc 关。
- **打开面板**：先从钥匙串（`evoloop-panel` / `evo`，和 `evo panel` 同一处）拿口令，探测 `http://127.0.0.1:端口`；没在跑就由应用起一个 `evo panel --port 端口`（日志 `~/.evoloop/logs/app-panel.log`，退出 Evo 时一起关），然后在内嵌窗口里打开。面板之外的链接交给默认浏览器。
- **原生通知**：新冒出的闸门（按「项目/闸门号」去重，重启也记得）和接棒器停了（停一次只报一次，恢复后再停再报）。读全局配置 `notify.quiet_hours`，免打扰时段不弹、结束后补发。面板窗口正在看时不弹横幅。点通知打开面板。
- **开机自启**：设置里开关，用 `SMAppService.mainApp`。
- **首次向导**：三步卡片（检查这台 Mac → 装好常驻 → 开始用）。检查 python3、git、orca、gh、magpie（`magpie_url/v1/models`）、`~/.evoloop`、launchd 常驻；一键跑包里的 `install.sh`（只检查）或 `install.sh --apply [--link]`，输出显示在窗口里。

### v0.4.0「团队」页（模型协调）
- 主窗口侧栏「团队」：施工 / 验收 / 决策各一张卡——状态灯（绿可用、黄用备用中或额度满带恢复时间、红要你动手：没装 / 未登录 / 模型已下线 / 和施工撞模型 / magpie 不通）、工具、模型下拉框（magpie 列表 + 用过的）、思考档位、一句职责、备用、每个模型的成绩（打回率、返工、漏放、分钟/件）、一句建议和「换成 X」按钮、本周用量。顶上「magpie 通 / 不通」和新模型提示（可在某个项目试用、可收起）；下面各项目「跟随全局 / 本项目专用」。数据来自 `evo team --json`（每 30 秒随状态一起刷新）。
- 换模型：卡片下拉框、建议按钮，或输入框写「把验收换成 X」「本项目把施工换成 X」「ST 的施工换成 X」→ 输入框上面弹确认卡 →「确认换」才跑 `evo team set`，下一次派工生效。
- 首次设置向导多一步「定岗位」：`evo team init --json` 给出建议，点「就这样」写入（`--apply`）。
- 纯逻辑在 `Sources/EvoCore/Team.swift`（解码、状态灯、成绩一句话、输入框意图、确认卡文字、向导提案），有测试；样例 `Tests/EvoCoreTests/Fixtures/team.json`（同一份在 `scripts/demo/team.json` 给 CI 实机演示用）。

### v0.5.0「调度球」：眼睛跟鼠标、更 QQ 弹、新图标
- **改名**：界面上的「球球」全部改叫 **调度球**（设置里的角色按钮、侧栏、读屏标签、提示文案、注释、测试）。形象仍是 aora-bot emotion-ball 的球形角色，许可照旧：只许自用、不得公开分发（`Resources/vendor/NOTICE.md`）。
- **眼睛跟鼠标**：鼠标进到调度球周围 **3 倍球径**（`EyeFollow.rangeFactor`，侧栏 58 点的球 ≈ 174 点半径）里，两只眼睛整体朝鼠标方向偏；离球心 1.2 倍球径以内幅度随距离变大，再远方向照跟、幅度拉满；出了范围眼睛弹回正中。眼睛的位置是 SwiftUI 原生弹簧（`.interpolatingSpring(stiffness: 170, damping: 13)` 跟随、`stiffness: 90, damping: 9` 回正）逐帧插值出来的，每帧交给宿主页 `evoMate.look(x, y, 放大)` 直接写进引擎（不再叠引擎自己的平滑）。主窗口侧栏、菜单栏弹窗、首次向导里的调度球都跟；本应用窗口里走本地鼠标监听，鼠标在别的应用上方走全局监听（鼠标移动不需要辅助功能权限）。
- **很近时**（0.85 倍球径以内，差不多贴着球）：眼睛放大到 1.16 倍、身体轻轻一缩（0.93），还会眨一下；离开再弹回。
- **更灵动**（全是 SwiftUI 原生弹簧）：
  - 待机呼吸：以底边为锚一吸一呼（约 1.9 秒一次、幅度 2%），像坐着的软球；
  - 随机眨眼：2.6～6.5 秒随机一次，偶尔连眨两下（引擎本身的眨眼照旧）；
  - 点一下：按下压扁（宽 1.13、高 0.84），松手弹过头（0.94 / 1.09）再回来；
  - 状态变化：完成 / 开心往上一跳（先蹲再跳、落地再压一下），等你 / 好奇 / 接任务竖起来一下，出错左右晃，开始思考 / 检索 / 回话点个头，睡觉往下一沉。
  - 小号实例（列表里 26～30 点的）不呼吸不弹，省得一屏都在动。
- **减少动态效果**：开了就全部关掉——不跟鼠标、不呼吸、不眨、不弹，只画静态一帧（和以前一样）。
- **应用图标**：深灰到黑的圆角方块，一个白色、带灰色柔和光泽的大圆球从左下探进来，右上两只略斜的竖椭圆黑眼睛（带一点高光）。`scripts/make-icon.py` 用代码画（不是拿参考图改的），出 `Resources/AppIcon.png`（1024）和全套尺寸的 `Resources/AppIcon.icns`（16～1024，含 @2x），`assemble-app.sh` 拷进包，Info.plist 加 `CFBundleIconFile`；Dock 图标不再在运行时换成角色截图，直接用包里的图标。改图标：改脚本 → `python3 scripts/make-icon.py`（要 `pip install pillow numpy`）→ 提交两张图。
- 纯逻辑在 `Sources/EvoCore/MateMotion.swift`（`EyeFollow.compute`：球心 + 球径 + 鼠标 → 偏移向量、在不在范围、是不是很近；眨眼间隔；状态 → 身体动作），有测试。
- CI 实机演示多一段：鼠标从右下远处慢慢移近调度球 → 绕一圈 → 贴近 → 移开，截 `03a-eyes-far`、`03b-eyes-near-right`、`03c-eyes-circle-left`、`03d-eyes-circle-below`、`03e-eyes-very-near`、`03f-eyes-away`，每张旁边在 `HOW.txt` 记下应用报出的注视值（`mate-gaze`：x、y、在不在范围、是不是很近）；图标拍 `15-dock`、`15b-dock-strip`（Dock 那一条）、`16-finder-icon`，再用 `sips` 把包里的 icns 读成 `AppIcon-from-icns.png`。

| 眼睛：远 → 右边近处 → 绕到左边 → 下方 → 贴近 → 移开（CI 实机截图） |
|---|
| ![眼睛跟鼠标](docs/mac-demo/03-eyes-strip.png) |

| Dock 里的新图标 | Finder 里的 Evo.app |
|---|---|
| ![Dock](docs/mac-demo/15b-dock-strip.png) | ![Finder](docs/mac-demo/16-finder-icon.png) |

注意：GitHub 的 macOS runner 默认开着「减弱动态效果」，调度球在那上面只画静态帧；演示脚本会先 `defaults write com.apple.universalaccess reduceMotion -bool false`，并用 `EVO_DEMO_MOTION=1`（只给录屏用）让应用忽略这个设置。

### v0.6.0 插件 + 接口版本（kit 第十六轮）
- **接口定版本**：App 只通过 `evo … --json` 取数，每个输出顶层都有 `schema_version`（现在 1）。`ContractCheck`（`Sources/EvoCore/Contract.swift`）先看版本号：同一大版本多了字段照常解码、忽略新字段；大版本不认识（比如 evo 升到 2）就不解码，窗口顶上出一条黄色横幅「evo 版本比 App 新（…），请更新 Evo App」（或「比 App 旧，请更新 evo」），对应项目卡片显示同一句，不崩溃。项目列表改读 `evo projects --json`，老 evo 不认就退回纯文本。字段表见 `../docs/app-contract.md`，Schema 在 `../kit/schemas/`。
- **侧栏「插件」分组**：`evo plugin list --json` 里打开了的插件的侧栏页，一页一行（图标是插件给的 SF Symbol）。点开 → `evo plugin run <插件> sidebar_page <id> --json` → 插件输出的卡片 JSON 用**通用卡片渲染器**画：标题、文字（正文 / 小字 / 大标题 / 等宽，五种色调）、列表（图标、副标题、角标）、表格、按钮。按钮点了再跑同一条插件命令（带 action / payload），卡片弹簧换上。三态：加载（转圈）、报错（红字 + 再试一次，写明「只是这个插件出错」）、空。
- **输入框 `/命令`**：打 `/hello 老板` → 交给插件的 composer_command，回话是一张卡片（气泡位置换成卡片，按钮照样能点）。不认识的 `/词` 照旧当反馈发，不会吞掉「/api 路径不对」这种话。
- **件详情页按钮**：插件的 item_action 在件详情右栏「插件」卡片里一个按钮，结果卡片画在下面。
- **设置 → 插件**：每个插件一个开关（跑 `evo plugin enable/disable`），下面一行是版本和贡献点；plugin.json 不合格或 evo_api 不兼容的插件红字说明、拨不开。新装的插件默认关着。
- 纯逻辑在 `Sources/EvoCore/Plugins.swift`（plugin list / run 解码、卡片模型、`/命令` 匹配、命令行拼装、三态）和 `Contract.swift`，测试 `Tests/EvoCoreTests/PluginTests.swift`（样例 `Fixtures/plugin_*.json` 是真 evo 的输出）。界面在 `Sources/Evo/PluginViews.swift`；组件截图 `make snapshots` 多一张 `plugin-light/dark.png`。
- CI 实机演示多一段：用包里的真 evo 装示例插件 `example-hello`（`evo plugin install` + `enable`，插件目录在临时目录）→ 侧栏点「你好」→ 点卡片上的「掷骰子」→ 输入框打 `/hello 老板`，截 `09e-plugin-page`、`09f-plugin-button`、`09g-plugin-hello`。假 evo（`scripts/demo/fake-evo.py`）把 `plugin` 子命令转给真 evo，所以演示的是真的插件机制。

| 侧栏「插件」→ 示例插件页（CI 实机） | 输入框 `/hello 老板` 的回话卡片 |
|---|---|
| ![插件页](docs/mac-demo/09e-plugin-page.png) | ![/hello](docs/mac-demo/09g-plugin-hello.png) |

### 动效和无障碍

- 按钮、胶囊按下压到 0.92、松手弹过头到 1.04 再回来（`spring(response: 0.3, dampingFraction: 0.55)`）；卡片依次弹入；批过的卡片缩小飞走；「等你处理」数字变了会晃一下；状态胶囊换状态时弹一下。
- 角色表情见上表；系统设置里开了「减弱动态效果」：不弹不跳，只淡入淡出，调度球只画静态一帧、不跟鼠标、不呼吸不眨眼。
- 卡片、项目行、按钮、角色都有读屏标签（VoiceOver 念「土布，看效果：注册页按钮…，件号 TB-UX-003」这类整句）。

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

`.github/workflows/app.yml`：改动 `app/**` 时在 macos-14 上跑 `swift test` → `make dmg` → 检查包内容（含角色宿主页、引擎、NOTICE，且没有 Google Fonts）、用空的 `EVO_HOME` 跑一次包里的 evo → `make snapshots` → **实机演示** → 上传构件 **Evo.dmg**、**snapshots**（组件截图）、**mac-demo**（整屏截图 + `evo-demo.mp4` + `HOW.txt`），保留 30 天。手动触发：Actions → app → Run workflow。

实机演示（`scripts/mac-demo.sh`）：在 runner 的真桌面上启动 Evo.app，接假 evo（`scripts/demo/fake-evo.py` + `demo-state.json`），`brew install ffmpeg cliclick`，用 ffmpeg avfoundation 录整屏，然后按顺序：点菜单栏图标 → 打开窗口 → 通过一张卡（飞走）→ 打回一张并写原话 → 选项目 → 打开件时间线 → ⌘K 输入「深色」回车 → 输入框发一句看回话 → 深色下再开弹窗，每步 `screencapture` 拍整屏。点击用 cliclick 真鼠标，坐标由应用在 `EVO_UITEST_GEOMETRY` 写出来。点不动就往 TCC.db 写辅助功能授权再试；还不行就让应用自己演（`EVO_DEMO=1`）照样录。用的哪条路写在 `HOW.txt`。

下载最新构件（要 gh 已登录）：

```bash
gh run download -R JAY5CXSDMY14/evomap -n Evo.dmg
gh run download -R JAY5CXSDMY14/evomap -n snapshots -D docs/screenshots   # 更新组件截图
gh run download -R JAY5CXSDMY14/evomap -n mac-demo -D /tmp/mac-demo       # 整屏截图 + 录屏
```

## Linux 上跑 EvoCore 测试

`Sources/Evo` 全部包在 `#if os(macOS)` 里，Linux 上装了 Swift 工具链也能 `swift test`（只测 EvoCore）。
