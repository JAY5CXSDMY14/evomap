#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

// v0.4.0「团队」页：每个岗位一张卡（工具 · 模型 · 思考档位 · 一句话职责 · 状态灯 · 备用 · 每个模型的成绩 · 建议 · 本周用量），
// 下面是各项目「跟随全局 / 本项目专用」。换模型一律先出确认卡（钉在输入框上面），点「确认换」才跑 evo team set。
// 外部 Agent 改不了：evo 那边设了 EVO_AGENT 一律拒绝。

extension AppState {
    func loadTeam() async {
        if previewQuiet != nil { return }                 // 截图 / 预览用的假状态：不去跑 evo
        let r = await Shell.evo(["team", "--json"], timeout: 60)
        if r.ok, let d = try? TeamDoc.decode(r.out) {
            team = d; teamError = nil
        } else {
            teamError = r.ok ? "不是 team JSON：\(r.out.prefix(80))" : (r.tail.isEmpty ? "退出码 \(r.code)" : r.tail)
        }
    }

    func confirmTeam(_ ch: TeamChange) {
        pendingTeam = nil
        Task {
            let r = await Shell.evo(ch.args, timeout: 60)
            let said = r.out.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "\n").last.map(String.init) ?? "换好了"
            chat.append(ChatLine(text: r.ok ? said : "没成：\(r.tail.prefix(160))", mine: false, failed: !r.ok))
            trimChat()
            react(r.ok ? .replied : .replyFailed)
            await loadTeam()
        }
    }

    func cancelTeam() {
        pendingTeam = nil
        chat.append(ChatLine(text: "好，不换", mine: false))
        trimChat()
    }

    func dismissSuggestion(_ model: String) {
        Task {
            _ = await Shell.evo(["team", "dismiss", model], timeout: 30)
            await loadTeam()
        }
    }
}

struct TeamPane: View {
    @ObservedObject var state: AppState
    let width: CGFloat

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            PaneTitle(title: "团队", subtitle: "每个岗位用哪个工具、哪个模型。换了下一次派工生效，正在跑的不打断。") {
                MagpiePill(ok: state.team?.magpieOK, url: state.team?.magpieURL)
            }
            if let t = state.team {
                if !t.suggestions.isEmpty {
                    SuggestionBanner(state: state, models: t.suggestions).padding(.bottom, 16)
                }
                let n = width >= 760 ? 2 : 1
                let rows = stride(from: 0, to: t.cards.count, by: n).map { Array(t.cards[$0..<min($0 + n, t.cards.count)]) }
                VStack(alignment: .leading, spacing: 14) {       // 不用 LazyVGrid：截图（ImageRenderer）里也要画全
                    ForEach(Array(rows.enumerated()), id: \.offset) { ri, row in
                        HStack(alignment: .top, spacing: 14) {
                            ForEach(Array(row.enumerated()), id: \.element.id) { ci, c in
                                TeamCardView(state: state, doc: t, card: c)
                                    .frame(maxWidth: .infinity, alignment: .topLeading)
                                    .staggeredAppear(ri * n + ci)
                            }
                            if row.count < n { Color.clear.frame(maxWidth: .infinity, maxHeight: 1) }
                        }
                    }
                }
                if !t.projects.isEmpty {
                    SectionTitle(text: "各项目").padding(.top, 26).padding(.bottom, 10)
                    ProjectBadges(doc: t)
                }
            } else if let e = state.teamError {
                Hint(text: "读不出团队：\(e)", color: Theme.danger)
            } else {
                HStack(spacing: 8) {
                    Spinner()
                    Text("正在读 evo team …").font(Theme.body()).foregroundStyle(Theme.textSecondary)
                }
            }
        }
        .task { await state.loadTeam() }
    }
}

struct MagpiePill: View {
    let ok: Bool?
    let url: String?
    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(ok == true ? Theme.success : (ok == false ? Theme.danger : Theme.textSecondary)).frame(width: 8, height: 8)
            Text(ok == true ? "magpie 通" : (ok == false ? "magpie 不通" : "magpie …"))
                .font(.system(size: 12, weight: .medium)).foregroundStyle(Theme.textPrimary)
        }
        .padding(.horizontal, 10).padding(.vertical, 5)
        .background(Capsule().fill(Theme.surfaceSunk))
        .help(url ?? "")
        .accessibilityElement(children: .combine)
    }
}

struct StatusLight: View {
    let light: TeamLight
    var color: Color {
        switch light {
        case .green: return Theme.success
        case .amber: return Theme.warning
        case .red: return Theme.danger
        case .gray: return Theme.textSecondary
        }
    }
    var body: some View {
        ZStack {
            Circle().fill(color.opacity(0.22)).frame(width: 16, height: 16)
            Circle().fill(color).frame(width: 9, height: 9)
        }
        .accessibilityHidden(true)
    }
}

