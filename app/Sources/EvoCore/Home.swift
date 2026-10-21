import Foundation

/// 第十九轮：首页只把「等老板处理」的事放最前；别的（项目在转、卡太久）收成一行，点开才看。
/// 三态：加载 / 出错 / 空（没有要你处理的）各有一句人话；有事时标题直接说几件、最久等了多久。
public struct HomeSummary: Equatable, Sendable {
    public enum Phase: Equatable, Sendable { case loading, error, clear, attention }

    public var phase: Phase
    public var headline: String          // 大标题下的一句
    public var detail: String?           // 再小一号的补充（出错原因、最久的那张等了多久）
    public var backgroundLine: String?   // 「其余：3 个项目在转 · 施工 2 · 验收 1」——默认收起
    public var stuckLine: String?        // 「2 件卡住了」——有才出，点了去「卡太久」
    public var attentionCount: Int

    public static func derive(loaded: Bool, globalError: String?, cards: [GateCard], rows: [ProjectRow],
                              stuck: Int, paused: Bool, now: Date = Date()) -> HomeSummary {
        let bg = backgroundText(rows, paused: paused)
        let st = stuck > 0 ? "\(stuck) 件卡住了，不用你点头，但值得看一眼" : nil
        if let e = globalError {
            return HomeSummary(phase: .error, headline: "evo 现在跑不起来，读不到要你处理的事",
                               detail: String(e.prefix(300)), backgroundLine: nil, stuckLine: nil, attentionCount: 0)
        }
        if !loaded {
            return HomeSummary(phase: .loading, headline: "正在问 evo 有什么要你处理…", detail: nil,
                               backgroundLine: nil, stuckLine: nil, attentionCount: 0)
        }
        if cards.isEmpty {
            let d = rows.isEmpty ? "还没有项目：在设置里跑一遍首次向导，或终端 evo new。" : (paused ? "循环暂停着，恢复后会接着干。" : "evo 自己在转，有要你点头的会第一时间放这里。")
            return HomeSummary(phase: .clear, headline: "没有要你处理的事", detail: d, backgroundLine: bg, stuckLine: st, attentionCount: 0)
        }
        let oldest = cards.compactMap(\.waitingSince).min()
        var detail: String?
        if let o = oldest {
            let m = max(0, now.timeIntervalSince(o) / 60)
            detail = "最久的一件等了 \(HeartbeatStatus.human(m))"
        }
        return HomeSummary(phase: .attention, headline: "有 \(cards.count) 件等你处理", detail: detail,
                           backgroundLine: bg, stuckLine: st, attentionCount: cards.count)
    }

    static func backgroundText(_ rows: [ProjectRow], paused: Bool) -> String? {
        guard !rows.isEmpty else { return nil }
        let b = rows.reduce(0) { $0 + $1.building }, v = rows.reduce(0) { $0 + $1.verifying }, m = rows.reduce(0) { $0 + $1.merged }
        var parts = ["\(rows.count) 个项目\(paused ? "（暂停中）" : "在转")"]
        if b > 0 { parts.append("施工 \(b)") }
        if v > 0 { parts.append("验收 \(v)") }
        if m > 0 { parts.append("可收菜 \(m)") }
        return parts.joined(separator: " · ")
    }
}

/// 件详情页「为什么卡住」：从 status 里的件状态、卡太久 / 没活路标记、log 时间线推出一句中文原因 + 下一步。
/// 不是卡住（正常推进、已合并、已上线）返回进展说明，`stuck = false`。
public struct ItemDiagnosis: Equatable, Sendable {
    public enum Tone: Equatable, Sendable { case calm, waitingOnYou, warning, danger }

    public var stuck: Bool
    public var tone: Tone
    public var headline: String
    public var because: [String]      // 推断依据（给人看的，最多 3 条）
    public var next: String?          // 你可以做什么

