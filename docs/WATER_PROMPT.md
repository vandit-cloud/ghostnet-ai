# The GhostNet landing-page water — exact reproduction prompt

Hand this whole file to any model/artist as the spec. Every number is lifted from
`app/frontend/src/features/landing/hero/scene.ts` (the `APPROVED` block and the
fragment shader) and `app/frontend/src/app/globals.css`. Nothing here is invented.

---

## 0. What it is, in one paragraph

A single full-screen **raymarched fragment shader** on one fullscreen quad — there is
no water mesh, no normal map, no texture file, no video. A pinhole camera sits on the
Y axis at `(0, camY, 0)` and looks down −Z. Scroll drives the camera from **+6.75 m
above the waterline down to −16.0 m** and simultaneously pitches the view down, so one
continuous shot crosses the surface from a sunny sea into a deep blue water column with
god rays, marine snow and a caustic-lit seabed. Above and below are shaded by two
different functions sharing **one** wave field, blended across a ±0.9 m band at the
waterline so the crossing never pops.

---

## 1. Render setup

- WebGL2 / three.js `ShaderMaterial` on a `PlaneGeometry(2,2)`, orthographic camera, `depthTest:false`, `depthWrite:false`.
- Renderer: `antialias: true`, `alpha: false`, `pixelRatio = min(devicePixelRatio, 1.6)`, `outputColorSpace = sRGB`, `toneMapping = ACESFilmic`.
- Uniforms: `uRes` (vec2 px), `uTime` (seconds), plus every parameter in §3.
- Ray construction, per pixel:
  ```glsl
  vec2 frag = gl_FragCoord.xy / uRes;
  vec2 uv   = (gl_FragCoord.xy - 0.5*uRes) / uRes.y;   // aspect-correct, y-up
  vec3 ro   = vec3(0.0, camY, 0.0);
  vec3 rd   = normalize(vec3(uv.x, uv.y - horizon, -1.0));
  ```
  `horizon` is a **pitch offset**, not a distance — it is what decides how much seabed
  is in frame.

---

## 2. Noise — the only "texture" in the piece

There are **no image textures at all**. Everything grainy is procedural:

```glsl
h21(p)  = fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453);   // hash
nse(p)  = value noise, smoothstep-interpolated (f*f*(3-2f))
fbm(p)  = 5 octaves, gain 0.5, lacunarity 2.03
fbmGrad(p,e) = forward-difference gradient of fbm, epsilon e
```

`fbm` is reused for: sea-surface chop, cloud mass, caustic cells, sand grain, god-ray
angular banding, and the per-frame film grain. Same function, six jobs — that visual
family resemblance is deliberate, do not substitute a different noise per effect.

---

## 3. The approved parameter set (copy verbatim)

```js
// camera / frame
camY: 6.75  -> -16.0 (scroll)   horizon: 0.125 -> 0.33 (scroll)
seabedDepth: 30.0               quality: 1

// sun — one source shared by sky, glitter, caustics and god rays
sunAz: 0.00   sunEl: 0.115   sunStr: 0.22   sunTight: 3200   sunGlow: 0.55

// sky
horR/G/B: 0.60, 0.86, 1.00     zenR/G/B: 0.05, 0.40, 0.86    skyGrad: 0.42
cloudAmt: 0.50   cloudCover: 0.84   cloudScale: 1.85

// waves (one field, both sides)
swellLen: 52.0  swellAmp: 0.55   medLen: 13.0  medAmp: 0.20
chopStr: 0.55   waveSpeed: 0.55  windDir: 0.30  detailFall: 0.024

// surface seen from above
seaR/G/B: 0.035, 0.135, 0.300   fresnelF0: 0.022
glitterPow: 260  glitterStr: 2.10   hazeAmt: 0.62

// seabed + caustics
floorScale: 6.0   sandR/G/B: 0.45, 0.44, 0.78   sandGrain: 0.87
causticStrength: 2.39  causticSharp: 14.8  causticSpeed: 0.79
causticBeat: 4.0       causticFade: 0.32

// water column
fogDensity: 0.030   absR: 2.9   absG: 1.2   absB: 0.6

// god rays
rayStr: 2.56  rayFreq: 27.8  rayReach: 2.0  raySharp: 6.3  rayDepthFade: 0.92

// particles
bubbleAmount: 2.63  bubbleSize: 0.0067  bubbleSpeed: 0.20
moteAmount: 0.47    moteSize: 0.013

// grade
exposure: 1.20   vignette: 0.45   grain: 0.012
```