struct TeamCardView: View {
    @ObservedObject var state: AppState
    let doc: TeamDoc
    let card: TeamCard
    @Environment(\.evoStatic) private var isStatic

    private var light: TeamLight { TeamLight.of(card.status.code) }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .center, spacing: 8) {
                StatusLight(light: light)
                Text(card.name).font(Theme.title(19)).foregroundStyle(Theme.textPrimary)
                Text(card.tool.isEmpty ? "没配置" : card.tool)
                    .font(.system(size: 11, weight: .bold, design: .rounded)).foregroundStyle(Theme.accent)
                    .padding(.horizontal, 7).padding(.vertical, 2).background(Capsule().fill(Theme.accentSoft))
                if let b = card.badge {
                    Text(b).font(.system(size: 10.5, weight: .medium)).foregroundStyle(Theme.textSecondary)
                        .padding(.horizontal, 6).padding(.vertical, 2).background(Capsule().fill(Theme.surfaceSunk))
                }
                Spacer(minLength: 4)
                Text(TeamLight.text(card.status)).font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(StatusLight(light: light).color).lineLimit(1)
            }
            if let d = card.duty, !d.isEmpty {
                Text(d).font(Theme.body(12.5)).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
            }
            if card.configured {
                HStack(spacing: 6) {
                    modelMenu
                    thinkingMenu
                    Spacer(minLength: 0)
                }
            }
            if let f = card.fallbackLine {
                Label(f, systemImage: "arrow.triangle.branch").font(Theme.caption(11.5)).foregroundStyle(Theme.textSecondary)
            }
            if light == .red, let w = card.status.why {
                Hint(text: w, color: Theme.danger)
            }
            ForEach(card.warnings, id: \.self) { w in
                Hint(text: w, color: Theme.warning)
            }
            if !card.stats.isEmpty {
                VStack(alignment: .leading, spacing: 5) {
                    ForEach(card.stats.keys.sorted(), id: \.self) { m in
                        VStack(alignment: .leading, spacing: 1) {
                            Text(m).font(.system(size: 11.5, weight: card.models.contains(m) ? .semibold : .regular, design: .monospaced))
                                .foregroundStyle(card.models.contains(m) ? Theme.accent : Theme.textPrimary).lineLimit(1)
                            Text((card.stats[m] ?? ModelStats()).line(role: card.role))
                                .font(Theme.caption(11)).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 8, style: .continuous).fill(Theme.surfaceSunk))
            }
            if !card.recommendation.isEmpty {
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "lightbulb").font(.system(size: 12)).foregroundStyle(Theme.accent)
                    Text(card.recommendation).font(Theme.body(12.5)).foregroundStyle(Theme.textPrimary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            if let s = card.switchTo {
                Button { state.pendingTeam = TeamChange(role: card.role, value: s) } label: {
                    Label("换成 \(s)", systemImage: "arrow.right.circle")
                }
                .buttonStyle(BouncyStyle(kind: .primary, compact: true))
                .uiProbe("team-switch-\(card.role)")
            }
            if let t = card.trial {
                Label("试用 \(t.model)：\(t.done)/\(t.needed) 件" + (t.base.map { "，对比 \($0)" } ?? ""), systemImage: "flask")
                    .font(Theme.caption(11.5)).foregroundStyle(Theme.accent)
            }
            if let u = card.usageLine {
                Text(u).font(Theme.caption(11)).foregroundStyle(Theme.textSecondary)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card(highlighted: light == .red)
        .uiProbe("team-card-\(card.role)")
        .accessibilityElement(children: .contain)
        .accessibilityLabel("\(card.name)：\(card.modelLine)，\(TeamLight.text(card.status))")
    }

    @ViewBuilder private var modelMenu: some View {
        if isStatic {
            Label(card.models.first ?? "工具默认模型", systemImage: "cpu").labelStyle(.titleAndIcon).modifier(ChipLook())
        } else {
            Menu {
                ForEach(doc.modelOptions(for: card), id: \.self) { m in
                    Button(m) { state.pendingTeam = TeamChange(role: card.role, value: m) }
                }
            } label: {
                Label(card.models.first ?? "工具默认模型", systemImage: "cpu")
            }
            .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
            .modifier(ChipLook())
            .uiProbe("team-model-\(card.role)")
            .accessibilityLabel("\(card.name)模型：\(card.models.first ?? "工具默认")，点开换")
        }
    }

    @ViewBuilder private var thinkingMenu: some View {
        if isStatic {
            Label("思考 \(card.thinking ?? "默认")", systemImage: "brain").labelStyle(.titleAndIcon).modifier(ChipLook())
        } else {
            Menu {
                ForEach(doc.thinkingLevels, id: \.self) { lv in
                    Button(lv) { state.pendingTeam = TeamChange(role: card.role, kind: .thinking, value: lv) }
                }
            } label: {
                Label("思考 \(card.thinking ?? "默认")", systemImage: "brain")
            }
            .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
            .modifier(ChipLook())
            .accessibilityLabel("\(card.name)思考档位：\(card.thinking ?? "默认")，点开换")
        }
    }
}

struct SuggestionBanner: View {
    @ObservedObject var state: AppState
    let models: [String]
    @Environment(\.evoStatic) private var isStatic

    var body: some View {
        HStack(alignment: .center, spacing: 10) {
            Image(systemName: "sparkles").foregroundStyle(Theme.accent)
            VStack(alignment: .leading, spacing: 2) {
                Text("新模型可用：\(models.joined(separator: "、"))").font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.textPrimary)
                Text("挑一个项目、一个岗位先试几件，满了给你对比，留不留你再点。").font(Theme.caption(11.5)).foregroundStyle(Theme.textSecondary)
            }
            Spacer(minLength: 6)
            if !isStatic, let m = models.first {
                Menu {
                    ForEach(state.codes, id: \.self) { p in
                        Button("在 \(p) 试施工") { state.pendingTeam = TeamChange(role: "build", kind: .trial, value: m, project: p) }
                        Button("在 \(p) 试验收") { state.pendingTeam = TeamChange(role: "verify", kind: .trial, value: m, project: p) }
                    }
                } label: { Label("试用…", systemImage: "flask") }
                .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                .modifier(ChipLook())
                Button("收起") { state.dismissSuggestion(m) }
                    .buttonStyle(BouncyStyle(kind: .ghost, compact: true))
            }
        }
        .padding(14)
        .card(highlighted: true)
    }
}

