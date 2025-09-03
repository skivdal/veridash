import { useState, useEffect, useRef, useCallback } from "react";
import useBackend, { SourceResponse } from "@/useBackend";

export default function VideoSource({
  videoId,
  onFinishedUpload: handleFinishedUpload,
  scrubToTime,
  onScrubAccepted: handleScrubAccepted,
}: {
  videoId: string | undefined;
  onFinishedUpload: (videoId?: string, error?: string) => void;
  scrubToTime: number | undefined;
  onScrubAccepted: () => void;
}) {
  const [file, setFile] = useState<[File, string] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [importUrl, setImportUrl] = useState("");

  // Signed URL fetch (unchanged behavior)
  const data = useBackend<SourceResponse>(
    undefined,
    "source",
    file ? `${file[0].name}:${file[1]}` : undefined
  );

  const videoElement = useRef<HTMLVideoElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // --- util: hex digest (same as before) ---
  function hex(buffer: ArrayBuffer) {
    let digest = "";
    const view = new DataView(buffer);
    for (let i = 0; i < view.byteLength; i += 4) {
      const value = view.getUint32(i);
      const stringValue = value.toString(16);
      const padding = "00000000";
      const paddedValue = (padding + stringValue).slice(-padding.length);
      digest += paddedValue;
    }
    return digest;
  }

  // --- choose file (click or drop) ---
  const chooseFile = useCallback(async (f: File) => {
    setErr(null);
    let hash = "";
    try {
      hash = hex(await window.crypto.subtle.digest("SHA-256", await f.arrayBuffer()));
    } catch {
      // ignore hashing errors; still proceed
    }
    setFile([f, hash]);
  }, []);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) await chooseFile(f);
  };

  // --- drag & drop ---
  const [dragOver, setDragOver] = useState(false);
  const onDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) await chooseFile(f);
    },
    [chooseFile]
  );
  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };
  const onDragLeave = () => setDragOver(false);

  // --- upload once backend returns signed URL (unchanged) ---
  useEffect(() => {
    if (!data || !file) return;
    setLoading(true);
    (async () => {
      try {
        const res = await fetch((data as SourceResponse).uploadUrl, {
          method: "PUT",
          body: file[0],
          headers: { "Content-Type": file[0].type },
        });
        if (!res.ok) {
          const msg = await res.text();
          setErr(msg || "Upload failed");
          handleFinishedUpload(undefined, msg || "Upload failed");
        } else {
          handleFinishedUpload((data as SourceResponse).videoId, undefined);
        }
      } catch (e: any) {
        const msg = e?.message ?? "Network error during upload";
        setErr(msg);
        handleFinishedUpload(undefined, msg);
      } finally {
        setLoading(false);
      }
    })();
  }, [data]);

  // --- scrub control (unchanged) ---
  useEffect(() => {
    if (videoElement.current && scrubToTime != null) {
      videoElement.current.currentTime = scrubToTime;
      handleScrubAccepted();
    }
  }, [scrubToTime]);

  const downloadUrl = (data as SourceResponse)?.downloadUrl;

  // --- optional: wire your import-by-URL endpoint here ---
  const handleImportUrl = async () => {
    // TODO: call your backend endpoint to import a remote URL and then call handleFinishedUpload(videoId)
    // For now we just noop with a friendly error if filled.
    if (importUrl.trim()) {
      setErr("Import by URL not yet implemented.");
    }
  };

  return (
    <div className="p-4">
      {/* Card container to match Figma: white, rounded, shadow, fixed-ish width */}
      <div className="bg-white rounded-xl shadow-lg border border-gray-100 w-[360px]">
        {/* Header bar */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h2 className="text-sm font-semibold">Media/Source</h2>
          <div className="flex items-center gap-2 text-gray-500">
            {/* Collapse */}
            <button
              type="button"
              onClick={() => setCollapsed((v) => !v)}
              className="p-1 rounded hover:bg-gray-100"
              aria-label="Collapse"
              title="Collapse"
            >
              {/* chevron up/down */}
              <svg
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                {collapsed ? (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
                )}
              </svg>
            </button>
            {/* Close (no-op placeholder, just for look) */}
            <button
              type="button"
              className="p-1 rounded hover:bg-gray-100"
              aria-label="Close"
              title="Close"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        {!collapsed && (
          <div className="px-4 py-4">
            {err && (
              <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {err}
              </div>
            )}

            {videoId && downloadUrl ? (
              // When a source exists, show the player inside the card
              <div className="rounded-lg overflow-hidden border bg-black">
                <video ref={videoElement} controls className="w-full h-[220px] object-contain bg-black">
                  <source src={downloadUrl} />
                </video>
              </div>
            ) : (
              <>
                {/* Drop zone */}
                <div
                  onDrop={onDrop}
                  onDragOver={onDragOver}
                  onDragLeave={onDragLeave}
                  onClick={() => fileInputRef.current?.click()}
                  className={[
                    "border-2 border-dashed rounded-md p-6 text-center cursor-pointer transition-colors",
                    dragOver ? "border-blue-400 bg-blue-50/40" : "border-gray-300",
                  ].join(" ")}
                >
                  <svg
                    className="h-8 w-8 mx-auto mb-2 text-blue-600"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6H17a4 4 0 010 8h-3m-2 3V9m0 0l-3 3m3-3l3 3" />
                  </svg>
                  <p className="text-sm text-gray-700">
                    Drag &amp; drop your video or{" "}
                    <span className="text-blue-600 underline">click to upload</span>
                  </p>
                  <input
                    ref={fileInputRef}
                    id="file"
                    type="file"
                    className="hidden"
                    accept="video/*"
                    onChange={handleFileChange}
                  />
                </div>

                {/* Loading overlay */}
                {loading && (
                  <div className="mt-3 rounded-md border bg-white px-3 py-2">
                    <div className="flex items-center gap-3">
                      <svg
                        aria-hidden="true"
                        className="h-5 w-5 animate-spin"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <circle cx="12" cy="12" r="10" opacity="0.25" />
                        <path d="M22 12a10 10 0 0 1-10 10" />
                      </svg>
                      <p className="text-sm">Uploading… this typically takes under 30 seconds</p>
                    </div>
                    <div className="mt-2 h-1 w-full overflow-hidden rounded bg-gray-200">
                      <div className="h-full w-1/3 animate-[progress_1.1s_ease-in-out_infinite]" />
                    </div>
                    <style>{`@keyframes progress {0%{transform:translateX(-100%)}100%{transform:translateX(300%)}}`}</style>
                  </div>
                )}

                {/* Import from URL */}
                <div className="mt-5">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Import from URL
                  </label>
                  <input
                    type="text"
                    placeholder="Add file URL"
                    value={importUrl}
                    onChange={(e) => setImportUrl(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleImportUrl()}
                    className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-inner focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
