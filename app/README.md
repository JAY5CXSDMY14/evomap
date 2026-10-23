# Evo 菜单栏应用

evo 自动循环的 macOS 菜单栏外壳。SwiftUI 写的小壳：菜单栏弹窗里直接批闸门、跟 evo 说话；完整界面嵌现有网页面板；evo 本体（整套 kit）打包在应用里。

> **第二十五轮（#12，老板 10-23 批）：App 冻结。** 不再批卡（按钮只提示「去 Telegram 批」，或在终端跑 `evo approve`），不再加功能；嵌的网页面板也是只读的看效果页。

v0.6.1（kit 第十七轮）：项目暂停时卡片写「暂停：原因」，不再显示成读不出状态（`evo status` 改为只读，暂停也照常返回）；闸门认 `confirm`（Orca 手机端点的「通过 / 上线」要在 App 里再点一次才生效，试运行）和 `budget`（每件上限：继续还是不做）。每件上限的三个数字这版没进 App 设置页，在面板项目页「每件上限」或 `evo limits` 改。

v0.6.0 起 App 读 evo 的 JSON 接口都带版本号（`../docs/app-contract.md`）。v0.6.0 加的插件（侧栏插件页、输入框 `/命令`、件按钮、设置里的插件开关）kit 第二十四轮删了（#16）。

v0.3.0 起有了**真正的 Mac 窗口**（Claude 桌面版的样子：左侧栏、宽内容区、底部钉着输入框、统一标题栏和工具栏），菜单栏弹窗变成紧凑的速览；吉祥物换成 aora-bot 表情引擎的球形角色，v0.5.0 起叫 **调度球**（可切 云宝 / 亮亮）。实机截图和录屏在 CI 构件 mac-demo / snapshots 里（含第三方角色形象，不进公开仓库）。

> **⚠️ 角色许可：只许自用。** 默认角色调度球的形象来自 sam70361/aora-bot 的 emotion-ball（固定版本 e3b6148）。它的**球形视觉形象只许个人学习研究、非商业使用，永远不给商业授权**，所以带调度球的 Evo **不得公开分发**（不发 Release、不放公开下载、不卖）。
> 哪天要分发：先在设置里换成 mood-mates 的云宝 / 亮亮并**向作者买商业许可**（1251579308@qq.com），或换成我们自己的角色。许可原文和 NOTICE 在 `Resources/vendor/`。


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
    Snapshots.swift      make snapshots 用的假数据和出图
    AppState / Panel / Notifier / Shell   轮询、面板窗口、通知、跑命令
  Tests/EvoCoreTests/    单元测试 + Fixtures/ 样例 JSON
  scripts/mac-demo.sh    实机演示：真鼠标点一遍 + 截图 + 录屏；scripts/demo/ 是假 evo 和假状态
  docs/screenshots/      make snapshots 出的组件截图（本机，不进仓库）
  docs/mac-demo/         CI 在真 macOS 桌面上拍的整屏截图（本机 / 构件 mac-demo，不进仓库）
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



注意：GitHub 的 macOS runner 默认开着「减弱动态效果」，调度球在那上面只画静态帧；演示脚本会先 `defaults write com.apple.universalaccess reduceMotion -bool false`，并用 `EVO_DEMO_MOTION=1`（只给录屏用）让应用忽略这个设置。

### v0.6.0 插件 + 接口版本（kit 第十六轮）
- **接口定版本**：App 只通过 `evo … --json` 取数，每个输出顶层都有 `schema_version`（现在 1）。`ContractCheck`（`Sources/EvoCore/Contract.swift`）先看版本号：同一大版本多了字段照常解码、忽略新字段；大版本不认识（比如 evo 升到 2）就不解码，窗口顶上出一条黄色横幅「evo 版本比 App 新（…），请更新 Evo App」（或「比 App 旧，请更新 evo」），对应项目卡片显示同一句，不崩溃。项目列表改读 `evo projects --json`，老 evo 不认就退回纯文本。字段表见 `../docs/app-contract.md`，Schema 在 `../kit/schemas/`。
- 插件部分（侧栏「插件」分组、通用卡片渲染器、输入框 `/命令`、件详情页插件按钮、设置 → 插件、`Plugins.swift` / `PluginViews.swift` / `PluginTests.swift`、实机演示的 09e–09g 三张图）第二十四轮删了（#16）。接口版本横幅 `ContractBanner` 挪到 `MainWindow.swift`，测试在 `Tests/EvoCoreTests/ContractTests.swift`，组件截图改叫 `contract-banner-light/dark.png`。


