import type { JobStatus } from "../types/contracts";

// Central palette + semantic mappings shared by 3D scenes and 2D UI.
// Values mirror the CSS @theme tokens in index.css.

export const COLORS = {
  abyss: "#06080f",
  void: "#0a0e18",
  surface: "#0d1320",
  primary: "#6366f1",
  primaryDeep: "#4f46e5",
  secondary: "#818cf8",
  accent: "#818cf8",
  accentSoft: "#d9a566",
  text: "#e8ecf4",
  textDim: "#9aa6bd",
  textFaint: "#646f86",
  border: "#1f2940",
  destructive: "#f87171",
  success: "#34d399",
  warning: "#fbbf24",
  asr: "#60a5fa",
  ocr: "#d9a566",
  audio: "#a99cf0",
  merged: "#5fd0b0",
  conflict: "#f0a3a3",
} as const;

export const MODALITY_COLOR: Record<string, string> = {
  asr: COLORS.asr,
  ocr: COLORS.ocr,
  audio: COLORS.audio,
  merged: COLORS.merged,
};

// Pipeline stages (the hero orbit). `key` matches the status prefix.
export interface StageMeta {
  key: string;
  label: string;
  short: string;
  blurb: string;
}

export const STAGES: StageMeta[] = [
  {
    key: "ingest",
    label: "Ingestion",
    short: "ING",
    blurb: "Download & upload to S3",
  },
  {
    key: "stage_a",
    label: "Stage A · Signal Census",
    short: "A",
    blurb: "Cheap physical signal probing",
  },
  {
    key: "stage_b",
    label: "Stage B · Targeted Extraction",
    short: "B",
    blurb: "Dynamic ASR / OCR dispatch",
  },
  {
    key: "stage_c",
    label: "Stage C · Evidence Fusion",
    short: "C",
    blurb: "Temporal align + Groq reasoning",
  },
  {
    key: "stage_d",
    label: "Stage D · Taxonomy",
    short: "D",
    blurb: "Classification + intent",
  },
];

// Map a job status to the stage it currently belongs to (or terminal).
export function statusStage(status: JobStatus): string {
  if (status.startsWith("v3_stage_a")) return "stage_a";
  if (status.startsWith("v3_stage_b")) return "stage_b";
  if (status.startsWith("v3_stage_c")) return "stage_c";
  if (status.startsWith("v3_stage_d")) return "stage_d";
  if (["downloading", "upload_pending", "downloaded"].includes(status))
    return "ingest";
  if (status === "pending") return "ingest";
  return "done";
}

export function isTerminal(status: JobStatus): boolean {
  return ["completed", "failed", "dead_letter", "v3_stage_d_failed"].includes(
    status,
  );
}

export function isFailure(status: JobStatus): boolean {
  return ["failed", "dead_letter", "v3_stage_d_failed"].includes(status);
}

// Progress 0..1 across the whole pipeline for a given status.
const ORDER: JobStatus[] = [
  "pending",
  "downloading",
  "upload_pending",
  "downloaded",
  "v3_stage_a_running",
  "v3_stage_a_complete",
  "v3_stage_b_running",
  "v3_stage_c_running",
  "v3_stage_c_complete",
  "v3_stage_d_running",
  "completed",
];

export function pipelineProgress(status: JobStatus): number {
  const i = ORDER.indexOf(status);
  if (i < 0) return isFailure(status) ? 1 : 0;
  return i / (ORDER.length - 1);
}

export function statusColor(status: JobStatus): string {
  if (isFailure(status)) return COLORS.destructive;
  if (status === "completed") return COLORS.success;
  return COLORS.primary;
}

export function statusLabel(status: JobStatus): string {
  return status
    .replace(/^v3_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
