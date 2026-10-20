# ST 种子待办（合并 REASTOCK → ios-stock-app）

每一件都能直接转成 GitHub issue：标题照抄，标签 = `type:<类别>` + 每个 `scope:<目录>` + 看效果打 `look`、要老板点「做不做」打 `product`、有时间窗打 `window:<写法>`。决策岗分拣完再打 `autopilot:ready`。**本文件只是待办清单，还没建 issue。**

约定：
- 件号 `ST-<类别>-NNN`，类别只用 FEAT / FIX / UX / OPS / DOC / CHORE；标题动作开头、24 字以内，不带版本、草案。
- 「参考」指 `reference/reastock/` 里的文件（ST-CHORE-001 收进来以后才有），路径相对 REASTOCK 根目录。
- 「金标准」= ST-OPS-004 收进来的冻结 K 线和对应结果。凡是移植件，都要求 Python/JS 移植版在同一份冻结 K 线上和 REASTOCK 的 Swift 输出逐字段一致（允许误差写明在件里），不能只靠读代码。
- 所有件都守 `project.json` 的 `red_lines`。表里「前置」写的 MAC-012A/B 是老板人工循环里的件，不是 evo 的件。

## 一览

| 件号 | 标题 | scope | 前置 | look | product | 窗口 |
|---|---|---|---|---|---|---|
| ST-OPS-001 | 修复股票仓库 git 基线 | 仓库根（手工件） | 无 | 否 | 否 | — |
| ST-OPS-002 | 建一键全量测试入口 | scripts/、replica/Backend/ | OPS-001 | 否 | 否 | — |
| ST-OPS-003 | 建股票项目脱敏词表 | docs/ | OPS-001 | 否 | 否 | — |
| ST-CHORE-001 | 收录 REASTOCK 参考快照 | reference/reastock/ | OPS-001 | 否 | 否 | — |
| ST-OPS-004 | 锁定执行分金标准回归 | replica/MarketData/ | CHORE-001、OPS-002 | 否 | 否 | — |
| ST-DOC-001 | 整理 REASTOCK 校准结论 | docs/ | CHORE-001 | 否 | 否 | — |
| ST-DOC-002 | 写明 evo 与人工循环分工 | docs/ | OPS-001、老板答 Q4 | 否 | 否 | — |
| ST-FEAT-001 | 移植形态过滤与顶底分型 | replica/MarketData/ | OPS-004、老板答 Q1 | 是 | 否 | — |
| ST-FEAT-002 | 移植三周期 N 型结构判定 | replica/MarketData/ | OPS-004 | 是 | 否 | — |
| ST-FEAT-003 | 补齐详情页完美与突破评分 | replica/WebChart/ | CHORE-001、OPS-002 | 是 | 否 | — |
| ST-FEAT-004 | 新增走坏个股清理提示 | replica/MarketData/、replica/Backend/、replica/WebChart/ | FEAT-001、FEAT-002、MAC-012B | 是 | 是 | — |
| ST-FEAT-005 | 新增止盈止损分批提示 | replica/MarketData/、replica/WebChart/ | OPS-004、老板答 Q7 | 是 | 是 | — |
| ST-FEAT-006 | 新增 ETF 独立选股流程 | replica/MarketData/、replica/WebChart/ | OPS-004 | 是 | 是 | — |
| ST-FEAT-007 | 用真实历史跑 120 日回测 | replica/MarketData/、replica/WebChart/ | FEAT-001、FEAT-005 | 是 | 是 | — |
| ST-FEAT-008 | 提速盘后榜评分计算 | replica/MarketData/ | OPS-004 | 否 | 否 | — |
| ST-UX-001 | 选股显示进度并可取消 | replica/Backend/、replica/WebChart/ | FEAT-008、MAC-012B | 是 | 否 | — |
| ST-FEAT-009 | 对齐列表分与案例库叠分 | replica/MarketData/ | OPS-004、老板答 Q1 | 是 | 是 | — |
| ST-FEAT-010 | 收盘后自动生成盘后榜 | replica/MarketData/、replica/MacApp/ | FEAT-008、MAC-012A 解除、老板答 Q6 | 是 | 是 | postclose:cn（验收时） |
| ST-UX-002 | 新增今日决策页 | replica/WebChart/、replica/Backend/ | FEAT-004、FEAT-005、MAC-012B、老板答 Q2/Q7 | 是 | 是 | — |
| ST-FEAT-011 | 接入盘中实时报价并标来源 | replica/MarketData/、replica/Backend/、replica/WebChart/ | 盘中资格补证通过、老板答 Q3 | 是 | 是 | trading:cn |
| ST-FEAT-012 | 实时选股受控并发拉取 | replica/MarketData/、replica/Backend/ | FEAT-011、FEAT-008 | 是 | 是 | trading:cn |
| ST-OPS-005 | 校准盘中执行分实时分支 | replica/MarketData/ | FEAT-011 | 否 | 否 | trading:cn |

