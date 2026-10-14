# 接入指南：分四期把 evoloop 装进现有项目

不要一次全上。每一期跑满几天、看夜审结果，再进入下一期。下面以 **tubu-platform**（Python API + pnpm Web，Postgres / MinIO，3D 预览，向量检索）为例说明，换成其它项目时替换命令即可。

---

## 第 0 期：盘点（半天）

回答这几个问题，答案写进 `AGENTS.md` 对应位置：
1. 项目分几个子系统？（tubu 示例：`api/` 后端、`web/` 前端、`storage` MinIO 资产、`search` 向量检索、`render` 3D 预览、`ai` 配色生成）
2. 全量检查命令是什么？（示例：`ruff check && ruff format --check && mypy && pytest`；`pnpm lint && pnpm typecheck && pnpm test && pnpm build`）
3. 测试如何与真实数据隔离？（示例：每个测试用临时 Postgres schema / testcontainers；MinIO 用临时 bucket；永不连生产库）
4. 有哪些已拍板的产品决定？（例如配色生成必须保留土布原始纹样比例）
5. 哪些改动必须人放行？（例如数据库迁移、删除资产、改鉴权、改 CI）
6. Agent 能用哪些**真实复现环境**？（tubu 示例：Chrome / Safari / Firefox 三引擎看 3D 预览、移动端浏览器、与生产同构的 Postgres + MinIO 测试实例）
7. **产品决策与审美**沉淀了没有？没有的话安排一次和 Agent 的头脑风暴，把结论写进 `docs/product-decisions.md`，只由人修改。

## 第 1 期：规则层（第 1～3 天）

```bash
./evoloop/scripts/install.sh ../tubu-platform
```
- 填写 `AGENTS.md`、`docs/code-standards.md` 的 `{{占位符}}`。
- 为每个子系统写一页 `docs/subsystems/<name>.md`（可以让 agent 读代码后起草，你审）。
- `CLAUDE.md` 只保留两行 `@AGENTS.md` `@LESSONS.md`；如果已有 CLAUDE.md，把原内容挪进 AGENTS.md。

**验收**：新开一个 agent 会话，问它"改 3D 预览之前要读什么、跑什么检查"，它能准确回答。

## 第 2 期：验证与互审（第 4～7 天）

- 所有改动开 PR，PR 模板强制填写 Red check / Ran / Not run。
- Builder 与 Reviewer 分开会话（L1 手动档即可）。
- 合并一律 `scripts/merge-reviewed.sh`。
- 开启 `evoloop-guard.yml`。

**验收**：一周内合并的 PR，100% 有 Red check 记录和 Not run 列表。

## 第 3 期：夜审与错题本（第 2 周）

- 先手动跑 3 晚复盘，人工检查教训质量（证据是否真实、规则是否可执行）。
- 质量稳定后打开 `evoloop-nightly-retro.yml` 定时任务。
- 第一次复盘可以回溯最近 7 天的 commit，快速建立初始 LESSONS。

**验收**：LESSONS.md 出现第一条 Seen 3× 并成功升级到 code-standards。

## 第 4 期：自动派活（第 3 周起，可选）

- 开启 `evoloop-triage.yml` 自动分诊。
- 视 Issue 量决定是否上 L3 调度器（见 `docs/orchestration.md`）。

---

## 观测指标

每周看一次（Retro Agent 可在周日的复盘里附带）：

| 指标 | 含义 | 健康趋势 |
|---|---|---|
| 返工率 | 修复后又被修 / 全部修复 | ↓ |
| Regressed Issue 数 | 报告人说没好 | ↓ |
| 无 Red check 合并数 | 违反硬标准 | → 0 |
| 新增教训数 / 升级数 | 规则在长 | 前期 ↑，后期趋稳 |
| main 红灯时长 | 红测试存活时间 | ↓ |
| 日发布数 | 刹车是否生效 | 稳定、不过载 |

## tubu 特有的建议教训种子（可在第一次复盘前预置为 Seen 0×）

- 任何涉及资产删除或覆盖的改动，测试必须证明读取 MinIO 失败时不会删除（"读失败=未知"）。
- 向量检索改动必须附带固定查询集的召回对比（改前 / 改后），不能只说"效果更好"。
- 3D 预览改动必须在至少两个浏览器引擎截图对比。
- 数据库迁移必须可回滚，并在临时库上跑过 up → down → up。


## 补充：借鉴 Readest 的接入选择（2026-10-14）

第 0 期盘点时额外回答：
1. 用哪种放权程度起步：全自动（magpie）还是审批台（Readest）？个人 / 私有项目建议审批台起步。
2. 外部贡献多不多？少的话可采用"只处理自己的 PR"的严格信任边界。
3. 发版是否必须人工（应用商店、小程序审核、签名）？
4. 用最近 1–2 周的提交做一次种子复盘，生成第一版 LESSONS.md。
