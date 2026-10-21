#if os(macOS)
import AppKit
import SwiftUI
import EvoCore

/// ⌘K 命令面板：一个浮动小窗，输入即模糊过滤动作、闸门、项目；↑↓ 选，回车执行，Esc 关。
@MainActor
final class PaletteController {
    static let shared = PaletteController()
    private var panel: NSPanel?
    private var monitor: Any?
    let model = PaletteModel()

    func show() {
        model.query = ""; model.selected = 0
        model.focusTick += 1
        if panel == nil {
            let p = KeyPanel(contentRect: NSRect(x: 0, y: 0, width: 520, height: 380),
                             styleMask: [.titled, .fullSizeContentView, .closable], backing: .buffered, defer: false)
            p.titleVisibility = .hidden
            p.titlebarAppearsTransparent = true
            p.isMovableByWindowBackground = true
            p.level = .floating
            p.isReleasedWhenClosed = false
            p.hidesOnDeactivate = true
            p.standardWindowButton(.closeButton)?.isHidden = true      // Esc 关；不要左上角红点
            p.standardWindowButton(.miniaturizeButton)?.isHidden = true
            p.standardWindowButton(.zoomButton)?.isHidden = true
            p.contentViewController = NSHostingController(rootView: PaletteView(state: AppState.shared, model: model))
            p.center()
            panel = p
        }
        panel?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        installMonitor()
    }

    func close() { panel?.orderOut(nil) }

    private func installMonitor() {
        guard monitor == nil else { return }
        monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] e in
            guard let self, let p = self.panel, p.isKeyWindow else { return e }
            switch e.keyCode {
            case 125: self.model.move(1); return nil                 // ↓
            case 126: self.model.move(-1); return nil                // ↑
            case 53: self.close(); return nil                        // Esc
            case 36, 76: self.runSelected(); return nil              // 回车
            default: return e
            }
        }
    }

    func runSelected() {
        let list = model.filtered(AppState.shared.palette)
        guard model.selected < list.count else { return }
        run(list[model.selected])
    }

    func run(_ e: PaletteEntry) {
        close()
        withAnimation(Motion.or(Motion.pop)) { AppState.shared.perform(e.action) }
    }
}

final class KeyPanel: NSPanel {
    override var canBecomeKey: Bool { true }
}

@MainActor
final class PaletteModel: ObservableObject {
    @Published var query = "" { didSet { selected = 0 } }
    @Published var selected = 0
    @Published var focusTick = 0       // 每次打开 +1：把光标放进搜索框
    var count = 0

    func filtered(_ all: [PaletteEntry]) -> [PaletteEntry] {
        Fuzzy.filter(all, query: query, text: \.searchText)
    }

    func move(_ d: Int) {
        guard count > 0 else { return }
        withAnimation(Motion.or(Motion.spring)) { selected = (selected + d + count) % count }
    }
}

struct PaletteView: View {
    @ObservedObject var state: AppState
    @ObservedObject var model: PaletteModel
    @Environment(\.evoStatic) private var isStatic
    @FocusState private var fieldFocused: Bool

    var body: some View {
        let list = model.filtered(state.palette)
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass").foregroundStyle(Theme.textSecondary)
                ThemedField(placeholder: "搜动作、闸门、项目…", text: $model.query) {
                    PaletteController.shared.runSelected()
                }
                .font(.system(size: 15))
                .focused($fieldFocused)
                .uiProbe("palette-field")
                Text("esc").font(.system(size: 10.5, design: .rounded)).foregroundStyle(Theme.textSecondary)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(RoundedRectangle(cornerRadius: 5).strokeBorder(Theme.border))
            }
            .padding(.horizontal, 16).padding(.vertical, 14)
            Rectangle().fill(Theme.border).frame(height: 1)
            MaybeScroll(maxHeight: 320) {
                VStack(spacing: 2) {
                    if list.isEmpty {
                        Text("没有匹配的").font(Theme.body()).foregroundStyle(Theme.textSecondary).padding(24)
                    }
                    ForEach(Array(list.prefix(isStatic ? 7 : 60).enumerated()), id: \.element.id) { i, e in
                        PaletteRow(entry: e, selected: i == model.selected)
                            .onTapGesture { PaletteController.shared.run(e) }
                            .onHover { if $0 { model.selected = i } }
                    }
                }
                .padding(8)
            }
        }
        .frame(width: 520)
        .background(Theme.bg)
        .onAppear { model.count = list.count; fieldFocused = true }
        .onReceive(model.$focusTick) { _ in DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) { fieldFocused = true } }
        .onChange(of: list.count) { model.count = $0 }
    }
}

struct PaletteRow: View {
    let entry: PaletteEntry
    let selected: Bool
    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: entry.symbol)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(selected ? Theme.accent : Theme.textSecondary)
                .frame(width: 26, height: 26)
                .background(RoundedRectangle(cornerRadius: 7).fill(selected ? Theme.accentSoft : Theme.surfaceSunk))
            VStack(alignment: .leading, spacing: 1) {
                Text(entry.title).font(.system(size: 13, weight: .medium)).foregroundStyle(Theme.textPrimary).lineLimit(1)
                Text(entry.subtitle).font(Theme.caption()).foregroundStyle(Theme.textSecondary).lineLimit(1)
            }
            Spacer()
            if selected { Image(systemName: "return").font(.system(size: 11)).foregroundStyle(Theme.textSecondary) }
        }
        .padding(.horizontal, 10).padding(.vertical, 7)
        .background(RoundedRectangle(cornerRadius: Theme.radiusSmall, style: .continuous).fill(selected ? Theme.surface : Color.clear)
            .shadow(color: .black.opacity(selected ? 0.05 : 0), radius: 4, y: 1))
        .scaleEffect(selected ? 1.0 : 0.985)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(selected ? [.isButton, .isSelected] : .isButton)
    }
}
#endif
