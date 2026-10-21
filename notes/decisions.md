# 决策记录

只追加。每条：日期、决定、为什么、怎么改回去。

## 2026-10-21 第十八轮（模块化 + 自维护 + 多机器）

- **内核 + 功能包，照 magpie 插件运行时。** 内核只管状态机、闸门、锁、权限、事件、运行时；12 个功能迁成 `kit/features/<id>/`。为什么：功能能单独开关、坏一个不拖垮别的；evo 自己改自己时，大多数改动落在功能包里，不碰受保护的内核。
- **渐进迁移，每批测试全绿才推。** 一次迁一个功能（7cc9051 → 9e28321）。JSON 接口字段和 `schema_version` 不变，第十六轮插件的 `evo_api 1.0` 不变。
- **跑着的 evo 和仓库代码分开。** 正式安装跑 `~/.evoloop/current → releases/<提交>`；换版本只能 `evo self-upgrade`（先自检、等一轮结束、切换后再自检）。开发用 `install.sh --apply --dev`。
- **看门狗独立、谁都不许改。** `kit/selfmaint/` 只有老板手改；工人改了交卷打回，决策岗不能安排改它。观察期默认 10 分钟（`GUARD_MINUTES`）。
- **自维护关键代码走老板闸门。** EV 项目 `self_maintained: true` 时，`SELF_PROTECTED`（内核五个文件、`kit/roles/**`、`install.sh`、`kit/selfmaint/**`、`item-caps`、`orca-gate-sync`）碰到就是老板闸门件；项目配置 `protected_paths` 可以再加。
- **待定项①（按推荐默认）：推送渠道 Telegram / 邮件关掉不受「在用」保护，维持现状。** 为什么：关掉只是不往那里推，配置留着，不会有东西没人管；webhook 不同（外部 bot 在等），配了算在用。改法：给 `notify-telegram` / `notify-email` 的 `feature.py` 加 `in_use()`，同时改测试 `test_push_channels_telegram_email_off_not_protected`。
- **待定项②（按推荐默认）：远端租约默认开。** 为什么：第二台机器后导入同一项目时，只有远端租约拦得住。改法：全局 `~/.evoloop/config.json` 写 `"lease_remote": false`；单个项目在项目配置里写，项目优先。测试 `test_remote_lease_default_on_global_off`。
- **App 0.7.0 订阅事件流，断线回退轮询。** 事件流活着时 2 分钟兜底；断了 30 秒轮询，5–60 秒退避重连；老 evo 没有 `watch` / `feature` 时界面照旧。
- **错误边界按「这页数据读没读出来」判断。** SwiftUI 没有异常式边界。团队、项目、件详情坏了只挡这一页；汇总页不整页挡；设置页永远能开（evo 路径填错要靠它改回来）。
- **设置页「功能」卡片里，管侧栏页的功能排最前。** 为什么：拨它侧栏马上变，最该先看到；CI 演示也因此点得到（原来团队开关在屏外）。

## 2026-10-21 第十九轮（App UI / 交互打磨）

- **子进程一律走 ProcessRunner，不阻塞任何线程等结果。** 为什么：第十八轮拨开关后 100 秒收不到结果，期间 MainActor 的活全排着队；老写法每条命令在 GCD 上占 3 个线程等到底。新写法退出靠 terminationHandler、读靠两条专用线程、超时 TERM→KILL。改回去：`Shell.run` 换回旧 `runSync`（git 9e367e7 之前）。
- **功能开关点击后下一拍再改状态；忙时不切 disabled。** 为什么：按钮动作里同步改 `featureBusy` 会让按钮在按下途中被重建（label 里塞转圈、disabled 切换）。
- **数字令牌放 EvoCore（能在 Linux 测），颜色留在 Theme.swift。** 弹簧阻尼下限 0.6 写进测试，以后谁把动效调得太弹测试会红。
- **首页只给「等你处理」，其余默认收起。** 为什么：老板打开窗口第一眼只该看到要他点头的事；项目在转不是他的活。展开状态存 `homeShowProjects`。
- **「为什么卡住」在 App 里推（EvoCore/ItemDiagnosis），不改 evo 的 JSON。** 为什么：不破坏 `schema_version` 1 的契约，也不碰内核；推不出的原因照实显示原始 reason。以后 evo 输出更细的原因，再在 App 里加分支。
- **mac-demo 失败数 ≤6 时 CI 仍算绿。** 真正每一步过没过看构件 HOW.txt 里的 ✓ / ✗。
- 2026-10-21 20:05 Air 试跑：EV 已导入 air（app 0.8.0）。修 ff426e6（make 自动借 Xcode-beta 的 SwiftUI 宏；无 Orca 时 import 不崩）。建议 EV 模型 build=group/build verify=group/check（Air 无 group/evo-*），待老板确认。Air 缺 orca/claude/codex。
- 2026-10-21 20:15 73b424a：evo -p 项目 models 只按项目实际模型判 exit。Air 建议全局岗位全走 dsh+magpie：build group/build、verify group/check、decide group/paid-opus（claude cli 不认 magpie 组名）；已发第三步指令，待回报。
- 2026-10-21 20:30 老板定：Air 装 Orca（/Applications，官方 stablyai/orca）；验收/决策用 Claude Code（已接 magpie）；全局施工 group/free-ds，验收 group/free-glm-5-3（我的建议，需与施工不同），决策 group/paid-opus；模型以后在团队页从 magpie 列表自选。792dd1f：install.sh 常驻 PATH 取登录 shell。

## 2026-10-21 21:45 Air 试跑 EV-FEAT-001：Orca 退出后的盲区
- 现象：施工岗 dsh·group/free-ds 派工后 17 分钟零产出，随后 Orca 进程退出；evo 一直显示「施工中」，autopilot.log 0 字节。
- 修：每轮先 orca status，不通→记一次、推 orca_down、不派工不判卡住，恢复后 C7 自动重启工人一次；status 显示「Orca 没开」+ JSON orca_down_since；stdout 行缓冲 + plist PYTHONUNBUFFERED；team 探测 CLI 时额外查 ~/.local/bin、/opt/homebrew/bin 等。
- 未查清：Orca 为什么退出、dsh 17 分钟为什么没写一行。
- 21:58 第 2 次观察：Orca 21:27 正常退出（非崩溃）、21:36 自己重启；C7 自动重启记了一笔，但 Orca 里没有 build 终端、没有 dsh 进程，21:37 起疑似卡住 20+ 分钟无人管。修：派工后 terminal show 确认终端在，不在就当派工失败；疑似卡住交决策岗一次；常驻把子进程输出写进 autopilot.log，开工人终端时打出命令。
- 22:10 老板确认：21:27 是他手动退出 Orca（给 Orca 开了一个系统权限，需要重启 app）。Orca 退出不是故障；剩下的疑点只有第一次派工 14 分钟零产出（可能也卡在那个权限上，待 Pi 复现）。
- 22:22 第 3 次观察定根因：evo 的 dsh 模板「dsh --model {model}」是猜的；dsh 是 profile 启动器，没有 --model、没有交互界面，headless 一次性跑完、模型用 DSH 自己的默认。修：dsh 改为 `dsh --profile headless -` + 任务书写文件「< 文件」启动（一次性工具不打 inject）；启动后读终端尾部，命令报错/立刻回提示符就当派工失败并关终端，任务书不再喂给 shell；旧配置 dsh --model 自动改写；claude 新工作区预先记信任（~/.claude.json hasTrustDialogAccepted），EV-decide 停在信任提示。状态文件真实路径 ~/.evoloop/projects/<代号>/state/state.json。