建议顺序：OPS-001（老板在场）→ OPS-002 / OPS-003 / CHORE-001 → OPS-004 / DOC-001 → FEAT-002 / FEAT-003 / FEAT-008 → 其余按老板对 Q1–Q7 的回答放行。evo 第一件建议跑 OPS-002（小、不碰界面）。

---

## 第 0 段：能让 evo 跑起来的基线

### ST-OPS-001 修复股票仓库 git 基线
- 类别：OPS　scope：仓库根目录（`.gitignore`、`.git`）　**手工件：evo 导入前由老板在场完成，不进 evo 队列**（evo 没有可用 git 就跑不起来，而且这件碰红线 `broken-git`）。
- 前置：无。look：否。product：否。
- 现状：`.git` 只剩 `hooks/ info/ logs/ objects/ refs/`，缺 `HEAD`、`config`、`index`，`refs/heads` 是空的，`refs/codex/turn-diffs` 是 Codex 的快照引用。项目 AGENTS.md 和状态页都写明「修复并复核前不声称有可用基线，不在残缺 .git 上 reset / checkout / 清理」。
- 做法：
  1. 不删旧目录：把残缺的 `.git` 整个改名为 `.git-broken-20261021`（只改名，不动里面的东西），并把它写进 `.gitignore`。
  2. 补 `.gitignore`：`**/.local/`、`**/.build/`、`.home/`、`**/__pycache__/`、`**/.venv/`、`.git-broken-*/`、`replica/MacApp/.local/`、`*.app/`；根目录 `backend/.env` 已被 `.env` 规则覆盖，确认它不进库。
  3. 先量体积：`du -sh 协作/证据 outputs work docs`。`协作/证据` 里单个超过 5 MB 的原文先列给老板决定（入库、走 LFS、或只保留哈希清单），不默默入库。
  4. `git init -b main` → `git add -A` → 核对 `git status` 里没有 `.local`、`.env`、`.venv`、`.app` → 首个提交「建立仓库基线」。
  5. 老板定了私有仓库名再 `gh repo create <名字> --private --source . --push`。
- 验收：`git status --porcelain` 为空；`git ls-files | grep -E '\.local/|\.env$|\.venv/|\.app/'` 为空；`.git-broken-20261021` 原样还在；`git log --oneline` 有一个提交；若建了远端，`git remote -v` 指向私有仓库。
- 参考：项目 `AGENTS.md`、`协作/项目循环.md`「本项目边界」。

### ST-OPS-002 建一键全量测试入口
- 类别：OPS　scope：`scripts/`、`replica/Backend/`（只改测试依赖说明，不改产品代码）。
- 前置：OPS-001。look：否。product：否。
- 背景：现在 6 套测试各有各的跑法，Backend 还要借 `replica/MacApp/.local/mac012a/test-env` 里的虚拟环境，evo 的 `test_cmd` 没法稳定复用。
- 做法：新建 `scripts/test-all.sh`：依次跑 MarketData、Backend、Simulation（`python3 -B -m unittest discover -s tests`）、WebChart 四个 `node --test`、`replica/MacApp/scripts/tests`、`replica/MacApp` 的 `swift test`。Backend 依赖按 `requirements-test.lock` 在 `.local/test-env`（已忽略）里自建，已存在且锁文件哈希没变就复用。任何一套红就整体非 0 退出，并在最后打印每套的通过数。不联网的套件要在断网时也能跑（依赖安装那一步除外）。
- 验收：干净克隆里第一次跑 `bash scripts/test-all.sh` 全绿、退出 0；第二次不重装依赖；故意让一个测试失败时退出码非 0，输出里点名是哪一套；各套通过数不少于现有基线（MarketData 355、Backend 90、Simulation 150、WebChart 99、打包脚本 47、Swift 21）。

