// Local footage never uploads. The browser will not reveal a full disk path
// from a file picker, so the editor pastes the path the API is allowed to open.

import { useRef, useState, type DragEvent } from "react";

const VIDEO_HINT = ".mp4, .mov, .mkv, .avi, .webm, .m4v";

type DropzoneProps = {
  busy: boolean;
  onIndex: (path: string) => Promise<void>;
};

export function Dropzone({ busy, onIndex }: DropzoneProps) {
  const [dragging, setDragging] = useState(false);
  const [pickedName, setPickedName] = useState("");
  const [path, setPath] = useState("");
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  function rememberFile(file: File | undefined) {
    if (!file) return;
    const lower = file.name.toLowerCase();
    const allowed = VIDEO_HINT.split(", ").some((suffix) => lower.endsWith(suffix));
    if (!allowed) {
      setError(`Choose a video (${VIDEO_HINT}).`);
      return;
    }
    setError("");
    setPickedName(file.name);
    // Electron and a few desktop shells attach a path. Browsers do not.
    const nativePath = (file as File & { path?: string }).path;
    if (nativePath) setPath(nativePath);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    rememberFile(event.dataTransfer.files[0]);
  }

  async function submit() {
    const trimmed = path.trim();
    if (!trimmed) {
      setError("Paste the full path on this computer. The picker only shares the file name.");
      return;
    }
    setError("");
    try {
      await onIndex(trimmed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start indexing.");
    }
  }

  return (
    <section className="rounded-2xl border border-[#3D5F58]/20 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-[#231F20]">Dropzone</h2>
      <p className="mt-1 text-sm text-[#2E4742]">
        Point at a local video or folder. Frames stay on this machine.
      </p>

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`mt-4 flex flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center ${
          dragging ? "border-[#E53927] bg-[#F5B726]/20" : "border-[#3D5F58]/40 bg-[#F2F2EB]"
        }`}
      >
        <p className="text-sm font-medium text-[#231F20]">
          {dragging ? "Release to note this file" : "Drop a video here, or choose one"}
        </p>
        <p className="text-xs text-[#3D5F58]">{VIDEO_HINT}</p>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            className="rounded-lg bg-[#3D5F58] px-3 py-2 text-sm text-[#F2F2EB]"
            onClick={() => fileRef.current?.click()}
          >
            Choose file
          </button>
          <button
            type="button"
            className="rounded-lg border border-[#3D5F58] px-3 py-2 text-sm text-[#2E4742]"
            onClick={() => folderRef.current?.click()}
          >
            Choose folder
          </button>
        </div>
        {pickedName ? <p className="text-sm text-[#231F20]">Selected name: {pickedName}</p> : null}
        <input
          ref={fileRef}
          type="file"
          accept="video/*,.mp4,.mov,.mkv,.avi,.webm,.m4v"
          className="hidden"
          onChange={(event) => rememberFile(event.target.files?.[0])}
        />
        <input
          ref={folderRef}
          type="file"
          className="hidden"
          multiple
          onChange={(event) => rememberFile(event.target.files?.[0])}
          {...{ webkitdirectory: "", directory: "" }}
        />
      </div>

      <label className="mt-4 block text-sm font-medium text-[#231F20]" htmlFor="footage-path">
        Full path on this computer
      </label>
      <input
        id="footage-path"
        value={path}
        onChange={(event) => setPath(event.target.value)}
        placeholder="C:\Footage\interview.mp4"
        className="mt-1 w-full rounded-lg border border-[#3D5F58]/30 bg-white px-3 py-2 text-sm text-[#231F20]"
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => void submit()}
        className="mt-3 rounded-lg bg-[#E53927] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
      >
        {busy ? "Starting…" : "Index footage"}
      </button>
      {error ? <p className="mt-2 text-sm text-[#671912]">{error}</p> : null}
    </section>
  );
}