---

## 4. Every colour, as linear RGB and as hex

### 4.1 The water column — four depth bands (the spine of the look)

```glsl
vec3 waterAt(float depthM){
  vec3 c =        vec3(0.380,0.600,0.712);                           // #6199B6 surface milk-blue
  c = mix(c, vec3(0.059,0.294,0.439), smoothstep( 1.0,27.0,depthM)); // #0F4B70 Atlantic
  c = mix(c, vec3(0.027,0.166,0.408), smoothstep(17.0,43.0,depthM)); // #072A68 deep
  c = mix(c, vec3(0.004,0.054,0.261), smoothstep(31.0,57.0,depthM)); // #010E43 abyss
  return c;
}
```

Band 2 is **exactly the brand's `--atlantic` #0f4b70**, and band 4 sits a hair off
`--imperial` #021f94 — the water *is* the palette, not a separate blue.
Bands overlap (1–27, 17–43, 31–57) so no seam is ever visible.

### 4.2 Sky / reflection source

| Role | Linear RGB | Hex |
|---|---|---|
| Horizon | 0.60, 0.86, 1.00 | `#99DBFF` |
| Zenith | 0.05, 0.40, 0.86 | `#0D66DB` |
| Sun disc tint | 1.00, 0.96, 0.88 | `#FFF5E0` |
| Sun halo tint | 1.00, 0.94, 0.84 | `#FFF0D6` |
| Cloud shadow → lit | 0.72 grey → white | `#B8B8B8` → `#FFFFFF` |

Gradient: `mix(horizon, zenith, pow(clamp(dir.y,0,1), 0.42))` — the 0.42 exponent
keeps the pale band low and tight to the waterline.
Clouds: `fbm(cuv) + fbm(cuv*2.7)*0.35`, masked by
`smoothstep(0.84, 1.14, f) * smoothstep(0.012, 0.16, dir.y)`, drifting at
`uTime*(0.004, 0.002)`, flattened onto the dome by `1/max(dir.y, 0.012)`.

### 4.3 Surface, from above

| Role | Linear RGB | Hex |
|---|---|---|
| Sea body colour (below-Fresnel) | 0.035, 0.135, 0.300 | `#09224D` |
| Glitter / sun facets | 1.00, 0.97, 0.90 | `#FFF7E6` |

### 4.4 Seabed

| Role | Linear RGB | Hex |
|---|---|---|
| Sand base × (0.55 + grain) | 0.45, 0.44, 0.78 | `#7370C7` |
| Caustic light | 0.85, 0.95, 1.00 | `#D9F2FF` |

The sand is deliberately **violet-blue, not tan** — it reads as sand only *because*
the water column is pulled over it by absorption. Do not "correct" it to beige.

### 4.5 Light in the column

| Role | Linear RGB | Hex |
|---|---|---|
| God rays | 0.72, 0.93, 1.00 | `#B8EDFF` |
| Snell-window specular | 0.72, 0.93, 1.00 | `#B8EDFF` |
| Bubbles | 0.85, 0.96, 1.00 | `#D9F5FF` |
| Marine snow | 0.80, 0.93, 1.00 | `#CCEDFF` |

All four are the same cyan family as `--sky` `#C4F8FF`. Every particle and every shaft
is cyan-white; nothing in the water is warm except the sun itself.

