# ST 种子待办（REASTOCK 为主力，移植 ios-stock-app 的严谨性）

老板 2026-10-21 定：REASTOCK 是主力工作代码库；ios-stock-app 是严谨性的来源，按件移植进来。本文件 26 件，每件都能直接转成 GitHub issue：标题照抄，标签 = `type:<类别>` + 每个 `scope:<目录>` + 看效果打 `look`、要老板点「做不做」打 `product`、有时间窗打 `window:<写法>`。决策岗分拣完再打 `autopilot:ready`。**本文件只是待办清单，还没建 issue。**

约定：
- 件号 `ST-<类别>-NNN`，类别只用 FEAT / FIX / UX / OPS / DOC / CHORE；标题动作开头、24 字以内。
- 路径相对干净工作仓库根（ST-OPS-001 建，建议 `~/Desktop/项目/reastock`）。「旧仓库」= `~/Desktop/项目/jailbreaks/reastock`（档案，只读）；「ISA」= `~/Desktop/项目/ios-stock-app`（只读）。
- 「金标准」= ST-OPS-003 用 ISA 的 `score_engine.py`（1.8.4 逐指令转写）在冻结 K 线上产出的结果，加三类独立真值。凡是改分数的件，都要在金标准上逐字段一致，不能只靠读代码。
- Q1–Q7 老板说「到时候再说」：只有「前置」里写了「等 Qn」的件依赖它们，那些件放在第 3 段，不排期。其余件答复前一律按现状做，不替老板定。
- 所有件守 `project.json` 的 `red_lines`。

## 一览

| # | 件号 | 标题 | scope | 前置 | look | 做不做 | 窗口 |
|---|---|---|---|---|---|---|---|
| 1 | ST-OPS-001 | 建 REASTOCK 干净工作仓库 | 仓库根（手工件） | 无（路径/远端名用建议值，Q5 可改） | 否 | 是 | — |
| 2 | ST-OPS-002 | 建一键全量测试入口 | scripts/、Tests/、Package.swift | OPS-001 | 否 | 否 | — |
| 3 | ST-OPS-003 | 移植 1.8.4 执行分金标准回归 | verify/、Tests/、reference/ios-stock-app/ | OPS-002 | 否 | 否 | — |
| 4 | ST-FEAT-001 | 行情数据逐项标注来源与时间 | Data/、Models/、Views/ | OPS-002 | 是 | 否 | 验收截图 trading:cn |
| 5 | ST-DOC-001 | 写测试移植对照表 | docs/ | OPS-003 | 否 | 否 | — |
| 6 | ST-CHORE-001 | 搬入官方对账与发布流水线 | pipeline/、reference/ios-stock-app/、scripts/ | OPS-002、DOC-001 | 否 | 否 | — |
| 7 | ST-CHORE-002 | 移植适用的指标与评分测试 | Tests/、verify/ | OPS-003、DOC-001 | 否 | 否 | — |
| 8 | ST-FEAT-002 | 接入官方收盘对账结果 | Data/、Core/、Views/、pipeline/ | CHORE-001、FEAT-001 | 是 | 是 | postclose:cn |
| 9 | ST-FEAT-003 | 选股结果按版本发布 | Core/、Views/、Tests/ | OPS-003、FEAT-001 | 是 | 否 | — |
| 10 | ST-OPS-004 | 测试断网并集中联网规则 | Data/、Tests/ | OPS-002 | 否 | 否 | — |
| 11 | ST-OPS-005 | 打包加校验与安装预演 | scripts/ | OPS-002 | 否 | 否 | — |
| 12 | ST-OPS-006 | 建股票项目脱敏词表 | docs/（词表在仓库外） | OPS-001 | 否 | 否 | — |
| 13 | ST-DOC-002 | 整理 REASTOCK 校准结论 | docs/ | OPS-001 | 否 | 否 | — |
| 14 | ST-OPS-007 | 选股提速加一致性基准 | Engine/、Core/、Tests/ | OPS-003、OPS-004 | 否 | 否 | — |
| 15 | ST-UX-001 | 选股可取消且不留半截结果 | Engine/、Views/ | OPS-007 | 是 | 否 | — |
| 16 | ST-UX-002 | 八个页面各窗口尺寸无截断 | Views/ | OPS-002 | 是 | 否 | — |
| 17 | ST-UX-003 | 无数据和出错时显示真实空态 | Views/、Data/ | FEAT-001 | 是 | 否 | — |
| 18 | ST-FEAT-004 | 走坏清理加确认与撤销 | Engine/、Core/、Views/ | OPS-003 | 是 | 是 | — |
| 19 | ST-FEAT-005 | 回测结果可复现并标样本数 | Engine/、Views/、Tests/ | OPS-003 | 是 | 否 | — |
| 20 | ST-FIX-001 | 核对 ETF 价格缩放口径 | Engine/、Data/、Tests/ | OPS-003 | 否（若数字变则是） | 否 | — |
| 21 | ST-FEAT-006 | 收盘后自动选股默认开启 | Core/ | 等 Q6；FEAT-003 | 是 | 是 | postclose:cn |
| 22 | ST-FEAT-007 | 盘中实时报价按口径接入 | Data/、Views/ | 等 Q3；FEAT-001、OPS-004 | 是 | 是 | trading:cn |
| 23 | ST-OPS-008 | 校准盘中执行分实时分支 | Engine/、verify/ | 等 Q1、Q3；OPS-003 | 否 | 否 | trading:cn |
| 24 | ST-FEAT-008 | 对齐列表分与案例库叠分 | Engine/、Views/ | 等 Q1；OPS-003 | 是 | 是 | — |
| 25 | ST-UX-004 | 定稿今日页与建议类文案 | Views/、Engine/TradeAdvice | 等 Q2、Q7 | 是 | 是 | — |
| 26 | ST-DOC-003 | 写明 evo 与人工循环分工 | docs/ | 等 Q4 | 否 | 否 | — |