struct ProjectBadges: View {
    let doc: TeamDoc
    var body: some View {
        VStack(spacing: 0) {
            ForEach(Array(doc.projects.enumerated()), id: \.element.code) { i, p in
                if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 14) }
                HStack(spacing: 10) {
                    Text(p.code).font(.system(size: 11, weight: .bold, design: .rounded)).foregroundStyle(Theme.accent)
                        .padding(.horizontal, 7).padding(.vertical, 2).background(Capsule().fill(Theme.accentSoft))
                    Text(p.name).font(Theme.body(13)).foregroundStyle(Theme.textPrimary).lineLimit(1)
                    Spacer(minLength: 8)
                    ForEach(["build", "verify", "decide"], id: \.self) { r in
                        let b = doc.badge(project: p.code, role: r)
                        let own = b == TeamCard.projectOnly
                        Text("\(TeamCard.roleName(r)) \(b)" + (own ? (p.overrides[r]?.models?.first.map { " · \($0)" } ?? "") : ""))
                            .font(.system(size: 11, weight: own ? .semibold : .regular))
                            .foregroundStyle(own ? Theme.accent : Theme.textSecondary)
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(Capsule().fill(own ? Theme.accentSoft : Theme.surfaceSunk))
                    }
                }
                .padding(.horizontal, 14).padding(.vertical, 10)
            }
        }
        .card()
    }
}

/// 换模型确认卡：钉在输入框上面。
struct TeamConfirmCard: View {
    @ObservedObject var state: AppState
    let change: TeamChange

    var body: some View {
        let c = state.team?.card(change.role)
        let cur: String? = change.kind == .thinking ? c?.thinking : c?.models.first
        HStack(alignment: .center, spacing: 10) {
            Image(systemName: "arrow.triangle.2.circlepath").font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.accent)
            Text(change.confirmText(current: cur)).font(Theme.body(13)).foregroundStyle(Theme.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 6)
            Button("算了") { withAnimation(Motion.or(Motion.pop)) { state.cancelTeam() } }
                .buttonStyle(BouncyStyle(kind: .ghost, compact: true))
                .uiProbe("team-confirm-no")
            Button("确认换") { withAnimation(Motion.or(Motion.pop)) { state.confirmTeam(change) } }
                .buttonStyle(BouncyStyle(kind: .primary, compact: true))
                .uiProbe("team-confirm-yes")
        }
        .padding(12)
        .card(highlighted: true)
        .transition(.scale(scale: 0.92, anchor: .bottom).combined(with: .opacity))
        .accessibilityElement(children: .contain)
    }
}
#endif
