# ST · 股票项目（evo 第二个项目）

## ST 是什么
老板自用的 A 股复盘与盘中协助工具，macOS 上的正式名字是 **vea**（价格阶梯图标，MAC-012B 已定）。路线三步：① 稳定出盘后复盘榜，给第二个交易日方向；② 盘中协助；③ AI 在模拟账户里按规矩交易。**全程只观察和模拟，不接券商、不下真单。**

ST 把 Mac mini 上的两个项目合成一个：

| | ios-stock-app（主仓库） | REASTOCK（参考） |
|---|---|---|
| 位置 | `~/Desktop/项目/ios-stock-app` | `~/Desktop/项目/jailbreaks/reastock` |
| 主线 | `replica/`：Mac 壳（Swift，约 74 KB）+ WebChart 界面（JS，约 300 KB）+ 本地后端（Python FastAPI）+ 盘后数据流水线 MarketData（Python，约 500 KB）+ 模拟服务 Simulation（Python，约 200 KB）；内嵌 CPython 打包成 App | 纯原生 SwiftUI，69 个 Swift 文件约 635 KB，26 个引擎模块，8 个页面三栏布局 |
| 测试 | 约 760 个自动测试：MarketData 355、Backend 90、Simulation 150、WebChart 99、打包脚本 47、Swift 21 | 没有单元测试目标；靠脚本对冻结数据回归（3 只界面真值、588 只评分板、20 只 JS 交叉验证） |
| 数据 | 官方交易所对账、封存原文、来源与新鲜度逐项标注；榜单版本化发布 | 腾讯实时报价 + 日 K 多源降级（腾讯 → 新浪 → 东财），没有官方对账 |
| 长处 | 数据可信、红线和证据纪律、打包/校验/安装流水线、品牌已定 | 1.9.1 新功能（形态过滤、三周期、走坏清理、止盈止损、ETF、回测、完美/突破评分）、选股并发提速 7.9 倍、缓存 315 倍、收盘自动选股、页面更全 |
| 短板 | `.git` 残缺（没有 HEAD/config/index）；流程很重；MAC-012A 等官方深市数据，从 10-04 起停着；界面除盘后榜外多是 Mock | git 里跟踪了约 200 MB 杂物，含对第三方 App 逆向的 Ghidra 工程；部分校准还没解开 |
| git | 不可用 | 健康，`main` 约 60 个提交（10-14 至 10-19），没有远端，HEAD `378d7ee` |

## 合并方案（推荐）
**一个主仓库 = ios-stock-app；REASTOCK 不并历史，只收一份精选快照做参考，它的长处按能力拆成待办，逐件移植进现有架构。**

理由：
1. **权威公式已经在 ST 里。** REASTOCK 说的「588/588 吻合」，是拿 ios-stock-app 的 `replica/MarketData/app/score_engine.py`（1.8.4 原生公式逐指令转写）当标准量出来的。真相本来就在主仓库，REASTOCK 证明的是它的 Swift 版和这份 Python 对得上。
2. **测试和数据纪律搬不动，功能搬得动。** 约 760 个测试、官方对账、版本化发布、安装流水线都绑在 Python/JS 架构上，换成 REASTOCK 等于全部重来。REASTOCK 的功能大多是纯计算，用它的冻结 K 线和 Swift 输出当金标准，移植成 Python/JS 后可以逐字段对拍，风险可控。
3. **合规和体积。** REASTOCK 的 git 历史带着 Ghidra 逆向工程和大量抓取数据，并进主仓库就永远去不掉。快照只收源码、文档、小体积冻结数据，按提交号钉住。
4. **主仓库本来就是唯一主目录**（`PROJECT_ROOT.md`），vea 的名字、图标和 MAC-012B 界面计划都在这里。

不推荐的做法：以 REASTOCK 为主（丢掉测试、数据纪律和打包）；`git subtree` 整个并进来（带进逆向材料和约 200 MB 杂物）；两边长期并行开发（同一套评分维护两份）。

这次不做决定、交给老板的：界面最后用哪套（vea 的 WebChart，还是将来改原生 SwiftUI）。我的建议是 MAC-012B 做完前不换，REASTOCK 的页面先当交互参考，见 `backlog.md` 的 Q2。

## 文件
- `project.json`：项目配置，含 scope 标签、看效果规则、时间窗用法、红线（决策岗的升级规则）、人工循环和参考仓库说明。
- `backlog.md`：22 件种子待办（ST-OPS / CHORE / DOC / FEAT / UX），每件写了 scope、前置、验收标准、要不要看效果，可以直接转成 GitHub issue；文末是 7 个要老板拍板的问题。

## 在 Mac mini 上导入（按顺序）
> evo 没有可用的 git 就跑不起来，所以第 1 步必须先做，而且要老板在场（红线：不在残缺 .git 上 reset/checkout/清理）。

1. **修 git 基线（ST-OPS-001，手工）**
   ```bash
   cd ~/Desktop/项目/ios-stock-app
   mv .git .git-broken-20261021          # 只改名，原样保留
   # 按 backlog ST-OPS-001 补 .gitignore（**/.local/、**/.build/、.home/、**/__pycache__/、**/.venv/、.git-broken-*/、*.app/）
   du -sh 协作/证据 outputs work docs   # 大文件先给老板过目
   git init -b main && git add -A
   git status --short | grep -E '\.local/|\.env$|\.venv/|\.app/' && echo "有不该入库的，先处理"   # 这行应该什么都不打印
   git commit -m "建立仓库基线"
   # 老板定了名字再建私有远端：
   # gh repo create JAY5CXSDMY14/ios-stock-app --private --source . --push
   ```
