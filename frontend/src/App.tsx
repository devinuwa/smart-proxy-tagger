import { useEffect, useState } from "react";
import { getHealth, startJob, type Health } from "./api";
import { Dropzone } from "./components/Dropzone";
import { ProcessingDashboard, storedWorkflowId } from "./components/ProcessingDashboard";
import { SearchGallery } from "./components/SearchGallery";

export default function App() {
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState("");

  useEffect(() => {
    setWorkflowId(storedWorkflowId());
    void getHealth()
      .then(setHealth)
      .catch((err: unknown) => {
        setHealthError(err instanceof Error ? err.message : "API unreachable");
      });
  }, []);

  async function onIndex(path: string) {
    setBusy(true);
    try {
      const started = await startJob(path);
      setWorkflowId(started.workflow_id);
    } finally {
      setBusy(false);
    }
  }

  const apiLabel = health
    ? `Database ${health.database} · Temporal ${health.temporal}`
    : healthError || "Checking the local API…";

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-4 py-8 text-[#231F20]">
      <header className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#E53927]">
          Hacktoberfest Week 2 · Side Hustle
        </p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Smart Proxy Tagger</h1>
        <p className="mt-2 max-w-2xl text-sm text-[#2E4742]">
          Index raw footage on this laptop. Search the moments without uploading the card.
        </p>
        <p className="mt-2 text-xs text-[#3D5F58]">{apiLabel}</p>
      </header>
      <div className="grid gap-4 lg:grid-cols-2">
        <Dropzone busy={busy} onIndex={onIndex} />
        <ProcessingDashboard workflowId={workflowId} />
        <div className="lg:col-span-2">
          <SearchGallery />
        </div>
      </div>
    </main>
  );
}
