// Talks to the FastAPI process on this machine. The UI never captions frames.
// Closing the page only stops these polls; the Temporal worker keeps going.

const API_BASE = "http://127.0.0.1:8000";

export type Job = {
  workflow_id: string;
  video_path: string;
  status: string;
  frames_seen: number;
  frames_captioned: number;
  voice_played: boolean;
  voice_error: string | null;
  caption_model: string | null;
  updated_at: string | null;
  progress: number;
};

export type SearchHit = {
  video_path: string;
  timestamp_seconds: number;
  caption: string;
  signals: string[];
};

export type Health = {
  database: string;
  temporal: string;
};

// "indexed" is written before the voice activity finishes. Stop only once the
// voice has played or recorded an error, so a refresh does not freeze on
// "Not yet" while the sentence is still being spoken.
export function isTerminal(job: Pick<Job, "status" | "voice_played" | "voice_error">): boolean {
  if (job.status === "failed" || job.status === "complete") return true;
  if (job.status === "indexed") return job.voice_played || Boolean(job.voice_error);
  return false;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // The body was not JSON. Fall through to the status line.
  }
  return `Request failed (${response.status})`;
}

export async function getHealth(): Promise<Health> {
  const response = await fetch(`${API_BASE}/api/health`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<Health>;
}

export async function startJob(path: string): Promise<{ workflow_id: string; status: string }> {
  const response = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<{ workflow_id: string; status: string }>;
}

export async function getJob(workflowId: string): Promise<Job> {
  const response = await fetch(`${API_BASE}/api/jobs/${workflowId}`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<Job>;
}

export async function searchFootage(query: string): Promise<SearchHit[]> {
  const params = new URLSearchParams({ q: query });
  const response = await fetch(`${API_BASE}/api/search?${params}`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<SearchHit[]>;
}

export function formatTimestamp(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(whole / 60);
  const remain = whole % 60;
  return `${minutes}:${remain.toString().padStart(2, "0")}`;
}
