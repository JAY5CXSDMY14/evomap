# ST · 股票项目（evo 第二个项目）

## ST 是什么
老板自用的 A 股复盘与盘中协助 Mac 应用。路线三步：① 稳定出盘后复盘和次日方向；② 盘中协助；③ AI 在模拟账户里按规矩交易。**全程只观察和模拟，不接券商、不下真单。**

**老板 2026-10-21 定：REASTOCK 为主力。** 他现在推进的就是 REASTOCK，两边本质是同一类产品。所以：

| | REASTOCK（主力工作代码库） | ios-stock-app（严谨性来源，只读） |
|---|---|---|
| 位置 | 旧仓库 `~/Desktop/项目/jailbreaks/reastock`（档案）→ 干净工作仓库建议 `~/Desktop/项目/reastock`（ST-OPS-001 建） | `~/Desktop/项目/ios-stock-app` |
| 拿它的什么 | 全部：原生 SwiftUI 三栏界面、8 个页面、26 个引擎模块、1.9.1 功能（形态过滤、三周期、走坏清理、止盈止损、ETF、回测、完美/突破评分）、选股并发提速 7.9 倍、缓存 315 倍、收盘自动选股 | 只拿严谨性：`score_engine.py`（1.8.4 逐指令转写）当执行分金标准；约 760 个测试里适用的部分；官方交易所对账；版本化发布；联网规则（官方源单线程、间隔 ≥2 秒）；打包校验思路 |
| 现状（10-21 经 MCP 只读核对） | git 健康，HEAD `378d7ee`（10-19 15:45），之后没有新提交；源码 67 个文件 0.64 MB；**没有单元测试目标**，只有脚本对冻结数据回归；git 里跟踪了约 201 MB 杂物 | `.git` 残缺（无 HEAD/config/index），任何 git 操作都不做；人工循环照旧管 MAC-0xx |

一句话：**在 REASTOCK 上开发，把 ios-stock-app 的纪律一件一件搬进来，不反过来。**

## 文件
- `project.json`：项目配置。`repo` 指向干净工作仓库；`scope_labels` 是工作仓库里的目录；`red_lines` 是决策岗的升级规则；`reference` 写清从 ios-stock-app 搬什么不搬什么、旧仓库的体积核对和不收清单；`open_questions` 是老板暂缓的 Q1–Q7。
- `backlog.md`：26 件种子待办（第 0 段基线 → 第 1 段移植严谨性 → 第 2 段功能打磨 → 第 3 段等老板答问题），每件写了 scope、前置、验收、look、做不做、时间窗，可以直接转成 GitHub issue。

## 给接手的 AI：先读这几条
1. **只在干净工作仓库里写。** 旧 REASTOCK 仓库和 ios-stock-app 都只读，不在上面跑任何 git 命令（红线 `archives-readonly`）。要用里面的文件，复制进工作仓库的 `reference/ios-stock-app/` 并写 PROVENANCE（原路径、日期、SHA-256）。
2. **逆向材料永远不进工作仓库**：Ghidra 工程/脚本、`analysis/`、`rea/`、`backup/`、`tools/ghidra*`、`tools/winutil/`、`verify/engine-extracted.js`（红线 `no-re-materials`）。
3. **改分数先过金标准。** ST-OPS-003 之后，任何改执行分/完美分/选股结果的件都必须在金标准上逐字段一致；不许为了变绿改夹具（红线 `golden-guard`）。
4. **Q1–Q7 不替老板定。** 老板 10-21 说「到时候再说」。只有 backlog 第 3 段依赖它们；碰到就挂起交老板（红线 `open-questions`），其余照现状做。
5. **来源要诚实。** 不混源补行、不用旧收盘价顶当前价、取不到就说取不到（红线 `honest-sources`）。
6. **不装正式包。** 覆盖 `/Applications` 和装后第一次启动等老板在场；`deploy_cmd` 故意留空。

## 在 Mac mini 上导入（按顺序）

### 第 1 步：建干净工作仓库（ST-OPS-001，手工，老板在场）
为什么：旧仓库 git 跟踪约 201 MB，其中 `verify/` 抓取数据 99 MB（sb-klines 52、gt-klines 24、live-scores* 23）、Ghidra 逆向工程 76 MB、截图 22 MB，源码只有 0.64 MB。从当前树开新历史，旧仓库原样留作档案。路径和远端名是 Q5，下面用建议值，老板当场可改。

