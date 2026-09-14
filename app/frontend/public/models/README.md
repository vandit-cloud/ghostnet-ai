# 3D model drop point

Two files are expected here. Nothing needs to be wired up when they arrive —
`ModelSlot.tsx` picks them up by filename on the next page load, and falls back
to the primitive geometry in `Vessel.tsx` / `Towfish.tsx` if a file is missing
or fails to parse.

| File             | What it is                         | Brief                               |
| ---------------- | ---------------------------------- | ----------------------------------- |
| `vessel.glb`     | Survey vessel (hero **and** map)    | `docs/HERO_VESSEL_MODEL_BRIEF.md`   |
| `towfish.glb`    | Side-scan sonar towfish             | `docs/HERO_VESSEL_MODEL_BRIEF.md`   |
| `hero-poster.jpg`| Still frame for phones / reduced-motion | Screenshot `/lab/hero` at p≈0.85 |

Hard requirements (both models):

- **Bow / nose along Blender +Y.** The glTF exporter maps Blender +Y to glTF −Z,
  which is the convention `Vessel.tsx` documents and `Scene3D.tsx` rotates real
  compass headings against.
- **Origin at the waterline** for the vessel, at the **nose tow-point** for the
  towfish.
- Apply all transforms (`Ctrl+A → All Transforms`) before exporting.
- Export as **glTF Binary (.glb)** with Draco compression.

Verify a drop by opening `/lab/hero` and watching the browser console: the slot
logs `[hero] model unavailable` in dev when it has fallen back.
