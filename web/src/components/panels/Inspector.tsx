import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  Search,
  AlertTriangle,
  Cpu,
  Clock,
  KeyRound,
  type LucideIcon,
} from "lucide-react";
import { useStore, type ViewKey } from "../../store/useStore";
import { COLORS, MODALITY_COLOR, isFailure, statusColor, statusLabel } from "../../design/tokens";
import { Badge, Button, EmptyState, Panel, ProgressBar, StatPill, cx } from "../ui/primitives";
import type { JobArtifact } from "../../types/contracts";
import * as api from "../../api/client";
import { Reveal } from "../motion/Reveal";
import { CountUp } from "../motion/CountUp";

function useActive(): JobArtifact | null {
  return useStore((s) => (s.activeJobId ? s.artifacts[s.activeJobId] ?? null : null));
}

function SectionTitle({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 label mb-2.5">
      <Icon size={12} />
      {children}
    </div>
  );
}

function duration(a: JobArtifact): number {
  const maxT = a.evidence?.segments.reduce((m, s) => Math.max(m, s.end_timestamp ?? s.timestamp), 0) ?? 0;
  return a.bundle?.total_duration_seconds ?? a.manifest?.duration_seconds ?? maxT ?? 60;
}

function modalityColorFor(type: string): string {
  switch (type) {
    case "product":
      return MODALITY_COLOR.ocr;
    case "person":
      return MODALITY_COLOR.asr;
    case "place":
      return MODALITY_COLOR.audio;
    default:
      return MODALITY_COLOR.merged;
  }
}

/* ---------------- Overview ---------------- */
function OverviewView({ a }: { a: JobArtifact }) {
  const result = a.result;
  return (
    <div className="flex flex-col gap-4 overflow-y-auto pr-1">
      <Panel title={a.job.video_title ?? "Untitled video"} subtitle={a.job.channel_name ?? a.job.youtube_url}>
        <div className="flex items-center gap-2 mb-3">
          <span className="mono text-[11px] px-2.5 py-0.5 rounded-full" style={{ color: statusColor(a.job.status as never), border: `1px solid ${statusColor(a.job.status as never)}55` }}>
            {statusLabel(a.job.status as never)}
          </span>
          {a.evidence && <Badge color={MODALITY_COLOR[a.evidence.primary_evidence_modality] ?? COLORS.textDim}>{a.evidence.primary_evidence_modality} primary</Badge>}
        </div>
        {result && <ProgressBar value={1} color="var(--color-success)" />}
      </Panel>

      {result && (
        <Panel title="Summary">
          <p className="text-[13px] text-[var(--color-text-dim)] leading-relaxed">{result.summary}</p>
        </Panel>
      )}

      {a.evidence && (
        <div className="grid grid-cols-2 gap-2">
          <StatPill label="Confidence" value={<CountUp value={a.evidence.confidence * 100} suffix="%" />} color={COLORS.merged} />
          <StatPill label="Segments" value={<CountUp value={a.evidence.total_segments} />} />
          <StatPill label="Entities" value={<CountUp value={a.evidence.entities.length} />} color={COLORS.ocr} />
          <StatPill label="Conflicts" value={<CountUp value={a.evidence.conflict_count} />} color={a.evidence.conflict_count ? COLORS.conflict : COLORS.textDim} />
        </div>
      )}

      {result && (
        <Panel title="Taxonomy" subtitle={`groq ${result.taxonomy.groq_taxonomy_used ? "used" : "not used"}`}>
          <div className="flex flex-wrap gap-1.5">
            <Badge color={COLORS.secondary}>{result.taxonomy.parent_category}</Badge>
            <Badge color={COLORS.accentSoft}>{result.taxonomy.child_category}</Badge>
            <Badge color={COLORS.merged}>{result.taxonomy.intent}</Badge>
          </div>
          <div className="mt-3"><ProgressBar value={result.taxonomy.confidence} color={COLORS.merged} /></div>
        </Panel>
      )}

      {result?.fallback_notes.length ? (
        <Panel title="Fallback notes">
          <ul className="text-[12px] text-[var(--color-warning)] space-y-1.5">
            {result.fallback_notes.map((n, i) => (
              <li key={i} className="flex gap-1.5"><AlertTriangle size={13} className="mt-0.5 shrink-0" />{n}</li>
            ))}
          </ul>
        </Panel>
      ) : null}
    </div>
  );
}

