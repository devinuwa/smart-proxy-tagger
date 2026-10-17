// Queries the local pgvector index. Each hit names keyword, vector, or both
// so a fused rank is not the only explanation a judge sees.

import { useState, type FormEvent } from "react";
import { formatTimestamp, searchFootage, type SearchHit } from "../api";

export function SearchGallery() {
  const [query, setQuery] = useState("stand-in demo");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setError("Type a search.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      setHits(await searchFootage(trimmed));
    } catch (err) {
      setHits(null);
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-2xl border border-[#3D5F58]/20 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-[#231F20]">Search gallery</h2>
      <p className="mt-1 text-sm text-[#2E4742]">
        Ask in plain language. Results are moments already stored on this machine.
      </p>
      <form onSubmit={(event) => void onSubmit(event)} className="mt-4 flex gap-2">
        <label className="sr-only" htmlFor="footage-query">
          Search captions
        </label>
        <input
          id="footage-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="w-full rounded-lg border border-[#3D5F58]/30 px-3 py-2 text-sm text-[#231F20]"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-[#3D5F58] px-4 py-2 text-sm text-[#F2F2EB] disabled:opacity-60"
        >
          {busy ? "Searching…" : "Search"}
        </button>
      </form>
      {error ? <p className="mt-3 text-sm text-[#671912]">{error}</p> : null}
      {hits && hits.length === 0 ? (
        <p className="mt-4 text-sm text-[#3D5F58]">No moments matched that wording.</p>
      ) : null}
      <ul className="mt-4 space-y-3">
        {hits?.map((hit) => (
          <li key={`${hit.video_path}-${hit.timestamp_seconds}`} className="rounded-xl bg-[#F2F2EB] p-3">
            <div className="flex items-baseline justify-between gap-3">
              <p className="font-mono text-sm font-semibold text-[#231F20]">
                {formatTimestamp(hit.timestamp_seconds)}
              </p>
              <p className="text-xs uppercase tracking-wide text-[#3D5F58]">{hit.signals.join(" + ")}</p>
            </div>
            <p className="mt-1 break-all text-xs text-[#2E4742]">{hit.video_path}</p>
            <p className="mt-2 text-sm text-[#231F20]">{hit.caption}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