---

## 5. The wave field (one field, used by both sides)

Height (used only to find the waterline at the camera):

```glsl
h = sin(dot(w ,p)*2PI/52.0 + t*0.55)*0.55        // swell
  + sin(dot(w2,p)*2PI/13.0 + t*1.05)*0.20        // medium
w  = (cos(0.30), sin(0.30))        // wind direction
w2 = wind + 0.7 rad,  w3 = wind - 0.9 rad,  t = uTime * 0.55
```

Normal (the thing you actually see) — five sinusoids plus three fbm gradients:

```glsl
p += (vec2(fbm(p*0.018), fbm(p*0.018+7.3)) - 0.5) * 9.0;   // domain warp: kills tiling
detail = exp(-dist * 0.024);   md = mix(0.35, 1.0, detail);
addWave(w , 52.0,        0.55,         t*0.55);
addWave(w2, 52.0*0.63,   0.55*0.55,    t*0.61);
addWave(w2, 13.0,        0.20*md,      t*1.05);
addWave(w3, 13.0*0.66,   0.20*0.72*md, t*1.24);
addWave(w , 13.0*0.41,   0.20*0.46*md, t*1.51);
drift = w*(t*0.6);
s += fbmGrad(p*0.22 + drift,      0.35) * 0.55 * 1.00 * detail;
s += fbmGrad(p*0.65 - drift*1.7,  0.18) * 0.55 * 0.55 * detail;
s += fbmGrad(p*1.80 + drift*2.6,  0.08) * 0.55 * 0.28 * detail*detail;  // high quality only
N = normalize(vec3(-s.x, 1.0, -s.y));
// addWave: s += d * (cos(dot(d,p)*k + t) * amp * k),  k = 2PI/len
```

`detailFall = 0.024` is **essential**: without the distance falloff the micro-chop
aliases into moiré at the horizon. That was a real bug in the lab; keep it.

---

## 6. Above the surface

```glsl
if (rd.y >= -0.0008) {                      // sky half
    c = skyColor(rd);
    c = mix(c, horizonColor, (1 - smoothstep(0,0.06,rd.y)) * 0.55 * 0.62);  // haze band
} else {                                    // water half
    t = (ro.y - surfH)/(-rd.y);  p = ro + rd*t;  N = waveNormal(p.xz, t);
    F = 0.022 + (1-0.022)*pow(1 - dot(N,-rd), 5.0);           // Schlick, F0 = 0.022
    R = reflect(rd, N);  R.y = abs(R.y);                      // never sample below
    c = mix(vec3(0.035,0.135,0.300), skyColor(R), F);
    c += vec3(1.0,0.97,0.90) * pow(max(dot(R,sd),0),260.0)
         * (0.65 + 0.35*fbm(p.xz*0.8 + uTime*0.05))           // glitter breaks up
         * 2.10 * exp(-t*0.024*0.55);
    c = mix(c, skyColor(vec3(rd.x,0.02,rd.z)), (1 - exp(-t*0.0016)) * 0.62);  // aerial haze
}
```

The `0.65 + 0.35*fbm` modulation on the glitter is what stops it reading as a regular
sparkle grid — do not drop it.

---

## 7. Below the surface

**Looking up — Snell's window.** The entire sky is compressed into a ~48.6° cone about
vertical; outside it the underside of the surface mirrors the water.

```glsl
crit = 0.8483;                             // asin(1/1.333)
win  = smoothstep(crit+0.10, crit-0.16, acos(rd.y));
thr  = refract(rd, -N, 1.0/1.333);
col  = mix(waterAt(eyeDepth + 6.0) * 1.15, skyColor(normalize(thr)), win);
col += vec3(0.72,0.93,1.0) * pow(max(dot(reflect(rd,N),sd),0.0), 90.0) * 0.25;
```

**Looking down — seabed at y = −30 m.**