（表中 Data/、Engine/、Core/、Views/、Models/ 都是 `REASTOCK/Sources/REASTOCK/` 下的目录，打 scope 标签时写全路径。）

顺序：OPS-001（老板在场）→ OPS-002 → OPS-003 → FEAT-001 → 第 1 段（DOC-001 → CHORE-001 / CHORE-002 → FEAT-002 / FEAT-003，OPS-004/005/006、DOC-002 可穿插）→ 第 2 段打磨 → 第 3 段等老板答问题。evo 的第一件跑 OPS-002（小、不碰界面），用来确认真工人、真验收在这个仓库里跑得通。

---

## 第 0 段：基线（让 evo 跑起来、把分数钉住）

### ST-OPS-001 建 REASTOCK 干净工作仓库
- 类别：OPS　scope：新仓库根　**手工件：evo 导入前由老板在场完成，不进 evo 队列。**
- 前置：无。look：否。做不做：是（老板在场执行；路径、远端名、旧缓存去处属 Q5，没答之前用下面的建议值，老板当场可改）。窗口：—。
- 为什么：旧仓库 git 里跟踪了约 201 MB，其中 Ghidra 逆向工程约 76 MB、`verify/` 抓取数据约 99 MB（sb-klines 52、gt-klines 24、live-scores* 23）、`ui-shots/` 截图约 22 MB；真正的源码只有 0.64 MB。逆向材料不能留在以后要推远端、要给 evo 工人反复克隆的工作库里，而且一旦进历史就去不掉。所以从当前树新开历史，旧仓库原样留作档案。
- 做法（命令写在 README「第 1 步」）：
  1. 旧仓库只读：先 `git -C <旧仓库> status --short`，确认没有未提交改动（MCP 核对时源码目录最后修改早于 HEAD，但没跑过 git status）。有改动先请老板决定是先在旧仓库提交，还是带进新库。
  2. 用 `rsync` 按排除清单（`project.json` 的 `reference.archive.never_import`）把旧仓库当前树复制到新路径。注意 `verify/klines-*.json`、`swift-*.json`、`js-*.json` 只在磁盘上不在 git 里，要靠 rsync 复制过来，不能用 `git archive`。
  3. 从 `ui-shots/` 只挑 7 张（`final-detail3.png`、`final-screening.png`、`final-holdings.png`、`final-settings.png`、`reastock-3col3.png`、`today-final.png`、`v7-market.png`）放进 `docs/ui-ref/`。
  4. 新 `.gitignore`：保留 `.build/`、`build/`、`.DS_Store`、`*.log`；去掉一刀切的 `verify/*.json`，改成只忽略 `verify/cache/`；再挡住 `ghidra*`、`analysis/`、`rea/`、`backup/`、`tools/winutil/`、`verify/engine-extracted.js`、`verify/sb-klines/`、`verify/gt-klines/`、`verify/live*/`，防止以后误加。
  5. 建空壳 `docs/LESSONS.md`、`docs/code-standards.md`；写 `docs/ORIGIN.md`：出处路径、旧提交 `378d7eee1140a3cd497865d03859cfebed20ccda`、排除了什么和为什么。
  6. 先量：`du -sh .`、`find . -size +1M -not -path './.git/*'`，大于 1 MB 的文件列给老板过目（预期只有 `assets/AppIcon.icns` 约 1.1 MB）。
  7. `swift build --disable-sandbox` 通过后再 `git init -b main && git add -A && git commit -m "从 REASTOCK 378d7ee 建立干净基线"`。
  8. 老板定了名字再 `gh repo create <名字> --private --source . --push`（建议 `JAY5CXSDMY14/reastock`）。
