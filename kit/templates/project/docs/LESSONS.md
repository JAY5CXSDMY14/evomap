# LESSONS

> 本项目的代码由 agent 编写、审查、合并和发布。本文件是**错题本**：每晚复盘 Agent 回顾当天合并的工作，记录
> ① 修完又返工的 ② 不该合并的 ③ 验证太薄的，以及做对了的（Done right）。
> **所有 Agent 改代码前必须读完本文件。**
> 同一条教训在 3 个不同日期出现 → 升级进 `docs/code-standards.md`「来自复盘的硬标准」。
> 关单标准：机制上不可能再发生才算关（Mechanism：code / test / script / gate / hook > static > rule > review）；只写进规则或靠人审的不算关。
> 机制：evoloop/docs/lessons-system.md

## 复盘日志
<!-- 最近 14 天，更早的移到 docs/lessons-archive/ -->
<!-- ### YYYY-MM-DD（窗口 <from>..<to>，N commits，vX → vY，tag 是否均在绿色 CI 上）
- 新增 L-xxxx；L-xxxx Seen +1；升级 L-xxxx；Done right N 条。 -->

## 活跃教训

### 1. 读懂报告

<!-- 示例条目（接入后删除）
### L-0001 先在报告人用的界面上原样复现，再说修好了
- **Why**: 只修截图里的那个场景，其它入口仍坏，Issue 来回返工。
- **Evidence**: #834 返工 4 次，每次只修截图里那一个场景：`abc1234`、`def5678`。
- **Do**: 复现步骤写进测试；列出所有入口逐个验证。
- **Done right**: `9f8e7d6` 用报告人原始配置复现后再修，一次通过。
- **Seen**: 1× (2026-10-05)
- **Category**: 读懂报告
- **Mechanism**: test — tests/test_signup.py::test_reporter_config（可选；挪进「已关单」时必填，且要 code/test/script/gate/hook/static 级）
-->

### 2. 修一类不修一例

### 3. 用户数据与设置

### 4. 验证

### 5. 并发与测试

### 6. 红测试与发布

### 7. 合并与关闭

### 8. 协作

## 已关单
<!-- 机制上不可能再发生的条目搬到这里（lessons.py lint 会查 Mechanism）；条目格式同上 -->

## 已升级为硬标准
<!-- - L-xxxx → S-Lxxxx（YYYY-MM-DD），之后的违反 / 做对继续记在这里 -->

## 归档