/* ---------------- Signals ---------------- */
function SignalsView({ a }: { a: JobArtifact }) {
  const m = a.manifest;
  if (!m) return <EmptyState title="No Stage A signal data" hint="Signal census runs first in the pipeline." />;
  const rows: Array<[string, number]> = [
    ["Structural score", m.structural_score],
    ["List likelihood", m.list_likelihood],
    ["Ordinal pattern", m.ordinal_pattern_score],
    ["Overlay text density", m.overlay_text_density],
    ["OCR expected coverage", m.ocr_expected_coverage],
    ["ASR expected value", m.asr_expected_value],
    ["Probing confidence", m.probing_confidence],
    ["Motion score", m.motion_score],
  ];
  const bools: Array<[string, boolean]> = [
    ["Speech", m.has_speech],
    ["Music", m.has_music],
    ["Burned-in text", m.has_burned_in_text],
    ["Faces", m.has_faces],
    ["Subtitle track", m.has_subtitle_track],
    ["OCR required", m.ocr_required],
  ];
  return (
    <div className="flex flex-col gap-4 overflow-y-auto pr-1">
      <Panel title="Structural type" subtitle={m.structural_video_type}>
        <div className="flex flex-wrap gap-1.5">
          {bools.map(([k, v]) => (
            <Badge key={k} color={v ? COLORS.success : COLORS.textFaint} filled={v}>{k}: {v ? "yes" : "no"}</Badge>
          ))}
        </div>
      </Panel>
      <Panel title="Signal strengths">
        <div className="flex flex-col gap-3">
          {rows.map(([k, v]) => (
            <div key={k}>
              <div className="flex justify-between text-[12px] mb-1.5">
                <span className="text-[var(--color-text-dim)]">{k}</span>
                <span className="mono" style={{ color: v > 0.66 ? COLORS.primary : v > 0.33 ? COLORS.secondary : COLORS.textFaint }}>{v.toFixed(2)}</span>
              </div>
              <ProgressBar value={v} color={v > 0.66 ? COLORS.primary : v > 0.33 ? COLORS.secondary : COLORS.textFaint} />
            </div>
          ))}
        </div>
      </Panel>
      <div className="grid grid-cols-2 gap-2">
        <StatPill label="Motion density" value={`${m.motion_density.toFixed(1)}/m`} />
        <StatPill label="Scene cuts" value={m.scene_cut_count} />
        <StatPill label="Duration" value={`${Math.round(m.duration_seconds)}s`} />
        <StatPill label="Format" value={m.content_format} />
      </div>
    </div>
  );
}

