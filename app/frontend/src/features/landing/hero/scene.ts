/* eslint-disable */
// @ts-nocheck
/* =============================================================================
 * GENERATED FILE -- DO NOT EDIT BY HAND.
 *
 * Ported verbatim from the standalone landing demo by
 * `scripts/port_hero_scene.py`. Tune the hero in
 * `ghostnet-demo/demo.src.html`, rebuild it with `build_demo.py`, then re-run
 * the port. Editing this file directly means the next port silently reverts it.
 *
 * ts-nocheck is deliberate and is the price of a verbatim port: the source is
 * plain JavaScript written against the DOM and three's untyped uniform objects,
 * and annotating it would mean rewriting it, which is the one thing this file
 * exists to avoid. The wrapper below is typed, and it is the only surface the
 * rest of the app touches.
 * ========================================================================== */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';

const VESSEL_URL = "/models/vessel.glb";
const TOWFISH_URL = "/models/towfish.glb";

/**
 * Build the hero scene against the elements the landing page has already
 * rendered, and start it. Returns a dispose function; call it on unmount.
 *
 * The scene reads the DOM by id, exactly as it does in the demo -- #gl, #hero,
 * #heroCopy and the instrument readouts. HeroCanvas renders those same ids, so
 * the two halves stay in step without a prop surface between them.
 */
