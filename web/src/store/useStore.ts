import { create } from "zustand";
import * as api from "../api/client";
import type { JobArtifact, ViewMode } from "../types/contracts";
import { isTerminal, isFailure } from "../design/tokens";

export type ViewKey =
  | "overview"
  | "signals"
  | "timeline"
  | "evidence"
  | "taxonomy"
  | "ocr"
  | "search";

type Connectivity = "offline" | "unknown" | "live";

interface AppState {
  token: string;
  useLive: boolean;
  connectivity: Connectivity;
  artifacts: Record<string, JobArtifact>;
  order: string[];
  activeJobId: string | null;
  view: ViewKey;
  selectedStage: string | null;
  playhead: number;
  lastError: string | null;
  submitting: boolean;

  setToken: (t: string) => void;
  setView: (v: ViewKey) => void;
  setStage: (s: string | null) => void;
  setPlayhead: (t: number) => void;
  selectJob: (id: string) => void;
  submit: (url: string) => Promise<void>;
  retry: (id: string) => Promise<void>;
  refresh: (id: string) => Promise<void>;
}

function buildArtifactFromResult(
  job: JobArtifact["job"],
  env: api.ResultEnvelope,
): JobArtifact {
  const artifact: JobArtifact = { job };
  if (env._debug_manifest) artifact.manifest = env._debug_manifest;
  if (env._debug_bundle) artifact.bundle = env._debug_bundle;
  if (env._debug_evidence_graph) artifact.evidence = env._debug_evidence_graph;
  artifact.result = {
    job_id: env.job_id,
    taxonomy: env.taxonomy,
    summary: env.summary,
    items: env.items,
    confidence: env.confidence,
    fallback_notes: env.fallback_notes,
    created_at: env.created_at,
    schema_version: env.schema_version,
  };
  return artifact;
}

export const useStore = create<AppState>((set, get) => ({
  token: "",
  useLive: false,
  connectivity: "offline",
  artifacts: {},
  order: [],
  activeJobId: null,
  view: "overview",
  selectedStage: null,
  playhead: 0,
  lastError: null,
  submitting: false,

  setToken: (t) =>
    set({
      token: t,
      useLive: t.trim().length > 0,
      connectivity: t.trim() ? "unknown" : "offline",
      lastError: null,
    }),

  setView: (v) => set({ view: v }),
  setStage: (s) => set({ selectedStage: s }),
  setPlayhead: (t) => set({ playhead: t }),
  selectJob: (id) => set({ activeJobId: id, playhead: 0 }),

  submit: async (url) => {
    const { token, useLive } = get();
    if (!useLive) {
      set({ lastError: "Connect a JWT token to submit jobs." });
      return;
    }
    set({ submitting: true, lastError: null });
    try {
      const job = await api.submitJob({ youtube_url: url }, token);
      const artifact: JobArtifact = {
        job: { ...job, video_title: null, channel_name: null, duration_seconds: null, thumbnail_url: null },
      };
      set((s) => ({
        artifacts: { ...s.artifacts, [job.job_id]: artifact },
        order: [job.job_id, ...s.order],
        activeJobId: job.job_id,
        connectivity: "live",
      }));
    } catch (e) {
      set({ connectivity: "offline", lastError: (e as Error).message });
    } finally {
      set({ submitting: false });
    }
  },

  retry: async (id) => {
    const { token, useLive } = get();
    if (!useLive) {
      set({ lastError: "Connect a JWT token to retry jobs." });
      return;
    }
    try {
      await api.retryJob(id, token);
      set((s) => ({
        artifacts: {
          ...s.artifacts,
          [id]: { ...s.artifacts[id], job: { ...s.artifacts[id].job, status: "pending" } },
        },
        lastError: null,
      }));
    } catch (e) {
      set({ connectivity: "offline", lastError: (e as Error).message });
    }
  },

  refresh: async (id) => {
    const { token, useLive } = get();
    if (!useLive) return;
    try {
      const job = await api.getJob(id, token);
      const artifact: JobArtifact = { job };
      try {
        const env = await api.getResult(id, token, "DEBUG");
        Object.assign(artifact, buildArtifactFromResult(job, env));
      } catch {
        // result not ready yet (in-progress job) — keep job status only
      }
      set((s) => ({
        artifacts: { ...s.artifacts, [id]: artifact },
        connectivity: "live",
        lastError: null,
      }));
    } catch (e) {
      set({ connectivity: "offline", lastError: (e as Error).message });
    }
  },
}));

export function activeArtifact(s: AppState): JobArtifact | null {
  return s.activeJobId ? s.artifacts[s.activeJobId] ?? null : null;
}

export { isTerminal, isFailure };