- 验收：`git log --oneline` 只有 1 个提交；`git ls-files | grep -Ei 'ghidra|engine-extracted|StockStation-bin|sb-klines|gt-klines|live-scores|/rea/|^analysis/|^backup/'` 为空；`du -sh .git` < 25 MB；`verify/` 下 24 只 `klines-*.json` 和 `swift-*.json` 在库里；新库里 `swift build --disable-sandbox` 通过；旧仓库 `git -C <旧仓库> rev-parse HEAD` 仍是 `378d7ee…`、`status` 与开工前一致；ISA 一个文件没动。

### ST-OPS-002 建一键全量测试入口
- 类别：OPS　scope：`scripts/`、`Tests/`、`Package.swift`（只加测试目标，不改产品代码行为）。
- 前置：OPS-001。look：否。做不做：否。窗口：—。
- 背景：REASTOCK 没有单元测试目标，现在靠 `verify/regression.sh`（3 只界面真值）、`verify/verify-all.sh`（其中 588 只评分板要联网补 K 线、读 `~/Library/Application Support` 里的评分板）、`verify/cross-check.sh`（依赖不收的 `engine-extracted.js`）。evo 需要一条稳定、离线、退出码可信的命令。
- 做法：
  1. `Package.swift` 加 `Tests/REASTOCKTests` 测试目标。先试 `@testable import REASTOCK`（SwiftPM 在 macOS 上支持测试 executableTarget）；不行就把 `Engine/ Data/ Models/ Core/` 拆成 `REASTOCKCore` 库目标、App 只留界面和入口，拆分前后 `--verify-dump` 输出逐字节一致。
  2. 新建 `scripts/test-all.sh`：依次跑 `swift build`、`swift test`、`verify/regression.sh` 的离线部分（去掉对 cross-check 的调用，或在缺 `engine-extracted.js` 时明确跳过并打印原因）、以后 `pipeline/` 的 Python 测试（CHORE-001 加入）。任何一套红就整体非 0，最后打印每套通过数。
  3. 修 `regression.sh` 的退出码：现在用 `set -uo pipefail` 不带 `-e`，失败数非 0 时也可能 0 退出。
- 验收：干净克隆里 `bash scripts/test-all.sh` 断网能跑完并退出 0；故意把 `regression.sh` 期望值改错一只，退出码非 0 且输出点名哪一套；`swift test` 至少有 1 个真测试（例如 `NativeScoreEngine` 对 `verify/baseline/klines-sh600968.json` 得 58）。若 3 只真值里中远海发（脚本注明「已知偏差」）现在不过，写成显式例外并注明原因，不改期望值。