```bash
OLD=~/Desktop/项目/jailbreaks/reastock
NEW=~/Desktop/项目/reastock            # Q5：老板可改
git -C "$OLD" status --short                            # 应为空；有改动先问老板
git -C "$OLD" rev-parse HEAD                            # 记下，应为 378d7eee…

cat > /tmp/st-exclude.txt <<'EOF'
.git/
.build/
.build-probe/
build/
ghidra-proj/
ghidra-home/
ghidra-scripts/
analysis/
rea/
backup/
tools/ghidra*
tools/winutil/
verify/engine-extracted.js
verify/sb-klines/
verify/gt-klines/
verify/live-scores*/
verify/live1015/
ui-shots/
.DS_Store
*.log
EOF
mkdir -p "$NEW" && rsync -a --exclude-from=/tmp/st-exclude.txt "$OLD/" "$NEW/"
# 注意：verify/klines-*.json、swift-*.json、js-*.json 只在磁盘上（旧 .gitignore 的 verify/*.json 挡住了），rsync 会带过来，git archive 不会

mkdir -p "$NEW/docs/ui-ref"
for f in final-detail3 final-screening final-holdings final-settings reastock-3col3 today-final v7-market; do
  cp "$OLD/ui-shots/$f.png" "$NEW/docs/ui-ref/"
done

cd "$NEW"
# 新 .gitignore：去掉一刀切的 verify/*.json，改挡缓存和逆向材料
cat > .gitignore <<'EOF'
.build/
.build-probe/
build/
.DS_Store
*.log
verify/cache/
verify/engine-extracted.js
verify/sb-klines/
verify/gt-klines/
verify/live*/
ghidra*/
tools/ghidra*
tools/winutil/
analysis/
rea/
backup/
EOF
printf '# 教训\n' > docs/LESSONS.md
printf '# 代码规范\n' > docs/code-standards.md
printf '# 出处\n从 %s 提交 378d7eee1140a3cd497865d03859cfebed20ccda 的当前树复制，新开历史。\n排除：Ghidra 逆向工程与脚本、analysis/、rea/、backup/、抽出的第三方 JS、抓取缓存 sb-klines/gt-klines/live-scores、构建产物；截图只留 7 张在 docs/ui-ref/。旧仓库原样保留做档案。\n' "$OLD" > docs/ORIGIN.md

du -sh . && find . -size +1M -not -path './.git/*'     # 大于 1 MB 的给老板过目（预期只有 assets/AppIcon.icns）
swift build --disable-sandbox                           # 必须通过再提交
git init -b main && git add -A
git ls-files | grep -Ei 'ghidra|engine-extracted|StockStation-bin|sb-klines|gt-klines|live-scores|^analysis/|^backup/|^rea/' && echo "有不该入库的，先处理"   # 应什么都不打印
git commit -m "从 REASTOCK 378d7ee 建立干净基线"
du -sh .git                                             # 应 < 25 MB
git -C "$OLD" rev-parse HEAD                            # 仍是 378d7eee…，旧仓库没动
# 老板定了名字再建私有远端（Q5）：
# gh repo create JAY5CXSDMY14/reastock --private --source . --push
```

### 第 2 步：登记项目
```bash
evo import ST --name 股票 \
  --path ~/Desktop/项目/reastock \
  --goal "以 REASTOCK 为主力，做老板自用的 A 股复盘与盘中协助 Mac 应用：先把评分钉死在可回归的金标准上、数据来源逐项标清，再把 ios-stock-app 的对账、测试和版本化发布纪律移植进来，最后打磨 REASTOCK 现有功能。只观察和模拟，不做真实交易。" \
  --test "bash scripts/test-all.sh"
# 建了私有远端就再加 --github JAY5CXSDMY14/reastock
```
`evo import` 不动代码和历史，只写 `~/.evoloop/projects/ST/config.json`，放一份未提交的 `AGENT_INTERFACE.md`，登记 Orca。

### 第 3 步：用本目录的配置补齐
只补 import 不会写的键，import 生成的 repo/github 等以实际为准：
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
`scripts/test-all.sh` 要等 ST-OPS-002 做完才有；在那之前把 `test_cmd` 临时换成 `project.json` 里的 `_test_cmd_interim`（`swift build` + `verify/regression.sh`，看它的注意事项）。

### 第 4 步：时间窗
在全局 `~/.evoloop/config.json` 的 `windows` 里填当年 A 股休市日，并加收盘后窗口：
```json
"windows": {"tz": "Asia/Shanghai", "holidays": ["2027-01-01"],
            "presets": {"postclose:cn": "mon-fri 15:35-23:30"}, "holiday_presets": ["postclose:cn"]}
```
要看真实盘中数据的件用 `--window trading:cn`，收盘后才有数据的件用 `--window postclose:cn`。哪几件见 `backlog.md` 一览表的「窗口」列。

### 第 5 步：脱敏词表（ST-OPS-006）
建 `~/.evoloop/projects/ST/policy-terms.txt`（仓库外，不入库），配置里 `policy_terms` 已指向它。

### 第 6 步：第一件
```bash
evo -p ST add --kind ops --title "建一键全量测试入口" --scope scripts/,Tests/
```
小、不碰界面，用来确认真工人、真验收在这个仓库里跑得通。之后按 backlog 顺序：OPS-003 金标准 → FEAT-001 来源标注 → 第 1 段移植。

## 和 ios-stock-app 人工循环怎么相处
- ios-stock-app 的人工循环（Codex 写任务书 → DSH 施工 → Claude Code 验收官）照旧管它自己的 MAC-0xx：MAC-012A 受阻挂账（维持 2026-09-30 / N=600），MAC-012B 排队。evo 不碰那个仓库，也不写它的 `协作/`。
- 两边以后怎么分工是 Q4，老板未定；在那之前 evo 只在 REASTOCK 工作仓库里接 `ST-<类别>-NNN` 新件。

## 盘点时看不到的（Mac mini 上要核）
- 这次通过 MCP 只读文件核对，不能在 Mac 上跑命令。REASTOCK 的 HEAD、跟踪文件和体积是读 `.git/logs/HEAD`、解析 `.git/index` 得出的；没跑 `git status`，有没有未提交改动只按目录修改时间推断（源码早于 HEAD），OPS-001 第一条命令要确认。
- `verify/regression.sh` 的 3 只真值现在是否全过、`swift build` 现在是否通过，没在 Mac 上跑过。
- ios-stock-app 的测试数字取自 10-02 的登记，没有重跑。
- `@testable import` 能不能直接测 REASTOCK 的可执行目标，要 OPS-002 实测；不行就拆库目标（件里写了）。