2. **登记项目**
   ```bash
   evo import ST --name 股票 \
     --path ~/Desktop/项目/ios-stock-app \
     --goal "把股票项目做成 vea：先稳定出盘后复盘榜给次日方向，再做盘中协助；吸收 REASTOCK 的 1.9.1 评分、选股提速和日常页面。只观察和模拟，不做真实交易。" \
     --test "bash scripts/test-all.sh"
   # 建了 GitHub 私有仓库就再加 --github JAY5CXSDMY14/ios-stock-app
   ```
   `evo import` 不动代码和历史，只写 `~/.evoloop/projects/ST/config.json`，放一份未提交的 `AGENT_INTERFACE.md`，登记 Orca。
3. **用本目录的配置补齐**（只补 import 不会写的键，import 生成的 repo/github 等以实际为准）
   ```bash
   KIT=<evoloop 仓库>/kit
   python3 - "$KIT/profiles/st/project.json" ~/.evoloop/projects/ST/config.json <<'PY'
   import json, sys
   prof, cfg = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
   keep = {"code", "repo", "main_branch", "github_repo", "push_cmd"}   # 以 import 实际结果为准
   for k, v in prof.items():
       if k not in keep:
           cfg[k] = v
   json.dump(cfg, open(sys.argv[2], "w"), ensure_ascii=False, indent=2)
   PY
   ```
   `scripts/test-all.sh` 要等 ST-OPS-002 做完才有；在那之前把 `test_cmd` 临时换成 `project.json` 里的 `_test_cmd_interim`。
4. **时间窗**：在全局 `~/.evoloop/config.json` 的 `windows` 里填当年 A 股休市日（`holidays`），并加一个收盘后窗口：
   ```json
   "windows": {"tz": "Asia/Shanghai", "holidays": ["2027-01-01"],
               "presets": {"postclose:cn": "mon-fri 15:35-23:30"}, "holiday_presets": ["postclose:cn"]}
   ```
   要看真实盘中数据的件用 `--window trading:cn`（周一到周五 09:30–11:30、13:00–15:00，跳过休市日），收盘后才有数据的件用 `--window postclose:cn`。具体哪几件见 `backlog.md`。
5. **脱敏词表（ST-OPS-003）**：建 `~/.evoloop/projects/ST/policy-terms.txt`（仓库外，不入库），配置里 `policy_terms` 已指向它。
6. **第一件**：`evo -p ST add --kind ops --title "建一键全量测试入口" --scope scripts/,replica/Backend/`。小、不碰界面，用来确认真工人、真验收在这个仓库里跑得通。
7. **REASTOCK 原仓库**：留在原处只读归档，不再在那里开发；它的精选快照由 ST-CHORE-001 收进 `reference/reastock/`（钉住提交 `378d7eee1140a3cd497865d03859cfebed20ccda`）。

## 和原来的人工循环怎么相处
- 原循环（Codex 写任务书 → DSH 施工 → Claude Code 验收官，状态在 `协作/状态.md`）继续管 MAC-0xx：MAC-012A 受阻挂账（维持 2026-09-30 / N=600），MAC-012B 排队。
- evo 只接新的 `ST-<类别>-NNN`；旧件保留原名，不迁移，除非老板另说（`backlog.md` Q4）。
- evo 的工人一律不写 `协作/`。MAC-012B 开工期间，evo 不接碰 `replica/WebChart/` 的件，避免两边同时改同一个文件。
- 正式安装（`install_app.py --apply`）永远等老板在场；`deploy_cmd` 故意留空。

## REASTOCK 里要留作参考的文件
详见 `backlog.md` ST-CHORE-001。简单说：
- **收**：`REASTOCK/Sources/REASTOCK/**`（全部 Swift 和两份 JSON 资源）、`docs/*.md`（22 份校准与审计）、`verify/` 的回归脚本、`baseline/`、`truth-2026-10-16/`、`picks/`、20 只 JS 交叉验证样本、24 只冻结日 K 和 Swift 输出、`tools/*.py` 和采集脚本、`README.md`、`Package.swift`、`scripts/build-app.sh`、7 张界面截图。
- **不收**：Ghidra 工程和脚本、`analysis/`（原 App 二进制）、`rea/`、`tools/ghidra*`、`tools/winutil/`、`backup/`（原 App 的 plist）、`verify/engine-extracted.js`（抽出的第三方代码）、`verify/sb-klines/`、`verify/gt-klines/`、`verify/live-scores*/`、其余截图、构建产物。

## 盘点时看不到的（Mac mini 上要核）
- 这次是通过 MCP 只读文件盘点的，不能在 Mac 上跑命令。ios-stock-app 的 git 状态是从 `.git` 目录结构判断的（缺 HEAD/config/index，`refs/heads` 为空）；REASTOCK 的跟踪文件和体积是解析它的 `.git/index` 得出的，没有跑 `git status`，所以 REASTOCK 有没有未提交改动没确认。
- 测试数字取自 `协作/交付/MAC-012A.md` 最近一轮登记（10-02），这次没有重跑。
- `协作/证据` 有多大、哪些该入库，要在 ST-OPS-001 的 `du` 那一步看。
