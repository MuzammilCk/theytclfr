import { useRef } from "react";
import {
  Activity,
  Network,
  Radar,
  ScanLine,
  Search,
  Share2,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { useStore, type ViewKey } from "../../store/useStore";
import { gsap, useGSAP, MOTION, prefersReducedMotion } from "../../lib/gsap";

const ITEMS: Array<{ key: ViewKey; icon: LucideIcon; label: string }> = [
  { key: "overview", icon: Workflow, label: "Pipeline" },
  { key: "signals", icon: Radar, label: "Signals" },
  { key: "timeline", icon: Activity, label: "Timeline" },
  { key: "evidence", icon: Share2, label: "Evidence" },
  { key: "taxonomy", icon: Network, label: "Taxonomy" },
  { key: "ocr", icon: ScanLine, label: "OCR" },
  { key: "search", icon: Search, label: "Search" },
];

export function NavRail() {
  const view = useStore((s) => s.view);
  const setView = useStore((s) => s.setView);
  const navRef = useRef<HTMLElement>(null);
  const indicatorRef = useRef<HTMLSpanElement>(null);

  // Slide the active pill to the selected item (shared-element continuity).
  useGSAP(
    () => {
      const nav = navRef.current;
      const ind = indicatorRef.current;
      if (!nav || !ind) return;
      const activeBtn = nav.querySelector<HTMLElement>(`[data-view="${view}"]`);
      if (!activeBtn) return;
      const y = activeBtn.offsetTop;
      if (prefersReducedMotion()) {
        gsap.set(ind, { y });
        return;
      }
      gsap.to(ind, { y, duration: 0.3, ease: MOTION.ease });
    },
    { dependencies: [view], scope: navRef },
  );

  return (
    <nav
      ref={navRef}
      aria-label="Primary"
      className="relative flex flex-col items-center gap-1.5 py-4 w-[68px] border-r border-[var(--color-border)] bg-[var(--color-void)]/50"
    >
      {/* sliding active pill — no side-tab accent bar */}
      <span
        ref={indicatorRef}
        aria-hidden
        className="absolute left-2 w-[52px] h-[48px] rounded-xl bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/25 pointer-events-none"
        style={{ top: 0 }}
      />
      {ITEMS.map(({ key, icon: Icon, label }) => {
        const active = view === key;
        return (
          <button
            key={key}
            data-view={key}
            onClick={() => setView(key)}
            aria-current={active ? "page" : undefined}
            title={label}
            className="relative z-10 w-[52px] h-[48px] rounded-xl flex items-center justify-center transition-colors duration-200 cursor-pointer group"
            style={{ color: active ? "var(--color-primary)" : "var(--color-text-faint)" }}
          >
            <Icon
              size={19}
              strokeWidth={active ? 2.1 : 1.7}
              className="transition-transform duration-200 group-hover:scale-110"
            />
            <span className="sr-only">{label}</span>
          </button>
        );
      })}
    </nav>
  );
}
