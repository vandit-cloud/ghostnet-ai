# 3D asset brief — survey vessel & side-scan towfish

Two assets, both consumed by `app/frontend/public/models/`. They serve the
scroll hero at `/lab/hero` **and** the survey map, which is why the spec is
stricter than a one-off render would need.

> **Read this first if you are using a text-to-3D generator.**
> Generators (Meshy, Tripo, Rodin, Hunyuan3D, …) respond to *visual* description
> and ignore instructions about axes, origin, scale and topology — those are not
> things they model. So this document is split in two: the **prompt** is what you
> paste into the generator, and the **spec** is what you fix in Blender
> afterwards. Skipping the spec pass will produce a boat that sails stern-first
> and floats a metre above the water.

---

## 1. Generator prompt — survey vessel

Paste as-is. Written to front-load the silhouette, because these models weight
the opening clause most heavily.

```
A modern coastal marine survey research vessel, side three-quarter view, full
hull visible above and below the waterline.

Hull: roughly 28 metres long, slender and purposeful, a working boat rather
than a yacht. Sharp raked bow, flared forward sections, flat transom stern.
Painted deep navy blue below a crisp white sheer line, with a dark red
antifouling band at the bottom of the hull and visible weld seams and hull
plating.

Superstructure: a white two-level deckhouse set forward of midships, with a
wraparound bridge of large tinted windows angled slightly outward, a walkway
and railings around it, watertight doors, and grab rails.

Above the bridge: a slim radar mast carrying a rotating scanner bar, two
whip antennas, a white steaming light and a small radar dome.

Stern: this is the important part. A clear open working aft deck, uncluttered,
with a large yellow A-frame gantry arching over the transom, and a heavy cable
winch drum mounted on the deck in front of it. Deck is grey non-slip plating
with a low bulwark and stanchion railings around the edge.

Details: orange life rings on the rails, a small crane davit on the starboard
side, mooring bollards and cleats, fenders along the rail, anchor at the bow,
a few deck lights, a red port navigation light and a green starboard light.

Style: clean realistic hard-surface game asset, believable engineering,
moderate polygon count, PBR metal and painted surfaces, neutral studio
lighting, no water, no background, no environment.
```

**Negative prompt**

```
cartoon, stylised, low-poly faceted, toy, sailboat, mast with sails, yacht,
cruise ship, warship, guns, cargo containers, fishing trawler nets, water,
waves, ocean, sea surface, sky, background scenery, people, text, watermark,
base, pedestal, display stand
```

Three things in there are doing real work and should not be trimmed:

- **"no water, no waves, no sea surface"** — generators love to produce a boat
  welded into a slab of ocean. The scene has its own animated water shader
  (`OceanSurface.tsx`); a baked sea slab is unusable and tedious to cut out.
- **"no base, no pedestal"** — the other common default, and it sits exactly
  where the origin needs to go.
- **"A-frame gantry and winch"** — the towfish is deployed over this. Without
  it the cable appears to emerge from bare hull and the whole deployment
  animation loses its anchor.

## 2. Generator prompt — side-scan towfish

```
A yellow side-scan sonar towfish, a towed underwater survey instrument, side
three-quarter view.

Shape: a slim torpedo-shaped body about 1.3 metres long with a rounded nose
and a tapering tail, finished in bright safety yellow with black end caps.

Sides: a long flat dark rectangular transducer array panel recessed into each
flank, running most of the body length, in dark grey composite.

Tail: four swept stabiliser fins in a cross arrangement at the rear, dark grey.

Nose: a stainless steel towing bracket and shackle at the very tip, with a
strain relief boot where the armoured tow cable enters.

Details: a depth sensor port, a small pressure housing, a couple of recessed
hex bolts, faint scuffs and scratches on the yellow paint.

Style: clean realistic hard-surface marine equipment, PBR painted metal,
neutral studio lighting, no background, no water, no cable, no stand.
```

**Negative prompt**

```
missile, rocket, bomb, torpedo weapon, submarine with conning tower, propeller,
cartoon, toy, water, background, stand, tripod, cable, rope, text, watermark
```