/* ---------------- Timeline ---------------- */
function TimelineView({ a }: { a: JobArtifact }) {
  const playhead = useStore((s) => s.playhead);
  const setPlayhead = useStore((s) => s.setPlayhead);
  const dur = duration(a);
  const segs = a.evidence?.segments ?? [];
  return (
    <div className="flex flex-col gap-4 overflow-y-auto pr-1">
      <Panel title="Scrubber">
        <div className="flex items-center gap-2 mb-2.5 mono text-[12px] text-[var(--color-text-dim)]">
          <Clock size={13} /> {playhead.toFixed(1)}s / {Math.round(dur)}s
        </div>
        <input
          type="range"
          min={0}
          max={dur}
          step={0.1}
          value={playhead}
          onChange={(e) => setPlayhead(parseFloat(e.target.value))}
          className="w-full accent-[var(--color-primary)] cursor-pointer"
          aria-label="Timeline scrubber"
        />
        <p className="text-[10.5px] text-[var(--color-text-faint)] mt-2.5">Drag, or click the 3D stage floor to seek.</p>
      </Panel>
      <Panel title={`Segments · ${segs.length}`}>
        <Reveal as="ul" staggerSelector="li" className="flex flex-col gap-1.5 list-none m-0 p-0">
          {segs.map((s, i) => (
            <li key={i}>
              <button
                onClick={() => setPlayhead(s.timestamp)}
                className="w-full text-left rounded-xl p-2.5 hover:bg-[var(--color-surface-2)] border border-transparent hover:border-[var(--color-border)] transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <span className="mono text-[10px]" style={{ color: MODALITY_COLOR[s.source] }}>{s.source}</span>
                  <span className="mono text-[10px] text-[var(--color-text-faint)]">{s.timestamp.toFixed(1)}s</span>
                  <span className="mono text-[10px] text-[var(--color-text-faint)] ml-auto">{(s.confidence * 100).toFixed(0)}%</span>
                </div>
                <div className="text-[12.5px] text-[var(--color-text)] mt-1 truncate">{s.text}</div>
              </button>
            </li>
          ))}
        </Reveal>
      </Panel>
    </div>
  );
}