### ST-OPS-003 移植 1.8.4 执行分金标准回归
- 类别：OPS　scope：`verify/fixtures/`、`verify/golden/`、`Tests/`、`reference/ios-stock-app/`。
- 前置：OPS-002。look：否。做不做：否。窗口：—。
- 背景：REASTOCK 说的「588/588 吻合」本来就是拿 ISA 的 `replica/MarketData/app/score_engine.py` 当权威量出来的。这件把权威搬进工作仓库并固化成离线测试，以后谁改评分都要过它。
- 做法：
  1. 复制 ISA 的 `score_engine.py`、`test_mac010_score_engine.py` 及其依赖到 `reference/ios-stock-app/`，写 `PROVENANCE.md`（原路径、复制日期、SHA-256；ISA 的 .git 残缺，无提交可钉）。
  2. 夹具：`verify/baseline/`（3 只界面真值 K 线，10-14 收盘）、24 只 `verify/klines-*.json`；官方评分板 588 只（9-24）的期望分从 `~/Library/Application Support/StockStationReplica/scoreboards/mac010-scoreboard-dc9efae5447cd92c.json` 只读抽出代码和分数；对应 K 线从旧仓库 `verify/sb-klines/` 裁到评分需要的最近 N 根并 gzip（目标 ≤ 8 MB，N 取 score_engine 实际用到的最长窗口再加余量，裁剪前后 score_engine 输出逐只一致才算数）。
  3. `verify/golden/gen.py` 用 `reference/ios-stock-app/score_engine.py` 在这些夹具上产出 `verify/golden/*.json`（七项分项 + 总分 + 封顶原因）；生成脚本自带 ISA 原测试做自检。
  4. Swift 测试：`NativeScoreEngine` 对 3 只界面读数精确相等（海油发展 58、海南机场 39、中远海发 58；中远海发若是已知偏差就写显式例外）；588 只吻合不低于 587，唯一已知差异中国化学 sh601117 写成显式例外并注明原因；24 只七项分项与金标准一致。
- 验收：新测试进 `scripts/test-all.sh` 且全绿、断网可跑；故意把项 5 的长 BBI 参数从 14/28/57/114 改回 3/6/12/24，测试必须红；重跑 `gen.py` 产物不变（确定性）；夹具总量 < 10 MB。

### ST-FEAT-001 行情数据逐项标注来源与时间
- 类别：FEAT　scope：`REASTOCK/Sources/REASTOCK/Data/`、`Models/`、`Views/`。
- 前置：OPS-002。look：是。做不做：否（这是 ISA 的既有纪律，不是新产品决定）。窗口：离线部分无；验收截图在 `trading:cn` 时段补一张盘中的。
- 背景：REASTOCK 日 K 走腾讯 → 新浪 → 东财降级、报价走腾讯，但界面上不显示用的是哪个源、什么时候取的、有没有降级。ISA 的规矩是来源与新鲜度逐项标注、不混源补行。
- 做法：`MarketDataService` 每次返回都带 `source`（tencent/sina/eastmoney/cache）、供应商时间、行情交易日、接收时间、是否降级、是否来自缓存；同一条 K 线序列只用一个源，降级就整条换源并标明，不拼接；取不到当前价就显示「暂无实时价」，不用旧收盘价顶。详情页、行情列表、选股结果、持仓都显示一个小标注（源 · 交易日 · 取数时间），点开有完整信息。
- 验收：单测覆盖四种情况（主源成功、降级、缓存命中、全失败）的标注字段；用假源测试「两个源各给半截」时不会拼接；全失败时界面显示真实空态而不是 0 或旧价；前后截图（详情、行情、选股、持仓 4 页）；金标准测试不受影响。

---

## 第 1 段：把 ios-stock-app 的严谨性移植进来