### ST-OPS-003 建股票项目脱敏词表
- 类别：OPS　scope：`docs/`（只放说明）；词表本体放仓库外 `~/.evoloop/projects/ST/policy-terms.txt`。
- 前置：OPS-001。look：否。product：否。
- 做法：从老板那里拿要屏蔽的词（券商与资金账号、持仓明细里的数量和成本、手机号、真实姓名、API 密钥前缀、机器内网地址），写进仓库外词表；`docs/evo/policy-terms.md` 只写「词表在哪、怎么加」，不写词本身。项目配置 `policy_terms` 指向它。
- 验收：`evo add` 一个标题含词表词的件被拒；`git grep -f <词表>` 在仓库里没有命中（命中的列给老板处理，不自动改）。

### ST-CHORE-001 收录 REASTOCK 参考快照
- 类别：CHORE　scope：`reference/reastock/`。
- 前置：OPS-001。look：否。product：否。
- 为什么不直接并历史：REASTOCK 的 git 索引里跟踪了约 200 MB 的东西，其中有 Ghidra 工程（约 76 MB，对第三方 App 二进制的逆向工程）、`verify/` 约 99 MB 的抓取数据、`ui-shots/` 约 22 MB 截图。`git subtree` 会把这些和逆向材料一起永久带进主仓库，所以只收精选文件快照，原仓库留原地做档案。
- 做法：从 REASTOCK 提交 `378d7eee1140a3cd497865d03859cfebed20ccda` 复制下列内容到 `reference/reastock/`，并写 `reference/reastock/PROVENANCE.md`（来源路径、提交号、每个文件的 SHA-256、明确「只读参考、不参与构建」）：
  - `README.md`、`Package.swift`、`scripts/build-app.sh`
  - `REASTOCK/Sources/REASTOCK/**`（69 个 Swift 文件 + `Resources/CaseFingerprints.json`、`Resources/StructureRAG.json`）
  - `docs/*.md`（22 份校准与审计文档）
  - `verify/regression.sh`、`verify/verify-all.sh`、`verify/cross-check.sh`、`verify/js-harness.mjs`、`verify/baseline/**`、`verify/truth-2026-10-16/**`、`verify/picks/**`、`verify/perfect-cases.json`、`verify/name-code-map.json`、`verify/swift-*.json`、`verify/klines-*.json`（共 24 只冻结日 K 与 Swift 输出，约 1.3 MB）
  - `tools/*.py`、`tools/collect-*.sh`
  - `ui-shots/` 只挑：`final-detail3.png`、`final-screening.png`、`final-holdings.png`、`final-settings.png`、`reastock-3col3.png`、`today-final.png`、`v7-market.png`（界面参考，约 2 MB）
  - **不收**：`project.json` 里 `reference.never_import` 列的全部内容。
- 验收：`reference/reastock/` 总体积 < 15 MB；PROVENANCE 里每个哈希与原仓库文件一致（抽 10 个复算）；仓库里搜不到 `ghidra`、`StockStation-bin`、`engine-extracted` 文件；任何构建和测试都不引用 `reference/`。

---

## 第 1 段：把 REASTOCK 的校准成果变成可回归的资产

### ST-OPS-004 锁定执行分金标准回归
- 类别：OPS　scope：`replica/MarketData/`（`tests/` 和 `tests/fixtures/reastock/`）。
- 前置：CHORE-001、OPS-002。look：否。product：否。
- 背景：REASTOCK 宣称的 588/588 吻合，是拿 ST 自己的 `replica/MarketData/app/score_engine.py`（1.8.4 原生公式的逐指令转写）当权威算出来的。真正独立的真值只有三类：原 App 界面读数（海油发展 58、海南机场 39、中远海发 58，冻结于 10-14 收盘）、1.8.4 官方评分板 588 只（9-24）、106 只实时读数表。
- 做法：把三类独立真值和对应冻结 K 线收进夹具；新增测试：`score_engine.py` 对三只界面读数精确相等；对官方评分板逐只比对，吻合数不低于 587/588，唯一已知差异中国化学 sh601117 写成显式例外并注明原因；24 只冻结 K 线上，`score_engine.py` 的七项分项与 REASTOCK `swift-*.json` 一致（这是以后所有移植件的对照基准）。
- 验收：新测试进 `scripts/test-all.sh` 且全绿；故意把项 5 的长 BBI 参数改回 3/6/12/24，测试必须红；夹具只来自 `reference/reastock/`，不联网。