export function initHero(): () => void {
  if (typeof window === "undefined") return () => {};
  if (!document.getElementById("gl") || !document.getElementById("hero")) {
    // Nothing to attach to. Returning a no-op is the right failure here: a
    // landing page without its background is degraded, not broken.
    return () => {};
  }

  let rafId = 0;
  let disposed = false;


  /* ===========================================================================
   * HERO — the merged sea (above + below) with the survey rig, driven by scroll.
   *
   * The water shader and its PARAMS are EXTRACTED from the sea lab at build time
   * and then overridden with the approved tuning, so the look on this page and
   * the look in the lab cannot drift apart.
   *
   * The scroll does two things at once: it DIVES the camera from above the
   * waterline down to working depth, and it runs the DEPLOYMENT. They are
   * deliberately offset - the dive leads, so you are already under when the
   * towfish starts paying out and can watch it go.
   * ======================================================================== */

  const PARAMS = {
    camera: {
      camY:        { v: -34.0, min: -52, max: 30, step: 0.25, label: "camera height (m)" },
      horizon:     { v: 0.06,  min: -0.35, max: 0.40, step: 0.005, label: "horizon / pitch" },
      seabedDepth: { v: 52.0,  min: 8, max: 90, step: 0.5, label: "seabed depth (m)" },
      quality:     { v: 1.0,   min: 0, max: 1, step: 1, label: "quality (0 med / 1 high)" },
    },
    // SECTION 2 — sun (shared by every effect, spec §29)
    sun: {
      sunAz:     { v: 0.00,  min: -1.5, max: 1.5, step: 0.01, label: "sun azimuth" },
      sunEl:     { v: 0.115, min: 0.005, max: 0.9, step: 0.005, label: "sun elevation" },
      sunStr:    { v: 0.22,  min: 0, max: 4, step: 0.02, label: "sun strength" },
      sunTight:  { v: 3200,  min: 60, max: 6000, step: 20, label: "sun tightness" },
      sunGlow:   { v: 0.55,  min: 0, max: 3, step: 0.01, label: "sun halo" },
    },
    // SECTION 3 — sky
    sky: {
      horR: { v: 0.60, min: 0, max: 1, step: 0.01, label: "horizon R" },
      horG: { v: 0.86, min: 0, max: 1, step: 0.01, label: "horizon G" },
      horB: { v: 0.96, min: 0, max: 1, step: 0.01, label: "horizon B" },
      zenR: { v: 0.05, min: 0, max: 1, step: 0.01, label: "zenith R" },
      zenG: { v: 0.40, min: 0, max: 1, step: 0.01, label: "zenith G" },
      zenB: { v: 0.86, min: 0, max: 1, step: 0.01, label: "zenith B" },
      skyGrad: { v: 0.42, min: 0.1, max: 2, step: 0.01, label: "sky gradient" },
      cloudAmt:{ v: 0.00, min: 0, max: 1, step: 0.01, label: "cloud amount" },
      cloudCover:{ v: 0.52, min: 0.2, max: 0.9, step: 0.01, label: "cloud cover" },
      cloudScale:{ v: 0.9, min: 0.1, max: 4, step: 0.05, label: "cloud scale" },
    },
    // SECTION 4 — waves (shared by both sides)
    waves: {
      swellLen:  { v: 52.0, min: 10, max: 160, step: 1, label: "swell wavelength (m)" },
      swellAmp:  { v: 0.55, min: 0, max: 3, step: 0.01, label: "swell amplitude (m)" },
      medLen:    { v: 13.0, min: 2, max: 40, step: 0.5, label: "medium wavelength (m)" },
      medAmp:    { v: 0.20, min: 0, max: 1.5, step: 0.01, label: "medium amplitude (m)" },
      chopStr:   { v: 0.55, min: 0, max: 2.5, step: 0.01, label: "chop roughness" },
      waveSpeed: { v: 0.55, min: 0, max: 3, step: 0.01, label: "wave speed" },
      windDir:   { v: 0.30, min: -3.14, max: 3.14, step: 0.02, label: "wind direction" },
      detailFall:{ v: 0.024,min: 0.0005, max: 0.05, step: 0.0005, label: "microdetail falloff" },
    },
    // SECTION 5 — surface seen from above
    surface: {
      seaR: { v: 0.035, min: 0, max: 0.6, step: 0.005, label: "sea R" },
      seaG: { v: 0.135, min: 0, max: 0.8, step: 0.005, label: "sea G" },
      seaB: { v: 0.300, min: 0, max: 1, step: 0.005, label: "sea B" },
      fresnelF0: { v: 0.022, min: 0.005, max: 0.2, step: 0.001, label: "Fresnel F0" },
      glitterPow:{ v: 260, min: 20, max: 4000, step: 10, label: "glitter tightness" },
      glitterStr:{ v: 2.10, min: 0, max: 5, step: 0.02, label: "glitter strength" },
      hazeAmt:   { v: 0.62, min: 0, max: 1, step: 0.01, label: "horizon haze" },
    },
    // SECTION 7 — seabed and caustics
    seabed: {
      floorScale: { v: 0.87, min: 0.05, max: 6, step: 0.01, label: "caustic cell size" },
      sandR: { v: 0.20, min: 0, max: 1, step: 0.01, label: "sand R" },
      sandG: { v: 0.34, min: 0, max: 1, step: 0.01, label: "sand G" },
      sandB: { v: 0.40, min: 0, max: 1, step: 0.01, label: "sand B" },
      sandGrain: { v: 0.20, min: 0, max: 1, step: 0.01, label: "sand grain" },
      causticStrength: { v: 1.85, min: 0, max: 3, step: 0.01, label: "caustic strength" },
      causticSharp: { v: 7.4, min: 1, max: 16, step: 0.1, label: "caustic sharpness" },
      causticSpeed: { v: 0.26, min: 0, max: 1.5, step: 0.01, label: "caustic speed" },
      causticBeat:  { v: 2.1, min: 1, max: 4, step: 0.02, label: "2nd layer scale" },
      causticFade:  { v: 0.20, min: 0, max: 1, step: 0.01, label: "caustic dist fade" },
    },
    // SECTION 8 — the water column
    column: {
      fogDensity: { v: 0.048, min: 0.002, max: 0.4, step: 0.002, label: "fog density" },
      absR: { v: 2.35, min: 0.5, max: 5, step: 0.05, label: "red absorption x" },
      absG: { v: 1.20, min: 0.3, max: 3, step: 0.05, label: "green absorption x" },
      absB: { v: 0.60, min: 0.1, max: 2, step: 0.05, label: "blue absorption x" },
    },
    // SECTION 9 — god rays
    rays: {
      rayStr:   { v: 1.72, min: 0, max: 4, step: 0.02, label: "ray strength" },
      rayFreq:  { v: 16.9, min: 1, max: 30, step: 0.1, label: "ray count" },
      rayReach: { v: 0.68, min: 0.1, max: 2, step: 0.01, label: "ray reach" },
      raySharp: { v: 6.85, min: 0.5, max: 12, step: 0.05, label: "ray sharpness" },
      rayDepthFade: { v: 0.85, min: 0, max: 1, step: 0.01, label: "ray depth fade" },
    },
    // SECTION 10 — particles
    particles: {
      bubbleAmount: { v: 1.0, min: 0, max: 3, step: 0.01, label: "bubbles" },
      bubbleSize:   { v: 0.0081, min: 0.0005, max: 0.03, step: 0.0002, label: "bubble size" },
      bubbleSpeed:  { v: 0.20, min: 0, max: 0.6, step: 0.005, label: "bubble rise" },
      moteAmount:   { v: 1.38, min: 0, max: 3, step: 0.01, label: "marine snow" },
      moteSize:     { v: 0.018, min: 0.002, max: 0.06, step: 0.001, label: "snow size" },
    },
    // SECTION 11 — grade
    grade: {
      exposure: { v: 1.20, min: 0.3, max: 2.5, step: 0.01, label: "exposure" },
      vignette: { v: 0.45, min: 0, max: 1.5, step: 0.01, label: "vignette" },
      grain:    { v: 0.012, min: 0, max: 0.08, step: 0.001, label: "grain" },
    },
  };
  const APPROVED = {"camY": 6.75, "horizon": 0.125, "seabedDepth": 30, "quality": 1, "sunAz": 0, "sunEl": 0.115, "sunStr": 0.22, "sunTight": 3200, "sunGlow": 0.55, "horR": 0.6, "horG": 0.86, "horB": 1, "zenR": 0.05, "zenG": 0.4, "zenB": 0.86, "skyGrad": 0.42, "cloudAmt": 0.5, "cloudCover": 0.84, "cloudScale": 1.85, "swellLen": 52, "swellAmp": 0.55, "medLen": 13, "medAmp": 0.2, "chopStr": 0.55, "waveSpeed": 0.55, "windDir": 0.3, "detailFall": 0.024, "seaR": 0.035, "seaG": 0.135, "seaB": 0.3, "fresnelF0": 0.022, "glitterPow": 260, "glitterStr": 2.1, "hazeAmt": 0.62, "floorScale": 6, "sandR": 0.45, "sandG": 0.44, "sandB": 0.78, "sandGrain": 0.87, "causticStrength": 2.39, "causticSharp": 14.8, "causticSpeed": 0.79, "causticBeat": 4, "causticFade": 0.32, "fogDensity": 0.03, "absR": 2.9, "absG": 1.2, "absB": 0.6, "rayStr": 2.56, "rayFreq": 27.8, "rayReach": 2, "raySharp": 6.3, "rayDepthFade": 0.92, "bubbleAmount": 2.63, "bubbleSize": 0.0067, "bubbleSpeed": 0.2, "moteAmount": 0.47, "moteSize": 0.013, "exposure": 1.2, "vignette": 0.45, "grain": 0.012};

  const RIG = {"towDepthM": 20, "laybackM": 47, "vesselX": 1, "fishScale": 3.4, "vesselYaw": 26, "towYawFollow": 0.12, "vesselZNear": -40, "vesselZFar": -86, "swathNearDeg": 3.5, "swathFarDeg": 50.5, "swathOpacity": 0.32, "returnsW": 120, "returnsL": 180, "returnsGain": 1.85};
  const SHOW = {"water": true, "vessel": true, "towfish": true, "cable": true, "swath": true, "returns": false, "wake": true, "debris": true, "coral": true};
  const MAT  = {"vessel": {"metalness": 0.45, "roughness": 0.58, "envInt": 1.9, "gain": 1.5}, "towfish": {"metalness": 0.72, "roughness": 0.46, "envInt": 1.8, "gain": 1.15}};

  // apply the approved tuning over the lab defaults
  for (const g in PARAMS) for (const k in PARAMS[g]) if (k in APPROVED) PARAMS[g][k].v = APPROVED[k];

  const START_Y = APPROVED.camY;          // above the waterline, vessel sailing
  /* The camera settles ABOVE the towfish, not level with it. With the seabed
     raised to 40 m the fish flies ~12.6 m off the bottom, and the shot only reads
     as "searching the seabed" if you are looking down past the fish onto the
     ground it is ensonifying. Level with it you see the fish against open water
     and the bottom falls out of frame. */
  /* The camera must stay ABOVE the towfish (-17.4 m at full deploy). Drop below
     it and the fish sits higher than the eye, so every degree of downward tilt
     pushes it further up the frame - at -21 m it ended jammed against the top
     edge behind the nav. -16 m is as low as it goes while keeping the fish in
     the upper third: 14 m off the bottom, looking down on both. */
  const WORK_Y  = -16.0;
  /* Pitch, not distance. The seabed "starts" wherever the view ray turns parallel
     to the floor, which is exactly uv.y = horizon - so how much bottom you see is
     set by the camera's downward tilt, not by how close it is. Holding the
     surface value all the way down leaves the floor in the bottom third however
     shallow the water gets. It now tilts down through the dive, the way you would
     actually look when you are working the bottom. */
  const HORIZON_SURF = APPROVED.horizon;
  const HORIZON_DEEP = 0.33;

  const VERT = `attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }`;

  const FRAG = `
  precision highp float;
  uniform vec2  uRes;
  uniform float uTime;
  uniform float camY, horizon, seabedDepth, quality;
  uniform float sunAz, sunEl, sunStr, sunTight, sunGlow;
  uniform float horR, horG, horB, zenR, zenG, zenB, skyGrad, cloudAmt, cloudCover, cloudScale;
  uniform float swellLen, swellAmp, medLen, medAmp, chopStr, waveSpeed, windDir, detailFall;
  uniform float seaR, seaG, seaB, fresnelF0, glitterPow, glitterStr, hazeAmt;
  uniform float floorScale, sandR, sandG, sandB, sandGrain;
  uniform float causticStrength, causticSharp, causticSpeed, causticBeat, causticFade;
  uniform float fogDensity, absR, absG, absB;
  uniform float rayStr, rayFreq, rayReach, raySharp, rayDepthFade;
  uniform float bubbleAmount, bubbleSize, bubbleSpeed, moteAmount, moteSize;
  uniform float exposure, vignette, grain;

  /* ==== SECTION 1 — NOISE (shared, not a look) ============================ */
  float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
  float nse(vec2 p){
    vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
    return mix(mix(h21(i),h21(i+vec2(1,0)),f.x), mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x), f.y);
  }
  float fbm(vec2 p){ float a=0.5,v=0.0; for(int i=0;i<5;i++){ v+=a*nse(p); p*=2.03; a*=0.5; } return v; }
  vec2 fbmGrad(vec2 p, float e){
    float c=fbm(p);
    return vec2(fbm(p+vec2(e,0.0))-c, fbm(p+vec2(0.0,e))-c)/e;
  }
  vec3 sunDirection(){ return normalize(vec3(sin(sunAz), sunEl, -cos(sunAz))); }

  /* ==== SECTION 3 — SKY, and the reflection source ======================== */
  vec3 skyColor(vec3 dir){
    float el = clamp(dir.y, -0.15, 1.0);
    vec3 c = mix(vec3(horR,horG,horB), vec3(zenR,zenG,zenB), pow(clamp(el,0.0,1.0), skyGrad));
    vec3 sd = sunDirection();
    float al = max(dot(normalize(dir), sd), 0.0);
    c += vec3(1.0,0.96,0.88)*pow(al,sunTight)*sunStr;
    c += vec3(1.0,0.94,0.84)*pow(al,12.0)*sunGlow*0.30;
    if (cloudAmt > 0.001 && dir.y > 0.012){
      float ct = 1.0/max(dir.y,0.012);
      vec2 cuv = (dir.xz*ct)*cloudScale*0.06 + vec2(uTime*0.004, uTime*0.002);
      float f = fbm(cuv) + fbm(cuv*2.7)*0.35;
      float m = smoothstep(cloudCover, cloudCover+0.30, f)*smoothstep(0.012,0.16,dir.y);
      c = mix(c, mix(vec3(0.72), vec3(1.0), smoothstep(0.0,0.6,f)), m*cloudAmt);
    }
    return c;
  }

  /* ==== SECTION 4 — THE WAVE FIELD, shared by both sides ==================
     One field. Above the surface it drives Fresnel and glitter; below it is the
     underside you look up at. Two wave fields would let the two halves of the
     frame disagree at the waterline. */
  void addWave(inout vec2 s, vec2 p, vec2 d, float len, float amp, float t){
    float k = 6.2831853/max(len,0.001);
    s += d*(cos(dot(d,p)*k + t)*amp*k);
  }
  float waveHeight(vec2 p){
    float t = uTime*waveSpeed;
    vec2 w = vec2(cos(windDir), sin(windDir));
    vec2 w2 = vec2(cos(windDir+0.7), sin(windDir+0.7));
    float k1 = 6.2831853/swellLen, k2 = 6.2831853/medLen;
    return sin(dot(w,p)*k1 + t*0.55)*swellAmp
         + sin(dot(w2,p)*k2 + t*1.05)*medAmp;
  }
  vec3 waveNormal(vec2 p, float dist){
    float t = uTime*waveSpeed;
    float detail = exp(-dist*detailFall);
    p += (vec2(fbm(p*0.018), fbm(p*0.018+7.3))-0.5)*9.0;
    vec2 s = vec2(0.0);
    vec2 w  = vec2(cos(windDir), sin(windDir));
    vec2 w2 = vec2(cos(windDir+0.7), sin(windDir+0.7));
    vec2 w3 = vec2(cos(windDir-0.9), sin(windDir-0.9));
    addWave(s,p,w, swellLen,       swellAmp,       t*0.55);
    addWave(s,p,w2,swellLen*0.63,  swellAmp*0.55,  t*0.61);
    float md = mix(0.35,1.0,detail);
    addWave(s,p,w2,medLen,         medAmp*md,      t*1.05);
    addWave(s,p,w3,medLen*0.66,    medAmp*0.72*md, t*1.24);
    addWave(s,p,w, medLen*0.41,    medAmp*0.46*md, t*1.51);
    vec2 drift = w*(t*0.6);
    s += fbmGrad(p*0.22+drift,       0.35)*chopStr*1.00*detail;
    s += fbmGrad(p*0.65-drift*1.7,   0.18)*chopStr*0.55*detail;
    if (quality > 0.5) s += fbmGrad(p*1.80+drift*2.6, 0.08)*chopStr*0.28*detail*detail;
    return normalize(vec3(-s.x, 1.0, -s.y));
  }

  /* ==== SECTION 6 — THE WATER COLUMN, four bands, BAND_BLEND 13 ========== */
  vec3 waterAt(float depthM){
    vec3 c = vec3(0.380,0.600,0.712);
    c = mix(c, vec3(0.059,0.294,0.439), smoothstep( 1.0,27.0,depthM));
    c = mix(c, vec3(0.027,0.166,0.408), smoothstep(17.0,43.0,depthM));
    c = mix(c, vec3(0.004,0.054,0.261), smoothstep(31.0,57.0,depthM));
    return c;
  }

  /* ==== SECTION 7 — CAUSTICS (ridged; cannot invert) ====================== */
  float causticLayer(vec2 p, float t){
    float v = 0.0;
    for (int i=0;i<3;i++){
      float fi=float(i);
      vec2 q = p*(1.0+fi*0.8) + vec2(t*(0.30+fi*0.11), -t*(0.22+fi*0.09));
      v += (1.0-abs(fbm(q)*2.0-1.0))*(1.0-fi*0.22);
    }
    return pow(clamp(v/2.34,0.0,1.0), causticSharp);
  }
  float caustics(vec2 uv, float t){
    float c  = causticLayer(uv, t);
    c += causticLayer(uv*causticBeat+23.0, -t*0.62)*0.55;
    if (quality > 0.5) c += causticLayer(uv*causticBeat*2.7+71.0, t*0.34)*0.28;
    return c;
  }

  /* ==== SECTION 5 — ABOVE THE SURFACE ==================================== */
  vec3 shadeAbove(vec3 ro, vec3 rd, float surfH){
    vec3 sd = sunDirection();
    if (rd.y >= -0.0008){
      vec3 c = skyColor(rd);
      float band = 1.0 - smoothstep(0.0, 0.06, rd.y);
      return mix(c, vec3(horR,horG,horB), band*0.55*hazeAmt);
    }
    float t = max(ro.y - surfH, 0.05)/(-rd.y);
    vec3  p = ro + rd*t;
    vec3  N = waveNormal(p.xz, t);
    float NdotV = max(dot(N,-rd), 0.0);
    float F = fresnelF0 + (1.0-fresnelF0)*pow(1.0-NdotV, 5.0);
    vec3 R = reflect(rd, N); R.y = abs(R.y);
    vec3 c = mix(vec3(seaR,seaG,seaB), skyColor(R), clamp(F,0.0,1.0));
    float facets = pow(max(dot(R,sd),0.0), glitterPow)*(0.65+0.35*fbm(p.xz*0.8+uTime*0.05));
    c += vec3(1.0,0.97,0.90)*facets*glitterStr*exp(-t*detailFall*0.55);
    float hz = 1.0 - exp(-t*0.0016);
    return mix(c, skyColor(vec3(rd.x,0.02,rd.z)), hz*hazeAmt);
  }

  /* ==== SECTIONS 6-10 — BELOW THE SURFACE ================================= */
  vec3 shadeBelow(vec3 ro, vec3 rd, vec2 frag, float surfH){
    vec3 sd = sunDirection();
    float eyeDepth = max(0.0, surfH - ro.y);
    float floorY = -seabedDepth;
    vec3 col; float underPath;

    if (rd.y > 0.0008){
      /* Looking UP: Snell's window. The whole sky is compressed into a cone of
         about 48.6 deg around vertical; outside it the surface is a mirror of the
         water below. It is the most recognisable thing about looking up from
         underwater and a plain "sky above" would lose it entirely. */
      float t = max(surfH - ro.y, 0.05)/rd.y;
      vec3  p = ro + rd*t;
      vec3  N = waveNormal(p.xz, t);
      float ang = acos(clamp(rd.y, -1.0, 1.0));
      float crit = 0.8483;                                   // asin(1/1.333)
      float win = smoothstep(crit + 0.10, crit - 0.16, ang);
      vec3 thr = refract(rd, -N, 1.0/1.333);
      vec3 through = (dot(thr,thr) < 0.0001) ? skyColor(vec3(rd.x,0.9,rd.z)) : skyColor(normalize(thr));
      col = mix(waterAt(eyeDepth + 6.0)*1.15, through, clamp(win,0.0,1.0));
      col += vec3(0.72,0.93,1.0)*pow(max(dot(reflect(rd,N),sd),0.0), 90.0)*0.25;
      underPath = t;
    } else {
      float t = (ro.y - floorY)/max(-rd.y, 1e-4);
      vec3  p = ro + rd*t;
      vec2 fuv = (p.xz + vec2(53.0,17.0))*(floorScale*0.1);
      float c = caustics(fuv, uTime*causticSpeed);
      float g = fbm(fuv*6.0)*sandGrain;
      float cFade = mix(1.0, exp(-t*0.09), causticFade);
      col  = vec3(sandR,sandG,sandB)*(0.55+g);
      col += vec3(0.85,0.95,1.0)*c*causticStrength*cFade;
      underPath = t;
    }

    /* Absorption over the optical path (spec §20/§22/§24). Normalised so the
       three multipliers shift COLOUR without also raising mean density. */
    vec3 ab = vec3(absR,absG,absB);
    ab /= max((ab.r+ab.g+ab.b)/3.0, 1e-4);
    col = mix(col, waterAt(eyeDepth), clamp(1.0 - exp(-underPath*fogDensity*ab), 0.0, 1.0));

    /* God rays, anchored to the REAL sun by inverting the ray construction.
       A hand-placed screen point drifts out of agreement with the glitter the
       moment the sun moves. */
    /* Underwater the shafts do not converge on the sun's raw direction: light
       entering the surface is REFRACTED, and Snell compresses the whole sky into
       a cone about vertical. Projecting the raw direction puts the vanishing
       point inside the frame, so the shafts fan out of a spot in mid-water
       instead of coming down from the surface. Bending it toward vertical first
       puts the origin above the top edge, where the sun actually is. */
    vec3 sdw = normalize(mix(sd, vec3(0.0, 1.0, 0.0), 0.35));
    if (sdw.z < -0.001){
      vec2 sunUV = vec2(-sdw.x/sdw.z, -sdw.y/sdw.z + horizon);
      vec2 sunFrag = vec2(sunUV.x*(uRes.y/uRes.x) + 0.5, sunUV.y + 0.5);
      vec2 d = frag - sunFrag; d.x *= uRes.x/uRes.y;
      float r = length(d);
      float a2 = atan(d.x, -d.y);
      float down = -d.y/max(r,1e-4);
      float shafts = pow(clamp(fbm(vec2(a2*rayFreq, uTime*0.04)),0.0,1.0), raySharp);
      shafts *= smoothstep(-0.10,0.70,down);
      shafts *= smoothstep(rayReach,0.0,r);
      shafts *= 0.70 + 0.30*sin(uTime*0.55 + a2*6.0);
      shafts *= mix(1.0, smoothstep(0.0,0.62,frag.y), rayDepthFade);
      col += vec3(0.72,0.93,1.0)*shafts*rayStr*0.25;
    }

    float bub = 0.0;
    for (int i=0;i<4;i++){
      float fi=float(i); float cx = h21(vec2(fi,3.0));
      for (int j=0;j<4;j++){
        float fj=float(j); float seed = h21(vec2(fi*9.1, fj*4.7));
        float y = fract(seed + uTime*bubbleSpeed*(0.55+seed*0.9));
        vec2 bp = vec2(cx + sin((y+seed)*9.0)*0.012, y*0.92+0.04) - frag;
        bp.x *= uRes.x/uRes.y;
        bub += smoothstep(bubbleSize*(0.5+seed)*(0.6+y*0.8), 0.0, length(bp))*(0.35+0.65*seed);
      }
    }
    col += vec3(0.85,0.96,1.0)*bub*bubbleAmount;

    float motes = 0.0;
    for (int i=0;i<12;i++){
      float fi=float(i);
      vec2 mp = vec2(h21(vec2(fi,1.3)), fract(h21(vec2(fi,5.9)) + uTime*0.006));
      vec2 dd = mp - frag; dd.x *= uRes.x/uRes.y;
      motes += smoothstep(moteSize*(0.4+h21(vec2(fi,8.8))), 0.0, length(dd))*0.5;
    }
    col += vec3(0.8,0.93,1.0)*motes*moteAmount*0.25;
    return col;
  }

  void main(){
    vec2 frag = gl_FragCoord.xy/uRes;
    vec2 uv   = (gl_FragCoord.xy - 0.5*uRes)/uRes.y;
    vec3 ro = vec3(0.0, camY, 0.0);
    vec3 rd = normalize(vec3(uv.x, uv.y - horizon, -1.0));

    /* THE CROSSING.
       A pinhole camera is either in air or in water - it cannot be half
       submerged, so this is one decision per frame, not per pixel. But switching
       on a hard camY > surfH makes the dive FLIP: a passing swell lifts the
       surface over the eye and the entire frame changes in one step.
       Blending over a band either side of the surface costs both branches only
       within that band, and makes the crossing continuous - which is the whole
       point of merging the two labs rather than keeping them apart. */
    float surfH = waveHeight(vec2(0.0, 0.0));
    float w = smoothstep(-0.9, 0.9, camY - surfH);
    vec3 col;
    if (w > 0.995)      col = shadeAbove(ro, rd, surfH);
    else if (w < 0.005) col = shadeBelow(ro, rd, frag, surfH);
    else                col = mix(shadeBelow(ro, rd, frag, surfH), shadeAbove(ro, rd, surfH), w);

    /* ==== SECTION 11 — GRADE (both sides, so the crossing is seamless) ===== */
    col *= exposure;
    col = col/(1.0 + col*0.55);
    float lum = dot(col, vec3(0.299,0.587,0.114));
    col = mix(vec3(lum), col, 1.18);
    vec2 vc = (frag-0.5)*vec2(1.06,1.0);
    float vigAmt = mix(0.22, vignette, clamp(-camY/8.0, 0.0, 1.0));  // stronger under
    col *= clamp(1.0 - vigAmt*pow(clamp(length(vc)*1.42,0.0,1.0),2.15), 0.0, 1.0);
    col += (h21(gl_FragCoord.xy + fract(uTime)) - 0.5)*grain;
    gl_FragColor = vec4(clamp(col,0.0,1.0), 1.0);
  }
  `;

  const clamp01=(v)=>Math.min(1,Math.max(0,v));
  const span=(p,a,b)=>clamp01((p-a)/(b-a));
  const easeInOut=(t)=>(t<0.5?2*t*t:1-Math.pow(-2*t+2,2)/2);
  const descentPitch=(d)=>-Math.sin(Math.PI*d)*0.26;
  const S_IDLE=0.18, S_DEPLOY=0.62, S_SEARCH=0.80;   // aligned to the motion above

  const cv = document.getElementById("gl");
  const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias:true, alpha:false });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.6));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.autoClear = false;
  renderer.localClippingEnabled = true;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const CLIP_ABOVE = [new THREE.Plane(new THREE.Vector3(0,1,0), 0)];

  const waterScene = new THREE.Scene();
  const waterCam = new THREE.OrthographicCamera(-1,1,1,-1,0,1);
  const wu = { uRes:{value:new THREE.Vector2(1,1)}, uTime:{value:0} };
  const WP = {};
  for (const g in PARAMS) for (const k in PARAMS[g]) { WP[k]=PARAMS[g][k]; wu[k]={value:PARAMS[g][k].v}; }
  waterScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2,2), new THREE.ShaderMaterial({
    uniforms: wu,
    vertexShader: VERT.replace("attribute vec2 p;","").replace("vec4(p, 0.0, 1.0)","vec4(position.xy, 0.0, 1.0)"),
    fragmentShader: FRAG, depthTest:false, depthWrite:false,
  })));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50,1,0.4,5000);
  /* LIGHTING.
   * The rig was lit for air while sitting in water, which is why it read as a
   * silhouette: a single hard key, no bounce, and an environment made of sky that
   * gives metal nothing blue to reflect once you are under. Four sources now,
   * and the balance between them shifts as the camera submerges. */
  const sun = new THREE.DirectionalLight(0xfff2dc, 2.6);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.near = 1; sun.shadow.camera.far = 420;
  sun.shadow.camera.left = -34; sun.shadow.camera.right = 34;
  sun.shadow.camera.top = 34; sun.shadow.camera.bottom = -34;
  sun.shadow.bias = -0.0012; sun.shadow.normalBias = 0.35;
  const sunTarget = new THREE.Object3D(); scene.add(sunTarget);
  sun.target = sunTarget; scene.add(sun);

  /* Bounce. Underwater almost all the light on a hull is scattered light arriving
     from every direction, not the beam - without it the shaded side is black. */
  const hemi = new THREE.HemisphereLight(0xbfe4ff, 0x0a2740, 1.1); scene.add(hemi);

  /* Downwelling fill: the lit surface overhead, which is the dominant source once
     you are under. Aimed straight down so the tops of things catch it. */
  const down = new THREE.DirectionalLight(0x9fd8f2, 0.0);
  down.position.set(0, 200, 0); scene.add(down);

  /* A cool rim from behind so the hull separates from the water rather than
     dissolving into it. */
  const rim = new THREE.DirectionalLight(0x7fc8ee, 0.0);
  rim.position.set(-160, 40, 120); scene.add(rim);

  scene.fog = new THREE.Fog(0x0f4b70, 30, 460);

  /* The sea shader forms its ray as vec3(uv.x, uv.y - horizon, -1): a principal
     point OFFSET, not a pitched camera. lookAt() would rotate instead and the two
     only agree on the centre pixel - the error reads as the rig floating clear of
     the water. Shear the projection to match exactly. */
  function matchCamera(){
    camera.fov = 2*Math.atan(0.5)*180/Math.PI;
    camera.position.set(0, WP.camY.v, 0);
    camera.rotation.set(0,0,0);
    camera.updateMatrixWorld();
    camera.updateProjectionMatrix();
    camera.projectionMatrix.elements[9] = -2.0*WP.horizon.v;
    camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    const az=WP.sunAz.v, el=WP.sunEl.v;
    sun.position.set(Math.sin(az)*400, el*400+120, -Math.cos(az)*400);
  }

  const draco = new DRACOLoader();
  draco.setDecoderPath("/draco/gltf/");
  const gltf = new GLTFLoader(); gltf.setDRACOLoader(draco);
  const vesselGroup=new THREE.Group(); scene.add(vesselGroup);
  const fishGroup=new THREE.Group(), fishScale=new THREE.Group();
  fishGroup.add(fishScale); scene.add(fishGroup);
  const MATS=[];
  /* TWO environments, because what the metal reflects changes at the waterline.
     Above: sky over sea. Below: a lit ceiling fading to the deep - reflecting a
     sky environment underwater is what leaves the hull looking dead. */
  const pmrem = new THREE.PMREMGenerator(renderer);
  function makeEnv(stops){
    const c=document.createElement("canvas"); c.width=8; c.height=128;
    const x=c.getContext("2d"); const g=x.createLinearGradient(0,0,0,128);
    for (const [at,col] of stops) g.addColorStop(at,col);
    x.fillStyle=g; x.fillRect(0,0,8,128);
    const tex=new THREE.CanvasTexture(c);
    tex.mapping=THREE.EquirectangularReflectionMapping; tex.colorSpace=THREE.SRGBColorSpace;
    const rt=pmrem.fromEquirectangular(tex).texture; tex.dispose(); return rt;
  }
  /* The HARD BAND at the horizon is the whole trick. A metal shows only what it
     reflects, so against a smooth gradient it has nothing to return but mush and
     reads as grey plastic. The thin blown-out strip where sky meets sea gives the
     hull a crisp reflected horizon line that slides along the plating as the boat
     rolls - that moving line, not the metalness number, is what the eye reads as
     metal. Underwater the same job is done by the bright Snell cone overhead. */
  /* THE LOWER HEMISPHERE IS NOT SCENERY - IT IS THE LIGHT.
     A ship's sides are vertical, so they reflect mostly what is BELOW the
     horizon. The first version had that half running to #04121f, near black,
     and once the hull went properly metallic it faithfully mirrored a dark
     ocean and disappeared. Sea seen from a few metres up is not black: it is a
     mid blue-grey carrying the whole sky's bounce. Brightening this half is
     what lets metal be metal without going dark - for a metal, the environment
     IS the exposure. */
  const ENV_AIR   = makeEnv([[0,"#9fd8ff"],[.40,"#eaf6ff"],[.487,"#ffffff"],
                             [.503,"#3d8fbe"],[.70,"#2a6d96"],[1,"#17435e"]]);
  const ENV_WATER = makeEnv([[0,"#f2ffff"],[.14,"#d6f2ff"],[.32,"#7cc4e4"],
                             [.62,"#2f73a0"],[1,"#15405e"]]);
  scene.environment = ENV_AIR;
  let envIsAir = true;
  /* Only the TOWFISH casts. A hull 20 m above the bottom would have its shadow
     scattered into nothing long before it got there - casting it anyway put a
     huge hard blob on the seabed, which read as a rock, not a shadow. The fish is
     12 m off the floor and its shadow is the one that carries information: it is
     most of what tells you how high the thing is flying. */
  /* THE REASON THE HULL WAS DARK, and it was never the lighting.
   *
   * Neither GLB declares metallicFactor or roughnessFactor, and glTF defaults
   * BOTH to 1.0 when absent. So three loaded a fully metallic, fully rough
   * surface - and a metal has no diffuse term at all: it shows only what it
   * reflects, blurred to almost nothing at roughness 1. The texture's actual
   * colour was never reaching the screen. No amount of extra light fixes that;
   * adding lights to a mirror just makes a slightly brighter mirror.
   *
   * A painted steel hull is a dielectric: metalness near zero, mid roughness.
   * The towfish keeps a little more because of its bare fittings.
   *
   * ...but fully dielectric read DULL, so the vessel now sits part way: enough
   * metalness for the environment to carry the surface, enough albedo left that
   * the texture still shows. ROUGHNESS is what actually sells it - dropping it
   * tightens the reflection into a highlight with an edge. Going to metalness 1
   * is the wrong lever: it deletes the diffuse term entirely and walks straight
   * back into the dark hull above. */
  /* AND THE REASON THE NUMBERS ABOVE DID NOTHING: both GLBs carry a
   * metallicRoughnessTexture. In glTF the scalar is a FACTOR, not a value -
   * three multiplies it by the map: metalness *= B, roughness *= G. Measured
   * over the actual textures: vessel B avg 0.307, towfish B avg 0.108. So
   * metalness 0.90 on the fish was really rendering 0.097 and stayed a
   * dielectric however high the number went.
   *
   * These maps are Tripo's generated guess, not an authored finish, so the
   * METALNESS map is deleted outright and the number rules. The ROUGHNESS map
   * is kept - it is the only surface variation the model has, and a uniform
   * roughness is exactly what makes CG metal look like a render. Its G averages
   * ~0.40, so MAT.roughness is a factor: the effective value is ~0.4x it. */
  function collect(r, cast, m){ r.traverse(o=>{ if(o.isMesh&&o.material){
    o.castShadow=!!cast; o.receiveShadow=true;
    o.material.metalnessMap = null;
    o.material.metalness = m.metalness;
    o.material.roughness = m.roughness;
    o.material.envMapIntensity = m.envInt;
    /* GAIN on the base colour. Two different brightness paths exist here and
       they are not interchangeable: envMapIntensity scales only what the surface
       REFLECTS, while material.color multiplies the base colour texture that
       feeds the diffuse. The hull reads dark because the texture itself is a
       dark navy, so the reflection lever cannot reach it. Colour is linear and
       three does not clamp it at 1, so this is a straight gain - and under ACES
       it rolls off into the highlights rather than clipping to white. */
    o.material.color.setScalar(m.gain);
    o.material.needsUpdate = true;
    MATS.push(o.material);} }); }
  gltf.load(VESSEL_URL,(r)=>{ if (disposed) { r.scene.traverse(o=>{o.geometry?.dispose?.(); const m=o.material; Array.isArray(m)?m.forEach(x=>x?.dispose?.()):m?.dispose?.();}); return; } vesselGroup.add(r.scene);collect(r.scene,false,MAT.vessel);});
  gltf.load(TOWFISH_URL,(r)=>{ if (disposed) { r.scene.traverse(o=>{o.geometry?.dispose?.(); const m=o.material; Array.isArray(m)?m.forEach(x=>x?.dispose?.()):m?.dispose?.();}); return; } fishScale.add(r.scene);collect(r.scene,true,MAT.towfish);});

  const CSEG=30;
  const cableGeo=new THREE.BufferGeometry();
  cableGeo.setAttribute("position",new THREE.BufferAttribute(new Float32Array((CSEG+1)*3),3));
  const cable=new THREE.Line(cableGeo,new THREE.LineBasicMaterial({color:0xc4f8ff,transparent:true,opacity:.5}));
  scene.add(cable);

  function beam(sign){
    const m=new THREE.Mesh(new THREE.BufferGeometry(),new THREE.ShaderMaterial({
      transparent:true,side:THREE.DoubleSide,depthWrite:false,blending:THREE.AdditiveBlending,
      uniforms:{uOpacity:{value:0}},
      vertexShader:"varying float vY; void main(){vY=position.y; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}",
      fragmentShader:"uniform float uOpacity; varying float vY; void main(){ float d=clamp(-vY,0.0,1.0);"+
        "float a=uOpacity*(1.0-d*0.78)*smoothstep(0.0,0.18,d); gl_FragColor=vec4(0.769,0.973,1.0,a); }",
    }));
    const n=Math.tan(THREE.MathUtils.degToRad(RIG.swathNearDeg));
    const f=Math.tan(THREE.MathUtils.degToRad(RIG.swathFarDeg));
    const g=new THREE.BufferGeometry();
    g.setAttribute("position",new THREE.BufferAttribute(new Float32Array([0,0,0, sign*n,-1,0, sign*f,-1,0]),3));
    m.geometry=g; return m;
  }
  const swath=new THREE.Group(); const bL=beam(-1), bR=beam(1);
  swath.add(bL,bR); scene.add(swath);

  const wakeMat=new THREE.ShaderMaterial({
    transparent:true,depthWrite:false,side:THREE.DoubleSide,
    uniforms:{uTime:{value:0},uOpacity:{value:0.5}},
    vertexShader:"varying vec2 vUv; void main(){vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}",
    fragmentShader:`
      uniform float uTime,uOpacity; varying vec2 vUv;
      float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
      float n(vec2 p){vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f);
        return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
      void main(){ float al=vUv.y; float ac=abs(vUv.x-0.5)*2.0;
        float sp=0.25+al*0.75; float core=smoothstep(sp,sp*0.35,ac);
        float foam=n(vec2(vUv.x*38.0,vUv.y*10.0-uTime*0.6));
        gl_FragColor=vec4(0.88,0.96,1.0, clamp(core*(0.35+0.65*foam)*(1.0-al)*uOpacity,0.0,1.0)); }`,
  });
  const wake=new THREE.Mesh(new THREE.PlaneGeometry(46,150),wakeMat);
  wake.rotation.x=-Math.PI/2; scene.add(wake);

  /* The seabed is drawn by the shader, so there is no geometry for a shadow to
     fall on. This invisible plane sits just above it and receives only shadow -
     which is what puts the towfish's shadow on the bottom, and that shadow is
     most of what tells you how high it is flying. */
  const shadowCatcher = new THREE.Mesh(new THREE.PlaneGeometry(700,700),
    new THREE.ShadowMaterial({ opacity:0.30, transparent:true }));
  shadowCatcher.rotation.x=-Math.PI/2; shadowCatcher.receiveShadow=true;
  scene.add(shadowCatcher);

  /* ------------------------------------------------------------ seabed life
     The bottom is drawn by the shader, so anything ON it has to be geometry.
     It earns the polygons twice over: an empty floor gives the eye nothing to
     judge SCALE or MOTION against - the towfish could be flying 2 m or 20 m up
     and you could not tell - and a real survey site is cluttered, which is the
     entire reason the model has to be good.

     SEEDED, not Math.random(). A scene that reshuffles on every reload cannot be
     tuned, and a rock that moves between two screenshots is an hour lost to a
     bug that was never there. */
  function rng(seed){ return function(){ seed|=0; seed=seed+0x6D2B79F5|0;
    let t=Math.imul(seed^seed>>>15,1|seed); t=t+Math.imul(t^t>>>7,61|t)^t;
    return ((t^t>>>14)>>>0)/4294967296; }; }

  const seabed = new THREE.Group(); scene.add(seabed);

  /* Deformed by POSITION, not per vertex. IcosahedronGeometry is non-indexed, so
     every corner is duplicated once per face - jitter them independently and the
     solid tears itself open along every edge. Driving the displacement from the
     original coordinate makes the duplicates agree. */
  function lumpy(geo, amt){
    const a=geo.getAttribute("position");
    for(let i=0;i<a.count;i++){
      const x=a.getX(i), y=a.getY(i), z=a.getZ(i);
      const k=1+amt*(Math.sin(x*4.1+y*2.3)*0.5+Math.cos(z*3.7-x*1.9)*0.5);
      a.setXYZ(i,x*k,y*k,z*k);
    }
    geo.computeVertexNormals(); return geo;
  }

  /* One InstancedMesh per kind: four draw calls for the whole bottom. */
  function scatter(mesh, n, rnd, place){
    const m=new THREE.Matrix4(), q=new THREE.Quaternion(), e=new THREE.Euler();
    const pos=new THREE.Vector3(), scl=new THREE.Vector3();
    for(let i=0;i<n;i++){
      place(i,rnd,pos,scl,e);
      q.setFromEuler(e);
      mesh.setMatrixAt(i, m.compose(pos,q,scl));
    }
    mesh.instanceMatrix.needsUpdate=true;
    /* castShadow stays OFF, the same call already made for the hull. A 30 m water
       column scatters a small object's shadow into nothing long before it reaches
       the floor, and the towfish's shadow is the one carrying information -
       letting fifty rocks compete with it buries the only cue that says how high
       the fish is flying. */
    mesh.castShadow=false; mesh.receiveShadow=true;
    seabed.add(mesh);
    return mesh;
  }

  /* A LANE, not a rectangle: dense along the track the fish sweeps, thinning to
     the sides. rnd()*rnd() biases toward zero, which piles the clutter near the
     lane centre without a hard edge where it stops. Clutter matters where the
     sonar is looking; scattering it evenly just costs fill rate out at the fog
     limit where nothing is legible anyway. */
  function lane(rnd, spread, zNear, zFar){
    const side = rnd()<0.5?-1:1;
    return [ side*spread*rnd()*rnd() + (rnd()-0.5)*10,
             zNear + (zFar-zNear)*rnd() ];
  }

  // ---- rubble
  const rockGeo = lumpy(new THREE.IcosahedronGeometry(1,0), 0.55);
  const rockMat = new THREE.MeshStandardMaterial({color:0x6b6f66, roughness:0.95, metalness:0.0});
  const rocks = new THREE.InstancedMesh(rockGeo, rockMat, 58);
  scatter(rocks, 58, rng(20260914), (i,rnd,pos,scl,e)=>{
    const [x,z]=lane(rnd, 58, -8, -168);
    const r = 0.35 + rnd()*rnd()*2.4;
    /* SUNK, not resting. A rock on a soft bottom is partly buried; the giveaway
       of dressed CG terrain is objects sitting on the surface like props on a
       table. Dropping each one about a third of its radius reads as sediment. */
    pos.set(x, r*0.62 - r*0.34, z);
    scl.set(r*(0.8+rnd()*0.5), r*(0.55+rnd()*0.4), r*(0.8+rnd()*0.5));
    e.set(rnd()*3.14, rnd()*6.28, rnd()*3.14);
  });

  // ---- broken slabs: flatter and angular, man-made rather than geological
  const slabMat = new THREE.MeshStandardMaterial({color:0x585d5c, roughness:0.88, metalness:0.05});
  const slabs = new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1), slabMat, 16);
  scatter(slabs, 16, rng(77003), (i,rnd,pos,scl,e)=>{
    const [x,z]=lane(rnd, 46, -14, -150);
    const w=1.2+rnd()*3.4;
    pos.set(x, 0.18, z);
    scl.set(w, 0.22+rnd()*0.35, w*(0.4+rnd()*0.7));
    /* Tipped, never level. Debris that has been through surf and settled does
       not lie flat, and a flat slab reads instantly as a placed box. */
    e.set((rnd()-0.5)*0.5, rnd()*6.28, (rnd()-0.5)*0.5);
  });

  // ---- coral: branching colonies
  /* Built from ONE tapered branch, instanced. A colony is not a random spray:
     coral radiates from a holdfast, so every branch shares an origin and tilts
     OUTWARD by an angle that grows with how high up the colony it starts. That
     single rule is most of what separates coral from scattered sticks. */
  const branchGeo = new THREE.CylinderGeometry(0.055, 0.17, 1, 5, 1, true);
  branchGeo.translate(0, 0.5, 0);
  const coralMat = new THREE.MeshStandardMaterial({color:0xa8614c, roughness:0.92,
    metalness:0.0, side:THREE.DoubleSide});
  const CLUSTERS = 11, PER = 14;
  const coral = new THREE.InstancedMesh(branchGeo, coralMat, CLUSTERS*PER);
  {
    const rnd = rng(5150), sites=[];
    for(let c=0;c<CLUSTERS;c++){ const [x,z]=lane(rnd, 50, -18, -160); sites.push([x,z,0.6+rnd()*1.5]); }
    let i=0;
    const m=new THREE.Matrix4(), q=new THREE.Quaternion(), e=new THREE.Euler();
    const pos=new THREE.Vector3(), scl=new THREE.Vector3();
    for(const site of sites){
      const cx=site[0], cz=site[1], size=site[2];
      for(let b=0;b<PER;b++){
        const az = (b/PER)*6.2831 + rnd()*0.5;
        const up = rnd();                       // how high on the colony it starts
        const tilt = 0.15 + up*0.85 + rnd()*0.25;
        const len = size*(1.4 - up*0.7)*(0.7+rnd()*0.6);
        const rad = size*up*0.45;
        pos.set(cx + Math.cos(az)*rad, size*0.15 + up*size*0.5, cz + Math.sin(az)*rad);
        scl.set(size*0.55, len, size*0.55);
        e.set(Math.cos(az)*tilt, az, Math.sin(az)*tilt, "ZYX");
        q.setFromEuler(e);
        coral.setMatrixAt(i++, m.compose(pos,q,scl));
      }
    }
    coral.instanceMatrix.needsUpdate=true;
    coral.castShadow=false; coral.receiveShadow=true;
    seabed.add(coral);
  }

  // ---- coral: massive heads, the rounded kind
  const headMat = new THREE.MeshStandardMaterial({color:0x9a8455, roughness:0.95, metalness:0.0});
  const headGeo = lumpy(new THREE.SphereGeometry(1, 12, 8), 0.28);
  const heads = new THREE.InstancedMesh(headGeo, headMat, 13);
  scatter(heads, 13, rng(31337), (i,rnd,pos,scl,e)=>{
    const [x,z]=lane(rnd, 44, -20, -155);
    const r=0.7+rnd()*1.7;
    pos.set(x, r*0.42, z);
    scl.set(r, r*0.62, r*(0.85+rnd()*0.3));
    e.set(0, rnd()*6.28, 0);
  });

  rocks.visible = slabs.visible = SHOW.debris;
  coral.visible = heads.visible = SHOW.coral;

  // ---------------------------------------------------------------- scroll
  const track=document.getElementById("hero");
  let pinned=null;
  window.__heroProgress=(v)=>{ pinned=(v==null)?null:clamp01(Number(v)); return pinned; };
  function readProgress(){
    if (pinned!==null) return pinned;
    const r=track.getBoundingClientRect();
    const s=r.height-innerHeight;
    return clamp01(s>0 ? -r.top/s : 0);
  }
  /* The dive LEADS the deployment: you are already underwater before the winch
     starts, so the descent is something you watch rather than something that
     happens to the camera. */
  const camYFor = (p) => START_Y + (WORK_Y-START_Y)*easeInOut(span(p,0.14,0.52));
  /* The descent was starting at 0.34 and still running at 0.86, which reads as
     lag: you scroll and nothing happens for a third of the hero. It now begins
     almost as soon as the dive does and finishes with room to spare, so the
     contact stage is a hold rather than the tail of the motion. */
  const deployFor = (p) => easeInOut(span(p,0.18,0.62));

  const el={ copy:document.getElementById("heroCopy"), foot:document.getElementById("heroFoot"),
    stats:document.getElementById("stats"), inst:document.getElementById("instruments"),
    cue:document.getElementById("cue"), swap:[...document.querySelectorAll("#swap b")],
    sub:document.getElementById("hudSub"), depth:document.getElementById("rdoDepth"),
    lay:document.getElementById("rdoLay"), alt:document.getElementById("rdoAlt"),
    ping:document.getElementById("ping") };
  const SUBS=["28 m survey vessel<br>towfish stowed in the A-frame",
    "winch paying out<br>fish trimming nose-down",
    "swath open · 120 m across-track<br>waterfall painting",
    "ghost_net · 0.91 calibrated<br>review_only — awaiting sign-off"];
  const stageIdx=(p)=> p<S_IDLE?0 : p<S_DEPLOY?1 : p<S_SEARCH?2 : 3;
  let shown=-1, pingN=18402;

  function resize(){
    const w=cv.clientWidth,h=cv.clientHeight;
    renderer.setSize(w,h,false);
    const pr=renderer.getPixelRatio();
    wu.uRes.value.set(w*pr,h*pr);
    camera.aspect=w/h;
  }
  window.addEventListener("resize", resize); resize();

  const clock=new THREE.Clock();
  /* THE SEA SURFACE, IN JS - the same two terms as the shader's waveHeight(),
     sampled from the same PARAMS and fed the same clock, so a body that rides
     the sea rides the sea the viewer is actually looking at. Anything else is
     guesswork: the old hull bob was an invented sin(t*0.6) with no relation to
     the water under it, and the moment a second body joins it that shows. At a
     52 m swell two bodies 47 m apart are close to ANTIPHASE - one clock would
     have the boat and the fish rising together, which a real swell never does.
     If the shader's waveHeight() ever changes, this changes with it. */
  function seaH(x, z, t){
    const tt = t*WP.waveSpeed.v;
    const d = WP.windDir.v, d2 = d + 0.7;
    const k1 = 6.2831853/WP.swellLen.v, k2 = 6.2831853/WP.medLen.v;
    return Math.sin((Math.cos(d)*x  + Math.sin(d)*z )*k1 + tt*0.55)*WP.swellAmp.v
         + Math.sin((Math.cos(d2)*x + Math.sin(d2)*z)*k2 + tt*1.05)*WP.medAmp.v;
  }
  const HULL_HALF_LEN = 9.0, HULL_HALF_BEAM = 3.2;
  const cablePos=cableGeo.getAttribute("position");
  let fishWaveTilt=0;
  function frame(){
    rafId = requestAnimationFrame(frame);
    const r=track.getBoundingClientRect();
    if (document.hidden) return;
    if (pinned===null && (r.bottom<0 || r.top>innerHeight)) return;
    const dt=Math.min(clock.getDelta(),.05), t=clock.elapsedTime;
    const p=readProgress();

    WP.camY.v=camYFor(p); wu.camY.value=WP.camY.v;
    WP.horizon.v = HORIZON_SURF + (HORIZON_DEEP-HORIZON_SURF)*easeInOut(span(p,0.20,0.66));
    wu.horizon.value = WP.horizon.v;
    matchCamera();

    const deploy=deployFor(p);
    const ping=span(p,S_DEPLOY-0.06,S_SEARCH-0.1);
    const seabedY=-WP.seabedDepth.v;
    const vx=RIG.vesselX;
    /* The vessel is CLOSER for the opening shot and falls back as the camera
       dives. Holding it at the near distance would put the towfish behind the
       camera by the contact stage - at 47 m of layback the fish ends up ahead of
       the vessel's start, so the near framing and the deep framing genuinely
       cannot be the same number. */
    const vz = RIG.vesselZNear + (RIG.vesselZFar - RIG.vesselZNear)*easeInOut(span(p,0.08,0.46));
    const yaw = RIG.vesselYaw*Math.PI/180;

    /* FOUR SAMPLES, not one. A hull does not sit at a point - it spans the wave,
       so it heaves on the AVERAGE of the water under it and pitches and rolls on
       the DIFFERENCE. Sampling one point gives a boat that bobs like a cork and
       stays dead level, which is the giveaway of a faked sea. Fore/aft sets
       pitch, port/stbd sets roll, and the four together damp the heave the way
       real length does: a long hull ignores short waves. */
    const fwd = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw));
    const bm  = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
    const hF = seaH(vx + fwd.x*HULL_HALF_LEN,  vz + fwd.z*HULL_HALF_LEN,  t);
    const hA = seaH(vx - fwd.x*HULL_HALF_LEN,  vz - fwd.z*HULL_HALF_LEN,  t);
    const hP = seaH(vx + bm.x*HULL_HALF_BEAM,  vz + bm.z*HULL_HALF_BEAM,  t);
    const hS = seaH(vx - bm.x*HULL_HALF_BEAM,  vz - bm.z*HULL_HALF_BEAM,  t);
    const heave = (hF+hA+hP+hS)*0.25;
    vesselGroup.position.set(vx, heave, vz);
    /* Damped: a displacement hull has mass and does not take the full slope of
       the water. 0.55 of the true pitch angle and 0.7 of the roll. */
    vesselGroup.rotation.set(Math.atan2(hA-hF, 2*HULL_HALF_LEN)*0.55, yaw,
                             Math.atan2(hS-hP, 2*HULL_HALF_BEAM)*0.7);

    /* Astern is the vessel's own +Z, turned by the yaw - so the cable still
       leaves the transom and the fish trails along the heading rather than along
       the world axis. Yawing only the hull would leave the tow gear pointing
       somewhere the ship is not going. */
    const astern = new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw));
    const towPt = new THREE.Vector3(vx,2.6+heave,vz).addScaledVector(astern, 13.2);
    /* The tow line lags the turn. A towed body follows the track the ship has
       already made, not its instantaneous heading, so the cable straightens out
       behind a turning vessel rather than swinging with the stern. That is both
       more truthful and what keeps the fish inside the frame: at the full yaw it
       ended up 29 m off axis at 32 m range, past the right edge. */
    const towYaw = yaw * RIG.towYawFollow;
    const trail = new THREE.Vector3(Math.sin(towYaw), 0, Math.cos(towYaw));
    const fishPos = towPt.clone().addScaledVector(trail, deploy*RIG.laybackM);
    fishPos.y = 2.6 - RIG.towDepthM*deploy;
    fishPos.x += deploy*Math.sin(t*.7)*1.4;
    /* HEAVE, in two regimes, because the fish changes what it is attached to.
       On the davit it is part of the ship and moves with the hull, full stop.
       Once it is in the water it rides the sea's OWN surface at its own position
       - which is not the ship's, and at 47 m of layback usually not even the same
       part of the wave.
       Then it sinks out of the motion. Deep-water orbital velocity decays as
       exp(-2*pi*d/L): half a wavelength down, 4% of the surface heave is left.
       That is the real reason a towed fish is a steadier sensor platform than the
       boat towing it, and it is why the bob has to FADE rather than switch off. */
    const onDavit = 1 - clamp01(deploy/0.10);
    const sh = seaH(fishPos.x, fishPos.z, t);
    const ride = Math.exp(-6.2831853*Math.max(0, sh-fishPos.y)/Math.max(4, WP.swellLen.v));
    fishPos.y += heave*onDavit + sh*ride*(1-onDavit);
    fishWaveTilt = Math.atan2(
      seaH(fishPos.x+trail.x*2.4, fishPos.z+trail.z*2.4, t) -
      seaH(fishPos.x-trail.x*2.4, fishPos.z-trail.z*2.4, t), 4.8) * ride;

    fishGroup.position.copy(fishPos);
    fishGroup.rotation.set(descentPitch(deploy)+fishWaveTilt+Math.sin(t*.9)*.04*deploy,
                           towYaw + Math.sin(t*.55)*.05*deploy, 0);
    fishScale.scale.setScalar(RIG.fishScale);

    const A=towPt.clone(), B=fishGroup.position.clone();
    const len=A.distanceTo(B);
    const sag=len*.16*Math.sin(Math.PI*Math.min(1,deploy))+len*.04;
    const M=A.clone().lerp(B,.5); M.y-=sag;
    new THREE.QuadraticBezierCurve3(A,M,B).getPoints(CSEG).forEach((q,i)=>cablePos.setXYZ(i,q.x,q.y,q.z));
    cablePos.needsUpdate=true; cableGeo.computeBoundingSphere();

    const alt=Math.max(1,fishGroup.position.y-seabedY);
    swath.position.copy(fishGroup.position); swath.scale.setScalar(alt);
    const pulse=ping>.25 ? .30+Math.sin(t*2.2)*.10 : 0;
    bL.material.uniforms.uOpacity.value=pulse*ping*RIG.swathOpacity/0.30;
    bR.material.uniforms.uOpacity.value=bL.material.uniforms.uOpacity.value;

    wake.position.copy(towPt).addScaledVector(astern, 75); wake.position.y=.12;
    wake.rotation.set(-Math.PI/2, 0, -yaw);
    wakeMat.uniforms.uTime.value=t;
    wake.visible = SHOW.wake && WP.camY.v>-1.0;

    /* Shift the rig as the camera submerges. Under water the beam is attenuated
       and scattered, so the key comes down and the bounce, downwelling fill and
       rim come up - that is what stops the hull going to silhouette. */
    const sub = clamp01(-WP.camY.v/9);
    sun.intensity  = 2.6 - 1.5*sub;
    hemi.intensity = 1.1 + 1.5*sub;
    hemi.color.set(sub>0.5 ? 0x9fe0ff : 0xbfe4ff);
    hemi.groundColor.set(sub>0.5 ? 0x16506f : 0x0a2740);
    down.intensity = 1.35*sub;
    rim.intensity  = 0.85*sub;
    sunTarget.position.copy(fishGroup.position);
    seabed.position.y = seabedY;
    shadowCatcher.position.set(vx, seabedY+0.05, fishGroup.position.z);
    shadowCatcher.visible = sub > 0.05;
    if ((sub>0.5) === envIsAir){ envIsAir = !(sub>0.5); scene.environment = envIsAir?ENV_AIR:ENV_WATER;
      for (const m of MATS) m.needsUpdate = true; }

    const d=Math.max(0,-WP.camY.v);
    scene.fog.color.setRGB(0.380+(0.004-0.380)*clamp01(d/50),
                           0.600+(0.054-0.600)*clamp01(d/50),
                           0.712+(0.261-0.712)*clamp01(d/50));
    scene.fog.near = WP.camY.v>0?120:25;
    scene.fog.far  = WP.camY.v>0?900:320;
    renderer.clippingPlanes = (WP.camY.v>0) ? CLIP_ABOVE : [];

    wu.uTime.value=t;
    renderer.clear();
    renderer.render(waterScene,waterCam);
    renderer.clearDepth();
    renderer.render(scene,camera);

    // ---- overlay ----
    const out=clamp01((p-0.04)/0.18);
    el.copy.style.opacity=String(1-out);
    el.copy.style.transform="translateY("+(-out*38).toFixed(1)+"px)";
    el.foot.style.opacity=String(1-out);
    el.foot.style.transform="translateY("+(out*30).toFixed(1)+"px)";
    el.copy.style.pointerEvents=el.foot.style.pointerEvents = out>0.6?"none":"auto";
    el.stats.style.opacity=String(1-out);
    el.inst.style.opacity=String(clamp01((p-0.16)/0.14));
    el.cue.style.opacity=p>0.04?"0":"1";
    el.depth.textContent=(RIG.towDepthM*deploy).toFixed(1)+" m";
    el.lay.textContent=(deploy*RIG.laybackM).toFixed(1)+" m";
    el.alt.textContent=alt.toFixed(1)+" m";
    if (ping>.25){ pingN+=Math.round(dt*14);
      el.ping.textContent=pingN.toLocaleString("en-US").replace(/,/g," "); }
    const si=stageIdx(p);
    if (si!==shown){ shown=si; el.swap.forEach((b,i)=>b.classList.toggle("on",i===si));
      el.sub.innerHTML=SUBS[si]; }
  }
  frame();

  return () => {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(rafId);
    window.removeEventListener("resize", resize);
    delete (window as any).__heroProgress;
    // Order matters: drop the scene graph's GPU handles before the context
    // that owns them. A WebGL context is not garbage collected on its own, and
    // React strict mode mounts this twice in development -- leak it and the
    // second mount runs on a browser that has already hit its context limit.
    renderer.setAnimationLoop(null);
    for (const s of [scene, waterScene]) {
      s.traverse((o: any) => {
        o.geometry?.dispose?.();
        const m = o.material;
        if (Array.isArray(m)) m.forEach((x: any) => x?.dispose?.());
        else m?.dispose?.();
      });
    }
    ENV_AIR?.dispose?.();
    ENV_WATER?.dispose?.();
    pmrem?.dispose?.();
    // DRACOLoader spins up WASM decoder workers -- two per mount, since both
    // GLBs are Draco-compressed -- and they outlive the page unless told to
    // stop. Measured before this line existed: {made: 2, killed: 0}.
    draco.dispose();
    renderer.dispose();
    renderer.forceContextLoss?.();
  };
}
