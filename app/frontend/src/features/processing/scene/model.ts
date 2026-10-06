/* =============================================================================
 * The processing page's "virtual scroll".
 *
 * The landing hero's scene is a pure function of one number, scroll progress
 * p in [0, 1]. Here the JOB drives p instead of the scroll bar, so the vessel
 * arrives, deploys the towfish, and surveys the line as the run advances.
 *
 * Two rules keep it honest:
 *   - p trails the job and never leads it. The only allowance is a creep inside
 *     the frame currently being processed, capped short of the next frame.
 *   - Each stage is held long enough to read. When the scene falls behind the
 *     live job it says so in the HUD rather than skipping.
 *
 * The model is a plain mutable object shared by three writers/readers: the
 * React view (feeds it the real job, frames and detections), the controller
 * below (advances p every animation frame) and the three.js scene (draws it).
 * React state would re-render 60 times a second; a shared object does not.
 * ========================================================================== */

import type { JobStage, ProcessingJob } from "@/types";

export interface StageDef {
  key: JobStage;
  /** The slice of p this stage owns. */
  p: [number, number];
  /** Minimum seconds on screen, so a 50 ms backend stage is still readable. */
  min: number;
  cap: string;
  sub: string;
}

// `min` is only what a caption needs to be read. The backend's validate,
// decode and preprocess stages take ~50 ms each, so anything longer here is
// the scene inventing time: these used to hold 1.0 / 1.0 / 3.2 s, and with
// detection pinned to 0.75 s a frame a one-image run played for ~13 s and a
// 40-frame run for ~30 s whatever the model actually took.
export const SCENE_STAGES: StageDef[] = [
  { key: "VALIDATING", p: [0.0, 0.07], min: 0.7, cap: "Vessel on station", sub: "Reading file headers · towfish stowed" },
  { key: "DECODING", p: [0.07, 0.14], min: 0.7, cap: "Decoding pings", sub: "Waterfall assembled from port + starboard" },
  { key: "PREPROCESSING", p: [0.14, 0.42], min: 1.4, cap: "Deploying towfish", sub: "Winch paying out · frames being normalized" },
  { key: "DETECTION", p: [0.42, 0.86], min: 0, cap: "Searching the seabed", sub: "" },
  { key: "VERIFICATION", p: [0.86, 0.9], min: 0.6, cap: "Verifying contacts", sub: "Dropout · edge-sliver · shadow evidence" },
  { key: "CALIBRATION", p: [0.9, 0.94], min: 0.6, cap: "Calibrating confidence", sub: "Raw scores → calibrated probability" },
  { key: "GEOTAGGING", p: [0.94, 0.97], min: 0.6, cap: "Geotagging", sub: "Slant-range corrected · error radius attached" },
  { key: "SAVING", p: [0.97, 1.0], min: 0.6, cap: "Saving results", sub: "Detections written · review queue updated" },
];
export const DETECTION_STAGE = 3;

export type Terminal = "COMPLETED" | "PARTIAL" | "FAILED" | "CANCELLED";
export const isTerminal = (s: string): s is Terminal =>
  s === "COMPLETED" || s === "PARTIAL" || s === "FAILED" || s === "CANCELLED";
export const isStopped = (s: string) => s === "FAILED" || s === "CANCELLED";

export interface SceneDetection {
  id: string;
  ref: string;
  frame: number;
  cls: string;
  conf: number | null;
  unc: string | null;
  /** Real position_error_m, or null when the run could not derive a position. */
  err: number | null;
  /** Frame-pixel box; normalised against the frame's real size when drawn. */
  bbox: { x: number; y: number; w: number; h: number };
  review: string;
  /** Animation time the towfish reached it; 0 = not yet on screen. */
  shownAt: number;
}

export interface SceneJobState {
  status: ProcessingJob["status"];
  /** 0..8 in SCENE_STAGES terms; -1 queued, 8 = all done. */
  stageIdx: number;
  framesDone: number;
  framesFailed: number;
  detCount: number;
  lastFrameAt: number;
  /** Smoothed seconds-per-frame, in ms. */
  frameDur: number;
  stageAt: number;
  /** How long the real run took, started_at -> completed_at, in ms; 0 while it
   *  is still running. Paces the detection stage when a finished run is
   *  played back, so the replay lasts as long as the model really worked. */
  runMs: number;
}