```glsl
fuv = (p.xz + vec2(53.0,17.0)) * (6.0*0.1);
c   = caustics(fuv, uTime*0.79);
g   = fbm(fuv*6.0) * 0.87;                                   // sand grain
col  = vec3(0.45,0.44,0.78) * (0.55 + g);
col += vec3(0.85,0.95,1.0) * c * 2.39 * mix(1.0, exp(-t*0.09), 0.32);
```

**Caustics — ridged, three layers, and they must never invert:**

```glsl
causticLayer(p,t): for i in 0..2:
   q  = p*(1 + i*0.8) + vec2(t*(0.30+i*0.11), -t*(0.22+i*0.09));
   v += (1.0 - abs(fbm(q)*2.0 - 1.0)) * (1.0 - i*0.22);
   return pow(clamp(v/2.34,0,1), 14.8);                      // causticSharp
caustics = L(uv,t) + L(uv*4.0+23.0, -t*0.62)*0.55 + L(uv*4.0*2.7+71.0, t*0.34)*0.28;
```

The `1 - abs(2n-1)` ridge is the trick: plain fbm gives blobs, the ridge gives the
bright interlocking net. The high `causticSharp` (14.8) is what makes the lines thin.

**Absorption over the optical path** — the single most important step:

```glsl
vec3 ab = vec3(2.9, 1.2, 0.6);
ab /= max((ab.r+ab.g+ab.b)/3.0, 1e-4);      // normalise: shift hue, not density
col = mix(col, waterAt(eyeDepth), 1.0 - exp(-pathLength * 0.030 * ab));
```

Red is absorbed ~4.8× faster than blue. This is why the violet sand turns blue-grey and
why everything distant dissolves into the band colour of the current depth.

**God rays** — anchored to the *refracted* sun, not the raw one:

```glsl
sdw = normalize(mix(sd, vec3(0,1,0), 0.35));   // bend toward vertical (Snell)
sunUV   = vec2(-sdw.x/sdw.z, -sdw.y/sdw.z + horizon);      // project
sunFrag = vec2(sunUV.x*(uRes.y/uRes.x) + 0.5, sunUV.y + 0.5);
d = frag - sunFrag; d.x *= uRes.x/uRes.y;  r = length(d);  a2 = atan(d.x, -d.y);
shafts  = pow(clamp(fbm(vec2(a2*27.8, uTime*0.04)),0,1), 6.3);
shafts *= smoothstep(-0.10, 0.70, -d.y/r);          // only downward
shafts *= smoothstep(2.0, 0.0, r);                  // rayReach
shafts *= 0.70 + 0.30*sin(uTime*0.55 + a2*6.0);     // slow breathing
shafts *= mix(1.0, smoothstep(0.0,0.62,frag.y), 0.92);  // fade toward the bottom
col += vec3(0.72,0.93,1.0) * shafts * 2.56 * 0.25;
```

Skipping the bend-to-vertical puts the vanishing point inside frame and the shafts fan
out of mid-water — wrong, and immediately readable as wrong.

**Particles** (screen-space, additive):

- Bubbles: 4×4 grid, rise `fract(seed + uTime*0.20*(0.55+seed*0.9))`, lateral wobble
  `sin((y+seed)*9.0)*0.012`, radius `0.0067*(0.5+seed)*(0.6+y*0.8)`, tint `#D9F5FF`,
  brightness `(0.35+0.65*seed)`, gain 2.63.
- Marine snow: 12 motes, drift `uTime*0.006`, radius `0.013*(0.4+hash)`, tint `#CCEDFF`,
  gain 0.47 × 0.25.

---

## 8. The crossing (do not skip)

```glsl
surfH = waveHeight(vec2(0.0));
w = smoothstep(-0.9, 0.9, camY - surfH);
w > 0.995  -> above only
w < 0.005  -> below only
else       -> mix(below, above, w)
```

