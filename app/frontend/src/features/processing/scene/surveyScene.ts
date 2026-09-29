/* =============================================================================
 * The processing page's live survey scene.
 *
 * The water shader, rig numbers and materials are lifted from the landing hero
 * (features/landing/hero/scene.ts). Two things differ:
 *   - the input: instead of reading scroll position it reads model.V.p, the
 *     virtual scroll the job drives (see ./model.ts);
 *   - the composition: the vessel sails TOWARD the viewer and the camera dives
 *     forward beneath it, so the surveyed strip recedes behind the towfish
 *     where the eye can follow it. The shader gains a camera offset so the
 *     vessel can actually travel along the line.
 *
 * What is real: the frames painted on the seabed and in the waterfall are the
 * survey's own frames, painted only once their frame.processed has arrived;
 * each marker is a real detection, shown only once the towfish has reached
 * the spot in the frame where the model boxed it, and its ring is the real
 * position_error_m. What is illustrative: the along-track scale (metres per
 * frame) and the vessel/towfish choreography.
 * ========================================================================== */

import * as THREE from "three";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

import { contactUV, hudText, type SceneDetection, type SceneModel, tick } from "./model";

const APPROVED = {"camY": 6.75, "horizon": 0.125, "seabedDepth": 30, "quality": 1, "sunAz": 0, "sunEl": 0.115, "sunStr": 0.22, "sunTight": 3200, "sunGlow": 0.55, "horR": 0.6, "horG": 0.86, "horB": 1, "zenR": 0.05, "zenG": 0.4, "zenB": 0.86, "skyGrad": 0.42, "cloudAmt": 0.5, "cloudCover": 0.84, "cloudScale": 1.85, "swellLen": 52, "swellAmp": 0.55, "medLen": 13, "medAmp": 0.2, "chopStr": 0.55, "waveSpeed": 0.55, "windDir": 0.3, "detailFall": 0.024, "seaR": 0.035, "seaG": 0.135, "seaB": 0.3, "fresnelF0": 0.022, "glitterPow": 260, "glitterStr": 2.1, "hazeAmt": 0.62, "floorScale": 6, "sandR": 0.45, "sandG": 0.44, "sandB": 0.78, "sandGrain": 0.87, "causticStrength": 2.39, "causticSharp": 14.8, "causticSpeed": 0.79, "causticBeat": 4, "causticFade": 0.32, "fogDensity": 0.03, "absR": 2.9, "absG": 1.2, "absB": 0.6, "rayStr": 2.56, "rayFreq": 27.8, "rayReach": 2, "raySharp": 6.3, "rayDepthFade": 0.92, "bubbleAmount": 2.63, "bubbleSize": 0.0067, "bubbleSpeed": 0.2, "moteAmount": 0.47, "moteSize": 0.013, "exposure": 1.2, "vignette": 0.45, "grain": 0.012} as const;
const RIG = {"towDepthM": 20, "laybackM": 47, "vesselX": 1, "fishScale": 3.4, "vesselYaw": 26, "towYawFollow": 0.12, "vesselZNear": -40, "vesselZFar": -86, "swathNearDeg": 3.5, "swathFarDeg": 50.5, "swathOpacity": 0.32} as const;
const MAT  = {"vessel": {"metalness": 0.45, "roughness": 0.58, "envInt": 1.9, "gain": 1.5}, "towfish": {"metalness": 0.72, "roughness": 0.46, "envInt": 1.8, "gain": 1.15}} as const;
const START_Y = APPROVED.camY, WORK_Y = -16.0, HORIZON_SURF = APPROVED.horizon, HORIZON_DEEP = 0.33;
const SEABED_Y = -APPROVED.seabedDepth;