### ST-DOC-001 写测试移植对照表
- 类别：DOC　scope：`docs/porting/isa-tests.md`。
- 前置：OPS-003。look：否。做不做：否。窗口：—。
- 做法：把 ISA 约 760 个测试（MarketData 355、Backend 90、Simulation 150、WebChart 99、打包脚本 47、Swift 21，数字取自 10-02 登记，未重跑）按文件列出，每个文件标一类：「随流水线原样搬」（CHORE-001）、「改写成 Swift 测试」（CHORE-002）、「不适用」（写一句原因，例如 FastAPI 后端、内嵌 CPython 打包、MAC-012A 专用）、「以后再说」（Simulation 等路线第 3 步）。
- 验收：ISA 每个测试文件都在表里且只属一类；「随流水线搬」和「改写」两类给出预计用例数；不写的理由具体到文件。

### ST-CHORE-001 搬入官方对账与发布流水线
- 类别：CHORE　scope：`pipeline/`、`reference/ios-stock-app/PROVENANCE.md`、`scripts/test-all.sh`。
- 前置：OPS-002、DOC-001。look：否。做不做：否。窗口：—。
- 做法：把 ISA `replica/MarketData/app/` 里对账与发布相关模块（清单见 `project.json` 的 `reference.rigor_source.port_in`，排除 MAC-012A 专用的三个）连同 DOC-001 标「原样搬」的测试，原样复制到 `pipeline/`，记 PROVENANCE。只改导入路径，不改逻辑。`scripts/test-all.sh` 加这一套。App 这时还不读它。
- 验收：`pipeline/` 测试断网全绿，用例数与 DOC-001 预计一致（少了要逐个说明）；`netpolicy` 的单线程、间隔 ≥2 秒原样保留且有测试；`git diff` 只在 `pipeline/`、PROVENANCE、test-all.sh。

### ST-CHORE-002 移植适用的指标与评分测试
- 类别：CHORE　scope：`Tests/`、`verify/fixtures/`。
- 前置：OPS-003、DOC-001。look：否。做不做：否。窗口：—。
- 做法：把 DOC-001 标「改写成 Swift」的用例（指标 BBI/KDJ/量比、交易日历与日期、前复权输入、完美评分与突破的 `strategy-core.test.js` 用例等）改写成 Swift 测试，喂同样的输入、断言同样的输出。KDJ 窗口按 9 根（REASTOCK 已证明 JS 参考的 10 根是 bug），对应用例改期望并注明。完美评分的对照数据用旧仓库磁盘上的 `verify/js-*.json`（原 JS 引擎的输出数字，不收它的代码）。
- 验收：改写的用例数与 DOC-001 预计一致；每个测试注释里写出处（ISA 文件名 + 用例名）；20 只完美评分与 js-*.json 一致，误差 ≤ 0.001，唯一已知不一致那只写成显式例外；全部断网可跑。

### ST-FEAT-002 接入官方收盘对账结果
- 类别：FEAT　scope：`Data/`、`Core/`、`Views/`、`pipeline/`。
- 前置：CHORE-001、FEAT-001。look：是。做不做：是（等于给 App 新增官方交易所联网源，碰红线 `network-scope`）。窗口：`postclose:cn`（验收时）。
- 做法：收盘后由 `pipeline/` 跑一次官方对账（沪市走官方源；深市官方数据在 ISA 里受阻于 MAC-012A，标「未对账」而不是假装对过），产出带哈希的对账结果；App 读它，在日 K 的最后一根和选股结果上显示「已对账 / 未对账 / 不一致」。不一致时不改数据，只标出来。
- 验收：在 `postclose:cn` 窗口真跑一次并留证；对账不一致的假数据能在界面上看到标记；官方源单线程、间隔 ≥2 秒；断网时 App 显示「未对账」而不是报错；截图前后对比。

### ST-FEAT-003 选股结果按版本发布
- 类别：FEAT　scope：`Core/`（`Picks.swift`）、`Views/`、`Tests/`。
- 前置：OPS-003、FEAT-001。look：是（选股页显示版本与输入哈希）。做不做：否。窗口：—。
- 背景：ISA 的榜单是版本化发布：内容哈希、输入集 ID、写完整份后原子切换「当前」指针、旧版本保留。REASTOCK 的选股结果目前直接覆盖。这件只改「怎么存、怎么切」，**不改「什么时候自动跑」**（那是 Q6）。
- 做法：每次选股产出一个不可变版本（交易日、输入集哈希、引擎版本、结果哈希、生成时间、数据来源汇总），写临时文件后原子改名切换当前指针；旧版本保留，可在选股页切换查看。
- 验收：中途杀进程不会留下半个当前版本（有测试）；同一输入两次生成的结果哈希相同；旧版本可读；个人记录目录里原有数据不被删改（红线 `private-data`）。

