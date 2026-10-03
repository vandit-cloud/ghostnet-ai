"use client";

import { useCallback, useState } from "react";

import { RequireAuth } from "@/components/RequireAuth";
import { useDetections } from "@/features/detections/hooks";
import { useLatestJob, useSurveyFrames } from "@/features/processing/hooks";
import { ProcessingSplitView } from "@/features/processing/ProcessingSplitView";
import { DEFAULT_SONAR_PALETTE, SONAR_PALETTES, type SonarPaletteName } from "@/features/processing/scene/surveyScene";
import { useSurveys } from "@/features/surveys/hooks";

/** Sandbox for choosing the processing scene's sonar colours -- NOT a product route.
 *
 * The processing page paints the survey's real frames onto the seabed and into
 * the waterfall through a colour map, viridis today. This page mounts the same
 * scene over a real processed survey and switches the map live, so a palette
 * can be judged on actual sonar rather than a swatch. Nothing here changes
 * the processing page: it never passes a palette, so it keeps DEFAULT_SONAR_PALETTE.
 *
 * Press "↺ Replay survey" in the summary (or "Run summary" to reopen it) to
 * watch the returns being painted in the chosen colours.
 */
export default function SonarPaletteLab() {
  return (
    <RequireAuth>
      <Lab />
    </RequireAuth>
  );
}

const NO_EVENTS = () => () => {};

function Lab() {
  const { data: surveys } = useSurveys(1, 100);
  const [picked, setPicked] = useState<string | undefined>();
  const [palette, setPalette] = useState<SonarPaletteName>(DEFAULT_SONAR_PALETTE);
  const processed = (surveys?.items ?? []).filter((s) => s.detection_count > 0 || s.status === "COMPLETED");
  const surveyId = picked ?? processed[0]?.id;

  const { data: job } = useLatestJob(surveyId);
  const { data: frames } = useSurveyFrames(job ? surveyId : undefined);
  const { data: detections } = useDetections({ survey_id: surveyId, page_size: 200 }, { enabled: Boolean(job) });
  const noop = useCallback(() => {}, []);

  return (
    <main className="min-h-screen bg-paper p-6 text-ink">
      <div className="mx-auto max-w-[1500px] space-y-4">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-ink-3">Lab · not a product route</p>
            <h1 className="font-display text-3xl font-semibold text-imperial">Sonar palette</h1>
            <p className="mt-1 max-w-2xl text-sm text-ink-2">
              Compare colour maps for the returns painted on the seabed and in the waterfall. The processing page uses
              the one marked current; picking another here previews it without changing the processing page.
            </p>
          </div>
          <label className="text-xs uppercase tracking-wide text-ink-3">
            Survey
            <select
              className="ml-2 border border-abyss-600 bg-white px-2 py-1 text-sm normal-case tracking-normal text-ink"
              value={surveyId ?? ""}
              onChange={(e) => setPicked(e.target.value)}
            >
              {processed.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        </header>

        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Sonar palette">
          {(Object.keys(SONAR_PALETTES) as SonarPaletteName[]).map((key) => {
            const p = SONAR_PALETTES[key];
            const gradient = `linear-gradient(90deg, ${p.stops.map(([at, [r, g, b]]) => `rgb(${r},${g},${b}) ${at * 100}%`).join(", ")})`;
            return (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={palette === key}
                onClick={() => setPalette(key)}
                className={`flex items-center gap-3 border px-3 py-2 text-sm ${
                  palette === key ? "border-imperial bg-imperial text-paper" : "border-abyss-600 bg-white text-ink"
                }`}
              >
                <span className="h-4 w-28 border border-black/20" style={{ background: gradient }} />
                <span>{p.label}</span>
                <span className="h-3 w-3 border border-black/30" style={{ background: p.box }} title="detection box colour" />
              </button>
            );
          })}
        </div>

        {!surveyId ? (
          <p className="text-sm text-ink-3">No processed survey yet. Process one, then come back.</p>
        ) : !job ? (
          <p className="text-sm text-ink-3">Loading the survey&apos;s last run…</p>
        ) : (
          <ProcessingSplitView
            key={surveyId}
            job={job}
            surveyId={surveyId}
            frames={frames}
            detections={detections?.items ?? []}
            subscribe={NO_EVENTS}
            onCancel={noop}
            cancelling
            palette={palette}
          />
        )}
      </div>
    </main>
  );
}
