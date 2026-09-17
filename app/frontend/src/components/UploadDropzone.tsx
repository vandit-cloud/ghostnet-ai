"use client";

import { useCallback, useRef, useState, type DragEvent } from "react";

export function UploadDropzone({
  onFilesSelected,
  accept,
}: {
  onFilesSelected: (files: File[]) => void;
  accept?: string;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragging(false);
      const files = Array.from(event.dataTransfer.files);
      if (files.length) onFilesSelected(files);
    },
    [onFilesSelected]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
        isDragging ? "border-cyan-accent bg-cyan-accent/5" : "border-abyss-600 hover:border-abyss-500"
      }`}
    >
      <p className="text-sm font-medium text-slate-200">Drag &amp; drop sonar files here</p>
      <p className="mt-1 text-xs text-slate-500">or click to browse. Supports XTF, JSF, TIFF, PNG, JPG.</p>
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
