// Polls the workflow the API already started. A failed poll keeps the last
// snapshot: the job may still be running, so we do not start a second one.
// The workflow id is stored in sessionStorage so a refresh resumes the same job.

import { useEffect, useState } from "react";
import { getJob, isTerminal, type Job } from "../api";

const STORAGE_KEY = "smart-proxy-workflow-id";

type ProcessingDashboardProps = {
  workflowId: string | null;
};

export function ProcessingDashboard({ workflowId }: ProcessingDashboardProps) {
  const [job, setJob] = useState<Job | null>(null);
  const [pollError, setPollError] = useState("");

  useEffect(() => {
    if (!workflowId) return;
    sessionStorage.setItem(STORAGE_KEY, workflowId);
    let stopped = false;
    let timer = 0;

    async function tick() {
      try {
        const next = await getJob(workflowId as string);
        if (stopped) return;
        setJob(next);
        setPollError("");
        if (!isTerminal(next)) timer = window.setTimeout(() => void tick(), 1000);
      } catch (err) {
        if (stopped) return;
        setPollError(err instanceof Error ? err.message : "Status check failed.");
        timer = window.setTimeout(() => void tick(), 2000);
      }
    }

    void tick();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [workflowId]);

  const percent = Math.round((job?.progress ?? 0) * 100);

  return (
    <section className="rounded-2xl border border-[#3D5F58]/20 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-[#231F20]">Processing dashboard</h2>
      <p className="mt-1 text-sm text-[#2E4742]">
        Temporal keeps this job if you close the tab. This panel only watches it.
      </p>
      {!workflowId ? (
        <p className="mt-4 text-sm text-[#3D5F58]">No job yet. Index a path to start one.</p>
      ) : (
        <div className="mt-4 space-y-3">
          <p className="break-all font-mono text-xs text-[#2E4742]">{workflowId}</p>
          <div className="h-3 overflow-hidden rounded-full bg-[#F2F2EB]">
            <div
              className="h-full rounded-full bg-[#3D5F58] transition-all"
              style={{ width: `${job ? percent : 8}%` }}
            />
          </div>
          <dl className="grid grid-cols-2 gap-2 text-sm text-[#231F20]">
            <div>
              <dt className="text-[#3D5F58]">Status</dt>
              <dd className="font-medium">{job?.status ?? "contacting worker"}</dd>
            </div>
            <div>
              <dt className="text-[#3D5F58]">Progress</dt>
              <dd className="font-medium">
                {job ? `${job.frames_captioned} / ${job.frames_seen} frames` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-[#3D5F58]">Voice</dt>
              <dd className="font-medium">{job?.voice_played ? "Played" : "Not yet"}</dd>
            </div>
            <div>
              <dt className="text-[#3D5F58]">Caption model</dt>
              <dd className="font-medium">{job?.caption_model ?? "—"}</dd>
            </div>
          </dl>
          {job?.voice_error ? <p className="text-sm text-[#671912]">{job.voice_error}</p> : null}
          {pollError ? <p className="text-sm text-[#671912]">Still checking: {pollError}</p> : null}
        </div>
      )}
    </section>
  );
}

export function storedWorkflowId(): string | null {
  return sessionStorage.getItem(STORAGE_KEY);
}