/* ---------------- Evidence ---------------- */
function EvidenceView({ a }: { a: JobArtifact }) {
  const ev = a.evidence;
  if (!ev) return <EmptyState title="No evidence graph" hint="Stage C produces the fused evidence graph." />;
  return (
    <div className="flex flex-col gap-4 overflow-y-auto pr-1">
      {ev.groq_summary && (
        <Panel title="Groq reasoning" subtitle={ev.groq_reasoning_used ? "used" : "not used"}>
          <p className="text-[13px] text-[var(--color-text-dim)] leading-relaxed">{ev.groq_summary}</p>
        </Panel>
      )}
      <Panel title="Modality coverage">
        <div className="flex flex-col gap-3">
          {Object.entries(ev.modality_coverage).map(([k, v]) => (
            <div key={k}>
              <div className="flex justify-between text-[12px] mb-1.5">
                <span className="mono" style={{ color: MODALITY_COLOR[k] ?? COLORS.textDim }}>{k}</span>
                <span className="mono text-[var(--color-text-dim)]">{(v * 100).toFixed(0)}%</span>
              </div>
              <ProgressBar value={v} color={MODALITY_COLOR[k] ?? COLORS.textDim} />
            </div>
          ))}
        </div>
      </Panel>
      <Panel title={`Entities · ${ev.entities.length}`}>
        <Reveal as="ul" staggerSelector="li" className="flex flex-col gap-1.5 list-none m-0 p-0">
          {ev.entities.map((e) => (
            <li key={e.name} className="flex items-center justify-between rounded-xl p-2.5 bg-[var(--color-surface-2)]">
              <div>
                <div className="text-[13px] font-medium">{e.name}</div>
                <div className="mono text-[10px] text-[var(--color-text-faint)]">@ {e.mentioned_at.map((t) => `${t.toFixed(0)}s`).join(", ")}</div>
              </div>
              <Badge color={modalityColorFor(e.entity_type)}>{e.entity_type}</Badge>
            </li>
          ))}
        </Reveal>
      </Panel>
      {ev.conflict_count > 0 && (
        <Panel title={`Conflicts · ${ev.conflict_count}`}>
          <ul className="text-[12px] text-[var(--color-conflict)] space-y-1.5">
            {ev.conflict_details.map((c, i) => (
              <li key={i} className="flex gap-1.5"><AlertTriangle size={13} className="mt-0.5 shrink-0" />{JSON.stringify(c).slice(0, 120)}</li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

/* ---------------- Taxonomy ---------------- */
function TaxonomyView({ a }: { a: JobArtifact }) {
  const r = a.result;
  if (!r) return <EmptyState title="No taxonomy result" hint="Stage D classifies the video and resolves intent." />;
  return (
    <div className="flex flex-col gap-4 overflow-y-auto pr-1">
      <Panel title="Classification">
        <div className="flex flex-col gap-2.5">
          {[["Parent", r.taxonomy.parent_category, COLORS.secondary], ["Child", r.taxonomy.child_category, COLORS.accentSoft], ["Intent", r.taxonomy.intent, COLORS.merged]].map(([l, v, c]) => (
            <div key={l as string} className="flex items-center justify-between">
              <span className="label">{l}</span>
              <span className="text-[14px] font-medium" style={{ color: c as string }}>{v as string}</span>
            </div>
          ))}
        </div>
        <div className="mt-3"><ProgressBar value={r.taxonomy.confidence} color={COLORS.merged} /></div>
      </Panel>
      <Panel title={`Items · ${r.items.length}`}>
        <Reveal as="ul" staggerSelector="li" className="flex flex-col gap-1.5 list-none m-0 p-0">
          {r.items.map((it, i) => (
            <li key={i} className="flex items-center justify-between rounded-xl p-2.5 bg-[var(--color-surface-2)]">
              <div className="min-w-0">
                <div className="text-[13px] font-medium truncate">{it.name}</div>
                <div className="mono text-[10px] text-[var(--color-text-faint)]">@ {it.timestamp?.toFixed(0) ?? "?"}s</div>
              </div>
              <Badge color={modalityColorFor(it.item_type)}>{it.item_type}</Badge>
            </li>
          ))}
        </Reveal>
      </Panel>
    </div>
  );
}

/* ---------------- OCR ---------------- */
function OcrView({ a }: { a: JobArtifact }) {
  const setPlayhead = useStore((s) => s.setPlayhead);
  const segs = a.bundle?.ocr_segments ?? [];
  if (!segs.length) return <EmptyState title="No OCR segments" hint="On-screen text is extracted in Stage B when structural signals demand it." />;
  return (
    <div className="flex flex-col gap-4 overflow-y-auto pr-1">
      <Panel title={`OCR frames · ${segs.length}`} subtitle="click to load into the 3D field">
        <Reveal as="ul" staggerSelector="li" className="flex flex-col gap-1.5 list-none m-0 p-0">
          {segs.map((s, i) => (
            <li key={i}>
              <button onClick={() => setPlayhead(s.frame_timestamp)} className="w-full text-left rounded-xl p-2.5 hover:bg-[var(--color-surface-2)] border border-transparent hover:border-[var(--color-border)] transition-colors cursor-pointer">
                <div className="flex items-center justify-between">
                  <span className="mono text-[10px]" style={{ color: COLORS.ocr }}>{s.frame_timestamp.toFixed(1)}s</span>
                  <span className="mono text-[10px] text-[var(--color-text-faint)]">{s.bounding_boxes?.length ?? 0} regions</span>
                </div>
                <div className="text-[12.5px] text-[var(--color-text)] mt-1">{s.text}</div>
              </button>
            </li>
          ))}
        </Reveal>
      </Panel>
    </div>
  );
}

/* ---------------- Search (live) ---------------- */
function SearchView({ a }: { a: JobArtifact }) {
  const token = useStore((s) => s.token);
  const connectivity = useStore((s) => s.connectivity);
  const setPlayhead = useStore((s) => s.setPlayhead);
  const setView = useStore((s) => s.setView);
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"keyword" | "similarity">("keyword");
  const [hits, setHits] = useState<api.SearchHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token || connectivity === "offline") {
    return <EmptyState icon={<KeyRound size={26} />} title="Connect to search" hint="Set a JWT token to run live keyword and vector search against this job's extracted transcript and OCR." />;
  }

  const run = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.searchSegments(a.job.job_id, q.trim(), mode, token);
      setHits(res.results);
    } catch (err) {
      setError((err as Error).message);
      setHits([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 overflow-y-auto pr-1">
      <Panel title="Search transcript & OCR" subtitle="live · backend /api/v3">
        <form onSubmit={run}>
          <div className="flex items-center gap-2 rounded-xl bg-[var(--color-void)] border border-[var(--color-border)] px-3 focus-within:border-[var(--color-primary)]/60 transition-colors">
            <Search size={15} className="text-[var(--color-text-faint)]" />
            <input
              value={q}
              autoFocus
              onChange={(e) => setQ(e.target.value)}
              placeholder="thinkpad, bake, track 3…"
              className="bg-transparent w-full py-2.5 text-sm outline-none placeholder:text-[var(--color-text-faint)]"
            />
          </div>
          <div className="flex items-center gap-2 mt-3">
            <div className="flex rounded-lg border border-[var(--color-border)] overflow-hidden text-[11px] mono">
              {(["keyword", "similarity"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={cx("px-2.5 py-1 transition-colors cursor-pointer", mode === m ? "bg-[var(--color-primary)]/15 text-[var(--color-primary)]" : "text-[var(--color-text-faint)]")}
                >
                  {m}
                </button>
              ))}
            </div>
            <Button type="submit" disabled={loading || !q.trim()} className="ml-auto !py-1.5 !px-3 text-[12px]">
              {loading ? "Searching…" : "Search"}
            </Button>
          </div>
        </form>
        {error && (
          <div className="flex items-start gap-1.5 text-[11px] text-[var(--color-destructive)] mt-3">
            <AlertTriangle size={12} className="mt-0.5 shrink-0" />{error}
          </div>
        )}
      </Panel>

      {hits && (
        <Panel title={`Results · ${hits.length}`}>
          {hits.length === 0 ? (
            <p className="text-[12px] text-[var(--color-text-faint)] py-4 text-center">No matches in this job.</p>
          ) : (
            <Reveal as="ul" staggerSelector="li" className="flex flex-col gap-1.5 list-none m-0 p-0">
              {hits.map((s, i) => (
                <li key={i}>
                  <button
                    onClick={() => { setPlayhead(s.start_seconds); setView("timeline"); }}
                    className="w-full text-left rounded-xl p-2.5 hover:bg-[var(--color-surface-2)] border border-transparent hover:border-[var(--color-border)] transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <span className="mono text-[10px]" style={{ color: MODALITY_COLOR[s.source] ?? COLORS.textDim }}>{s.source}</span>
                      <span className="mono text-[10px] text-[var(--color-text-faint)]">{s.start_seconds.toFixed(1)}s</span>
                      <span className="mono text-[10px] text-[var(--color-text-faint)] ml-auto">{(s.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div className="text-[12.5px] text-[var(--color-text)] mt-1">{s.text}</div>
                  </button>
                </li>
              ))}
            </Reveal>
          )}
        </Panel>
      )}
    </div>
  );
}

const TITLES: Record<ViewKey, string> = {
  overview: "Job Overview",
  signals: "Stage A · Signals",
  timeline: "Timeline Theatre",
  evidence: "Evidence Graph",
  taxonomy: "Taxonomy",
  ocr: "OCR Spatial Field",
  search: "Search",
};

export function Inspector() {
  const view = useStore((s) => s.view);
  const a = useActive();

  return (
    <aside className="w-[380px] shrink-0 flex flex-col border-l border-[var(--color-border)] bg-[var(--color-void)]/40">
      <div className="px-4 py-3.5 border-b border-[var(--color-border)] flex items-center gap-2">
        <Cpu size={15} className="text-[var(--color-primary)]" />
        <h2 className="text-[13px] font-semibold tracking-wide">{TITLES[view]}</h2>
      </div>
      <div className="flex-1 min-h-0 p-3.5">
        {!a ? (
          <EmptyState title="No job selected" hint="Select a job from the list, or submit a new video URL." />
        ) : (
          <>
            {view === "overview" && <OverviewView a={a} />}
            {view === "signals" && <SignalsView a={a} />}
            {view === "timeline" && <TimelineView a={a} />}
            {view === "evidence" && <EvidenceView a={a} />}
            {view === "taxonomy" && <TaxonomyView a={a} />}
            {view === "ocr" && <OcrView a={a} />}
            {view === "search" && <SearchView a={a} />}
          </>
        )}
      </div>
    </aside>
  );
}