### v0.7.0 功能开关 + 事件流 + 错误边界（kit 第十八轮）
- **侧栏跟着功能走**：启动读 `evo feature list --json`；功能包 `team` 关了侧栏「团队」消失，正选着就退回「等你处理」。老 evo 没有 `feature` 命令 → 照旧全显示。
- **设置 → 功能**：每个功能一个开关（状态角标：开着 / 关着 / 出错 / 等服务；「在用」的关不掉，灰着写原因）。管侧栏页的排最前，再是有设置的。点「设置（N 项）」展开**按 settings schema 自动画的表单**：boolean → 开关、enum → 一排按钮、integer / number → 数字框带范围、string → 文本框。先在 App 里按 schema 校验（红字），合格才跑 `evo feature set`；evo 拒了把原话挂在字段下。
- **订阅 `evo watch --json`**：有事件去抖 1.2 秒刷新；事件流活着时只做 2 分钟兜底轮询；45 秒没收到一行就当断了，回到 30 秒轮询，并按 5/10/20/40/60 秒退避重连。设置 → evo 里一行写着现在是连上还是轮询。
- **每页错误边界**：团队页、项目页、件详情读不出来 → 只这一页画「出错了」卡片（原因、重试、返回），侧栏和别的页照常；等你处理、卡太久不整页挡；设置页永远能开。（SwiftUI 没有异常式边界，这里按「这页的数据读没读出来」判断。）
- 纯逻辑 `Sources/EvoCore/Features.swift`，测试 `Tests/EvoCoreTests/FeatureTests.swift`（14 个，样例 `Fixtures/feature_list.json` 是真 evo 的输出）；界面 `Sources/Evo/FeatureViews.swift`。组件截图多 `features-*.png`、`page-error-*.png`。
- CI 实机演示多三步：设置 → 关掉「团队 / 模型协调」（真 evo `feature off team`）→ 侧栏「团队」消失；展开「每件上限」填 2000 → 红字「不能大于 1000」，再填 30 → 存好；假 evo 的 `log` 弄坏 → 件详情出错误卡片 → 修好点重试。截 `09h`–`09l`。假 evo 把 `feature`、`watch` 转给包里的真 evo，另有 `_demo break|fix log`。
- 结果：Swift 测试 88 个（74 → 88）；app CI run 39563598844（8913b8c）、39564662641（b1fc493）、39565976360（833128d）都绿（编译、测试、打包、组件截图都过）。
- **还没过的（实机演示）**：错误卡片 + 重试在 run 39563598844 真鼠标跑通（`09k`、`09l`）；功能列表、表单都画出来了，但在 CI 上**拨一个功能开关后主线程卡住约 100 秒**（app.log：`feature off team` 到返回 101.4 秒，期间 watch.ping 全攒着、探点文件 14 秒没更新；同一条命令在 Linux 上 0.17 秒），所以「侧栏团队消失」「红字」两步没拍到，后面的点击落在旧坐标上。要在真 Mac 上 `sample Evo` 查是什么卡住主线程。

### v0.8.0 UI / 交互打磨 + 拨开关卡顿修复（第十九轮）

