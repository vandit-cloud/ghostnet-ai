import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createModel,
  DETECTION_MIN_S,
  newView,
  SCENE_STAGES,
  type SceneModel,
  tick,
} from "@/features/processing/scene/model";

/* The processing scene paces itself stage by stage. These drive its model on a
 * simulated 60 fps clock and measure how long each stage is on screen, because
 * the complaint it guards against is timing: a one-image run used to play for
 * ~13 s and a 40-frame run for ~30 s whatever the backend actually took. */

let clock = 0;
beforeEach(() => {
  clock = 0;
  vi.spyOn(performance, "now").mockImplementation(() => clock);
});
afterEach(() => {
  vi.restoreAllMocks();
});

const FRAME = 1000 / 60;

function freshModel(N: number): SceneModel {
  const m = createModel();
  m.N = N;
  m.V = newView();
  return m;
}

/** Run until the summary would open; returns seconds each stage was on screen. */
function play(m: SceneModel, onStep?: (tMs: number) => void, limitS = 120) {
  const entered: number[] = [];
  let finishedAt = -1;
  m.onFinished = () => (finishedAt = clock);
  let last = -1;
  while (clock < limitS * 1000 && finishedAt < 0) {
    clock += FRAME;
    onStep?.(clock);
    tick(m, FRAME / 1000);
    if (m.V.vIdx !== last) {
      entered[m.V.vIdx] = clock;
      last = m.V.vIdx;
    }
  }
  const stage = (i: number) => ((entered[i + 1] ?? finishedAt) - entered[i]) / 1000;
  return { stage, total: finishedAt / 1000 };
}

function finishedJob(N: number, runMs: number): SceneModel["job"] {
  return {
    status: "COMPLETED", stageIdx: SCENE_STAGES.length, framesDone: N, framesFailed: 0, detCount: 1,
    lastFrameAt: 0, frameDur: 1300, stageAt: 0, runMs,
  };
}

describe("processing scene pacing", () => {
  it("plays a one-image run in about ten seconds, with 2-3 s of detection", () => {
    const m = freshModel(1);
    m.job = finishedJob(1, 900);
    const { stage, total } = play(m);

    for (const i of [0, 1]) expect(stage(i)).toBeLessThan(1.2);   // validating, decoding
    expect(stage(2)).toBeLessThan(1.9);                            // preprocessing (towfish deploys)
    expect(stage(3)).toBeGreaterThanOrEqual(DETECTION_MIN_S);
    expect(stage(3)).toBeLessThan(3.2);
    for (const i of [4, 5, 6, 7]) expect(stage(i)).toBeLessThan(1.0);
    expect(total).toBeLessThan(11);
  });

  it("replays a finished run for as long as the run really took", () => {
    const m = freshModel(40);
    m.job = finishedJob(40, 14_000);                               // a GPU run: 40 frames in 14 s
    const { stage } = play(m);
    expect(stage(3)).toBeGreaterThan(13.5);
    expect(stage(3)).toBeLessThan(15.5);                           // not the old 30 s floor
  });

  it("compresses the replay of a very long run", () => {
    const m = freshModel(400);
    m.job = finishedJob(400, 600_000);
    const { stage } = play(m, undefined, 200);
    expect(stage(3)).toBeLessThan(47);
  });

  it("follows a live run frame by frame instead of its own timer", () => {
    const N = 40;
    const perFrame = 350;                                          // ms, a GPU-speed run
    const detectStart = 150;                                       // the backend's setup stages
    const m = freshModel(N);
    m.job = {
      status: "VALIDATING", stageIdx: 0, framesDone: 0, framesFailed: 0, detCount: 0,
      lastFrameAt: 0, frameDur: 1300, stageAt: 0, runMs: 0,
    };
    const runEnd = detectStart + N * perFrame;
    const { stage } = play(m, (t) => {
      const j = m.job!;
      if (t < 50) j.stageIdx = 0;
      else if (t < 100) j.stageIdx = 1;
      else if (t < detectStart) j.stageIdx = 2;
      else if (t < runEnd) {
        j.stageIdx = 3;
        const done = Math.floor((t - detectStart) / perFrame);
        if (done > j.framesDone) { j.framesDone = done; j.lastFrameAt = t; }
      } else if (j.status !== "COMPLETED") {
        Object.assign(j, { status: "COMPLETED", stageIdx: SCENE_STAGES.length, framesDone: N, runMs: runEnd });
      }
    });
    // The run's detection lasted 14 s; the scene must not hold it for 30.
    expect(stage(3)).toBeGreaterThan(12);
    expect(stage(3)).toBeLessThan(16);
  });
});
