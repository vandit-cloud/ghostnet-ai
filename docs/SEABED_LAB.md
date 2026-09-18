# Seabed lab

A sandbox for the clutter on the bottom of the landing hero — the rocks, broken
slabs, coral colonies and coral heads that `features/landing/hero/scene.ts`
scatters across the seabed.

**Where:** `/lab/seabed` (dev only, never linked from a public route)

**Code:** `app/frontend/src/features/seabedlab/`

| File | Owns |
| --- | --- |
| `optics.ts` | the shared optical model, mirrored from the hero's water shader |
| `params.ts` | `PARAMS` — every number the look depends on |
| `underwaterMaterial.ts` | `patchUnderwater()`, the `onBeforeCompile` that joins props to the water |
| `seabed.ts` | geometry, scatter and per-instance colour |
| `SeabedScene.tsx` | renderer, water backdrop, the two-pass wipe |

## The problem it exists to solve

The hero renders two things with two different optical models and composites
them in one frame:

| | Model |
| --- | --- |
| water + seabed | raymarched shader, wavelength-dependent absorption, caustics, its own display-space grade |
| the props on it | `MeshStandardMaterial`, `THREE.Fog`, ACES, no caustics, no vignette, no grain |

At 80 m the shader has absorbed ~99% of red out of the background while the
linear fog has faded the props by ~12% toward a flat navy. The props are not so
much "low poly looking" as **lit by a different ocean**. On the live hero this
shows up as olive-khaki coral heads and salmon-pink coral branches at 30 m
depth, where red is optically gone — a colour that could not survive that water.

Seven mismatches, in order of how much they hurt:

1. **Fog model.** Linear vs. exponential per-channel absorption.
2. **No caustics on props.** They stand in a pool of moving light and receive none.
3. **No maps.** One flat albedo, uniform roughness, all 58 rocks identical.
4. **Tessellation.** `IcosahedronGeometry(1, 0)` is 20 faces. The rocks are d20s.
5. **Nothing grounded.** No contact darkening where an object meets sediment.
6. **No vignette or grain**, while the water around them has both.
7. **Colour space.** The water writes display values directly; the props go
   linear → ACES → sRGB.

(7) is why the fix is injected after `<colorspace_fragment>`: that is the only
point in the pipeline where the two are speaking the same units. Mixing the fog
in while the props are still linear gets it tonemapped and encoded afterwards,
and the match fails.

## Rules

1. **`PARAMS` is the single source of truth.** Tuning means changing
   `params.ts` or the sliders that read it, never a shader body. Editing the
   shader is for changing what a feature *is*.
2. **The reference is in the tool — and here the reference is what ships
   today.** Press `R` to cycle `patched / wipe / blend / shipped`, arrows to
   move the seam, or drag the slider. Judge a change by running the seam across
   the same rock twice, never from memory: memory reliably says "close enough"
   about props that are 20× under-fogged.
3. **Placement is frozen.** Same seeds (`20260914`, `77003`, `5150`, `31337`),
   same `lane()` bias, same counts and sink depths as the hero. Only
   tessellation and material move. If the rocks also moved, every comparison
   would be confounded and a luckier arrangement would be indistinguishable
   from a better material.
4. **Hand tuning over as JSON.** "Copy params" emits a block.
5. **Nothing here edits the hero.** When a pass is signed off it ports the
   other way, deliberately, in one reviewable diff.

## Controls

`R` cycle compare mode · `←`/`→` seam · `space` pause · drag orbit · wheel dolly

`window.__sb` exposes `{ scene, renderer, camera, uniforms, sun }` for console
work, the same courtesy `window.__heroProgress` gives on the hero.

## The mirrored-constants hazard

`optics.ts` duplicates the hero's absorption, caustic and grade constants rather
than importing them, because `scene.ts` builds its whole shader as a local
`const FRAG` inside `initHero()` and there is nothing to import without
refactoring a file still marked as a verbatim port.

**If the hero is re-tuned and `optics.ts` is not, the lab starts lying.** Check
`APPROVED_OPTICS` against `scene.ts`'s `APPROVED` block before trusting a
tuning session. When this work ports back, `optics.ts` becomes the source and
`scene.ts` imports from it.

## Two bugs found while building it

Both are recorded because they cost time and would cost it again:

- **`instanceColor` is a multiplier, not an absolute colour.** three's
  instancing shader does `diffuseColor *= vColor`. Setting `material.color` and
  `setColorAt()` both to `0x6b6f66` squares the albedo — 0.147 linear becomes
  0.0216 — and the whole field renders as black silhouettes. The patched build
  now drives `material.color` to white and carries the colour per instance; the
  shipped build sets no instance colour at all, because the hero sets none.
- **The hemisphere light swaps colours underwater.** `scene.ts:964-965` moves
  the ground half from `0x0a2740` to `0x16506f` at `sub > 0.5`, nearly three
  times brighter. Lighting the props with the air values makes them read as
  silhouettes in the lab while the live hero shows them clearly — a lab bug
  masquerading as a finding.

## Status

Phase 1 (fog, caustics, grade integration) and Phase 2 (procedural micro
detail, tessellation, per-instance colour) are implemented and live in the lab.

`sedimentMask()` in `underwaterMaterial.ts` is deliberately naive and is the
first thing to improve — a clean `smoothstep` on `normal.y` alone puts a hard
horizontal waterline across every rock, which is the giveaway of procedural
dressing.

Not started: **Phase 3** — clumping into rubble fields rather than lane-biased
even scatter, and a scour/AO ring where each object meets the sediment.

## Targets: the wreck and the ghost net

`targets.ts` adds the two things a survey is actually looking for, as opposed to
the clutter it looks past.

**Why they exist.** The hero's contact stage reads `ghost_net · 0.91 calibrated`
over a seabed containing rocks, slabs and coral. There is no net in it — the
scroll ends by announcing a detection with nothing to detect, and that is the
one claim on the page a marine reader would check. A wreck earns its place from
the other direction: it is the canonical side-scan target, and lost gear fouls
structure, which is exactly why structure is where you look.

**The net is not geometry.** A 6 m panel at a realistic gauge is thousands of
openings; as tubes it would cost more than the rest of the seabed combined. It
is cut out of a subdivided plane in the fragment shader — distance to the
nearest cell edge, thresholded at the twine gauge, `fwidth()` antialiased
(without which it aliases into moiré at any range). Two noise fields tear it:
one removes whole panels, a second frays the hole boundaries. A third erodes the
outer edge, because the eye reads the **outline** first and a tidy rectangle
says "texture on a plane" however shredded the interior is.

Panels are draped toward horizontal, not stood vertical. A flat grid at right
angles to the bottom reads as fence — it is the one attitude netting never holds
once it is off a boat.

**`netUv` is a custom attribute**, not the plane's `uv`. three only declares
`uv` in the vertex shader when something defines `USE_UV`, and a material with
no maps has no UVs at all. Carrying our own avoids attaching a dummy texture.

**A third bug worth recording:** `customProgramCacheKey` must include the
variant. three caches compiled programs by that string, so returning a constant
hands the net's program to the rocks (or the reverse) depending on which
compiled first. It shows up as rocks full of holes and is very hard to trace
back to a cache.

### Known weak point

The hull silhouette. It currently reads as a smooth open bowl rather than a
vessel — the crowned deck in `hullGeometry()` is too subtle to survive the
absorption, so there is no "built" surface to separate it from a canoe. The
exposed frames and deckhouse carry most of the "wreck" read on their own. Worth
either a proper deck surface across the sheer line, or tipping it further onto
its side so the hull is seen from outside rather than into.
