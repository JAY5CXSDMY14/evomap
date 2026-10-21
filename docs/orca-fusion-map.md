# Orca 和 evo 在循环里的关系

Orca 是身体，负责动手和给你看。evo 是大脑，负责决定下一步。

## 整体拓扑

```flow LR
(老板) -> [Orca 手机端]: 看状态 / 回复 / 审批
[Orca 手机端] -> [Orca 桌面或常驻服务]: 配对
*[evo 大脑] -> [Orca 桌面或常驻服务]: orca 命令行
[evo 大脑] -> [(GitHub issue 和 PR)]: 读需求 / 合并
[Orca 桌面或常驻服务] -> [DSH 施工] & [Claude 验收] & [决策岗]
[DSH 施工] -> [Magpie 模型网关]
[Claude 验收] -> [Magpie 模型网关]
[决策岗] -> [Magpie 模型网关]
[Orca 桌面或常驻服务] --> [(GitHub issue 和 PR)]: 在界面里看
group Orca 负责: Orca 手机端, Orca 桌面或常驻服务
group 干活的 agent: DSH 施工, Claude 验收, 决策岗
```

## 一件活怎么走完

```flow TB
(GitHub 新 issue) -> {要做吗?}
{要做吗?} -> [排队]: 老板在手机上点头
{要做吗?} --> (关掉): 不做
[排队] -> *[evo 派施工]
*[evo 派施工] -> [Orca 开工作区和 DSH]
[Orca 开工作区和 DSH] -> [DSH 写代码]
[DSH 写代码] -> [Orca 报告干完]
[Orca 报告干完] -> *[evo 派验收]
*[evo 派验收] -> [Claude 换个模型检查]
[Claude 换个模型检查] -> {验收过了?}
{验收过了?} --> [决策岗判断]: 没过
[决策岗判断] --> *[evo 派施工]: 重做, 最多 2 次
{验收过了?} -> {用户能看到吗?}
{用户能看到吗?} -> [手机上看效果]: 能
{用户能看到吗?} -> *[evo 合并]: 不能
[手机上看效果] -> *[evo 合并]
*[evo 合并] -> [手机上批准上线]
[手机上批准上线] -> (上线)
group evo 决定: evo 派施工, evo 派验收, evo 合并
group Orca 执行: Orca 开工作区和 DSH, Orca 报告干完
```

## 谁在什么时候说话

```sequence num
participants: 老板手机, Orca, evo, 施工 agent, 验收 agent
evo -> Orca: 开工作区，启动 DSH
Orca -> 施工 agent: 任务书
施工 agent --> Orca: 干完了
Orca --> evo: 状态变为完成
evo -> Orca: 用另一个模型启动验收
Orca -> 验收 agent: 检查清单
验收 agent --> evo: 通过
evo -> Orca: 开审批，问上线吗
Orca -> 老板手机: 推送
老板手机 --> Orca: yes
Orca --> evo: 已批准
evo -> evo: 合并并上线
```

## 变化：哪些交给 Orca，哪些删掉

```flow LR
*[evo 大脑] -> [Orca]
- [evo 大脑] -> [Evo 菜单栏 App]
- [evo 大脑] -> [网页面板]
- [evo 大脑] -> [Telegram 推送]
- [evo 大脑] -> [自己猜终端状态]
+ [Orca] -> [手机端审批和推送]
+ [Orca] -> [agent 状态钩子]
+ [Orca] -> [多机器同屏]
```

## 待实测的 3 点

| 点 | 备选 |
|---|---|
| DSH 能否单独指定模型 | 用 Magpie 默认模型 |
| 手机上能否看到审批 | 开一个等待回复的审批终端 |
| 卡住时能否推送 | 保留 Telegram |