### ST-DOC-001 整理 REASTOCK 校准结论
- 类别：DOC　scope：`docs/`（新文件 `docs/reference/reastock-calibration.md`，不碰 `docs/reference/stockstation/`）。
- 前置：CHORE-001。look：否。product：否。
- 做法：把 22 份文档压成一份：已证实的（七项分档、封顶顺序、长 BBI 14/28/57/114、KDJ 9 根、量比口径、止损三套口径）、已证伪的（5 日跌幅压制等四个假设）、仍未解的（1.9.1 列表分来源、盘中 −8 组、J≥80 封顶 52 还是 48、砖型评分权重），以及教训（两个正样本的「完美相关」会被 97 只数据推翻，规则至少要 5 个以上正样本；JS 参考实现 KDJ 用了 10 根是 bug；执行分实证无预测力，相关 +0.014）。每条注明出处文件。
- 验收：每条结论都能点到 `reference/reastock/docs/` 里的原文；「仍未解」一节不少于 4 条；不写成投资建议。

### ST-DOC-002 写明 evo 与人工循环分工
- 类别：DOC　scope：`docs/`（新文件 `docs/evo/README.md`；`协作/` 一个字不改）。
- 前置：OPS-001，老板回答 Q4。look：否。product：否。
- 做法：写清哪些件走 evo（ST-*），哪些仍走 Codex → DSH → 验收官（MAC-0xx），两边怎么避免同时改同一文件（例如 MAC-012B 开工期间 evo 不接碰 `replica/WebChart/` 的件），状态各看哪里（`evo status` 与 `协作/状态.md`）。要改 `协作/项目循环.md` 的话，只写一段建议给老板。
- 验收：老板读完能回答「这件该交给谁」；文中列出的每条红线都和 `project.json` 一致。

---

## 第 2 段：引擎移植（REASTOCK 的 1.9.1 功能 → ST 的 Python / JS）

### ST-FEAT-001 移植形态过滤与顶底分型
- 类别：FEAT　scope：`replica/MarketData/`（新模块 `app/pattern_filter.py` + 测试）。
- 前置：OPS-004；老板回答 Q1（以哪一版评分为准）。look：是（榜单里会出现瑕疵扣分、排除标记）。product：否。
- 参考：`REASTOCK/Sources/REASTOCK/Engine/PatternFilter.swift`、`docs/原App文案挖掘.md`。
- 做法：移植 10 条形态规则（长上影、高换手、倒锤子排除、锤子保留、瑕疵扣 10、底分型 / 顶分型）。作为执行分之外的独立标记和可选过滤，不改 `score_engine.py` 的七项和封顶。
- 验收：24 只冻结 K 线上，每条规则的命中和 Swift 版一致；`score_engine.py` 产出的分数与 scoreboardHash 不变；manual_checks 写明在榜单里看哪几只带标记。

### ST-FEAT-002 移植三周期 N 型结构判定
- 类别：FEAT　scope：`replica/MarketData/`（新模块 `app/triple_cycle.py`）。
- 前置：OPS-004。look：是。product：否。
- 参考：`Engine/TripleCycle.swift`、`Engine/LongCycleBrick`（在 `BrickScoreEngine.swift` 里）。
- 做法：日 K 聚合成周 K、月 K，按「高点、低点都抬高」判 N 型；输出三周期状态和长周期砖型三态（红 / 绿 / 青），作为榜单附加字段和选股过滤条件。
- 验收：周 K、月 K 聚合用交易日历切分（不是自然周），有测试覆盖跨节假日；24 只冻结 K 线三周期结论与 Swift 版一致；K 线不足时返回「不可计算」并写原因，不给默认值。

