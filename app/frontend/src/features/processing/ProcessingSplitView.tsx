"use client";

import clsx from "clsx";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiFetchBlob } from "@/api/client";
import { STAGE_DESCRIPTIONS } from "@/components/ProcessingProgress";
import type { Detection, ProcessingJob, RealtimeEvent, SurveyFrame } from "@/types";

import {
  createModel,
  DETECTION_STAGE,
  framesPassed,
  isStopped,
  RECENT_RUN_MS,
  isTerminal,
  newView,
  now,
  realStageIndex,
  SCENE_STAGES,
  type SceneDetection,
  settleAtEnd,
  surveyLength,
} from "./scene/model";
import type { SceneHandle } from "./scene/surveyScene";
import css from "./ProcessingSplitView.module.css";

/** Above this many frames only the frames with detections are fetched for the
 * seabed; the rest paint as neutral tiles. Hundreds of full-size frame images
 * would cost more than the picture is worth. */
const MAX_FRAME_IMAGES = 160;
const IMAGE_CONCURRENCY = 3;

interface LogLine { time: string; msg: string; cls?: "bad" | "hit" }
interface Toast { id: number; label: string; text: string; cls?: "bad" }

const STAGE_LOG: Record<string, string> = {
  QUEUED: "QUEUED — Waiting for a worker to pick this job up.",
  VALIDATING: "VALIDATING — File container and ping headers accepted.",
  DECODING: "DECODING — Pings split into frames.",
  PREPROCESSING: "PREPROCESSING — Speckle suppression and normalization applied before detection.",
  DETECTION: "DETECTION — Running the trained model over every frame.",
  VERIFICATION: "VERIFICATION — Dropout, edge-sliver and shadow checks.",
  CALIBRATION: "CALIBRATION — Temperature-scaled confidences.",
  GEOTAGGING: "GEOTAGGING — Slant-range corrected positions with error radius.",
  SAVING: "SAVING — Detections written.",
};

const BADGE: Record<string, [string, string]> = {
  QUEUED: ["QUEUED", css.idle],
  VALIDATING: ["PROCESSING", ""],
  PROCESSING: ["PROCESSING", ""],
  COMPLETED: ["COMPLETED", css.ok],
  PARTIAL: ["PARTIAL", css.warn],
  FAILED: ["FAILED", css.bad],
  CANCELLED: ["CANCELLED", css.warn],
};

const fmtS = (ms: number) => (ms / 1000).toFixed(1) + "s";
const clock = () => new Date().toLocaleTimeString();

