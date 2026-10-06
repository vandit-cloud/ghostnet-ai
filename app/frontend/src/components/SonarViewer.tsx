"use client";

import { useEffect, useRef, useState, type MouseEvent, type WheelEvent } from "react";

import { useFrameImage } from "@/features/sonar/hooks";
import { LoadingSkeleton } from "@/components/States";
import { DETECTION } from "@/utils/palette";
import { despeckleImage } from "@/utils/despeckle";
import type { BBox } from "@/types";

const MIN_ZOOM = 1;
const MAX_ZOOM = 4;

/** Outline polygon [[x, y], ...] in frame pixels -- the same frame and origin
 *  as `bbox` (AI contract 1.3.0). Only nets from the segmentation model carry
 *  one; everything else is box-only and passes null. */
type Polygon = number[][];

export function SonarViewer({
  frameId,
  bbox,
  polygon = null,
}: {
  frameId: string;
  bbox: BBox | null;
  polygon?: Polygon | null;
}) {
  const { url, isLoading, isError } = useFrameImage(frameId);
  const imgRef = useRef<HTMLImageElement>(null);
  const [scale, setScale] = useState<{ x: number; y: number } | null>(null);
  const [decodeFailed, setDecodeFailed] = useState(false);
  /** The frame currently on screen, readable from an async callback without
   *  capturing a stale render's value. */
  const urlRef = useRef(url);
  urlRef.current = url;

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragging = useRef<{ startX: number; startY: number; panX: number; panY: number } | null>(null);

  /* Despeckled view. Off by default and never persisted: the raw frame is the
   * evidence of record, and a filter that can erase a small target should be
   * something the operator turns on deliberately, on this frame, having
   * already seen it unfiltered. See utils/despeckle.ts. */
  const [despeckled, setDespeckled] = useState(false);
  const [filteredUrl, setFilteredUrl] = useState<string | null>(null);
  const [filtering, setFiltering] = useState(false);
  const [filterFailed, setFilterFailed] = useState(false);

  /* A new frame invalidates everything derived from the old one.
   *
   * `decodeFailed` belongs in here too, and its absence was a real trap: this
   * component instance is KEPT MOUNTED while the selected detection changes
   * (the GIS map swaps `frameId` on the same instance), so a single frame that
   * failed to decode left the flag latched and every subsequent detection
   * rendered "Sonar image unavailable" until a full remount. The failure is a
   * property of one frame, so it has to be cleared with that frame. */
  useEffect(() => {
    setFilteredUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return null;
    });
    setDespeckled(false);
    setFilterFailed(false);
    setDecodeFailed(false);
  }, [url]);

  // Revoke on unmount too.
  useEffect(() => {
    return () => {
      if (filteredUrl) URL.revokeObjectURL(filteredUrl);
    };
  }, [filteredUrl]);

  async function toggleDespeckle() {
    if (despeckled) {
      setDespeckled(false);
      return;
    }
    // Filter once per frame, then the toggle is just a src swap.
    if (filteredUrl) {
      setDespeckled(true);
      return;
    }
    if (!url) return;

    /* Capture the url this run is filtering.
     *
     * despeckleImage is hundreds of milliseconds on a full frame, and the
     * operator can move to the next detection inside that window. The `[url]`
     * effect above has already reset the derived state by then, so a late
     * resolution would publish the PREVIOUS frame's filtered blob against the
     * new frame -- with the "Filtered view" badge asserting it belongs to the
     * frame on screen. That is a wrong image presented as evidence, which is
     * worse than no image, so a stale run revokes its own result and returns
     * without touching state. */
    const requestedUrl = url;
    setFiltering(true);
    setFilterFailed(false);
    try {
      const next = await despeckleImage(requestedUrl);
      if (requestedUrl !== urlRef.current) {
        URL.revokeObjectURL(next);
        return;
      }
      setFilteredUrl(next);
      setDespeckled(true);
    } catch {
      if (requestedUrl !== urlRef.current) return;
      setFilterFailed(true);
    } finally {
      if (requestedUrl === urlRef.current) setFiltering(false);
    }
  }

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
  const hasPolygon = Array.isArray(polygon) && polygon.length >= 3;

  return (
    <div className="relative inline-block max-w-full">
      <div className="absolute right-2 top-2 z-10 flex items-center gap-2">
        {zoom > 1 && (
          <button
            type="button"
            onClick={resetView}
            className="rounded-md border border-abyss-600 bg-abyss-900/85 px-2 py-1 text-xs text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
          >
            Reset
          </button>
        )}
        <button
          type="button"
          onClick={toggleDespeckle}
          disabled={filtering}
          aria-pressed={despeckled}
          title={
            despeckled
              ? "Show the unfiltered frame"
              : "Suppress speckle for viewing. Does not affect detection — the model has already scored the raw frame."
          }
          className="rounded-md border bg-abyss-900/85 px-2 py-1 text-xs transition disabled:opacity-60"
          style={
            despeckled
              ? { borderColor: DETECTION, color: DETECTION }
              : undefined
          }
        >
          {filtering ? "Filtering…" : despeckled ? "Despeckled" : "Despeckle"}
        </button>
      </div>

      {/* The filtered frame is a reading aid, not the record. Say so on screen
        * for as long as it is the thing being looked at. */}
      {despeckled && (
        <div
          className="absolute left-2 top-2 z-10 rounded-md border bg-abyss-900/85 px-2 py-1 text-[11px] uppercase tracking-[0.18em]"
          style={{ borderColor: DETECTION, color: DETECTION }}
        >
          Filtered view · 3×3 median + sharpen
        </div>
      )}

      {filterFailed && (
        <div className="absolute left-2 top-2 z-10 rounded-md border border-alert-high bg-abyss-900/85 px-2 py-1 text-[11px] text-alert-high">
          Despeckle failed — showing raw frame
        </div>
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
            src={despeckled && filteredUrl ? filteredUrl : url}
            onLoad={handleLoad}
            onError={() => setDecodeFailed(true)}
            alt="Sonar frame"
            className="block max-w-full select-none"
            draggable={false}
          />
          {/* With an outline, the box is demoted to a faint dashed frame: a
            * net is a thin diagonal chain, so its box is mostly seabed, and a
            * solid box would point the reviewer at the wrong pixels. */}
          {hasBox && scale && (
            <div
              className={
                hasPolygon
                  ? "pointer-events-none absolute border border-dashed opacity-50"
                  : "pointer-events-none absolute border-2 shadow-[0_0_0_1px_rgba(0,0,0,0.6)]"
              }
              style={{
                borderColor: DETECTION,
                left: (bbox!.x as number) * scale.x,
                top: (bbox!.y as number) * scale.y,
                width: (bbox!.w as number) * scale.x,
                height: (bbox!.h as number) * scale.y,
              }}
            />
          )}
          {hasPolygon && scale && imgRef.current && (
            <svg
              className="pointer-events-none absolute left-0 top-0"
              width={imgRef.current.clientWidth}
              height={imgRef.current.clientHeight}
              aria-label="Detected outline"
            >
              <polygon
                points={polygon!.map(([x, y]) => `${x * scale.x},${y * scale.y}`).join(" ")}
                fill={DETECTION}
                fillOpacity={0.18}
                stroke={DETECTION}
                strokeWidth={2}
                strokeLinejoin="round"
                // Constant on-screen width while zoomed, like the box border.
                vectorEffect="non-scaling-stroke"
                style={{ filter: "drop-shadow(0 0 1px rgba(0,0,0,0.8))" }}
              />
            </svg>
          )}
        </div>
      </div>
    </div>
  );
}