A pinhole camera cannot be half-submerged, so this is one decision **per frame**, not
per pixel — but a hard `camY > surfH` test makes a passing swell flip the entire frame
in one step. The ±0.9 m blend band costs both branches only inside the band.

---

## 9. Grade — applied to both sides, so the crossing is seamless

```glsl
col *= 1.20;                                   // exposure
col  = col / (1.0 + col*0.55);                 // Reinhard-ish shoulder
lum  = dot(col, vec3(0.299,0.587,0.114));
col  = mix(vec3(lum), col, 1.18);              // +18% saturation
vc   = (frag - 0.5) * vec2(1.06, 1.0);
vigAmt = mix(0.22, 0.45, clamp(-camY/8.0, 0, 1));            // vignette deepens underwater
col *= 1.0 - vigAmt * pow(clamp(length(vc)*1.42,0,1), 2.15);
col += (h21(gl_FragCoord.xy + fract(uTime)) - 0.5) * 0.012;  // per-frame grain
```

Plus the renderer's ACES tone map on top. The vignette ramp from 0.22 to 0.45 as the
camera submerges sells the descent as much as the colour does.

---

## 10. Scroll drive

```js
p = scroll progress 0..1 over a 360vh track (hero pane is sticky, 100vh)
camY    = 6.75  + (-16.0 - 6.75)  * easeInOut(span(p, 0.14, 0.52));
horizon = 0.125 + (0.33  - 0.125) * easeInOut(span(p, 0.20, 0.66));
easeInOut(t) = t<0.5 ? 2t*t : 1 - pow(-2t+2, 2)/2
span(p,a,b)  = clamp01((p-a)/(b-a));
```

The dive **leads** the towfish deployment (0.14–0.52 vs 0.18–0.62) on purpose: you are
already underwater before the winch starts, so you watch the fish go down rather than
arriving after it.

---

## 11. The CSS layers over the canvas (part of the final look)

Pane base fill, visible for one frame and behind any transparency: `#0a2a44`.

**Static fallback plate** (pre-scene, and permanent under `prefers-reduced-motion`) — the
same water read as a flat gradient:

```css
linear-gradient(180deg,
  #7fb4d8 0%,      /* sky */
  #a9d4ea 11%,     /* haze band at the horizon */
  #5e9dc4 12.5%,   /* the waterline itself */
  #12547e 26%,
  #0f4b70 52%,     /* --atlantic */
  #0a3552 78%,
  #072639 100%);   /* deep */
```

Cross-fades out over 0.6 s on the scene's first frame.

**Scrim** (z-index 2, over the canvas, under the copy) — two imperial-blue washes:

```css
linear-gradient(180deg, rgba(2,31,148,.42) 0%, rgba(2,31,148,.05) 30%, rgba(2,31,148,0) 52%),
linear-gradient(0deg,   rgba(2,31,148,.70) 0%, rgba(2,31,148,.14) 32%, rgba(2,31,148,0) 54%)
```

Top and bottom only; the middle band stays clean water.

**Grain overlay** (`.grain`, z-index 8) — SVG turbulence, no asset, `multiply` at 0.13:

```
feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="4" stitchTiles="stitch"
-> feColorMatrix saturate 0 -> rect opacity 0.5, tile 260x260
```

This sits on top of the shader's own grain. Both are present; the look is a *printed*
sea, not a glassy one.

**Brand tokens the water must agree with:**
`--atlantic #0f4b70` · `--sky #c4f8ff` · `--imperial #021f94` · `--paper #f5f2f3`

---

## 12. Rules of thumb if you are re-tuning

1. One wave field for both sides. Two fields make the halves disagree at the waterline.
2. Never sample the sky below the horizon for a reflection — `R.y = abs(R.y)`.
3. Normalise the absorption triple before using it, or changing hue also changes density.
4. Keep `detailFall`; distance-attenuate the micro-chop or the horizon aliases.
5. Bend the sun toward vertical before projecting the god rays.
6. Grade **after** the above/below blend, never inside either branch.