### ST-FEAT-003 补齐详情页完美与突破评分
- 类别：FEAT　scope：`replica/WebChart/`（`strategy-engine.js` + 测试）。
- 前置：CHORE-001、OPS-002。look：是（详情页出现完美评分、突破判定）。product：否。
- 背景：WebChart 的 README 明确写着「未实现完整树 + RAG 融合评分」；REASTOCK 已实现，并与原 JS 引擎交叉验证 19/20。
- 参考：`Engine/PerfectScoreEngine.swift`、`Engine/PerfectVector.swift`、`Engine/BreakoutEngine.swift`、`verify/cross-check.sh`、`verify/js-harness.mjs`、`verify/perfect-cases.json`。
- 做法：在 `strategy-engine.js` 里补 `treeScore`、`ragSim`、融合分（0.55 / 0.45）、突破判定、黄金相似度、三套止损；继续用「参考核心」命名，和 `mock*` 启发式分开。
- 验收：对 20 只冻结 K 线，融合分、明细 16 项、止损和 REASTOCK 输出一致，误差 ≤ 0.001，唯一已知不一致那只写成显式例外；KDJ 窗口按 9 根（REASTOCK 已证明 JS 参考的 10 根是 bug），并有对应测试；详情页来源标注仍写「本地计算，非真实信号」。

### ST-FEAT-004 新增走坏个股清理提示
- 类别：FEAT　scope：`replica/MarketData/`、`replica/Backend/`、`replica/WebChart/`。
- 前置：FEAT-001、FEAT-002；MAC-012B 已合入（界面归属定了再动 WebChart）。look：是。product：是。
- 参考：`Engine/RiskRules.swift`（`WeakStockDetector`）、`Views/WeakCleanupSheet.swift`、`docs/复刻完成度-最终.md`「走坏判定」。
- 做法：对自选和持仓按四条判走坏（跌破止损、砖型未翻红、顶分型、J 为负），盘后榜发布后给出一份清单；默认只提示，移除要用户点确认，可撤销。
- 验收：判定规则有单测（每条至少一正一反）；个人记录 SQLite 只在用户确认后才改，撤销能恢复；没有当日盘后榜时不出清单，写明原因；文案带「仅供参考」。

### ST-FEAT-005 新增止盈止损分批提示
- 类别：FEAT　scope：`replica/MarketData/`、`replica/WebChart/`。
- 前置：OPS-004；老板回答 Q7（仓位类提示能不能做、怎么措辞）。look：是。product：是。
- 参考：`Engine/RiskRules.swift`（≥85 首仓 50%、70–84 首仓 30%、放飞 50% / 75%）、`Engine/TradeAdvice.swift`。
- 做法：在详情页显示「参考止损位 / 参考止盈档」，数字来自已核验的计算；仓位比例是否显示按 Q7 的答复。
- 验收：止损三套口径（B1 / B2 / B3）与 ST-OPS-004 金标准一致；所有提示带「仅供参考、不构成投资建议」；没有任何下单、导出到券商的入口。

### ST-FEAT-006 新增 ETF 独立选股流程
- 类别：FEAT　scope：`replica/MarketData/`、`replica/WebChart/`。
- 前置：OPS-004。look：是。product：是。
- 参考：`Engine/ETFScanner.swift`（规模六档、钩头 → J 顶自适应）。
- 做法：ETF 单独一条选股流程和榜单，口径与股票榜分开。东财 ETF 价格缩放因子实测是 1000，不许固定除以 100（状态页已登记的口径约束）。
- 验收：ETF 与股票不混在一个榜；规模分档有单测；缩放因子从数据推断并有测试；来源和新鲜度标注齐全。

### ST-FEAT-007 用真实历史跑 120 日回测
- 类别：FEAT　scope：`replica/MarketData/`、`replica/WebChart/`。
- 前置：FEAT-001、FEAT-005。look：是。product：是。
- 参考：`Engine/Backtest.swift`、`tools/backtest-*.py`、`docs/执行分预测力验证.md`。
- 做法：替换 WebChart 里的 Mock 回测：基于已核验的历史快照跑三种策略和「放飞 / 破 BBI」卖出规则；结果页同时显示样本数和「执行分实证无预测力」这一已知结论。
- 验收：同一输入两次运行结果完全相同；只用封存过的历史数据，不联网；样本不足时明确报错不出结果；页面标「历史模拟，不代表未来收益」。