### ST-OPS-004 测试断网并集中联网规则
- 类别：OPS　scope：`Data/`、`Tests/`。
- 前置：OPS-002。look：否。做不做：否。窗口：—。
- 做法：照 ISA 的 `network_guard.py`，测试里替换 URLProtocol，任何真实联网直接让测试失败；把散在各处的并发数、缓存时长、重试次数、Referer 等集中到一个联网配置里，默认值保持现状（并发 8、列表缓存 60 秒、日 K 缓存 300 秒），只写清不改大。
- 验收：故意在测试里发一次真请求会红；所有联网参数在一个文件里且有单测；现有行为（金标准、选股结果）不变。

### ST-OPS-005 打包加校验与安装预演
- 类别：OPS　scope：`scripts/`。
- 前置：OPS-002。look：否。做不做：否。窗口：—。
- 做法：借 ISA 打包流水线的思路：`scripts/build-app.sh` 打包后自动校验（bundle 结构、Info.plist 版本号、资源齐全、签名状态、可执行文件架构），另加 `--dry-run` 安装：只打印会覆盖 `/Applications` 里的什么、备份到哪，不真装。
- 验收：校验项各有一条失败用例；`--dry-run` 不写 `/Applications`（测试里用临时目录断言）；真装仍要老板在场（红线 `apply-needs-owner`），脚本里没有无人值守的安装路径。

### ST-OPS-006 建股票项目脱敏词表
- 类别：OPS　scope：`docs/evo/policy-terms.md`；词表本体放仓库外 `~/.evoloop/projects/ST/policy-terms.txt`。
- 前置：OPS-001。look：否。做不做：否。窗口：—。
- 做法：从老板那里拿要屏蔽的词（券商与资金账号、持仓数量和成本、手机号、真实姓名、API 密钥前缀、内网地址），写进仓库外词表；仓库里只写「词表在哪、怎么加」。
- 验收：`evo add` 标题含词表词的件被拒；`git grep -f <词表>` 无命中（命中的列给老板处理，不自动改）。

### ST-DOC-002 整理 REASTOCK 校准结论
- 类别：DOC　scope：`docs/calibration.md`。
- 前置：OPS-001。look：否。做不做：否。窗口：—。
- 做法：把 `docs/` 里 22 份校准与审计文档压成一份：已证实的（七项分档、封顶顺序、长 BBI 14/28/57/114、KDJ 9 根、量比口径、止损三套口径）、已证伪的（5 日跌幅压制等四个假设）、仍未解的（1.9.1 列表分来源、盘中 −8 组、J≥80 封顶 52 还是 48、砖型评分权重）、教训（规则至少要 5 个以上正样本；执行分实证无预测力，相关 +0.014）。每条注明出处文件。原 22 份保留不删。
- 验收：每条结论能点到原文；「仍未解」不少于 4 条；不写成投资建议。

---

## 第 2 段：REASTOCK 功能打磨

### ST-OPS-007 选股提速加一致性基准
- 类别：OPS　scope：`Engine/ScreeningEngine.swift`、`Core/ScanBench.swift`、`Tests/`。
- 前置：OPS-003、OPS-004。look：否。做不做：否。窗口：—。
- 背景：REASTOCK 的并发 8 相对串行 7.9 倍、缓存命中 315 倍，是它的长处，但没有「快了结果还一样」的测试。
- 做法：在冻结夹具上用假源跑串行、并发、缓存命中三种，断言逐只结果一致；缓存键带输入哈希，输入变了必失效；`ScanBench` 输出写进交卷。不改默认并发和缓存时长。
- 验收：三种跑法结果逐只一致（测试）；改一根 K 线后缓存失效（测试）；交卷附基准数字。