export interface SceneView {
  p: number;
  vIdx: number;
  vEnter: number;
  done: boolean;
  doneAt: number;
  frozen: boolean;
  catchup: boolean;
  frozenAt: number;
  retrieve: number;
  scrub: boolean;
  replay: { t0: number; dur: number } | null;
}

export interface SceneModel {
  /** Frames in the run. */
  N: number;
  /** Along-track metres the survey line represents (illustrative scale). */
  S: number;
  frameM: number;
  job: SceneJobState | null;
  V: SceneView;
  dets: SceneDetection[];
  painted: Set<number>;
  failed: Set<number>;
  images: Map<number, HTMLImageElement>;
  /** Frames whose image could not be fetched: painted as a neutral tile. */
  imageMissing: Set<number>;
  quality: 0 | 1;
  /** Bumped when the run changes, so the scene rebuilds its strip. */
  version: number;
  modelsReady: number;
  /** Notified when a contact first appears (toast) and when the survey
   *  animation finishes (summary). Set by the React view. */
  onContact?: (d: SceneDetection) => void;
  onFinished?: () => void;
}

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

export function newView(): SceneView {
  return {
    p: 0, vIdx: 0, vEnter: now(), done: false, doneAt: 0, frozen: false, catchup: false,
    frozenAt: 0, retrieve: 0, scrub: false, replay: null,
  };
}

export function createModel(): SceneModel {
  return {
    N: 1, S: 180, frameM: 30, job: null, V: newView(), dets: [],
    painted: new Set(), failed: new Set(), images: new Map(), imageMissing: new Set(),
    quality: 1, version: 0, modelsReady: 0,
  };
}

export const now = () => performance.now();

/** Survey length for N frames. Thirty metres a frame reads well for a short
 * line; a long survey is compressed so the vessel is not a speck at the end. */
export function surveyLength(N: number) {
  return Math.min(480, Math.max(180, N * 30));
}

/** Where the real job is, in SCENE_STAGES terms.
 *
 * The backend runs DETECTION → SAVING once PER FRAME, so its `stage` flickers
 * through all five while frames remain. For the story, everything until the
 * last frame is "searching the seabed"; only after it do verification through
 * saving play out. */
export function realStageIndex(job: ProcessingJob): number {
  if (job.status === "COMPLETED" || job.status === "PARTIAL" || job.stage === "DONE") return SCENE_STAGES.length;
  if (job.stage === "QUEUED") return -1;
  const idx = SCENE_STAGES.findIndex((s) => s.key === job.stage);
  const finished = job.frames_processed + job.frames_failed;
  if (idx >= DETECTION_STAGE && finished < job.frames_total) return DETECTION_STAGE;
  return idx;
}

/** How far through visual stage vIdx the real job has got, 0..1. */
function realFraction(m: SceneModel, vIdx: number, t: number): number {
  const j = m.job!;
  if (j.stageIdx > vIdx) return 1;
  if (j.stageIdx < vIdx) return 0;
  const stopped = isTerminal(j.status);
  if (vIdx === DETECTION_STAGE) {
    const done = j.framesDone + j.framesFailed;
    const since = j.lastFrameAt ? t - j.lastFrameAt : t - j.stageAt;
    // The frame being processed right now creeps forward, never past 85 %.
    const creep = stopped ? 0 : Math.min(0.85, (since / Math.max(300, j.frameDur)) * 0.85);
    return clamp01((done + creep) / m.N);
  }
  return stopped ? 0 : 0.85 * (1 - Math.exp(-(t - j.stageAt) / 1400));
}

/** Detection is never shorter than this on screen: long enough to see the
 *  towfish pass over a one-image survey and the contact appear. */
export const DETECTION_MIN_S = 2.5;
/** A long run is not replayed in full: past this it is compressed. */
export const DETECTION_REPLAY_MAX_S = 45;