const FRAG = `
precision highp float;
uniform vec2  uRes; uniform float uTime; uniform vec2 camOff;
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
float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
float nse(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
  return mix(mix(h21(i),h21(i+vec2(1,0)),f.x), mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x), f.y); }
float fbm(vec2 p){ float a=0.5,v=0.0; for(int i=0;i<5;i++){ v+=a*nse(p); p*=2.03; a*=0.5; } return v; }
vec2 fbmGrad(vec2 p, float e){ float c=fbm(p); return vec2(fbm(p+vec2(e,0.0))-c, fbm(p+vec2(0.0,e))-c)/e; }
vec3 sunDirection(){ return normalize(vec3(sin(sunAz), sunEl, -cos(sunAz))); }
vec3 skyColor(vec3 dir){
  float el = clamp(dir.y, -0.15, 1.0);
  vec3 c = mix(vec3(horR,horG,horB), vec3(zenR,zenG,zenB), pow(clamp(el,0.0,1.0), skyGrad));
  vec3 sd = sunDirection(); float al = max(dot(normalize(dir), sd), 0.0);
  c += vec3(1.0,0.96,0.88)*pow(al,sunTight)*sunStr; c += vec3(1.0,0.94,0.84)*pow(al,12.0)*sunGlow*0.30;
  if (cloudAmt > 0.001 && dir.y > 0.012){
    float ct = 1.0/max(dir.y,0.012);
    vec2 cuv = (dir.xz*ct)*cloudScale*0.06 + vec2(uTime*0.004, uTime*0.002);
    float f = fbm(cuv) + fbm(cuv*2.7)*0.35;
    float m = smoothstep(cloudCover, cloudCover+0.30, f)*smoothstep(0.012,0.16,dir.y);
    c = mix(c, mix(vec3(0.72), vec3(1.0), smoothstep(0.0,0.6,f)), m*cloudAmt);
  }
  return c;
}
void addWave(inout vec2 s, vec2 p, vec2 d, float len, float amp, float t){ float k = 6.2831853/max(len,0.001); s += d*(cos(dot(d,p)*k + t)*amp*k); }
float waveHeight(vec2 p){
  float t = uTime*waveSpeed; vec2 w = vec2(cos(windDir), sin(windDir)); vec2 w2 = vec2(cos(windDir+0.7), sin(windDir+0.7));
  float k1 = 6.2831853/swellLen, k2 = 6.2831853/medLen;
  return sin(dot(w,p)*k1 + t*0.55)*swellAmp + sin(dot(w2,p)*k2 + t*1.05)*medAmp;
}
vec3 waveNormal(vec2 p, float dist){
  float t = uTime*waveSpeed; float detail = exp(-dist*detailFall);
  p += (vec2(fbm(p*0.018), fbm(p*0.018+7.3))-0.5)*9.0;
  vec2 s = vec2(0.0);
  vec2 w  = vec2(cos(windDir), sin(windDir)); vec2 w2 = vec2(cos(windDir+0.7), sin(windDir+0.7)); vec2 w3 = vec2(cos(windDir-0.9), sin(windDir-0.9));
  addWave(s,p,w, swellLen, swellAmp, t*0.55); addWave(s,p,w2,swellLen*0.63, swellAmp*0.55, t*0.61);
  float md = mix(0.35,1.0,detail);
  addWave(s,p,w2,medLen, medAmp*md, t*1.05); addWave(s,p,w3,medLen*0.66, medAmp*0.72*md, t*1.24); addWave(s,p,w, medLen*0.41, medAmp*0.46*md, t*1.51);
  vec2 drift = w*(t*0.6);
  s += fbmGrad(p*0.22+drift, 0.35)*chopStr*1.00*detail; s += fbmGrad(p*0.65-drift*1.7, 0.18)*chopStr*0.55*detail;
  if (quality > 0.5) s += fbmGrad(p*1.80+drift*2.6, 0.08)*chopStr*0.28*detail*detail;
  return normalize(vec3(-s.x, 1.0, -s.y));
}
vec3 waterAt(float depthM){
  vec3 c = vec3(0.380,0.600,0.712);
  c = mix(c, vec3(0.059,0.294,0.439), smoothstep( 1.0,27.0,depthM));
  c = mix(c, vec3(0.027,0.166,0.408), smoothstep(17.0,43.0,depthM));
  c = mix(c, vec3(0.004,0.054,0.261), smoothstep(31.0,57.0,depthM));
  return c;
}
float causticLayer(vec2 p, float t){ float v = 0.0;
  for (int i=0;i<3;i++){ float fi=float(i); vec2 q = p*(1.0+fi*0.8) + vec2(t*(0.30+fi*0.11), -t*(0.22+fi*0.09)); v += (1.0-abs(fbm(q)*2.0-1.0))*(1.0-fi*0.22); }
  return pow(clamp(v/2.34,0.0,1.0), causticSharp); }
float caustics(vec2 uv, float t){ float c = causticLayer(uv, t); c += causticLayer(uv*causticBeat+23.0, -t*0.62)*0.55;
  if (quality > 0.5) c += causticLayer(uv*causticBeat*2.7+71.0, t*0.34)*0.28; return c; }
vec3 shadeAbove(vec3 ro, vec3 rd, float surfH){
  vec3 sd = sunDirection();
  if (rd.y >= -0.0008){ vec3 c = skyColor(rd); float band = 1.0 - smoothstep(0.0, 0.06, rd.y); return mix(c, vec3(horR,horG,horB), band*0.55*hazeAmt); }
  float t = max(ro.y - surfH, 0.05)/(-rd.y); vec3 p = ro + rd*t; vec3 N = waveNormal(p.xz, t);
  float NdotV = max(dot(N,-rd), 0.0); float F = fresnelF0 + (1.0-fresnelF0)*pow(1.0-NdotV, 5.0);
  vec3 R = reflect(rd, N); R.y = abs(R.y);
  vec3 c = mix(vec3(seaR,seaG,seaB), skyColor(R), clamp(F,0.0,1.0));
  float facets = pow(max(dot(R,sd),0.0), glitterPow)*(0.65+0.35*fbm(p.xz*0.8+uTime*0.05));
  c += vec3(1.0,0.97,0.90)*facets*glitterStr*exp(-t*detailFall*0.55);
  float hz = 1.0 - exp(-t*0.0016);
  return mix(c, skyColor(vec3(rd.x,0.02,rd.z)), hz*hazeAmt);
}
vec3 shadeBelow(vec3 ro, vec3 rd, vec2 frag, float surfH){
  vec3 sd = sunDirection(); float eyeDepth = max(0.0, surfH - ro.y); float floorY = -seabedDepth; vec3 col; float underPath;
  if (rd.y > 0.0008){
    float t = max(surfH - ro.y, 0.05)/rd.y; vec3 p = ro + rd*t; vec3 N = waveNormal(p.xz, t);
    float ang = acos(clamp(rd.y, -1.0, 1.0)); float crit = 0.8483; float win = smoothstep(crit + 0.10, crit - 0.16, ang);
    vec3 thr = refract(rd, -N, 1.0/1.333);
    vec3 through = (dot(thr,thr) < 0.0001) ? skyColor(vec3(rd.x,0.9,rd.z)) : skyColor(normalize(thr));
    col = mix(waterAt(eyeDepth + 6.0)*1.15, through, clamp(win,0.0,1.0));
    col += vec3(0.72,0.93,1.0)*pow(max(dot(reflect(rd,N),sd),0.0), 90.0)*0.25; underPath = t;
  } else {
    float t = (ro.y - floorY)/max(-rd.y, 1e-4); vec3 p = ro + rd*t;
    vec2 fuv = (p.xz + vec2(53.0,17.0))*(floorScale*0.1);
    float c = caustics(fuv, uTime*causticSpeed); float g = fbm(fuv*6.0)*sandGrain; float cFade = mix(1.0, exp(-t*0.09), causticFade);
    col = vec3(sandR,sandG,sandB)*(0.55+g); col += vec3(0.85,0.95,1.0)*c*causticStrength*cFade; underPath = t;
  }
  vec3 ab = vec3(absR,absG,absB); ab /= max((ab.r+ab.g+ab.b)/3.0, 1e-4);
  col = mix(col, waterAt(eyeDepth), clamp(1.0 - exp(-underPath*fogDensity*ab), 0.0, 1.0));
  vec3 sdw = normalize(mix(sd, vec3(0.0, 1.0, 0.0), 0.35));
  if (sdw.z < -0.001){
    vec2 sunUV = vec2(-sdw.x/sdw.z, -sdw.y/sdw.z + horizon); vec2 sunFrag = vec2(sunUV.x*(uRes.y/uRes.x) + 0.5, sunUV.y + 0.5);
    vec2 d = frag - sunFrag; d.x *= uRes.x/uRes.y; float r = length(d); float a2 = atan(d.x, -d.y); float down = -d.y/max(r,1e-4);
    float shafts = pow(clamp(fbm(vec2(a2*rayFreq, uTime*0.04)),0.0,1.0), raySharp);
    shafts *= smoothstep(-0.10,0.70,down); shafts *= smoothstep(rayReach,0.0,r); shafts *= 0.70 + 0.30*sin(uTime*0.55 + a2*6.0);
    shafts *= mix(1.0, smoothstep(0.0,0.62,frag.y), rayDepthFade);
    col += vec3(0.72,0.93,1.0)*shafts*rayStr*0.25;
  }
  float bub = 0.0;
  for (int i=0;i<4;i++){ float fi=float(i); float cx = h21(vec2(fi,3.0));
    for (int j=0;j<4;j++){ float fj=float(j); float seed = h21(vec2(fi*9.1, fj*4.7)); float y = fract(seed + uTime*bubbleSpeed*(0.55+seed*0.9));
      vec2 bp = vec2(cx + sin((y+seed)*9.0)*0.012, y*0.92+0.04) - frag; bp.x *= uRes.x/uRes.y;
      bub += smoothstep(bubbleSize*(0.5+seed)*(0.6+y*0.8), 0.0, length(bp))*(0.35+0.65*seed); } }
  col += vec3(0.85,0.96,1.0)*bub*bubbleAmount;
  float motes = 0.0;
  for (int i=0;i<12;i++){ float fi=float(i); vec2 mp = vec2(h21(vec2(fi,1.3)), fract(h21(vec2(fi,5.9)) + uTime*0.006));
    vec2 dd = mp - frag; dd.x *= uRes.x/uRes.y; motes += smoothstep(moteSize*(0.4+h21(vec2(fi,8.8))), 0.0, length(dd))*0.5; }
  col += vec3(0.8,0.93,1.0)*motes*moteAmount*0.25;
  return col;
}
void main(){
  vec2 frag = gl_FragCoord.xy/uRes; vec2 uv = (gl_FragCoord.xy - 0.5*uRes)/uRes.y;
  vec3 ro = vec3(camOff.x, camY, camOff.y); vec3 rd = normalize(vec3(uv.x, uv.y - horizon, -1.0));
  float surfH = waveHeight(camOff); float w = smoothstep(-0.9, 0.9, camY - surfH); vec3 col;
  if (w > 0.995) col = shadeAbove(ro, rd, surfH);
  else if (w < 0.005) col = shadeBelow(ro, rd, frag, surfH);
  else col = mix(shadeBelow(ro, rd, frag, surfH), shadeAbove(ro, rd, surfH), w);
  col *= exposure; col = col/(1.0 + col*0.55);
  float lum = dot(col, vec3(0.299,0.587,0.114)); col = mix(vec3(lum), col, 1.18);
  vec2 vc = (frag-0.5)*vec2(1.06,1.0); float vigAmt = mix(0.22, vignette, clamp(-camY/8.0, 0.0, 1.0));
  col *= clamp(1.0 - vigAmt*pow(clamp(length(vc)*1.42,0.0,1.0),2.15), 0.0, 1.0);
  col += (h21(gl_FragCoord.xy + fract(uTime)) - 0.5)*grain;
  gl_FragColor = vec4(clamp(col,0.0,1.0), 1.0);
}`;