### ST-FEAT-008 提速盘后榜评分计算
- 类别：FEAT　scope：`replica/MarketData/`。
- 前置：OPS-004。look：否（批处理，用户不直接等它；耗时写进交卷）。product：否。
- 参考：`Engine/ScreeningEngine.swift`（并发 8 相对串行 7.9 倍、缓存命中 315 倍）、`Core/ScanBench.swift`。
- 做法：只在**本地计算**这一侧提速：按 inputSetId 缓存已解析的 K 线和指标；600 只评分改为多进程或线程池计算；加 `--bench` 打印耗时。**联网采集的单线程、间隔 ≥2 秒等 netpolicy 规则一个都不改**（红线 `network-scope`）。
- 验收：N=600 夹具上，提速前后 scoreboardHash 完全一致；耗时下降写进交卷（给出前后数字）；缓存键含输入哈希，输入变了必然失效（有测试）；netpolicy 相关测试原样通过。

### ST-UX-001 选股显示进度并可取消
- 类别：UX　scope：`replica/Backend/`、`replica/WebChart/`。
- 前置：FEAT-008；MAC-012B 已合入。look：是。product：否。
- 参考：`ScreeningEngine.Phase`（拉列表 → 硬过滤 → 评分 n/N）、`Views/ScreeningView.swift`。
- 做法：筛选按阶段回报进度，可以随时取消；取消后界面回到之前的结果，不留半截数据。
- 验收：有进度、完成、取消、失败四种状态，并有测试；取消后不残留旧来源标签（沿用 WebChart「不混源」规矩）；遵守 reduced motion。

### ST-FEAT-009 对齐列表分与案例库叠分
- 类别：FEAT　scope：`replica/MarketData/`。
- 前置：OPS-004；老板回答 Q1。look：是。product：是。
- 参考：`Engine/CaseLibraryBonus.swift`、`docs/1.9.1与1.8.4差异发现.md`（列表分 = 执行分 + 案例库叠分 0 或 5，实测 8/8）、`docs/执行分剩余偏差分析.md`。
- 做法：如果 Q1 选追 1.9.1，就把叠分作为单独一列，不改执行分本身；1.9.1 新版 J 值差异、盘中 −8 组未解释部分如实标「未对齐」。
- 验收：8 只已知样本列表分全对；执行分列与 ST-OPS-004 金标准不变；界面上执行分和列表分有区分说明。

---

## 第 3 段：日常闭环与盘中（路线图第 1、2 步）

### ST-FEAT-010 收盘后自动生成盘后榜
- 类别：FEAT　scope：`replica/MarketData/`、`replica/MacApp/`（调度入口）。
- 前置：FEAT-008；MAC-012A 解除受阻（有可发布的新榜）；老板回答 Q6。look：是。product：是。窗口：验收时用 `postclose:cn`（收盘后才有当天数据）。
- 参考：`Core/AutoScheduler.swift`（默认 15:35、只在交易日、走坏只提示不自动移除）。
- 做法：交易日收盘后跑一次「采集 → 官方对账 → 评分 → 发布新版本 + 原子切换指针」；任一步非 0 就停在那一步并通知，不发布半成品；不在休市日跑。
- 验收：在 `postclose:cn` 窗口里真跑一次并留证；失败注入（采集失败、对账不过）都停在对应步骤，旧榜仍是当前版本；没有自动重试循环；不碰 apply。

### ST-UX-002 新增今日决策页
- 类别：UX　scope：`replica/WebChart/`、`replica/Backend/`。
- 前置：FEAT-004、FEAT-005；MAC-012B 已合入；老板回答 Q2、Q7。look：是。product：是。
- 参考：`Views/TodayView.swift`（只给「关注什么 / 风险什么 / 市场环境」，完整判据收在详情页）、`ui-shots/today-final.png`。
- 做法：作为 vea 的首页模块：当日盘后榜高分、走坏清单、市场环境一句话；每块标数据日期和来源。措辞按 Q7 回答，不用「买 / 卖」这类指令式字眼（除非老板同意）。
- 验收：没有盘后榜时显示真实空态并说明原因；每块都有来源和日期；三视口（1440×900、960×760、390×844）无截断。