- **卡顿修了**：第十八轮 CI 上拨功能开关后约 100 秒收不到 `evo feature off` 的结果（Linux 0.17 秒）。日志显示这 100 秒里窗口照样重画、能点，但所有排到 MainActor 的活（命令结果、evo watch 的事件、探点注册）全卡住，下一次鼠标点击后一起涌入。改法：所有子进程走 `EvoCore/ProcessRunner.swift`——不调用 `waitUntilExit`、不 `wait` 任何东西，退出靠 `terminationHandler`；stdout / stderr 各一条专用读线程边出边读（>64KB 也不会塞住管道）；超时 SIGTERM，2 秒后 SIGKILL；孙进程拿着管道最多再等 2 秒。功能开关：点击后下一拍才改状态，转圈移出开关按钮的 label，忙时不切 `disabled`（只挡点击、变淡）；转圈改用系统 `ProgressView`。功能列表内容没变不重新赋值（每次赋值整窗重算，CI 上一次 3–4 秒）。CI 结果：关 team 0.6 秒返回，侧栏 5 秒内变化（含 1.2 秒去抖和截图等待）。
- **卡顿探针**（只在 CI 演示时开）：后台每 0.5 秒看主队列和 MainActor 各跳没跳，超过 3 秒没跳就记一行并 `sample` 主线程栈，写进构件 `stall-N.txt`。
- **设计令牌**：间距 / 圆角 / 字号 / 动效时长 / 弹簧只在 `EvoCore/DesignTokens.swift` 定义（颜色在 `Theme.swift`，也只在那一处）。弹簧阻尼 ≥ 0.6、过冲 < 8%（有测试）：QQ 弹弹但克制；按下缩到 0.96，不再手动弹到 1.04；角标晃动幅度减半。`MotionPolicy`：系统开了「减弱动态效果」就只淡入淡出，CI 用 `EVO_DEMO_MOTION=1` 照常动。
- **首页只放「等你处理」**：标题下一句「有 N 件等你处理」「最久的一件等了 X」；卡住几件、其余项目在转收成两行，默认收起（展开状态会记住）。三态：加载（系统 redacted 占位卡 + 转圈）、出错（错误卡片 + 重试）、空（一切顺利 + 一句说明）。逻辑在 `EvoCore/Home.swift`（`HomeSummary`）。
- **件详情「为什么卡住」**：时间线上面一张卡，从 status 的件状态、卡太久、没活路和 log 时间线推出一句人话 + 依据 + 你能做什么：没活路（依赖没了 / 没人拍板 / 额度满 / 任务没了）、在等你（看效果 / 拍板）、部署失败、交卷说做不下去、排队 / 施工 / 验收太久、按你的话返工中；不卡就是一行进展。逻辑在 `ItemDiagnosis`。时间线最新一条实心加重、带「X 分钟前」；加载有占位，没记录有说明。
- **⌘K**：没输入时分组（动作 / 跳转 / 等你处理 / 件 / 项目），右边显示快捷键；新增「去等你处理 / 卡太久 / 团队」和直接打件号跳到件详情（卡住的排前面）。
- **CI 实机结果**（run 39571576780，提交 acea666，macos-14）：单元测试、打包、截图、mac-demo 全绿；真鼠标 1 处失败。✓ 关 team 后侧栏「团队」消失（命令 0.6 秒返回）；✓ 表单填 2000 出红字「不能大于 1000」、填 30 存好；✓ 错误卡片 + 重试；✓ 首页、展开其余项目、⌘K 分组；✓ 深色下 ⌘K 跳到件详情（「为什么卡住」卡片）；✗ 浅色那次 ⌘K 回车时主线程正忙，没跳过去。
- **还没解决：CI 虚拟机上主线程常卡 2–8 秒**（16 次，多在设置页和鼠标移动时）。sample 显示约 91% 时间在 SwiftUI 的 AttributeGraph 更新，栈里几乎没有 Evo 自己的代码；怀疑是调度球跟鼠标的 60Hz 弹簧动画 + 整窗都观察 AppState，在没有 GPU 的虚拟机上被放大。要在真 Mac 上用 Instruments（SwiftUI 模板）确认，再决定拆 AppState 的观察范围还是降调度球帧率。
- 测试：Swift 108 个（+8 子进程、+12 令牌 / 首页 / 卡住原因 / ⌘K）；Linux 上 1 个孙进程用例跳过（swift-corelibs 的 Process 要等孙进程退出才算结束，macOS 上照跑）。

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
