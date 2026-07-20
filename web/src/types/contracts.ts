// TypeScript mirror of the ytclfr V3 Pydantic contracts.
// Kept permissive (optionals) so live API responses and rich mock data both fit.

export type JobStatus =
  | "pending"
  | "downloading"
  | "upload_pending"
  | "downloaded"
  | "v3_stage_a_running"
  | "v3_stage_a_complete"
  | "v3_stage_b_running"
  | "v3_stage_c_running"
  | "v3_stage_c_complete"
  | "v3_stage_d_running"
  | "completed"
  | "failed"
  | "dead_letter"
  | "v3_stage_d_failed";

export interface Job {
  job_id: string;
  status: JobStatus;
  youtube_url: string;
  created_at: string;
  schema_version: string;
  error_message?: string | null;
  // enrichment from the Job ORM row (exposed for richer UI)
  video_title?: string | null;
  channel_name?: string | null;
  duration_seconds?: number | null;
  thumbnail_url?: string | null;
}

export interface SubmitJobRequest {
  youtube_url: string;
}

export interface JobResponse extends Job {}

export interface RetryResponse {
  job_id: string;
  message: string;
  resumed_from: string;
}

export type ViewMode = "BASIC" | "FULL" | "DEBUG";

/* ---------------- FinalResponse (Stage D terminal output) ---------------- */

export interface TaxonomyResult {
  parent_category: string;
  child_category: string;
  intent: string;
  confidence: number;
  groq_taxonomy_used: boolean;
}

export interface ExtractedItem {
  name: string;
  item_type: "product" | "person" | "place" | "topic";
  timestamp?: number | null;
  confidence: number;
}

export interface FinalResponse {
  job_id: string;
  taxonomy: TaxonomyResult;
  summary: string;
  items: ExtractedItem[];
  confidence: Record<string, number>;
  fallback_notes: string[];
  created_at: string;
  schema_version?: string;
}

/* ---------------- SignalManifest (Stage A) ---------------- */

export interface SignalManifest {
  job_id: string;
  audio_type:
    | "speech_only"
    | "music_only"
    | "speech_music"
    | "sfx"
    | "ambient"
    | "silent";
  language?: string | null;
  has_speech: boolean;
  has_music: boolean;
  has_burned_in_text: boolean;
  has_subtitle_track: boolean;
  has_faces: boolean;
  motion_density: number;
  motion_score: number;
  aspect_ratio: string;
  content_format:
    | "live_action"
    | "animation"
    | "screen_recording"
    | "mixed"
    | "unknown";
  scene_cut_count: number;
  duration_seconds: number;
  metadata_prior_confidence: number;
  structural_score: number;
  list_likelihood: number;
  countdown_likelihood: number;
  overlay_text_density: number;
  ordinal_pattern_score: number;
  scene_repeat_score: number;
  ocr_required: boolean;
  ocr_expected_coverage: number;
  asr_expected_value: number;
  structural_video_type:
    | "none"
    | "list"
    | "ranking"
    | "countdown"
    | "compilation"
    | "slideshow"
    | "infographic"
    | "unknown";
  probing_confidence: number;
  created_at: string;
}

/* ---------------- ExtractorBundle (Stage B) ---------------- */

export interface ASRSegment {
  segment_type: "asr";
  start_time: number;
  end_time: number;
  text: string;
  confidence: number;
  words: Array<{ start: number; end: number; word: string; score: number }>;
}

export interface OCRSegment {
  segment_type: "ocr";
  frame_timestamp: number;
  text: string;
  confidence: number;
  bounding_boxes?: Array<{
    x: number;
    y: number;
    w: number;
    h: number;
    text?: string;
  }> | null;
}

export interface AudioSegment {
  segment_type: "audio";
  label: string;
  confidence: number;
  codec?: string | null;
  bitrate_kbps?: number | null;
}

export interface ASRCompletenessMetrics {
  total_vad_speech_ms: number;
  total_transcribed_ms: number;
  untranscribed_speech_ratio: number;
  max_untranscribed_segment_ms: number;
  is_degraded: boolean;
}

export interface ExtractorBundle {
  job_id: string;
  asr_segments: ASRSegment[];
  ocr_segments: OCRSegment[];
  audio_segments: AudioSegment[];
  asr_metrics?: ASRCompletenessMetrics | null;
  total_duration_seconds: number;
  extracted_at: string;
}

/* ---------------- EvidenceGraph (Stage C) ---------------- */

export interface FusedSegment {
  timestamp: number;
  end_timestamp?: number | null;
  text: string;
  source: "asr" | "ocr" | "merged" | "audio";
  confidence: number;
  entity_refs: string[];
}

export interface ExtractedEntity {
  name: string;
  entity_type: "product" | "person" | "place" | "topic" | "unknown";
  mentioned_at: number[];
  confidence: number;
}

export interface EvidenceGraph {
  job_id: string;
  segments: FusedSegment[];
  entities: ExtractedEntity[];
  dominant_subject?: string | null;
  groq_summary?: string | null;
  scene_boundaries: number[];
  groq_reasoning_used: boolean;
  modality_coverage: Record<string, number>;
  conflict_count: number;
  conflict_details: Array<Record<string, unknown>>;
  structural_video_type: string;
  evidence_priority_notes: string[];
  primary_evidence_modality: string;
  total_segments: number;
  confidence: number;
  created_at: string;
}

/* ---------------- Aggregate job payload the UI renders ---------------- */

export interface JobArtifact {
  job: Job;
  manifest?: SignalManifest;
  bundle?: ExtractorBundle;
  evidence?: EvidenceGraph;
  result?: FinalResponse;
}

/* Live API envelope for DEBUG/FULL views — carries the full stage artifacts */
export interface DebugPayload {
  _debug_manifest?: SignalManifest;
  _debug_bundle?: ExtractorBundle;
  _debug_evidence_graph?: EvidenceGraph;
}