function stageMin(m: SceneModel, vIdx: number) {
  if (vIdx !== DETECTION_STAGE) return SCENE_STAGES[vIdx].min;
  // While the job runs, realFraction() already holds the scene to the frames
  // actually finished, so only the floor applies. Once it has finished, the
  // replay takes as long as the run did -- it used to take 0.75 s a frame
  // regardless, so a 40-frame run scored in 14 s still played for 30 s.
  const run = (m.job?.runMs ?? 0) / 1000;
  return Math.min(DETECTION_REPLAY_MAX_S, Math.max(DETECTION_MIN_S, run));
}

/** How many frames the towfish has finished surveying in the scene. The rail
 * counts frames by this, so the numbers on the right move with the picture on
 * the left instead of jumping to the job's final count. Never more than the
 * real job has finished, because p never leads the job. */
export function framesPassed(m: SceneModel): number {
  const [a, z] = SCENE_STAGES[DETECTION_STAGE].p;
  return Math.max(0, Math.min(m.N, Math.floor(((m.V.p - a) / (z - a)) * m.N + 1e-6)));
}

/** A finished run opened within this long plays its story rather than
 * jumping to the end: someone who just started it on the survey page and
 * came here should still see it run. */
export const RECENT_RUN_MS = 3 * 60 * 1000;

/** Jump straight to the end state: used when the page opens on a job that had
 * already finished, so nobody sits through a replay they did not ask for. */
export function settleAtEnd(m: SceneModel) {
  const j = m.job;
  if (!j) return;
  const V = m.V;
  const t = now();
  if (isStopped(j.status)) {
    const vIdx = Math.max(0, Math.min(j.stageIdx, SCENE_STAGES.length - 1));
    const st = SCENE_STAGES[vIdx];
    const f = vIdx === DETECTION_STAGE ? clamp01((j.framesDone + j.framesFailed) / m.N) : 0;
    Object.assign(V, { vIdx, p: st.p[0] + (st.p[1] - st.p[0]) * f, frozen: true, catchup: false, frozenAt: t - 4000, retrieve: 1 });
  } else {
    Object.assign(V, { vIdx: SCENE_STAGES.length, p: 1, done: true, doneAt: t - 5000, scrub: true });
  }
  for (const d of m.dets) if (V.p >= contactP(m, d) - 0.0005) d.shownAt = t - 10000;
}

/** Frame-pixel size, from the loaded image; 640 until it arrives (frames are
 * decoded to 640 × 640). */
export function frameSize(m: SceneModel, frame: number) {
  const im = m.images.get(frame);
  return im && im.naturalWidth ? { w: im.naturalWidth, h: im.naturalHeight } : { w: 640, h: 640 };
}

/** Where along the line (0..1 of the frame) and across it (0..1) a contact sits. */
export function contactUV(m: SceneModel, d: SceneDetection) {
  const { w, h } = frameSize(m, d.frame);
  return { xc: clamp01((d.bbox.x + d.bbox.w / 2) / w), yc: clamp01((d.bbox.y + d.bbox.h / 2) / h) };
}

/** The p at which the towfish passes over a contact. */
export function contactP(m: SceneModel, d: SceneDetection) {
  const [a, z] = SCENE_STAGES[DETECTION_STAGE].p;
  return a + ((z - a) * (d.frame + contactUV(m, d).yc)) / m.N;
}

/** Advance p by one animation frame. `dt` is wall-clock seconds (capped), so
 * the story runs at the same pace on 12 fps as on 60. */