export function ProcessingSplitView({
  job,
  surveyId,
  frames,
  detections,
  subscribe,
  onCancel,
  cancelling,
  onPresented,
}: {
  job: ProcessingJob;
  surveyId: string;
  frames: SurveyFrame[] | undefined;
  detections: Detection[];
  /** Raw realtime events from the page's single socket. */
  subscribe: (fn: (e: RealtimeEvent) => void) => () => void;
  onCancel: () => void;
  cancelling: boolean;
  /** True once the story has reached the end, so the page can hold back the
   *  results card until the scene has actually shown the run finishing. */
  onPresented?: (presented: boolean) => void;
}) {
  const model = useRef(createModel()).current;
  const refs = useSceneRefs();
  const [webgl, setWebgl] = useState(true);
  const [log, setLog] = useState<LogLine[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [scrubbing, setScrubbing] = useState(false);
  const [stageTimes, setStageTimes] = useState<(number | null)[]>([]);
  const [, setSecond] = useState(0);
  /** The rail follows the scene until the story ends, then shows the job. */
  const [presented, setPresented] = useState(false);
  const [snap, setSnap] = useState<Snapshot>(() => snapshot(model));

  useEffect(() => onPresented?.(presented), [presented, onPresented]);

  // The scene advances every animation frame; the rail samples it five times
  // a second, which is plenty for counters and a stepper.
  useEffect(() => {
    const id = setInterval(() => setSnap((s) => {
      const n = snapshot(model);
      return n.vIdx === s.vIdx && n.frames === s.frames && n.failed === s.failed && n.dets === s.dets && n.idle === s.idle ? s : n;
    }), 200);
    return () => clearInterval(id);
  }, [model]);

  const pushLog = useCallback((msg: string, cls?: LogLine["cls"]) => {
    setLog((l) => [{ time: clock(), msg, cls }, ...l].slice(0, 60));
  }, []);
  const toastId = useRef(0);
  const pushToast = useCallback((label: string, text: string, cls?: Toast["cls"]) => {
    const id = ++toastId.current;
    setToasts((t) => [...t, { id, label, text, cls }].slice(-3));
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3600);
  }, []);

  // ---- mount the scene once
  useEffect(() => {
    let handle: SceneHandle | null = null;
    let cancelled = false;
    import("./scene/surveyScene").then(({ mountSurveyScene }) => {
      if (cancelled || !refs.ready()) return;
      handle = mountSurveyScene(model, refs.elements());
      setWebgl(handle.webgl);
    });
    return () => {
      cancelled = true;
      handle?.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- callbacks the controller fires from the animation loop
  useEffect(() => {
    model.onContact = (d) =>
      pushToast("CONTACT", `${d.cls} · ${d.conf != null ? d.conf.toFixed(2) + " calibrated" : "unscored"} · frame ${d.frame + 1}/${model.N}`);
    model.onFinished = () => {
      setScrubbing(model.V.scrub);
      setSummaryOpen(true);
      setPresented(true);
      if (latestJob.current) pushLog(terminalLine(latestJob.current), latestJob.current.status === "COMPLETED" ? undefined : "bad");
    };
  }, [model, pushToast, pushLog]);

  const latestJob = useRef(job);
  latestJob.current = job;

  // ---- the log follows the scene: a stage is logged when the scene enters
  // it, a frame when the towfish has surveyed it
  const logged = useRef({ vIdx: -1, frames: 0 });
  useEffect(() => {
    if (presented || snap.idle) return;
    const L = logged.current;
    while (L.vIdx < Math.min(snap.vIdx, SCENE_STAGES.length - 1)) {
      L.vIdx++;
      pushLog(STAGE_LOG[SCENE_STAGES[L.vIdx].key]);
    }
    while (L.frames < snap.frames) {
      const i = L.frames++;
      if (model.failed.has(i)) {
        pushLog(`frame ${i + 1}/${model.N} FAILED — skipped.`, "bad");
      } else {
        const n = model.dets.filter((d) => d.frame === i).length;
        pushLog(`frame ${i + 1}/${model.N} processed · ${n} detection${n === 1 ? "" : "s"}`, n ? "hit" : undefined);
      }
    }
  }, [snap, presented, model, pushLog]);

  /** Start the story over from the vessel on station. */
  const restartStory = useCallback(() => {
    const stopped = model.job && isStopped(model.job.status);
    model.V = newView();
    if (stopped) Object.assign(model.V, { frozen: true, catchup: true, frozenAt: now() });
    model.dets.forEach((d) => (d.shownAt = 0));
    logged.current = { vIdx: -1, frames: 0 };
    setLog([]);
    setSummaryOpen(false);
    setScrubbing(false);
    setPresented(false);
    setSnap(snapshot(model));
  }, [model]);

  // ---- feed the real job into the model
  const jobIdRef = useRef<string | null>(null);
  const prevStageRef = useRef<{ idx: number; at: number; stage: string | null }>({ idx: -2, at: 0, stage: null });

  useEffect(() => {
    const t = now();
    const N = Math.max(1, job.frames_total || frames?.length || 1);
    const stageIdx = realStageIndex(job);
    const finished = job.frames_processed + job.frames_failed;

    if (jobIdRef.current !== job.id) {
      // A new run (or the first look at one): start the story over.
      jobIdRef.current = job.id;
      const openedFinished = isTerminal(job.status);
      model.N = N;
      model.S = surveyLength(N);
      model.frameM = model.S / N;
      model.V = newView();
      model.dets = [];
      model.painted = new Set();
      model.failed = new Set();
      model.version++;
      model.job = {
        status: job.status, stageIdx, framesDone: job.frames_processed, framesFailed: job.frames_failed,
        detCount: job.detections_found, lastFrameAt: finished ? t : 0, frameDur: 1300, stageAt: t,
      };
      prevStageRef.current = { idx: stageIdx, at: t, stage: job.stage };
      setStageTimes([]);
      setLog([]);
      logged.current = { vIdx: -1, frames: 0 };
      setSummaryOpen(false);
      setScrubbing(false);
      for (let i = 0; i < finished; i++) model.painted.add(i);
      const endedAt = job.completed_at ? new Date(job.completed_at).getTime() : 0;
      if (openedFinished && Date.now() - endedAt > RECENT_RUN_MS) {
        // An old run: show the end state. "Replay survey" plays the story.
        settleAtEnd(model);
        setScrubbing(model.V.scrub);
        setSummaryOpen(true);
        setPresented(true);
        pushLog(terminalLine(job), job.status === "COMPLETED" ? undefined : "bad");
      } else {
        // Live, or finished moments ago: play the story. The scene paces
        // itself stage by stage and the rail follows it.
        if (isStopped(job.status)) Object.assign(model.V, { frozen: true, catchup: true, frozenAt: t });
        setPresented(false);
      }
      setSnap(snapshot(model));
      return;
    }

    const j = model.job!;
    // Stage transitions, as observed here (the backend keeps no stage history).
    const prev = prevStageRef.current;
    if (stageIdx !== prev.idx) {
      setStageTimes((times) => {
        const next = [...times];
        if (prev.idx >= 0 && prev.idx < SCENE_STAGES.length) next[prev.idx] = t - prev.at;
        for (let k = Math.max(0, prev.idx + 1); k < Math.min(stageIdx, SCENE_STAGES.length); k++) next[k] ??= 0;
        return next;
      });
      prevStageRef.current = { idx: stageIdx, at: t, stage: job.stage };
      j.stageAt = t;
    }
    if (finished > j.framesDone + j.framesFailed) {
      if (j.lastFrameAt) j.frameDur = j.frameDur * 0.6 + ((t - j.lastFrameAt) / (finished - j.framesDone - j.framesFailed)) * 0.4;
      j.lastFrameAt = t;
      for (let i = 0; i < finished; i++) if (!model.failed.has(i)) model.painted.add(i);
    }
    const becameTerminal = isTerminal(job.status) && !isTerminal(j.status);
    Object.assign(j, {
      status: job.status, stageIdx, framesDone: job.frames_processed, framesFailed: job.frames_failed, detCount: job.detections_found,
    });
    if (becameTerminal) {
      if (isStopped(job.status)) {
        pushToast(job.status === "FAILED" ? "JOB FAILED" : "CANCELLED",
          job.status === "FAILED" ? job.error_summary ?? "The run stopped." : "Towfish recovered · partial results kept", "bad");
        Object.assign(model.V, { frozen: true, catchup: true, frozenAt: t, vEnter: t });
      }
    }
  }, [job, frames, model, pushLog, pushToast]);

  // ---- per-frame detail from the socket: which frame, and did it fail
  useEffect(
    () =>
      subscribe((e) => {
        if (e.job_id && e.job_id !== jobIdRef.current) return;
        const idx = typeof e.frame_index === "number" ? e.frame_index : null;
        // Logged later, when the towfish reaches the frame (see above).
        if (e.event === "frame.processed" && idx !== null) {
          if (e.failed) {
            model.failed.add(idx);
            model.painted.delete(idx);
          } else {
            model.painted.add(idx);
          }
        }
      }),
    [subscribe, model]
  );

  // ---- detections → markers (real boxes, real confidences, real error radii)
  const frameIndex = useMemo(() => new Map((frames ?? []).map((f) => [f.id, f.index])), [frames]);
  const sceneDets = useMemo(() => {
    const out: SceneDetection[] = [];
    for (const d of detections) {
      // A review candidate is not a claim, so it is not drawn as a contact.
      if (d.review_only) continue;
      const frame = frameIndex.get(d.frame_id);
      if (frame === undefined) continue;
      out.push({
        id: d.id, ref: d.detection_ref, frame, cls: d.detection_class, conf: d.calibrated_confidence, unc: d.uncertainty,
        err: d.position_error_m,
        bbox: { x: d.bbox.x ?? 0, y: d.bbox.y ?? 0, w: d.bbox.w ?? 0, h: d.bbox.h ?? 0 },
        review: d.review_status, shownAt: 0,
      });
    }
    return out.sort((a, b) => a.frame - b.frame || a.bbox.y - b.bbox.y);
  }, [detections, frameIndex]);
  useEffect(() => {
    // The scene keeps its own copies: shownAt is animation state.
    const prev = new Map(model.dets.map((d) => [d.id, d.shownAt]));
    const next = sceneDets.map((d) => ({ ...d, shownAt: prev.get(d.id) ?? 0 }));
    // Opened on a finished run: contacts are already found, so show them.
    if (model.V.done || model.V.retrieve >= 1) {
      const t = now();
      for (const d of next) if (!d.shownAt && (model.V.done || d.frame < model.painted.size)) d.shownAt = t - 10000;
    }
    model.dets = next;
  }, [sceneDets, model]);

  // ---- the survey's real frame images, fetched as they are needed
  const requested = useRef(new Set<number>());
  const objectUrls = useRef<string[]>([]);
  const queue = useRef<number[]>([]);
  const inFlight = useRef(0);
  useEffect(() => {
    if (!frames?.length) return;
    const wanted = new Set<number>(model.dets.map((d) => d.frame));
    if (frames.length <= MAX_FRAME_IMAGES) for (const i of model.painted) wanted.add(i);
    else for (const i of model.painted) if (!wanted.has(i)) model.imageMissing.add(i);
    for (const i of [...wanted].sort((a, b) => a - b)) {
      if (!requested.current.has(i) && frames[i]) { requested.current.add(i); queue.current.push(i); }
    }
    const pump = () => {
      while (inFlight.current < IMAGE_CONCURRENCY && queue.current.length) {
        const i = queue.current.shift()!;
        inFlight.current++;
        apiFetchBlob(`/frames/${frames[i].id}/image`)
          .then((blob) => new Promise<void>((resolve) => {
            const url = URL.createObjectURL(blob);
            objectUrls.current.push(url);
            const im = new Image();
            im.onload = () => { model.images.set(i, im); resolve(); };
            im.onerror = () => { model.imageMissing.add(i); resolve(); };
            im.src = url;
          }))
          .catch(() => { model.imageMissing.add(i); })
          .finally(() => { inFlight.current--; pump(); });
      }
    };
    pump();
  }, [frames, job, detections, model]);
  useEffect(() => () => objectUrls.current.forEach((u) => URL.revokeObjectURL(u)), []);

  // ---- rail clock
  const running = !isTerminal(job.status);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setSecond((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [running]);

  // ---- Escape hides the summary
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setSummaryOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // ---- rail numbers
  // Until the story ends the rail shows what the SCENE has reached: the stage
  // it is playing, the frames the towfish has surveyed, the contacts it has
  // passed. The scene never runs ahead of the job, so none of these can claim
  // more than the run has really done. Once the story ends, the job's own
  // final numbers take over.
  const N = Math.max(1, job.frames_total || frames?.length || 1);
  const done = job.frames_processed, failed = job.frames_failed;
  const shownDone = presented ? done : snap.frames - snap.failed;
  const shownFailed = presented ? failed : snap.failed;
  const shownDets = presented ? job.detections_found : snap.dets;
  const remaining = Math.max(0, N - shownDone - shownFailed);
  const pct = Math.floor(((shownDone + shownFailed) / N) * 100);
  const startMs = job.started_at ? new Date(job.started_at).getTime() : null;
  const endMs = job.completed_at ? new Date(job.completed_at).getTime() : Date.now();
  const elapsed = startMs ? Math.max(0, endMs - startMs) : null;
  const fps = elapsed ? (done + failed) / Math.max(0.5, elapsed / 1000) : 0;
  const realFinished = isTerminal(job.status);
  const railStatus = presented ? job.status : snap.idle && !realFinished ? job.status : "PROCESSING";
  const barColor =
    railStatus === "FAILED" ? "var(--bad)" : railStatus === "CANCELLED" || railStatus === "PARTIAL" ? "var(--warn)" : railStatus === "COMPLETED" ? "var(--ok)" : "var(--imperial)";
  const stageIdx = presented ? realStageIndex(job) : snap.idle && !realFinished ? -1 : snap.vIdx;
  const [badgeText, badgeCls] = BADGE[railStatus] ?? [railStatus, ""];
  // The run itself is already over and the scene is still telling it: say so.
  const playingBack = realFinished && !presented;
  const modelVersion = detections.find((d) => d.model_version)?.model_version;
  const summaryDets = sceneDets.length ? sceneDets : null;
  const anyNoFix = sceneDets.some((d) => d.err == null);

  return (
    <div className={css.split}>
      <section
        ref={refs.card}
        className={clsx(css.sceneCard, scrubbing && css.scrubbing, summaryOpen && css.summaryOpen)}
        aria-label="Live survey visualisation"
      >
        <canvas ref={refs.canvas} className={css.gl} />
        {!webgl && (
          <div className={css.fallback}>
            3D view unavailable (WebGL could not start). Processing is unaffected — the details are on the right.
          </div>
        )}
        <div ref={refs.labels} className={css.labels} />
        <div className={css.hudCap}>
          <div ref={refs.capK} className={css.k}>READY</div>
          <div ref={refs.capT} className={css.t}>Awaiting job</div>
          <div ref={refs.capS} className={css.s} />
          <div ref={refs.capLag} className={css.lag} />
        </div>
        <div className={css.hudRead} aria-hidden>
          <div ref={refs.sonarLed} className={css.sonar} data-on="0"><i /><b ref={refs.sonarText}>SONAR IDLE</b></div>
          <div><span>DEPTH</span><b ref={refs.rDepth}>0.0 m</b></div>
          <div><span>LAYBACK</span><b ref={refs.rLay}>0.0 m</b></div>
          <div><span>ALTITUDE</span><b ref={refs.rAlt}>— m</b></div>
          <div><span>SPEED</span><b ref={refs.rSpd}>0.0 kn</b></div>
          <div><span>PING</span><b ref={refs.rPing}>—</b></div>
        </div>
        <div className={css.wf} aria-hidden>
          <div className={css.h}><span>WATERFALL</span><span ref={refs.wfFrame}>—</span></div>
          <canvas ref={refs.wf} width={160} height={200} />
          <div className={css.f}>survey frames · model boxes</div>
        </div>
        <div className={css.toasts} aria-live="polite">
          {toasts.map((t) => (
            <div key={t.id} className={clsx(css.toast, t.cls === "bad" && css.bad)}>
              <b>{t.label}</b>{t.text}
            </div>
          ))}
        </div>

        {summaryOpen && (
          <div className={css.summary} role="dialog" aria-label="Run summary">
            <div className={css.top}>
              <div>
                <h3 className={clsx(job.status === "FAILED" && css.bad, (job.status === "CANCELLED" || job.status === "PARTIAL") && css.warn)}>
                  {job.status === "FAILED" ? "Processing failed" : job.status === "CANCELLED" ? "Processing cancelled" : job.status === "PARTIAL" ? "Survey processed · partial" : "Survey processed"}
                </h3>
                <div className={css.meta}>
                  {[
                    `${done}/${N} frames`,
                    `${job.detections_found} detection${job.detections_found === 1 ? "" : "s"}`,
                    `${failed} failed`,
                    ...(elapsed != null ? [fmtS(elapsed)] : []),
                    ...(modelVersion ? [`model ${modelVersion}`] : []),
                  ].map((x, i) => (
                    <span key={i}>{i > 0 && " · "}{x}</span>
                  ))}
                </div>
              </div>
              <button className={css.x} onClick={() => setSummaryOpen(false)} aria-label="Hide summary">×</button>
            </div>
            {summaryDets ? (
              <>
                <div className={css.tbl}>
                  <table>
                    <thead>
                      <tr><th>ID</th><th>CLASS</th><th>CONF.</th><th>UNCERT.</th><th>FRAME</th><th>± POS.</th><th>REVIEW</th></tr>
                    </thead>
                    <tbody>
                      {summaryDets.map((d) => (
                        <tr key={d.id}>
                          <td><Link href={`/app/detections/${d.id}`}>{d.ref}</Link></td>
                          <td><span className={clsx(css.pill, css.debris)}>{d.cls}</span></td>
                          <td>{d.conf != null ? d.conf.toFixed(2) : "—"}</td>
                          <td>{d.unc ?? "—"}</td>
                          <td>{d.frame + 1}/{N}</td>
                          <td>{d.err != null ? `${d.err.toFixed(1)} m` : "—"}</td>
                          <td><span className={css.pill}>{d.review.replace(/_/g, " ")}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {anyNoFix && <div className={css.meta} style={{ marginTop: 6 }}>— no navigation fix: position not derived, so none is shown</div>}
              </>
            ) : (
              <div className={css.empty}>
                {isStopped(job.status)
                  ? job.error_summary ?? `The run stopped after ${done} of ${N} frames. Frames already saved are kept.`
                  : `No targets found in the surveyed frames. That is a result, not an error: no contact met the reporting floor in ${done} processed frame${done === 1 ? "" : "s"}.`}
              </div>
            )}
            <div className={css.btns}>
              <Link className={clsx(css.btn, css.solid)} href={`/app/review?survey_id=${surveyId}`}>Open Review Queue</Link>
              <Link className={css.btn} href={`/app/map?survey_id=${surveyId}`}>Open GIS Map</Link>
              <button className={css.btn} onClick={restartStory}>↺ Replay survey</button>
            </div>
          </div>
        )}

        {scrubbing && (
          <div className={css.scrubbar}>
            <span>SURVEY REPLAY</span>
            <input
              ref={refs.scrub}
              type="range" min={0} max={1000} defaultValue={1000} aria-label="Survey replay position"
              onInput={(e) => {
                model.V.replay = null;
                model.V.p = Number((e.target as HTMLInputElement).value) / 1000;
              }}
            />
            <span ref={refs.scrubValue}>100%</span>
          </div>
        )}
      </section>

      <aside className={css.rail} aria-label="Processing details">
        <div className={css.sec}>
          <div className={css.statusRow}>
            <span className={clsx(css.badge, badgeCls)}>{badgeText}</span>
            <span className={css.pct}>{pct}%</span>
          </div>
          <div className={css.bar}><i style={{ width: `${pct}%`, background: barColor }} /></div>
          <div className={css.rates}>
            <span>{realFinished ? "Run took" : "Elapsed"} {elapsed != null ? (realFinished ? fmtS(elapsed) : `${Math.floor(elapsed / 1000)}s`) : "—"}</span>
            <span>{fps.toFixed(1)} frames/s</span>
            <span>ETA {running && fps > 0 ? `~${Math.max(1, Math.round(Math.max(0, N - done - failed) / Math.max(fps, 0.3)))}s` : "—"}</span>
          </div>
          {playingBack && (
            <p className={css.playback}>
              The run finished in {elapsed != null ? fmtS(elapsed) : "moments"}. The scene is playing it back step by step; the
              counts below follow the towfish.
            </p>
          )}
        </div>
        <div className={css.sec}>
          <ul className={css.steps}>
            {SCENE_STAGES.map((s, i) => {
              let c = "";
              if (stageIdx > i || (presented && (job.status === "COMPLETED" || job.status === "PARTIAL"))) c = css.done;
              else if (stageIdx === i) c = presented && isStopped(job.status) ? css.failed : css.active;
              // Real stage durations, as this page observed them; shown once
              // the story has caught up so they never contradict the scene.
              const tm = presented || !realFinished ? stageTimes[i] ?? (stageIdx === i && running ? now() - prevStageRef.current.at : null) : null;
              return (
                <li key={s.key} className={c}>
                  <span className={css.dot} />
                  <div><div className={css.n}>{s.key}</div><div className={css.d}>{STAGE_DESCRIPTIONS[s.key]}</div></div>
                  <span className={css.tm}>{tm != null ? fmtS(tm) : ""}</span>
                </li>
              );
            })}
          </ul>
        </div>
        <div className={css.sec}>
          <div className={css.fbar}>
            <i style={{ background: "var(--imperial)", width: `${(shownDone / N) * 100}%` }} />
            <i style={{ background: "var(--bad)", width: `${(shownFailed / N) * 100}%` }} />
          </div>
          <div className={css.flegend}>
            <span>{shownDone} processed</span><span className={css.f}>{shownFailed} failed</span><span className={css.r}>{remaining} remaining</span>
          </div>
        </div>
        <div className={css.sec}>
          <div className={css.kpis}>
            <div className={css.kpi}><b>{shownDone}</b><span>FRAMES PROCESSED</span></div>
            <div className={css.kpi}><b>{shownFailed}</b><span>FRAMES FAILED</span></div>
            <div className={css.kpi}><b>{shownDets}</b><span>DETECTIONS</span></div>
            <div className={css.kpi}><b>{N}</b><span>FRAMES TOTAL</span></div>
          </div>
        </div>
        <div className={clsx(css.sec, css.logSec)}>
          <div className={css.log}>
            {log.map((l, i) => (
              <div key={i} className={l.cls ? css[l.cls] : undefined}>{l.time}  {l.msg}</div>
            ))}
          </div>
        </div>
        {running && (
          <div className={css.foot}>
            <button className={css.cancel} onClick={onCancel} disabled={cancelling}>
              {cancelling ? "Cancelling…" : "Cancel Processing"}
            </button>
          </div>
        )}
      </aside>
    </div>
  );
}

function terminalLine(job: ProcessingJob) {
  if (job.status === "FAILED") return `FAILED — ${job.error_summary ?? "the run stopped."}`;
  if (job.status === "CANCELLED") return "CANCELLED — Stopped by operator. Frames already saved are kept.";
  return `${job.status} — ${job.frames_processed} frames, ${job.detections_found} detections, ${job.frames_failed} failed.`;
}

/** Refs for every element the animation loop writes to directly. */
function useSceneRefs() {
  const r = {
    card: useRef<HTMLElement>(null), canvas: useRef<HTMLCanvasElement>(null), labels: useRef<HTMLDivElement>(null),
    wf: useRef<HTMLCanvasElement>(null), wfFrame: useRef<HTMLSpanElement>(null),
    capK: useRef<HTMLDivElement>(null), capT: useRef<HTMLDivElement>(null), capS: useRef<HTMLDivElement>(null), capLag: useRef<HTMLDivElement>(null),
    sonarLed: useRef<HTMLDivElement>(null), sonarText: useRef<HTMLElement>(null),
    rDepth: useRef<HTMLElement>(null), rLay: useRef<HTMLElement>(null), rAlt: useRef<HTMLElement>(null), rSpd: useRef<HTMLElement>(null), rPing: useRef<HTMLElement>(null),
    scrub: useRef<HTMLInputElement>(null), scrubValue: useRef<HTMLSpanElement>(null),
  };
  return {
    ...r,
    ready: () => Boolean(r.card.current && r.canvas.current && r.labels.current && r.wf.current),
    elements: () => {
      return {
        card: r.card.current!, canvas: r.canvas.current!, labels: r.labels.current!,
        waterfall: r.wf.current!, waterfallFrame: r.wfFrame.current!,
        capK: r.capK.current!, capT: r.capT.current!, capS: r.capS.current!, capLag: r.capLag.current!,
        sonarLed: r.sonarLed.current!, sonarText: r.sonarText.current!,
        rDepth: r.rDepth.current!, rLay: r.rLay.current!, rAlt: r.rAlt.current!, rSpd: r.rSpd.current!, rPing: r.rPing.current!,
        scrub: () => r.scrub.current, scrubValue: () => r.scrubValue.current,
      };
    },
  };
}

interface Snapshot {
  /** Stage the scene is playing (8 = past the last). */
  vIdx: number;
  /** Frames the towfish has surveyed, and how many of those failed. */
  frames: number;
  failed: number;
  /** Contacts the towfish has passed. */
  dets: number;
  /** No run in the scene yet, or the scene has not begun moving. */
  idle: boolean;
}

function snapshot(m: ReturnType<typeof createModel>): Snapshot {
  if (!m.job) return { vIdx: -1, frames: 0, failed: 0, dets: 0, idle: true };
  const frames = m.V.vIdx > DETECTION_STAGE ? m.N : framesPassed(m);
  let failed = 0;
  for (const i of m.failed) if (i < frames) failed++;
  return {
    vIdx: m.V.vIdx,
    frames,
    failed,
    dets: m.dets.filter((d) => d.shownAt > 0).length,
    idle: m.job.status === "QUEUED" && m.V.p === 0,
  };
}