### ST-UX-001 选股可取消且不留半截结果
- 类别：UX　scope：`Engine/ScreeningEngine.swift`、`Views/ScreeningView.swift`。
- 前置：OPS-007。look：是。做不做：否。窗口：—。
- 做法：选股按阶段（拉列表 → 硬过滤 → 评分 n/N）显示进度，随时可取消；取消后回到上一次完整结果，不留半截数据、不残留旧来源标签。
- 验收：进度、完成、取消、失败四种状态有测试；取消后的结果哈希等于取消前；尊重「减少动态效果」；前后截图。

### ST-UX-002 八个页面各窗口尺寸无截断
- 类别：UX　scope：`Views/`。
- 前置：OPS-002。look：是。做不做：否。窗口：—。
- 做法：8 个页面在 1440×900、1280×800 和应用允许的最小窗口下逐页检查截断、重叠、省略号吃掉关键数字；只修布局，不改内容和数字。
- 验收：24 张截图（8 页 × 3 尺寸）前后对比；修过的地方逐条列出；深色/浅色各抽查 2 页。

### ST-UX-003 无数据和出错时显示真实空态
- 类别：UX　scope：`Views/`、`Data/`。
- 前置：FEAT-001。look：是。做不做：否。窗口：—。
- 做法：断网、源全挂、K 线不足、休市日、没有选股结果这几种情况，每页显示具体原因和下一步（例如「K 线不足 120 根，执行分不可计算」），不显示 0、空白或旧数据冒充当前。
- 验收：用假源逐个注入，每种情况每页都有截图；没有任何数字在这些情况下显示为 0。

### ST-FEAT-004 走坏清理加确认与撤销
- 类别：FEAT　scope：`Engine/RiskRules.swift`、`Core/WatchStore.swift`、`Views/WeakCleanupSheet.swift`。
- 前置：OPS-003。look：是。做不做：是（会改个人自选/持仓记录）。窗口：—。文案措辞属 Q7，这件只做机制，文案保持现状。
- 做法：四条走坏判定（跌破止损、砖型未翻红、顶分型、J 为负）补单测；清理只在用户确认后执行，提供撤销（一次操作可整体恢复）；没有当天数据时不出清单并说明原因。
- 验收：每条判定至少一正一反用例；撤销后自选/持仓与清理前逐条一致（测试）；自动调度只提示、不自动移除。

### ST-FEAT-005 回测结果可复现并标样本数
- 类别：FEAT　scope：`Engine/Backtest.swift`、`Views/`、`Tests/`。
- 前置：OPS-003。look：是。做不做：否。窗口：—。
- 做法：回测只用冻结或已发布版本的历史数据，同一输入两次结果完全相同；结果页显示样本数、数据区间、数据来源，以及「执行分实证无预测力（相关 +0.014）」这条已知结论；样本不足明确报错。
- 验收：确定性测试；样本不足用例；页面标「历史模拟，不代表未来收益」；前后截图。

### ST-FIX-001 核对 ETF 价格缩放口径
- 类别：FIX　scope：`Engine/ETFScanner.swift`、`Data/`、`Tests/`。
- 前置：OPS-003。look：否（若显示数字变了就改成是）。做不做：否。窗口：—。
- 背景：ISA 登记过东财 ETF 价格缩放因子实测是 1000，不能固定除以 100。REASTOCK 有没有这个问题没核对过。
- 做法：先用夹具核对；已正确就只补测试并关单，不对再修成从数据推断缩放因子。
- 验收：至少 2 只 ETF（如 sh510300）在东财源和腾讯源下价格一致（夹具测试）；结论写进交卷。

---

## 第 3 段：等老板答问题再放行（列着，不排期）

### ST-FEAT-006 收盘后自动选股默认开启
- 前置：**等 Q6**；FEAT-003。scope：`Core/AutoScheduler.swift`。look：是。做不做：是。窗口：`postclose:cn`。
- 现状照旧：AutoScheduler 维持当前开关和默认值，不改。若 Q6 答「开」：只在交易日 15:35 后跑一次，任一步失败就停并通知、不发布半成品、不自动重试，结果走 FEAT-003 的版本化发布。验收：在 `postclose:cn` 窗口真跑一次留证；失败注入时当前版本不变。