export function tick(m: SceneModel, dt: number) {
  const j = m.job;
  if (!j) return;
  const V = m.V;
  const t = now();
  // How fast p closes on the stage target. At 4/s each stage overran its
  // minimum by ~0.5 s waiting for p to settle within 0.3 % of the slice end, so
  // a one-image run's three 50 ms setup stages filled ~5 s; 7/s halves the
  // lag and stays smooth, since the target itself moves continuously.
  const ease = 1 - Math.exp(-dt * 7);

  if (V.scrub) {
    if (V.replay) {
      V.p = clamp01((t - V.replay.t0) / V.replay.dur);
      if (V.p >= 1) V.replay = null;
    }
  } else if (V.frozen && !V.catchup) {
    const was = V.retrieve;
    V.retrieve = clamp01((t - V.frozenAt) / 3200);
    if (was < 1 && V.retrieve >= 1) m.onFinished?.();
  } else if (V.frozen) {
    // Failed or cancelled: first reach the point the job REALLY got to, so
    // contacts found before the stop still appear, then recover the towfish.
    const st = SCENE_STAGES[Math.min(V.vIdx, SCENE_STAGES.length - 1)];
    const inStage = (t - V.vEnter) / 1000;
    const f = Math.min(realFraction(m, V.vIdx, t), inStage / Math.max(0.6, stageMin(m, V.vIdx) * 0.5));
    const target = st.p[0] + (st.p[1] - st.p[0]) * f;
    V.p += Math.max(0, target - V.p) * ease;
    if (j.stageIdx > V.vIdx && f >= 1 && V.p >= st.p[1] - 0.003) {
      V.vIdx++;
      V.vEnter = t;
    } else if (
      V.vIdx >= Math.min(j.stageIdx, SCENE_STAGES.length - 1) &&
      target - V.p < 0.004 &&
      f >= realFraction(m, V.vIdx, t) - 1e-6
    ) {
      V.catchup = false;
      V.frozenAt = t;
    }
  } else if (V.vIdx < SCENE_STAGES.length) {
    const st = SCENE_STAGES[V.vIdx];
    const inStage = (t - V.vEnter) / 1000;
    const f = Math.min(realFraction(m, V.vIdx, t), inStage / stageMin(m, V.vIdx));
    const target = st.p[0] + (st.p[1] - st.p[0]) * f;
    V.p += Math.max(0, target - V.p) * ease;
    if (j.stageIdx > V.vIdx && f >= 1 && V.p >= st.p[1] - 0.003) {
      V.vIdx++;
      V.vEnter = t;
    }
  } else {
    V.p += (1 - V.p) * ease;
    if (!V.done && V.p > 0.998) {
      V.done = true;
      V.doneAt = t;
      V.p = 1;
    }
    if (V.done && !V.scrub && t - V.doneAt > 1200) {
      V.scrub = true;
      m.onFinished?.();
    }
  }

  // A marker appears only when its detection exists AND the towfish reached it.
  for (const d of m.dets) {
    const vis = V.p >= contactP(m, d) - 0.0005;
    if (vis && !d.shownAt) {
      d.shownAt = t;
      if (!V.scrub) m.onContact?.(d);
    }
    if (!vis && V.scrub) d.shownAt = 0;
  }
}

/** Caption for the HUD over the scene. */
export function hudText(m: SceneModel): { k: string; t: string; s: string; lag: string } {
  const j = m.job;
  const V = m.V;
  if (!j) return { k: "READY", t: "Awaiting job", s: "", lag: "" };
  let k: string, t: string, s: string;
  if (V.scrub) {
    k = "SURVEY REPLAY"; t = "Replay"; s = "Drag the slider to scrub the survey line";
  } else if (V.frozen) {
    k = j.status; t = j.status === "FAILED" ? "Job failed" : "Job cancelled";
    s = V.catchup ? "Showing the survey up to where the job stopped" : "Recovering towfish · frames already saved are kept";
  } else if (V.vIdx >= SCENE_STAGES.length) {
    k = "DONE"; t = j.status === "PARTIAL" ? "Survey processed · partial" : "Survey processed";
    s = `${j.detCount} detection${j.detCount === 1 ? "" : "s"} · ${j.framesFailed} failed frame${j.framesFailed === 1 ? "" : "s"}`;
  } else {
    const st = SCENE_STAGES[V.vIdx];
    k = `STAGE ${V.vIdx + 1}/8 · ${st.key}`; t = st.cap;
    if (V.vIdx === DETECTION_STAGE) {
      const fr = Math.min(m.N, Math.floor(((V.p - st.p[0]) / (st.p[1] - st.p[0])) * m.N) + 1);
      s = `Frame ${Math.max(1, fr)}/${m.N} · swath 120 m across-track · waterfall painting`;
    } else s = st.sub;
  }
  let lag = "";
  if (isTerminal(j.status) && !V.done && !V.frozen && !V.scrub) lag = "● processing finished · replaying survey…";
  else if (!V.scrub && !V.frozen && V.vIdx >= 0 && V.vIdx < Math.min(j.stageIdx, SCENE_STAGES.length))
    lag = "● live job is ahead · scene catching up";
  return { k, t, s, lag };
}
