import type {
  DebugPayload,
  FinalResponse,
  Job,
  JobResponse,
  RetryResponse,
  SubmitJobRequest,
  ViewMode,
} from "../types/contracts";

// Thin wrapper over the ytclfr FastAPI v3 endpoints. Every call throws on
// network/HTTP error so the store can surface an offline state.

const BASE = "/api/v3";

function authHeaders(token: string): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export async function submitJob(
  req: SubmitJobRequest,
  token: string,
): Promise<JobResponse> {
  const res = await fetch(`${BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(req),
  });
  return json<JobResponse>(res);
}

export async function getJob(jobId: string, token: string): Promise<Job> {
  const res = await fetch(`${BASE}/jobs/${jobId}`, {
    headers: authHeaders(token),
  });
  return json<Job>(res);
}

export async function retryJob(
  jobId: string,
  token: string,
): Promise<RetryResponse> {
  const res = await fetch(`${BASE}/jobs/${jobId}/retry`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return json<RetryResponse>(res);
}

export interface ResultEnvelope extends FinalResponse, DebugPayload {}

export async function getResult(
  jobId: string,
  token: string,
  view: ViewMode = "DEBUG",
): Promise<ResultEnvelope> {
  const res = await fetch(
    `${BASE}/jobs/${jobId}/result?view=${view}`,
    { headers: authHeaders(token) },
  );
  return json<ResultEnvelope>(res);
}

export interface SearchHit {
  start_seconds: number;
  end_seconds: number | null;
  text: string;
  source: string;
  confidence: number;
}

export interface SearchResponse {
  job_id: string;
  mode: "keyword" | "similarity";
  query: string;
  count: number;
  results: SearchHit[];
}

export async function searchSegments(
  jobId: string,
  query: string,
  mode: "keyword" | "similarity",
  token: string,
): Promise<SearchResponse> {
  const res = await fetch(
    `${BASE}/jobs/${jobId}/search?q=${encodeURIComponent(query)}&mode=${mode}`,
    { headers: authHeaders(token) },
  );
  return json<SearchResponse>(res);
}