### ST-FEAT-007 盘中实时报价按口径接入
- 前置：**等 Q3**；FEAT-001、OPS-004。scope：`Data/`、`Views/`。look：是。做不做：是。窗口：`trading:cn`。
- 现状照旧（腾讯报价，FEAT-001 之后会标清来源）。Q3 答了再定哪些源可用、要不要资格探针；量额按已登记口径换算（腾讯量是取整手、成交额整数万元）。验收：交易时段覆盖上午、午休、下午、收盘边界留证。

### ST-OPS-008 校准盘中执行分实时分支
- 前置：**等 Q1、Q3**；OPS-003。scope：`Engine/LastBarNormalizer.swift`、`verify/`。look：否。做不做：否。窗口：`trading:cn`。
- 只记录不改公式：开盘后、午后、收盘后三个时点算分，和收盘后结果比吻合率（已知交易日原样模型 79.4%、收盘后 83.3%、−8 组盘中专属）。不再用截屏 OCR 读第三方 App（红线 `new-re-work`）。结论写进 `docs/calibration.md` 的「仍未解」。

### ST-FEAT-008 对齐列表分与案例库叠分
- 前置：**等 Q1**；OPS-003。scope：`Engine/CaseLibraryBonus.swift`、`Views/`。look：是。做不做：是。
- 若追 1.9.1：叠分（0 或 5，实测 8/8）作为单独一列，执行分列与金标准不变；未解释的部分标「未对齐」。验收：8 只已知样本列表分全对。

### ST-UX-004 定稿今日页与建议类文案
- 前置：**等 Q2、Q7**。scope：`Views/TodayView.swift`、`Engine/TradeAdvice.swift`。look：是。做不做：是。
- 答复前文案保持现状，只保证都带「仅供参考、不构成投资建议」。答复后按措辞改今日页、止盈止损分批提示、走坏清单文案；品牌名和图标按 Q2。

### ST-DOC-003 写明 evo 与人工循环分工
- 前置：**等 Q4**。scope：`docs/evo/README.md`。look：否。做不做：否。
- 写清哪些件走 evo（工作仓库里的 ST-*），哪些仍走 ISA 的人工循环（MAC-0xx），状态各看哪里。ISA 的 `协作/` 一个字不改，有建议只写一段给老板。

---

## 给老板的问题（Q1–Q7，10-21 暂缓「到时候再说」）

答复前的默认：一律按现状，不替老板定。只有上面第 3 段的件依赖它们；OPS-001 用建议值先做，Q5 答了可以改远端名和路径。

- **Q1 评分目标版本**：以 1.8.4（金标准齐全）为准，还是追 1.9.1（列表分 = 执行分 + 案例叠分，J 值和盘中 −8 组没解释清）？影响 OPS-008、FEAT-008。
- **Q2 界面**：REASTOCK 原生 SwiftUI 就是最终界面吗？名字和图标用 vea（ISA 已定）还是 REASTOCK？ISA 的 WebChart 怎么处理？影响 UX-004、`assets/`。
- **Q3 盘中数据源口径**：只用过了资格探针的源，还是允许标明来源、未经官方对账的腾讯等实时源？影响 FEAT-007、OPS-008。
- **Q4 evo 和人工循环怎么分**：影响 DOC-003。
- **Q5 git 修复细节**：新仓库路径（建议 `~/Desktop/项目/reastock`）和私有远端名（建议 `JAY5CXSDMY14/reastock`）；旧仓库里 sb-klines/gt-klines 这些大缓存是留原处、移到仓库外数据目录还是删（默认留原处不动）；ISA 的残缺 `.git` 要不要另修。影响 OPS-001 的细节。
- **Q6 每日自动出选股**：收盘后自动跑要不要默认开？影响 FEAT-006。
- **Q7 建议类文案边界**：止盈止损分批比例、「今日关注 / 风险」能不能出现、怎么措辞？影响 UX-004，以及 FEAT-004 的文案。