    public static func explain(item: StatusDoc.Item?, log: ItemLog?, stale: StatusDoc.Flag?, noLivePath: StatusDoc.Flag?,
                               now: Date = Date()) -> ItemDiagnosis {
        let raw = (item?.raw ?? log?.raw ?? "").lowercased()
        let stateText = item?.state ?? log?.state ?? ""
        let events = log?.events ?? []
        let last = events.last
        let reworks = events.filter { $0.event == "gate_reject" || $0.event == "rework" }.count
        var because: [String] = []
        if !stateText.isEmpty { because.append("现在的状态：\(stateText)") }
        if let l = last, let t = l.date {
            because.append("最后一件事：\(l.label)（\(HeartbeatStatus.human(max(0, now.timeIntervalSince(t) / 60)))前）")
        }

        // 1) 没活路：最硬的卡
        if let f = noLivePath ?? (item?.noLivePath == true ? StatusDoc.Flag(key: item?.key ?? "") : nil) {
            let r = f.reason ?? ""
            let (h, n): (String, String)
            switch r {
            case "dep_dead": (h, n) = ("它依赖的件没了，这件没人能接着做", "去看依赖的那件：放弃它就把这件也放弃，或在输入框说清楚怎么改")
            case "no_decider": (h, n) = ("该决策岗拍板，但没有能用的决策模型", "去「团队」给决策岗换一个能用的模型")
            case "rate_limited": (h, n) = ("模型额度满了，在等额度恢复", "不用动，额度回来会自己继续；急的话去「团队」换备用模型")
            case "task_dead": (h, n) = ("后面的验收 / 合并任务没了，没人会接手", "在终端 evo retry \(f.key) 重新派一次")
            case "stalled": (h, n) = ("停着不动，也没有排队的下一步", "在终端 evo retry \(f.key)，或在输入框说要不要继续")
            default: (h, n) = ("没有能走通的下一步" + (r.isEmpty ? "" : "（\(r)）"), "在终端 evo retry \(f.key)，或在输入框说要不要继续")
            }
            if let m = f.minutes { because.insert("已经这样 \(HeartbeatStatus.human(m))", at: 0) }
            return ItemDiagnosis(stuck: true, tone: .danger, headline: h, because: Array(because.prefix(3)), next: n)
        }

        // 2) 最后一件事是部署失败（件可能还显示「已合并」）
        if let l = last, l.event == "deploy_failed" {
            let why = l.fields["reason"] ?? l.fields["why"] ?? l.fields["error"]
            return ItemDiagnosis(stuck: true, tone: .danger, headline: "上线时部署失败" + (why.map { "：\($0.prefix(80))" } ?? ""),
                                 because: Array(because.prefix(3)), next: "看部署日志修好后，再点一次「上线」")
        }

        // 2b) 在等你：不算卡，但球在你这
        switch raw {
        case "look":
            return ItemDiagnosis(stuck: false, tone: .waitingOnYou, headline: "施工和验收都过了，在等你看效果",
                                 because: Array(because.prefix(3)), next: "回「等你处理」点「通过」，或「打回」并写一句哪里不对")
        case "proposed":
            return ItemDiagnosis(stuck: false, tone: .waitingOnYou, headline: "决策岗提了这件，在等你拍板做不做",
                                 because: Array(because.prefix(3)), next: "回「等你处理」点「做」或「不做」")
        case "merged":
            return ItemDiagnosis(stuck: false, tone: .calm, headline: "已经合进主线，等下一批上线", because: Array(because.prefix(2)),
                                 next: "攒够了点「收菜」建上线闸门")
        case "shipped", "deployed":
            return ItemDiagnosis(stuck: false, tone: .calm, headline: "已经上线了", because: Array(because.prefix(2)), next: nil)
        case "dropped":
            return ItemDiagnosis(stuck: false, tone: .calm, headline: "这件不做了", because: Array(because.prefix(2)), next: nil)
        default: break
        }

        // 3) 交卷说卡住
        if let l = events.last(where: { $0.event == "report" }), l.fields["status"] == "blocked", raw == "building" || raw == "blocked" {
            let why = l.fields["summary"] ?? l.fields["why"] ?? l.fields["reason"]
            return ItemDiagnosis(stuck: true, tone: .warning, headline: "施工交卷说做不下去" + (why.map { "：\($0.prefix(80))" } ?? ""),
                                 because: Array(because.prefix(3)), next: "决策岗会接手拆分或改方案；要插话就在输入框说")
        }

        // 4) 同一状态太久
        if let s = stale ?? (item?.stalled == true ? StatusDoc.Flag(key: item?.key ?? "") : nil) {
            let mins = s.hours.map { $0 * 60 } ?? s.minutes
            let dur = mins.map { HeartbeatStatus.human($0) }
            if let d = dur { because.insert("在「\(s.state ?? stateText)」待了 \(d)", at: 0) }
            let (h, n): (String, String)
            switch raw {
            case "queued", "ready", "":
                (h, n) = ("排队\(dur.map { " \($0)" } ?? "很久")还没开工", "多半是同时开工的名额满了、在时间窗外，或模型额度满；不急就等，急就在输入框说先做这件")
            case "building":
                (h, n) = ("施工\(dur.map { " \($0)" } ?? "很久")没交卷", "可能卡在长任务或模型没响应；看门狗会兜底重派，急就 evo retry \(s.key)")
            case "built", "verifying":
                (h, n) = ("验收\(dur.map { " \($0)" } ?? "很久")没出结果", "验收模型可能在排队；急就去「团队」给验收换个模型")
            default:
                (h, n) = ("在「\(stateText.isEmpty ? raw : stateText)」停了\(dur.map { " \($0)" } ?? "很久")", "在终端 evo retry \(s.key)，或在输入框说要不要继续")
            }
            return ItemDiagnosis(stuck: true, tone: .warning, headline: h, because: Array(because.prefix(3)), next: n)
        }

        // 5) 正常推进：给一句进展
        let h: String
        if reworks > 0 && (raw == "building" || raw == "rework") {
            h = "你打回过 \(reworks) 次，正在按你的话返工"
        } else {
            switch raw {
            case "queued", "ready": h = "排着队，轮到就开工"
            case "building": h = "施工中，进展正常"
            case "built": h = "交卷了，等验收"
            case "verifying": h = "验收中"
            case "verified": h = "验收过了，等合并"
            default: h = stateText.isEmpty ? "进展正常" : "\(stateText)，进展正常"
            }
        }
        return ItemDiagnosis(stuck: false, tone: .calm, headline: h, because: Array(because.prefix(2)), next: nil)
    }
}