### ST-FEAT-011 接入盘中实时报价并标来源
- 类别：FEAT　scope：`replica/MarketData/`、`replica/Backend/`、`replica/WebChart/`。
- 前置：盘中资格补证通过（人工循环里的 MAC-012 盘中探针）；老板回答 Q3。look：是。product：是。窗口：`trading:cn`。
- 参考：`Data/MarketDataService.swift`（腾讯 qt 报价为主、日 K 多源降级、需要 Referer、有限重试）、`Data/IPv4URLProtocol.swift`。
- 做法：只接资格探针认可的报价源；量和额按已登记口径换算（腾讯量是取整手、成交额是整数万元）；供应商时间、行情交易日、接收时间分开记；不混源补行，取不到就显示「暂无实时价」，不用旧收盘价填。
- 验收：交易时段真跑并留证（覆盖上午、午休、下午、收盘边界）；新鲜度和来源标注逐项显示；断网时界面如实降级；限频和重试次数在配置里且有测试。

### ST-FEAT-012 实时选股受控并发拉取
- 类别：FEAT　scope：`replica/MarketData/`、`replica/Backend/`。
- 前置：FEAT-011、FEAT-008。look：是（选股速度）。product：是。窗口：`trading:cn`。
- 参考：`Engine/ScreeningEngine.swift`（并发 8、全市场列表缓存 60 秒、日 K 缓存 300 秒）。
- 做法：只对 FEAT-011 已认可的实时源用受控并发；并发数、缓存时长可配，默认值保守；官方源仍单线程（红线 `network-scope`，提高并发要老板批）。
- 验收：交易时段 150 只基准实测（串行 vs 并发 vs 缓存命中）写进交卷；触发限频时自动退回串行并标注；结果与串行版逐只一致。

### ST-OPS-005 校准盘中执行分实时分支
- 类别：OPS　scope：`replica/MarketData/`（测试与校准工具）。
- 前置：FEAT-011。look：否。product：否。窗口：`trading:cn`。
- 参考：`Engine/LastBarNormalizer.swift`、`docs/开盘工作计划.md`、`docs/交易日验证结果.md`（交易日原样模型 79.4%、收盘后 83.3%、−8 组盘中专属）。
- 做法：在交易时段用实时 bar 算分，和收盘后结果对比，记录吻合率和差异分布；只做记录与测试，不改公式。REASTOCK 用截屏 OCR 读原 App 的办法只作参考，不进 ST（依赖第三方 App 窗口，不可复现）。
- 验收：至少三个时点（开盘后、午后、收盘后）留证；结论写进 `docs/reference/reastock-calibration.md` 的「仍未解」一节，不硬改规则；没有 5 个以上正样本的规律不写成规则。

---

## 给老板的问题（Q1–Q7，决定上面哪些件能放行）

- **Q1 评分目标版本**：以 1.8.4（已逐指令转写、金标准齐全）为准，还是追 1.9.1（列表分 = 执行分 + 案例叠分，J 值和盘中 −8 组还没解释清）？影响 FEAT-001、FEAT-009。
- **Q2 哪套界面胜出**：vea（WebChart + Mac 壳，MAC-012B 已定名、定图标）当唯一界面，REASTOCK 的三栏原生 SwiftUI 只当交互参考？还是以后改成原生 SwiftUI？影响 UX-001、UX-002 和所有 look 件。
- **Q3 实时数据口径**：盘中功能只能用通过资格探针的源，还是允许「标明来源、未经官方对账」的腾讯等实时源先用起来？影响 FEAT-011、FEAT-012。
- **Q4 evo 和人工循环怎么分**：evo 只接新 ST 件、MAC-012A/B 继续人工？还是 MAC-012B 也转进 evo？影响 DOC-002、所有碰 WebChart 的件。
- **Q5 git 基线**：同意 OPS-001 的做法吗（旧 `.git` 只改名保留、重新建库、首个提交）？私有仓库叫什么？`协作/证据` 里的大文件入库、走 LFS，还是只留哈希清单？
- **Q6 每日自动出榜**：MAC-012A 的裁定禁止为补证设定时任务和自动重试。每个交易日收盘后自动出榜算不算新的允许？影响 FEAT-010。
- **Q7 提示类文案边界**：止盈止损分批比例、「今日关注 / 风险」这类提示能不能出现？用什么措辞？影响 FEAT-004、FEAT-005、UX-002。