export interface SceneElements {
  card: HTMLElement;
  canvas: HTMLCanvasElement;
  labels: HTMLElement;
  waterfall: HTMLCanvasElement;
  waterfallFrame: HTMLElement;
  capK: HTMLElement;
  capT: HTMLElement;
  capS: HTMLElement;
  capLag: HTMLElement;
  sonarLed: HTMLElement;
  sonarText: HTMLElement;
  rDepth: HTMLElement;
  rLay: HTMLElement;
  rAlt: HTMLElement;
  rSpd: HTMLElement;
  rPing: HTMLElement;
  /** The replay slider mounts only once the run has finished, so it is read
   *  through getters rather than captured at mount. */
  scrub: () => HTMLInputElement | null;
  scrubValue: () => HTMLElement | null;
}

export interface SceneHandle {
  /** False when WebGL could not start: the controller still runs, nothing draws. */
  webgl: boolean;
  dispose(): void;
}

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const span = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));
const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
const descentPitch = (d: number) => -Math.sin(Math.PI * d) * 0.26;

/** Sonar colour map: black → bronze → cream, as a 256-entry RGB lookup. */
const LUT = (() => {
  const a = new Uint8ClampedArray(256 * 3);
  const stops: [number, number[]][] = [[0, [0, 0, 0]], [0.25, [46, 22, 4]], [0.5, [140, 74, 16]], [0.75, [226, 160, 60]], [1, [255, 240, 190]]];
  for (let i = 0; i < 256; i++) {
    const v = i / 255;
    let k = 0;
    while (k < stops.length - 2 && v > stops[k + 1][0]) k++;
    const [a0, c0] = stops[k], [a1, c1] = stops[k + 1], t = (v - a0) / (a1 - a0);
    for (let c = 0; c < 3; c++) a[i * 3 + c] = c0[c] + (c1[c] - c0[c]) * t;
  }
  return a;
})();

