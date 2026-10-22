# 岗位规则的写法参考（第二十一轮）

> 现状说明，不是约束。这份记录我们改 `kit/roles/*.md` 时参考了哪些公开资料、借了什么。资料都是 2026-10-23 实际打开读过的；优先官方文档 / 官方博客和大项目里在维护的规则文件，没用零散博客。

## 读过的资料

| # | 资料 | 日期 | 借了什么 |
|---|------|------|----------|
| 1 | Anthropic · Thariq Shihipar《The new rules of context engineering for Claude 5 generation models》 https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models | 2026-07-24 | 主框架。旧规矩「给规则 / 给例子 / 全放前面 / 反复说」换成「给判断 / 设计接口 / 渐进披露 / 只说一次」。我们据此：把模型自己能判断的事从规则里删掉；例子只在 evo 解析的格式处留一个最小样例（接口本身就是提示）；岗位规则只放红线、接口和现状，细节交给 ponytail skill、UI 规范、docs 按需读 |
| 2 | OpenAI · Eric Provencher《Rethinking skills and prompts for GPT-6 Astra》 https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra | 2026-09-11 | ①「边界写得太重，新模型会过度当真、该继续时停下」→ 不是真红线的「不许 / 严禁」改成平实说法；②「仓库里的规则也会被别的、更弱的模型读」→ 施工（DSH）、验收（glm）的【接口】照旧写得很具体，只有决策岗（Claude）那份放得最开；③「按需读文档，别要求每次先读一堆」→ 现状层用「需要时看 docs/architecture.md」这种写法 |
| 3 | Claude Code 文档 · Best practices https://code.claude.com/docs/en/best-practices （由 anthropic.com/engineering/claude-code-best-practices 跳转） | 活文档，2026-10-23 读（文中提到 v2.1.283） | 「每行问一句：删掉它 Claude 会出错吗？不会就删」；「强调只用在一两行，处处强调等于没强调」；「必须每次都发生的事用 hook，不靠文字」→ 红线里标出哪些 evo 代码已经强制 |
| 4 | Claude Code 文档 · How Claude remembers your project（CLAUDE.md / AGENTS.md） https://code.claude.com/docs/en/memory | 活文档，2026-10-23 读 | 「CLAUDE.md 是上下文不是强制配置，要拦就用 hook / 设置」「两条指令矛盾时模型会随便挑一条」→ 删掉三份文件里互相重复、措辞不一的条目，每条规矩只在一处说 |
| 5 | OpenAI Codex 文档 · Custom instructions with AGENTS.md https://developers.openai.com/codex/guides/agents-md | 活文档，2026-10-23 读 | 「Code Review Rules：写清要标记的行为，以及安全做法 / 例外」→ 验收岗「重复造轮子」一条写了什么算必须修、什么只建议另开 issue |
| 6 | agents.md 规范 https://agents.md/ （仓库 agentsmd/agents.md 最近提交 2026-09-11） | 2026-09 | 没有必填字段，按「环境 / 命令 / 规范 / 安全」分节；就近文件优先 → 三层用固定小标题，evo 拼进任务书时各岗位只看到自己那份 |
| 7 | apache/airflow 的 AGENTS.md https://github.com/apache/airflow/blob/main/AGENTS.md | 最近提交 2026-10-19 | 末尾 Boundaries 只分「Ask first / Never」两档，各三四条 → 我们的【红线】也只放真正的硬线，并把「问老板」的四类集中写一处；安全一节「区分真漏洞 / 已知限制 / 部署加固」→ 验收岗的「写出触发情形才算发现」照旧保留 |
| 8 | openai/codex 的 codex-rs/exec-server/src/sandbox_integrity/AGENTS.md https://github.com/openai/codex/blob/main/codex-rs/exec-server/src/sandbox_integrity/AGENTS.md | 最近提交 2026-10-08 | 「Deliberate approximation：这些是本阶段接受的限制，不是要你重做」→ 对应我们 `shortcut:` 注释不算发现的规矩，保留；「scope and review contract」的写法 → 现状层统一一句「这是当前做法，不是定论」 |

没采用：awesome-cursorrules、awesome-claude-code 这类合集。它们收的是社区各自的规则文件，年代和质量参差，大多是给旧模型写的长规则清单，正是上面 1、2 说要删的那种。

## 落到我们文件里的结构
- 【红线】少而硬；每条标明是不是 evo 代码强制（强制的在 kit/bin/evo：越出 scope 打回、报告格式 / 失败测试打回、改 kit/selfmaint 打回、受保护件的 answer 改成 ask_owner、外部 Agent 不能批闸门 / 上线、propose 只登记不开工）。
- 【接口】evo 真的解析的格式：decisions JSON、施工报告 JSON、worker_done outcome、提交信息格式、`evo suite`。只留一个最小样例。
- 【现状】一句「这是当前做法，不是定论；发现更好的做法就用 propose 提出来」开头，下面是当前做法。老板的核心原则「不重复造轮子」放在这一层第一条：它是判断，不是清单。
