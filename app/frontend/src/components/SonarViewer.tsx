"use client";

import { useRef, useState, type MouseEvent, type WheelEvent } from "react";

import { useFrameImage } from "@/features/sonar/hooks";
import { LoadingSkeleton } from "@/components/States";
import type { BBox } from "@/types";

const MIN_ZOOM = 1;
const MAX_ZOOM = 4;

export function SonarViewer({ frameId, bbox }: { frameId: string; bbox: BBox | null }) {
  const { url, isLoading, isError } = useFrameImage(frameId);
  const imgRef = useRef<HTMLImageElement>(null);
  const [scale, setScale] = useState<{ x: number; y: number } | null>(null);
  const [decodeFailed, setDecodeFailed] = useState(false);

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragging = useRef<{ startX: number; startY: number; panX: number; panY: number } | null>(null);

  function handleLoad() {
    const img = imgRef.current;
    if (!img) return;
    setScale({
      x: img.clientWidth / img.naturalWidth,
      y: img.clientHeight / img.naturalHeight,
    });
  }

  function handleWheel(e: WheelEvent) {
    e.preventDefault();
    setZoom((z) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z - e.deltaY * 0.0015)));
  }

  function handleMouseDown(e: MouseEvent) {
    if (zoom <= 1) return;
    dragging.current = { startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y };
  }

  function handleMouseMove(e: MouseEvent) {
    if (!dragging.current) return;
    setPan({ x: dragging.current.panX + (e.clientX - dragging.current.startX), y: dragging.current.panY + (e.clientY - dragging.current.startY) });
  }

  function endDrag() {
    dragging.current = null;
  }

  function resetView() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }

  if (isLoading) {
    return <LoadingSkeleton rows={1} label="Loading sonar evidence…" />;
  }

  if (isError || !url || decodeFailed) {
    return (
      <div className="flex h-64 items-center justify-center panel text-sm text-slate-500">
        Sonar image unavailable for this frame.
      </div>
    );
  }

  const hasBox = bbox && bbox.x !== null && bbox.y !== null && bbox.w !== null && bbox.h !== null;

  return (
    <div className="relative inline-block max-w-full">
      {zoom > 1 && (
        <button
          type="button"
          onClick={resetView}
          className="absolute right-2 top-2 z-10 rounded-md border border-abyss-600 bg-abyss-900/85 px-2 py-1 text-xs text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
        >
          Reset
        </button>
      )}
      <div
        className="relative max-w-full overflow-hidden rounded-lg border border-abyss-600 bg-black"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={endDrag}
        onMouseLeave={endDrag}
        style={{ cursor: zoom > 1 ? "grab" : "default" }}
      >
        <div
          className="inline-block"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center",
            transition: dragging.current ? "none" : "transform 0.1s ease-out",
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            ref={imgRef}
            src={url}
            onLoad={handleLoad}
            onError={() => setDecodeFailed(true)}
            alt="Sonar frame"
            className="block max-w-full select-none"
            draggable={false}
          />
          {hasBox && scale && (
            <div
              className="pointer-events-none absolute border-2 border-cyan-accent shadow-[0_0_0_1px_rgba(0,0,0,0.6)]"
              style={{
                left: (bbox!.x as number) * scale.x,
                top: (bbox!.y as number) * scale.y,
                width: (bbox!.w as number) * scale.x,
                height: (bbox!.h as number) * scale.y,
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
