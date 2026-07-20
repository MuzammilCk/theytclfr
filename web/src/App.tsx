import { useEffect } from "react";
import { TopBar } from "./components/layout/TopBar";
import { NavRail } from "./components/layout/NavRail";
import { LeftRail } from "./components/layout/LeftRail";
import { Inspector } from "./components/panels/Inspector";
import { SceneRouter } from "./components/three/SceneRouter";
import { useStore, type ViewKey } from "./store/useStore";
import { isFailure, isTerminal } from "./design/tokens";

const VIEW_HINT: Record<ViewKey, string> = {
  overview: "Drag to orbit the pipeline · click a stage to drill in",
  signals: "Hover a signal star to inspect its strength",
  timeline: "Click the floor or drag the scrubber to seek",
  evidence: "Hover an entity node for details",
  taxonomy: "Classification hierarchy from Stage D",
  ocr: "On-screen text regions in frame space",
  search: "Filter the transcript & OCR of the active job",
};

export default function App() {
  const view = useStore((s) => s.view);

  // Live polling loop: refresh the active job until it reaches a terminal state.
  useEffect(() => {
    const id = setInterval(() => {
      const st = useStore.getState();
      if (st.connectivity === "offline") return;
      if (!st.useLive || !st.activeJobId) return;
      const a = st.artifacts[st.activeJobId];
      if (a && !isTerminal(a.job.status) && !isFailure(a.job.status)) {
        st.refresh(st.activeJobId);
      }
    }, 2500);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="h-full w-full flex flex-col">
      <TopBar />
      <div className="flex-1 min-h-0 flex">
        <NavRail />
        <LeftRail />
        <main className="relative flex-1 min-w-0 grid-backdrop">
          <SceneRouter />
          {/* overlay hint */}
          <div className="absolute top-4 left-4 pointer-events-none select-none">
            <div className="label">{view}</div>
            <div className="text-[12px] text-[var(--color-text-dim)] mt-1 max-w-[340px] leading-snug">
              {VIEW_HINT[view]}
            </div>
          </div>
          {/* legend */}
          <div className="absolute bottom-4 left-4 flex flex-wrap gap-2 pointer-events-none">
            {[
              ["asr", "Speech"],
              ["ocr", "On-screen text"],
              ["audio", "Audio"],
              ["merged", "Fused"],
            ].map(([k, label]) => (
              <span key={k} className="flex items-center gap-1.5 text-[10.5px] text-[var(--color-text-dim)] glass-soft rounded-full px-2.5 py-1">
                <span className="w-2 h-2 rounded-full" style={{ background: `var(--color-${k})` }} />
                {label}
              </span>
            ))}
          </div>
        </main>
        <Inspector />
      </div>
    </div>
  );
}