Note "no cable" — the tow cable is a live sagging curve in `TowCable.tsx` that
has to lengthen and slacken during the drop. A modelled cable fights it.

---

## 3. Blender spec — the fixup pass

Apply to whatever comes out of the generator, or model to this directly.

### Importing from Tripo AI

**Export from Tripo as GLB**, not FBX/OBJ/STL. It is already glTF, so the PBR
materials survive into Blender and back out again untranslated, and the textures
are embedded in the one file. FBX exports reference external textures that
Blender often fails to link; OBJ drops PBR to diffuse-only. If the tier exposes
a **quad topology** toggle, turn it on — the default triangle soup renders fine
but resists loop cuts and bevels.

A generated asset always imports in the same three wrong states:

| | What Tripo gives you | Fix |
| --- | --- | --- |
| Scale | Normalised to ~1–2 units whatever the subject | `S`, factor, then `Ctrl+A → Scale` |
| Origin | Mesh bounding-box centre (mid-hull) | 3D cursor to waterline, `Object → Set Origin → Origin to 3D Cursor` |
| Rotation | Upright (the importer converts Y-up→Z-up) but arbitrary heading | Rotate bow to **+Y**, `Ctrl+A → Rotation` |

Also expect one material slot for the whole hull, and parts fused that should be
separate. The **A-frame is worth separating** — it is where the tow cable
visually originates, so it wants to be identifiable.

### Orientation — the one that breaks things

| Asset   | Points along |
| ------- | ------------ |
| Vessel  | Bow toward Blender **+Y** |
| Towfish | Nose toward Blender **+Y** |

The glTF exporter maps Blender **+Y → glTF −Z**. `Vessel.tsx:4-6` documents tha t
local +z is where the tow gear trails, and `Scene3D.tsx:159` rotates the vessel
group by real compass heading. Get the axis wrong and every boat on the survey
map sails backwards along its own track.

Blender is Z-up and glTF is Y-up; the exporter handles that conversion itself as
long as **+Y Up** stays ticked.

### Origin

- **Vessel:** at the **waterline**, centred port-to-starboard, roughly under the
  mast fore-and-aft. Hull below `Z=0`, superstructure above.
  *This fixes a live bug:* `OceanSurface` sits at Y=0 but the current hull box
  (`Vessel.tsx:14`) spans y=0.5→1.9, so the boat has half a unit of air under
  the keel. Invisible at map scale, glaring at hero scale.
- **Towfish:** at the **nose tow-point**, so the cable attaches to the origin
  and the body hangs from it naturally.

### Scale

Model at real size — ~28 m vessel, ~1.3 m towfish — and say what you used. One
constant normalises it in code. Do not pre-scale to match the existing
primitives; that guesswork is better done once, in code, where it is visible.

### Budget & materials

| | Triangles | Textures |
| --- | --- | --- |
| Vessel | 8k–15k | one 2048 atlas, or none |
| Towfish | 2k–4k | one 1024 atlas, or none |

glTF carries **only PBR metallic-roughness**. Blender procedural node trees do
not export — bake them, or use flat base colours, which suits the existing look
fine. Leave the beacon material's emission on; the scene relies on it.

Palette (Atlantic): `#0F4B70` atlantic · `#C4F8FF` sky · `#021F94` imperial
(accent only — beacons and nav lights) · `#F5F2F3` paper.

### Export

- Format **glTF Binary (.glb)**, Draco compression on
- `Ctrl+A → All Transforms` on every object first
- Apply modifiers; triangulate
- Tick **+Y Up**
- Single root object, no empties, no cameras, no lights
- Save to `app/frontend/public/models/vessel.glb` and `towfish.glb`

### Checking it

Open `/lab/hero`, switch the panel to **scrub**, and step the marks. In dev the
console logs `[hero] model unavailable` whenever it has fallen back to the
primitives — no log means your model loaded.

---

## 4. What is *not* modelled

Water, the sonar swath, the tow cable, the seabed, the acoustic returns, beacon
glow, detection markers. All of it is code — see `OceanSurface.tsx`,
`SonarSweep.tsx`, `TowCable.tsx`, `SonarReturns.tsx`. Anything baked into the
mesh will fight the live version.