export function mountSurveyScene(m: SceneModel, el: SceneElements): SceneHandle {
  let raf = 0;
  let disposed = false;
  let visible = true;
  const cleanups: (() => void)[] = [];

  let renderer: THREE.WebGLRenderer | null = null;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: el.canvas, antialias: true, alpha: false });
  } catch {
    renderer = null;
  }

  // Without WebGL the controller still has to run: it is what reveals
  // contacts, fires their toasts and brings up the summary.
  if (!renderer) {
    let last = performance.now();
    const loop = () => {
      raf = requestAnimationFrame(loop);
      const t = performance.now();
      const dt = Math.min(0.5, (t - last) / 1000);
      last = t;
      tick(m, dt);
      writeCaption();
      writeScrub();
    };
    raf = requestAnimationFrame(loop);
    return { webgl: false, dispose: () => { disposed = true; cancelAnimationFrame(raf); } };
  }
  const R = renderer;

  R.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  R.outputColorSpace = THREE.SRGBColorSpace;
  R.toneMapping = THREE.ACESFilmicToneMapping;
  R.autoClear = false;
  R.localClippingEnabled = true;
  R.shadowMap.enabled = true;
  R.shadowMap.type = THREE.PCFSoftShadowMap;
  const CLIP_ABOVE = [new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)];

  // ---- water pass: a full-screen quad running the hero's shader
  const waterScene = new THREE.Scene(), waterCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const wu: Record<string, THREE.IUniform> = {
    uRes: { value: new THREE.Vector2(1, 1) }, uTime: { value: 0 }, camOff: { value: new THREE.Vector2() },
  };
  for (const k in APPROVED) wu[k] = { value: APPROVED[k as keyof typeof APPROVED] };
  const waterMat = new THREE.ShaderMaterial({
    uniforms: wu, vertexShader: "void main(){ gl_Position = vec4(position.xy, 0.0, 1.0); }", fragmentShader: FRAG,
    depthTest: false, depthWrite: false,
  });
  waterScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), waterMat));

  // ---- 3D pass
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1, 0.4, 5000);
  const sun = new THREE.DirectionalLight(0xfff2dc, 2.6);
  sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { near: 1, far: 420, left: -34, right: 34, top: 34, bottom: -34 });
  sun.shadow.bias = -0.0012; sun.shadow.normalBias = 0.35;
  const sunTarget = new THREE.Object3D(); scene.add(sunTarget); sun.target = sunTarget; scene.add(sun);
  const hemi = new THREE.HemisphereLight(0xbfe4ff, 0x0a2740, 1.1); scene.add(hemi);
  const down = new THREE.DirectionalLight(0x9fd8f2, 0.0); down.position.set(0, 200, 0); scene.add(down);
  const rim = new THREE.DirectionalLight(0x7fc8ee, 0.0); rim.position.set(-160, 40, 120); scene.add(rim);
  const fog = new THREE.Fog(0x0f4b70, 30, 460);
  scene.fog = fog;

  const pmrem = new THREE.PMREMGenerator(R);
  function makeEnv(stops: [number, string][]) {
    const c = document.createElement("canvas"); c.width = 8; c.height = 128;
    const x = c.getContext("2d")!; const g = x.createLinearGradient(0, 0, 0, 128);
    for (const [at, col] of stops) g.addColorStop(at, col);
    x.fillStyle = g; x.fillRect(0, 0, 8, 128);
    const tex = new THREE.CanvasTexture(c); tex.mapping = THREE.EquirectangularReflectionMapping; tex.colorSpace = THREE.SRGBColorSpace;
    const rt = pmrem.fromEquirectangular(tex).texture; tex.dispose(); return rt;
  }
  const ENV_AIR = makeEnv([[0, "#9fd8ff"], [0.4, "#eaf6ff"], [0.487, "#ffffff"], [0.503, "#3d8fbe"], [0.7, "#2a6d96"], [1, "#17435e"]]);
  const ENV_WATER = makeEnv([[0, "#f2ffff"], [0.14, "#d6f2ff"], [0.32, "#7cc4e4"], [0.62, "#2f73a0"], [1, "#15405e"]]);
  scene.environment = ENV_AIR; let envIsAir = true;

  // ---- models (the hero's GLBs; primitive stand-ins if they fail to load)
  const vesselGroup = new THREE.Group(); scene.add(vesselGroup);
  const fishGroup = new THREE.Group(), fishScale = new THREE.Group(); fishGroup.add(fishScale); scene.add(fishGroup);
  const MATS: THREE.MeshStandardMaterial[] = [];
  function collect(r: THREE.Object3D, cast: boolean, mm: { metalness: number; roughness: number; envInt: number; gain: number }) {
    r.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh || !mesh.material) return;
      mesh.castShadow = cast; mesh.receiveShadow = true;
      const mat = mesh.material as THREE.MeshStandardMaterial;
      mat.metalnessMap = null; mat.metalness = mm.metalness; mat.roughness = mm.roughness; mat.envMapIntensity = mm.envInt;
      mat.color.setScalar(mm.gain); mat.needsUpdate = true; MATS.push(mat);
    });
  }
  function fallbackVessel() {
    const g = new THREE.Group(); const mat = new THREE.MeshStandardMaterial({ color: 0x1d3f73, roughness: 0.6, metalness: 0.3 });
    const hull = new THREE.Mesh(new THREE.BoxGeometry(6, 3, 26), mat); hull.position.y = 0.2; g.add(hull);
    const cab = new THREE.Mesh(new THREE.BoxGeometry(4.6, 3.2, 8), new THREE.MeshStandardMaterial({ color: 0xf2f2f2, roughness: 0.5 })); cab.position.set(0, 3.2, -3); g.add(cab);
    vesselGroup.add(g);
  }
  function fallbackFish() {
    const g = new THREE.Mesh(new THREE.CapsuleGeometry(0.12, 1.1, 6, 12), new THREE.MeshStandardMaterial({ color: 0xffc000, roughness: 0.4, metalness: 0.5 }));
    g.rotation.x = Math.PI / 2; g.position.z = 0.6; g.castShadow = true; fishScale.add(g);
  }
  const draco = new DRACOLoader(); draco.setDecoderPath("/draco/gltf/");
  const gltf = new GLTFLoader(); gltf.setDRACOLoader(draco);
  const ready = () => { m.modelsReady++; };
  gltf.load("/models/vessel.glb", (r) => { if (disposed) return; vesselGroup.add(r.scene); collect(r.scene, false, MAT.vessel); ready(); }, undefined, () => { fallbackVessel(); ready(); });
  gltf.load("/models/towfish.glb", (r) => { if (disposed) return; fishScale.add(r.scene); collect(r.scene, true, MAT.towfish); ready(); }, undefined, () => { fallbackFish(); ready(); });

  // ---- cable, swath beams, wake, shadow catcher (as in the hero)
  const CSEG = 30, cableGeo = new THREE.BufferGeometry();
  cableGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array((CSEG + 1) * 3), 3));
  scene.add(new THREE.Line(cableGeo, new THREE.LineBasicMaterial({ color: 0xc4f8ff, transparent: true, opacity: 0.5 })));
  function beam(sign: number) {
    const mesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.ShaderMaterial({
      transparent: true, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uOpacity: { value: 0 } },
      vertexShader: "varying float vY; void main(){vY=position.y; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}",
      fragmentShader: "uniform float uOpacity; varying float vY; void main(){ float d=clamp(-vY,0.0,1.0); float a=uOpacity*(1.0-d*0.78)*smoothstep(0.0,0.18,d); gl_FragColor=vec4(0.769,0.973,1.0,a); }",
    }));
    const n = Math.tan(THREE.MathUtils.degToRad(RIG.swathNearDeg)), f = Math.tan(THREE.MathUtils.degToRad(RIG.swathFarDeg));
    mesh.geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array([0, 0, 0, sign * n, -1, 0, sign * f, -1, 0]), 3));
    return mesh;
  }
  const swath = new THREE.Group(), bL = beam(-1), bR = beam(1); swath.add(bL, bR); scene.add(swath);
  const beamU = (bL.material as THREE.ShaderMaterial).uniforms;
  (bR.material as THREE.ShaderMaterial).uniforms = beamU;
  const wakeMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, side: THREE.DoubleSide, uniforms: { uTime: { value: 0 }, uOpacity: { value: 0.5 } },
    vertexShader: "varying vec2 vUv; void main(){vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}",
    fragmentShader: `uniform float uTime,uOpacity; varying vec2 vUv;
      float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
      float n(vec2 p){vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
      void main(){ float al=vUv.y; float ac=abs(vUv.x-0.5)*2.0; float sp=0.25+al*0.75; float core=smoothstep(sp,sp*0.35,ac);
        float foam=n(vec2(vUv.x*38.0,vUv.y*10.0-uTime*0.6)); gl_FragColor=vec4(0.88,0.96,1.0, clamp(core*(0.35+0.65*foam)*(1.0-al)*uOpacity,0.0,1.0)); }`,
  });
  const wake = new THREE.Mesh(new THREE.PlaneGeometry(46, 150), wakeMat); wake.rotation.x = -Math.PI / 2; scene.add(wake);
  const shadowCatcher = new THREE.Mesh(new THREE.PlaneGeometry(700, 700), new THREE.ShadowMaterial({ opacity: 0.3, transparent: true }));
  shadowCatcher.rotation.x = -Math.PI / 2; shadowCatcher.receiveShadow = true; scene.add(shadowCatcher);

  // ---- survey geometry: heading toward the viewer (yaw 160°)
  const yaw = (160 * Math.PI) / 180;
  const FWD = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw));
  const STBD = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
  const ASTERN = FWD.clone().negate();
  const towYaw = yaw, TRAIL = ASTERN.clone();
  const V0 = new THREE.Vector3(6, 0, -50);
  const V_ADV = 20, TOW_ARM = 13.2, CAM_DIVE = 61.5, SWATH_W = 120;
  const LINE0 = V0.clone().addScaledVector(FWD, V_ADV).addScaledVector(ASTERN, TOW_ARM + RIG.laybackM); LINE0.y = 0;

  // ---- sonar returns: the survey's real frames, sonar-coloured, revealed behind the towfish
  let TILE = 256;
  const wfCanvas = document.createElement("canvas"), wfCtx = wfCanvas.getContext("2d", { willReadFrequently: true })!;
  let stripTex: THREE.CanvasTexture | null = null, strip: THREE.Mesh | null = null, stripMat: THREE.ShaderMaterial | null = null;
  let paintedSeen = new Set<number>(), failedSeen = new Set<number>(), missingSeen = new Set<number>();

  function paintFrame(i: number, kind: "ok" | "failed" | "missing") {
    const y = i * TILE;
    if (kind === "failed") {
      wfCtx.fillStyle = "#1a0606"; wfCtx.fillRect(0, y, TILE, TILE);
      wfCtx.strokeStyle = "rgba(220,60,40,.55)"; wfCtx.lineWidth = Math.max(2, TILE / 40);
      for (let x = -TILE; x < TILE; x += Math.max(8, TILE / 9)) { wfCtx.beginPath(); wfCtx.moveTo(x, y); wfCtx.lineTo(x + TILE, y + TILE); wfCtx.stroke(); }
      return;
    }
    const tmp = document.createElement("canvas"); tmp.width = TILE; tmp.height = TILE; const t = tmp.getContext("2d")!;
    const im = m.images.get(i);
    if (kind === "ok" && im && im.naturalWidth) t.drawImage(im, 0, 0, TILE, TILE);
    else { t.fillStyle = "#2a2a2a"; t.fillRect(0, 0, TILE, TILE); }
    const d = t.getImageData(0, 0, TILE, TILE), px = d.data;
    for (let p = 0; p < px.length; p += 4) {
      const lum = px[p] * 0.299 + px[p + 1] * 0.587 + px[p + 2] * 0.114;
      const g = Math.min(255, (lum * 1.9) | 0);
      px[p] = LUT[g * 3]; px[p + 1] = LUT[g * 3 + 1]; px[p + 2] = LUT[g * 3 + 2]; px[p + 3] = 255;
    }
    wfCtx.putImageData(d, 0, y);
  }

  function buildStrip() {
    // One tile per frame, stacked; tiles shrink for a long survey so the
    // canvas stays under the texture limits every GPU supports.
    TILE = Math.max(16, Math.min(256, Math.floor(8192 / m.N)));
    wfCanvas.width = TILE; wfCanvas.height = TILE * m.N;
    wfCtx.fillStyle = "#000"; wfCtx.fillRect(0, 0, TILE, TILE * m.N);
    if (strip) { scene.remove(strip); strip.geometry.dispose(); stripMat?.dispose(); stripTex?.dispose(); }
    stripTex = new THREE.CanvasTexture(wfCanvas); stripTex.colorSpace = THREE.SRGBColorSpace; stripTex.flipY = false;
    const S = m.S;
    const a = LINE0.clone().addScaledVector(STBD, -SWATH_W / 2), b = LINE0.clone().addScaledVector(STBD, SWATH_W / 2);
    const c = a.clone().addScaledVector(FWD, S), d = b.clone().addScaledVector(FWD, S);
    const g = new THREE.BufferGeometry(), y = SEABED_Y + 0.08;
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array([a.x, y, a.z, b.x, y, b.z, c.x, y, c.z, d.x, y, d.z]), 3));
    g.setAttribute("uv", new THREE.BufferAttribute(new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), 2));
    g.setIndex([0, 2, 1, 1, 2, 3]);
    stripMat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, side: THREE.DoubleSide,
      uniforms: { uTex: { value: stripTex }, uReveal: { value: 0 }, uLen: { value: S }, uFog: { value: new THREE.Color(0x0f4b70) }, uFogNear: { value: 25 }, uFogFar: { value: 320 }, uOn: { value: 0 } },
      vertexShader: "varying vec2 vUv; varying float vD; void main(){ vUv=uv; vec4 mv=modelViewMatrix*vec4(position,1.0); vD=-mv.z; gl_Position=projectionMatrix*mv; }",
      fragmentShader: `uniform sampler2D uTex; uniform float uReveal,uLen,uFogNear,uFogFar,uOn; uniform vec3 uFog; varying vec2 vUv; varying float vD;
        void main(){ float s=vUv.y*uLen; float shown=smoothstep(uReveal+0.6, uReveal-0.6, s);
          vec3 c=texture2D(uTex,vUv).rgb;
          float edge=exp(-abs(s-uReveal)*0.9)*uOn;
          float side=smoothstep(0.0,0.14,vUv.x)*smoothstep(1.0,0.86,vUv.x);
          float lum=dot(c,vec3(0.299,0.587,0.114));
          vec3 col=c*2.1 + vec3(0.77,0.97,1.0)*edge*0.9;
          /* Opacity follows return strength: shadow and quiet seabed let the
             real bottom show through, strong returns glow. */
          float a=(shown*(0.34+0.66*smoothstep(0.02,0.2,lum)) + edge*0.6)*side;
          float f=smoothstep(uFogNear,uFogFar,vD); col=mix(col,uFog,f*0.85);
          gl_FragColor=vec4(col,a*(1.0-f*0.4)*uOn); }`,
    });
    strip = new THREE.Mesh(g, stripMat); strip.renderOrder = 2; scene.add(strip);
    paintedSeen = new Set(); failedSeen = new Set(); missingSeen = new Set();
  }

  // ---- seabed rocks along the line: scale and motion reference
  let rocks: THREE.InstancedMesh | null = null;
  const rockGeo = new THREE.DodecahedronGeometry(1, 0);
  const rockMat = new THREE.MeshStandardMaterial({ color: 0x6f8fb0, roughness: 1, metalness: 0, flatShading: true });
  function buildRocks() {
    if (rocks) { scene.remove(rocks); rocks.dispose(); }
    const S = m.S; const n = Math.round(90 + S * 1.1);
    rocks = new THREE.InstancedMesh(rockGeo, rockMat, n); rocks.receiveShadow = true;
    const mx = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), sv = new THREE.Vector3();
    let seed = 20260926; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (let i = 0; i < n; i++) {
      const s = -140 + rnd() * (S + 300), lat = (rnd() - 0.5) * 260;
      const p = LINE0.clone().addScaledVector(FWD, s).addScaledVector(STBD, lat); p.y = SEABED_Y + 0.1;
      const k = 0.35 + Math.pow(rnd(), 3) * 2.6; sv.set(k * (0.8 + rnd() * 0.8), k * (0.35 + rnd() * 0.4), k * (0.8 + rnd() * 0.8));
      e.set(rnd() * 0.4, rnd() * 6.28, rnd() * 0.4); q.setFromEuler(e); mx.compose(p, q, sv); rocks.setMatrixAt(i, mx);
    }
    scene.add(rocks);
  }

  // ---- detection markers
  interface Marker { g: THREE.Group; head: THREE.Mesh; wave: THREE.Mesh; el: HTMLDivElement; r: number }
  const markerGroup = new THREE.Group(); scene.add(markerGroup);
  const MK = new Map<string, Marker>();
  const DEBRIS_COL = new THREE.Color(0xffb547);
  function contactPos(d: SceneDetection, out: THREE.Vector3) {
    const { xc, yc } = contactUV(m, d);
    return out.copy(LINE0).addScaledVector(FWD, ((d.frame + yc) / m.N) * m.S).addScaledVector(STBD, (xc - 0.5) * SWATH_W).setY(SEABED_Y + 0.15);
  }
  function makeMarker(d: SceneDetection): Marker {
    const g = new THREE.Group();
    // A ring of the real error radius; a detection without a derived position
    // still gets a small ring so it can be seen, and its label says "no fix".
    const r = Math.max(2.5, d.err ?? 2.5);
    const basic = (o: THREE.MeshBasicMaterialParameters) => new THREE.MeshBasicMaterial({ transparent: true, side: THREE.DoubleSide, depthWrite: false, ...o });
    const ring = new THREE.Mesh(new THREE.RingGeometry(r - 0.22, r, 56), basic({ color: DEBRIS_COL, opacity: 0.95 }));
    ring.rotation.x = -Math.PI / 2; g.add(ring);
    const disc = new THREE.Mesh(new THREE.CircleGeometry(r, 56), basic({ color: DEBRIS_COL, opacity: 0.14 }));
    disc.rotation.x = -Math.PI / 2; disc.position.y = 0.02; g.add(disc);
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 8, 6), new THREE.MeshBasicMaterial({ color: DEBRIS_COL, transparent: true, opacity: 0.9 }));
    pole.position.y = 4; g.add(pole);
    const head = new THREE.Mesh(new THREE.OctahedronGeometry(0.9, 0), new THREE.MeshBasicMaterial({ color: DEBRIS_COL }));
    head.position.y = 8.4; g.add(head);
    const wave = new THREE.Mesh(new THREE.RingGeometry(0.9, 1, 64), basic({ color: 0xc4f8ff, opacity: 0 }));
    wave.rotation.x = -Math.PI / 2; wave.position.y = 0.05; g.add(wave);
    g.visible = false; markerGroup.add(g);
    const lbl = document.createElement("div"); lbl.className = "gn-mlabel"; lbl.style.display = "none";
    const b = document.createElement("b"); b.textContent = d.cls.toUpperCase();
    lbl.append(b, ` ${d.conf != null ? d.conf.toFixed(2) : "—"} · ${d.err != null ? `±${d.err.toFixed(1)} m` : "no fix"}`);
    el.labels.appendChild(lbl);
    const mk = { g, head, wave, el: lbl, r }; MK.set(d.id, mk); return mk;
  }
  function clearMarkers() {
    for (const mk of MK.values()) {
      markerGroup.remove(mk.g); mk.el.remove();
      mk.g.traverse((o) => { const mesh = o as THREE.Mesh; if (mesh.isMesh) { mesh.geometry.dispose(); (mesh.material as THREE.Material).dispose(); } });
    }
    MK.clear();
  }

  // ---- camera, resize
  function matchCamera(camY: number, horizon: number, ox: number, oz: number) {
    camera.fov = (2 * Math.atan(0.5) * 180) / Math.PI; camera.position.set(ox, camY, oz); camera.rotation.set(0, 0, 0);
    camera.updateMatrixWorld(); camera.updateProjectionMatrix();
    camera.projectionMatrix.elements[9] = -2.0 * horizon; camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    const az = APPROVED.sunAz, elv = APPROVED.sunEl; sun.position.set(ox + Math.sin(az) * 400, elv * 400 + 120, oz - Math.cos(az) * 400);
  }
  let W = 1, H = 1;
  function resize() {
    const r = el.card.getBoundingClientRect(); W = Math.max(1, r.width); H = Math.max(1, r.height);
    R.setSize(W, H, false); const pr = R.getPixelRatio(); (wu.uRes.value as THREE.Vector2).set(W * pr, H * pr); camera.aspect = W / H;
  }
  const ro = new ResizeObserver(resize); ro.observe(el.card); resize();
  cleanups.push(() => ro.disconnect());
  // Offscreen (scrolled down to the results) the shader is pure cost.
  const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; });
  io.observe(el.card); cleanups.push(() => io.disconnect());

  function seaH(x: number, z: number, t: number) {
    const tt = t * APPROVED.waveSpeed, d = APPROVED.windDir, d2 = d + 0.7, k1 = 6.2831853 / APPROVED.swellLen, k2 = 6.2831853 / APPROVED.medLen;
    return Math.sin((Math.cos(d) * x + Math.sin(d) * z) * k1 + tt * 0.55) * APPROVED.swellAmp + Math.sin((Math.cos(d2) * x + Math.sin(d2) * z) * k2 + tt * 1.05) * APPROVED.medAmp;
  }

  // ---- mini waterfall (2D), newest pings at the top
  const wf = el.waterfall, wfx = wf.getContext("2d")!;
  function drawWaterfall(travel: number, on: boolean) {
    wfx.fillStyle = "#000"; wfx.fillRect(0, 0, wf.width, wf.height);
    if (!on) { el.waterfallFrame.textContent = "—"; return; }
    const rowsPerM = TILE / m.frameM, rowNow = travel * rowsPerM, view = TILE * 1.25, y0 = rowNow - view;
    wfx.save(); wfx.translate(0, wf.height); wfx.scale(1, -1);
    const src0 = Math.max(0, y0), destOff = ((src0 - y0) / view) * wf.height, h = rowNow - src0;
    if (h > 1) wfx.drawImage(wfCanvas, 0, src0, TILE, h, 0, destOff, wf.width, (h / view) * wf.height);
    for (const d of m.dets) {
      if (!d.shownAt) continue;
      const fs = m.images.get(d.frame);
      const fw = fs?.naturalWidth || 640, fh = fs?.naturalHeight || 640;
      const rTop = d.frame * TILE + (d.bbox.y / fh) * TILE, rBot = rTop + (d.bbox.h / fh) * TILE;
      const yA = ((rTop - y0) / view) * wf.height, yB = ((rBot - y0) / view) * wf.height;
      if (yB < 0 || yA > wf.height) continue;
      wfx.strokeStyle = "#FFB547"; wfx.lineWidth = 2;
      wfx.strokeRect((d.bbox.x / fw) * wf.width, yA, (d.bbox.w / fw) * wf.width, yB - yA);
    }
    wfx.restore();
    const fr = Math.min(m.N, Math.floor(travel / m.frameM) + 1); el.waterfallFrame.textContent = `frame ${fr}/${m.N}`;
  }

  function writeCaption() {
    const h = hudText(m);
    if (el.capK.textContent !== h.k) el.capK.textContent = h.k;
    if (el.capT.textContent !== h.t) el.capT.textContent = h.t;
    if (el.capS.textContent !== h.s) el.capS.textContent = h.s;
    el.capS.style.display = h.s ? "" : "none";
    if (h.lag) el.capLag.textContent = h.lag;
    el.capLag.style.opacity = h.lag ? "0.9" : "0";
  }
  function writeScrub() {
    if (!m.V.scrub) return;
    const input = el.scrub(), value = el.scrubValue();
    if (m.V.replay && input) input.value = String(Math.round(m.V.p * 1000));
    if (value) value.textContent = Math.round(m.V.p * 100) + "%";
  }

  // ---- main loop
  const clock = new THREE.Clock();
  let version = -1, pingN = 18402;
  const cablePos = cableGeo.getAttribute("position") as THREE.BufferAttribute;
  const HULL_HALF_LEN = 9.0, HULL_HALF_BEAM = 3.2;
  const tmpV = new THREE.Vector3(), towPt = new THREE.Vector3(), fishPos = new THREE.Vector3(), midV = new THREE.Vector3();
  const curve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3());
  let lastTick = performance.now();

  function frame() {
    raf = requestAnimationFrame(frame);
    // The controller always runs, even hidden: it is what advances the story
    // and brings up the summary. Only the drawing is skipped.
    const tNow = performance.now();
    tick(m, Math.min(0.5, (tNow - lastTick) / 1000)); lastTick = tNow;
    writeCaption(); writeScrub();
    if (document.hidden || !visible) { clock.getDelta(); return; }

    const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;
    if (m.version !== version) { version = m.version; buildStrip(); buildRocks(); clearMarkers(); }
    const q = m.quality; wu.quality.value = q; const pr = q ? Math.min(devicePixelRatio, 1.5) : 1;
    if (R.getPixelRatio() !== pr) { R.setPixelRatio(pr); resize(); }
    R.shadowMap.enabled = !!q;

    const V = m.V, p = V.p, ret = V.retrieve || 0;
    // ---------- the choreography: a pure function of p (+ retrieve on fail/cancel)
    const deploy = easeInOut(span(p, 0.16, 0.4)) * (1 - easeInOut(ret));
    const camY = START_Y + (WORK_Y - START_Y) * easeInOut(span(p, 0.12, 0.4));
    const horizon = HORIZON_SURF + (HORIZON_DEEP - HORIZON_SURF) * easeInOut(span(p, 0.16, 0.42));
    const travel = m.S * span(p, 0.42, 0.86);
    const glide = CAM_DIVE * easeInOut(span(p, 0.1, 0.4));
    const ox = FWD.x * travel + ASTERN.x * glide, oz = FWD.z * travel + ASTERN.z * glide;
    wu.camY.value = camY; wu.horizon.value = horizon; (wu.camOff.value as THREE.Vector2).set(ox, oz);
    matchCamera(camY, horizon, ox, oz);

    const adv = V_ADV * easeInOut(span(p, 0.05, 0.42)) + travel;
    const vx = V0.x + FWD.x * adv, vz = V0.z + FWD.z * adv;
    const hF = seaH(vx + FWD.x * HULL_HALF_LEN, vz + FWD.z * HULL_HALF_LEN, t), hA = seaH(vx - FWD.x * HULL_HALF_LEN, vz - FWD.z * HULL_HALF_LEN, t);
    const hP = seaH(vx - STBD.x * HULL_HALF_BEAM, vz - STBD.z * HULL_HALF_BEAM, t), hS = seaH(vx + STBD.x * HULL_HALF_BEAM, vz + STBD.z * HULL_HALF_BEAM, t);
    const heave = (hF + hA + hP + hS) * 0.25;
    vesselGroup.position.set(vx, heave, vz);
    vesselGroup.rotation.set(Math.atan2(hA - hF, 2 * HULL_HALF_LEN) * 0.55, yaw, Math.atan2(hS - hP, 2 * HULL_HALF_BEAM) * 0.7);

    towPt.set(vx, 2.6 + heave, vz).addScaledVector(ASTERN, TOW_ARM);
    fishPos.copy(towPt).addScaledVector(TRAIL, deploy * RIG.laybackM);
    fishPos.y = 2.6 - RIG.towDepthM * deploy; fishPos.x += deploy * Math.sin(t * 0.7) * 1.4;
    const onDavit = 1 - clamp01(deploy / 0.1), sh = seaH(fishPos.x, fishPos.z, t);
    const ride = Math.exp((-6.2831853 * Math.max(0, sh - fishPos.y)) / Math.max(4, APPROVED.swellLen));
    fishPos.y += heave * onDavit + sh * ride * (1 - onDavit);
    const fishWaveTilt = Math.atan2(seaH(fishPos.x + TRAIL.x * 2.4, fishPos.z + TRAIL.z * 2.4, t) - seaH(fishPos.x - TRAIL.x * 2.4, fishPos.z - TRAIL.z * 2.4, t), 4.8) * ride;
    fishGroup.position.copy(fishPos);
    fishGroup.rotation.set(descentPitch(deploy) + fishWaveTilt + Math.sin(t * 0.9) * 0.04 * deploy, towYaw + Math.sin(t * 0.55) * 0.05 * deploy, 0);
    fishScale.scale.setScalar(RIG.fishScale);

    const len = towPt.distanceTo(fishPos);
    const sag = len * 0.16 * Math.sin(Math.PI * Math.min(1, deploy)) + len * 0.04;
    midV.copy(towPt).lerp(fishPos, 0.5); midV.y -= sag;
    curve.v0.copy(towPt); curve.v1.copy(midV); curve.v2.copy(fishPos);
    curve.getPoints(CSEG).forEach((v, i) => cablePos.setXYZ(i, v.x, v.y, v.z));
    cablePos.needsUpdate = true; cableGeo.computeBoundingSphere();

    const alt = Math.max(1, fishPos.y - SEABED_Y);
    // Sonar runs from the start of the line to its end, not after it.
    const searching = span(p, 0.38, 0.44) * (1 - span(p, 0.86, 0.89)) * (1 - ret) * (V.frozen ? 0 : 1);
    swath.position.copy(fishPos); swath.scale.setScalar(alt); swath.rotation.y = towYaw;
    const pulse = searching > 0.25 ? 0.3 + Math.sin(t * 2.2) * 0.1 : 0;
    beamU.uOpacity.value = (pulse * searching * RIG.swathOpacity) / 0.3;

    wake.position.copy(towPt).addScaledVector(ASTERN, 75); wake.position.y = 0.12; wake.rotation.set(-Math.PI / 2, 0, -yaw);
    wakeMat.uniforms.uTime.value = t; wake.visible = camY > -1.0;

    const sub = clamp01(-camY / 9);
    sun.intensity = 2.6 - 1.5 * sub; hemi.intensity = 1.1 + 1.5 * sub;
    hemi.color.set(sub > 0.5 ? 0x9fe0ff : 0xbfe4ff); hemi.groundColor.set(sub > 0.5 ? 0x16506f : 0x0a2740);
    down.intensity = 1.35 * sub; rim.intensity = 0.85 * sub; sunTarget.position.copy(fishPos);
    shadowCatcher.position.set(fishPos.x, SEABED_Y + 0.05, fishPos.z); shadowCatcher.visible = sub > 0.05;
    if (sub > 0.5 === envIsAir) { envIsAir = !(sub > 0.5); scene.environment = envIsAir ? ENV_AIR : ENV_WATER; for (const mt of MATS) mt.needsUpdate = true; }
    const dd = clamp01(Math.max(0, -camY) / 50);
    fog.color.setRGB(0.38 + (0.004 - 0.38) * dd, 0.6 + (0.054 - 0.6) * dd, 0.712 + (0.261 - 0.712) * dd);
    fog.near = camY > 0 ? 120 : 25; fog.far = camY > 0 ? 900 : 320;
    R.clippingPlanes = camY > 0 ? CLIP_ABOVE : [];

    // ---------- sonar returns: paint frames whose frame.processed has ARRIVED
    if (stripMat && stripTex && strip) {
      let dirty = false;
      for (const i of m.painted) {
        if (paintedSeen.has(i)) continue;
        if (m.images.get(i)?.naturalWidth) { paintFrame(i, "ok"); paintedSeen.add(i); dirty = true; }
        else if (m.imageMissing.has(i) && !missingSeen.has(i)) { paintFrame(i, "missing"); missingSeen.add(i); dirty = true; }
      }
      for (const i of m.failed) if (!failedSeen.has(i)) { paintFrame(i, "failed"); failedSeen.add(i); dirty = true; }
      if (dirty) stripTex.needsUpdate = true;
      const su = stripMat.uniforms;
      su.uReveal.value = travel; su.uOn.value = span(p, 0.4, 0.45);
      (su.uFog.value as THREE.Color).copy(fog.color); su.uFogNear.value = fog.near; su.uFogFar.value = fog.far;
      strip.visible = camY < 0;
    }

    // ---------- markers
    const placed: { el: HTMLDivElement; x: number; y: number }[] = [];
    const nowMs = performance.now();
    for (const d of m.dets) {
      const mk = MK.get(d.id) || makeMarker(d);
      const vis = !!d.shownAt && camY < 0;
      mk.g.visible = vis;
      if (!vis) { mk.el.style.display = "none"; continue; }
      contactPos(d, mk.g.position);
      const age = (nowMs - d.shownAt) / 1000;
      mk.g.scale.setScalar(0.3 + 0.7 * easeInOut(Math.min(1, age / 0.5)));
      mk.head.rotation.y = t * 1.4; mk.head.position.y = 8.4 + Math.sin(t * 2 + d.frame) * 0.25;
      const wa = (age % 2.2) / 2.2;
      mk.wave.scale.setScalar(1 + wa * Math.max(8, mk.r * 3));
      (mk.wave.material as THREE.MeshBasicMaterial).opacity = (1 - wa) * 0.8 * (age < 6.6 ? 1 : 0.35);
      tmpV.copy(mk.g.position); tmpV.y += 9.6; tmpV.project(camera);
      if (tmpV.z < 1 && Math.abs(tmpV.x) < 1.1 && Math.abs(tmpV.y) < 1.1) {
        mk.el.style.display = "block"; placed.push({ el: mk.el, x: ((tmpV.x + 1) / 2) * W, y: ((1 - tmpV.y) / 2) * H });
      } else mk.el.style.display = "none";
    }
    // Labels of nearby contacts would overlap: stack them upward.
    placed.sort((a, b) => b.y - a.y);
    for (let i = 0; i < placed.length; i++) for (let k = 0; k < i; k++) {
      const A = placed[i], B = placed[k];
      if (Math.abs(A.x - B.x) < 150 && Math.abs(A.y - B.y) < 26) A.y = B.y - 27;
    }
    // A label under the caption or the readout box cannot be read, and
    // stacking it on top would hide the HUD instead: hide the label, keep
    // the marker (and it reappears as the camera moves on).
    const cardBox = el.card.getBoundingClientRect();
    const hud = [el.capK.parentElement, el.sonarLed.parentElement]
      .filter((x): x is HTMLElement => !!x && x.offsetParent !== null)
      .map((x) => { const b = x.getBoundingClientRect(); return { l: b.left - cardBox.left - 6, r: b.right - cardBox.left + 6, t: b.top - cardBox.top - 6, b: b.bottom - cardBox.top + 6 }; });
    for (const L of placed) {
      const w = L.el.offsetWidth || 150, h = L.el.offsetHeight || 24;
      const box = { l: L.x - w / 2, r: L.x + w / 2, t: L.y - h, b: L.y };
      const hit = hud.some((z) => box.l < z.r && box.r > z.l && box.t < z.b && box.b > z.t);
      if (hit) { L.el.style.display = "none"; continue; }
      L.el.style.left = L.x + "px"; L.el.style.top = L.y + "px";
    }

    // ---------- HUD readouts (rig numbers, not telemetry)
    el.rDepth.textContent = (RIG.towDepthM * deploy).toFixed(1) + " m";
    el.rLay.textContent = (deploy * RIG.laybackM).toFixed(1) + " m";
    el.rAlt.textContent = deploy > 0.05 ? alt.toFixed(1) + " m" : "— m";
    const moving = !V.frozen && p > 0.42 && p < 0.86 && !V.scrub;
    el.rSpd.textContent = (moving ? 4.0 : p < 0.42 ? 1.2 * deploy : 0.8).toFixed(1) + " kn";
    if (searching > 0.5 && !V.scrub) pingN += Math.round(dt * 12);
    el.rPing.textContent = searching > 0.3 ? "#" + pingN.toLocaleString() : "—";
    const on = searching > 0.3;
    el.sonarLed.dataset.on = on ? "1" : "0";
    el.sonarText.textContent = on ? "SONAR LIVE" : V.frozen ? "SONAR OFF" : "SONAR IDLE";
    drawWaterfall(travel, span(p, 0.4, 0.45) > 0);

    wu.uTime.value = t;
    R.clear(); R.render(waterScene, waterCam); R.clearDepth(); R.render(scene, camera);
  }
  raf = requestAnimationFrame(frame);

  return {
    webgl: true,
    dispose() {
      disposed = true;
      cancelAnimationFrame(raf);
      cleanups.forEach((f) => f());
      clearMarkers();
      // DRACOLoader holds WASM decoder workers; the renderer holds the GL context.
      draco.dispose();
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (mesh.isMesh || (o as THREE.Line).isLine) {
          mesh.geometry?.dispose();
          const mat = mesh.material as THREE.Material | THREE.Material[];
          (Array.isArray(mat) ? mat : [mat]).forEach((x) => x?.dispose());
        }
      });
      rockGeo.dispose(); rockMat.dispose(); stripTex?.dispose(); waterMat.dispose();
      ENV_AIR.dispose(); ENV_WATER.dispose(); pmrem.dispose();
      R.dispose();
      R.forceContextLoss();
    },
  };
}
