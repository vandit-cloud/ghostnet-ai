"use client";

import { useCallback, useRef, useState, type DragEvent } from "react";

export function UploadDropzone({
  onFilesSelected,
  accept,
  busy = null,
}: {
  onFilesSelected: (files: File[]) => void;
  accept?: string;
  /** While set, the zone shows this status and ignores new files. A sonar
   *  container is split into frames during the upload, so a 40 MB .xtf can
   *  take a few seconds, and the zone used to sit unchanged through them. */
  busy?: string | null;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragging(false);
      if (busy) return;
      const files = Array.from(event.dataTransfer.files);
      if (files.length) onFilesSelected(files);
    },
    [onFilesSelected, busy]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => { if (!busy) inputRef.current?.click(); }}
      role="button"
      tabIndex={0}
      aria-busy={Boolean(busy)}
      onKeyDown={(e) => {
        if (!busy && (e.key === "Enter" || e.key === " ")) inputRef.current?.click();
      }}
      className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
        busy
          ? "cursor-progress border-cyan-accent/60 bg-cyan-accent/5"
          : isDragging
            ? "cursor-pointer border-cyan-accent bg-cyan-accent/5"
            : "cursor-pointer border-abyss-600 hover:border-abyss-500"
      }`}
    >
      {busy ? (
        <>
          <p className="flex items-center gap-2 text-sm font-medium text-slate-200" role="status">
            <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-accent" aria-hidden />
            {busy}
          </p>
          <p className="mt-1 text-xs text-slate-500">Sonar files are split into frames as they upload.</p>
        </>
      ) : (
        <>
          <p className="text-sm font-medium text-slate-200">Drag &amp; drop sonar files here</p>
          <p className="mt-1 text-xs text-slate-500">or click to browse. Supports XTF, Klein SDF, JSF, TIFF, PNG, JPG.</p>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length) onFilesSelected(files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
