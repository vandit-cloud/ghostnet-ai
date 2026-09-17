# Underwater reference lab

A standalone WebGL reproduction of the underwater plate in `docs/` (the one with
god rays, a caustic web on sand, and bubble columns), built so several people
and several AIs can converge on it without stepping on each other.

**Where:** `C:\Users\vandi\OneDrive\Desktop\ghostnet-water-lab\`
- `water-lab.src.html` — edit this
- `build_lab.py` — inlines the reference photo, writes `water-lab.html`
- `water-lab.html` — open by double-click, no server

Run `python build_lab.py` after any edit.

## How to give someone a task on it

Name a section. The fragment shader is divided into nine numbered, independent
sections and none reads another's locals:

| # | Section | What it owns |
| --- | --- | --- |
| 1 | Noise | shared helpers — not a look, do not tune |
| 2 | Caustics | the cellular web |
| 3 | Seabed | the ground plane and sand |
| 4 | Water column | depth haze that welds floor to water |
| 5 | Surface | the bright rippled ceiling |
| 6 | God rays | shafts and sun glow |
| 7 | Bubbles | rising columns |
| 8 | Particulate | bokeh motes |
| 9 | Grade | vignette, tonemap, saturation, grain |

"Improve SECTION 6, the shafts are too spoke-like" is a workable task.
"Make it look better" is not.

## Rules

1. **`PARAMS` is the single source of truth.** Every number the look depends on
   is there with a range and a label. Tuning means changing `PARAMS`, never
   editing the shader — unless you are changing what a feature *is*.
2. **The reference is in the tool.** Press `R` to cycle wipe / blend / hidden,
   arrow keys to move the seam. Judge by running the seam through the same
   feature twice, not from memory.
3. **Hand tuning over as JSON.** "Copy params" emits a block; paste it into
   `PARAMS_OVERRIDE` at the bottom of the file to adopt someone else's pass.
4. **The match score is a regression alarm, not a target.** It is a 12×7 grid
   of mean RGB error and is blind to structure. It will happily score a blurry
   mess higher than a sharp near-miss — this has already happened once here,
   67.1 for a mushy floor against 63.1 for a better-looking one. Trust the wipe.

## Conformance to the ocean spec

`GhostNet-AI_Technical_Ocean_Underwater_Rendering_Specification.md` now drives
the optical model. Implemented:

- **§20 absorption** — per-channel, red attenuating fastest and blue carrying
  furthest, instead of one scalar fog. The three multipliers are **normalised**
  so they shift colour without also raising mean density; un-normalised they
  silently re-tune `fogDensity` behind you and bury the seabed.
- **§22 / §24** — non-linear `exp(-density x path)`, with depth and distance
  both in play: the water *colour* comes from the depth band, the *amount* from
  the optical path.
- **§23 / §25** — the four-band GhostNet ramp at its exact source values with
  `BAND_BLEND = 13`, interpolated, no hard thresholds.
- **§30-32 god rays** — soft, irregular, directional, noise-varied, attenuating
  with depth (`rayDepthFade`) and with radial distance from the sun.
- **§34 caustic scale** — three spatial frequencies (large, medium, breakup) at
  different directions and phases, so no single translated layer is legible.
- **§36 caustic attenuation** — caustics fade with optical distance.

Still to do from the spec: §21 forward/back scattering as separate terms, §39
marine-snow lighting from the sun direction, §43 bubble optical response.

## State as of 13 Sept 2026

Score ~72 on the user's tuned parameter set at the agreed framing
(`pitch 0.05`, `camHeight 1.35`), now the defaults in the file.
Structure is right: straight shafts, floor perspective, four-band water column,
bubbles, motes, vignette.

**Note on the current framing.** `pitch = -0.15` puts the horizon at 35% of
frame height, so the seabed occupies the bottom third. In the reference plate
the sand fills the bottom *half* and its caustic web is the dominant feature.
If matching the plate more closely is the goal, `pitch` around `+0.05` and a
lower `camHeight` bring the floor up and closer, which also makes the caustics
large enough to read. Left as supplied — this is a framing choice, not a bug.

**Known gaps, in priority order:**
1. The caustic web is faint at the current framing — the floor sits far enough
   away that distance attenuation and fog take most of it. Either raise the
   horizon (see the framing note above) or lower `causticFade` / `fogDensity`.
2. The surface band (SECTION 5) is the worst-scoring region. The plate's top
   fifth is a bright, sharply rippled ceiling; ours is a soft gradient.
3. No bokeh depth-of-field on the motes — the plate's are visibly out of focus.

**Two bugs already found and fixed here, worth not reintroducing:**
- The classic reciprocal-distance caustic formula **explodes at the plane
  origin** — the point directly beneath the camera — saturating a blown white
  ellipse into the middle of the seabed. Sample coordinates are offset away
  from the origin for this reason.
- That same formula takes `abs()` of a value straddling zero, so **both**
  extremes render bright and the mid-tone dark: the web comes out inverted, as
  dark streaks on pale sand. Ridged noise (`1 - |2n-1|`) cannot invert.

## Licence note

The reference is a watermarked Adobe Stock comp, inlined for local comparison
only. It must never ship in anything published.
