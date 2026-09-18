"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

import {
  APPROVED_OPTICS,
  GLSL_CAUSTICS,
  GLSL_NOISE,
  GLSL_SCREEN_GRADE,
  GLSL_WATER_AT,
  WORK_Y,
} from "./optics";
import { buildSeabed, type BuildOpts } from "./seabed";
import { buildTargets, type TargetOpts } from "./targets";
import { makeUnderwaterUniforms, SHIPPED_FOG } from "./underwaterMaterial";

/* =============================================================================
 * The seabed sandbox renderer. NOT a product route - see app/lab/seabed/page.tsx.
 *
 * It renders the props against a faithful reproduction of the hero's UNDERWATER
 * water, because a fog match judged against approximate fog is worth nothing.
 * The backdrop below is the shadeBelow half of scene.ts's shader with the sky
 * and above-surface branches removed: the props never see those, and carrying
 * them would mean carrying the wave field too.
 *
 * ONE DELIBERATE DIFFERENCE FROM THE HERO. scene.ts builds its ray as
 * vec3(uv.x, uv.y-horizon, -1) - a principal-point OFFSET, not a pitched
 * camera - and shears the perspective matrix to match. That is the right call
 * for a fixed hero shot and the wrong one for a lab you need to orbit in, so
 * the backdrop here reconstructs its ray from the camera's actual inverse
 * projection instead. The two agree exactly at the hero's framing and stay
 * aligned anywhere else, which is what lets the seam be dragged across a rock
 * from any angle.
 * ========================================================================== */

const BACKDROP_FRAG = /* glsl */ `
precision highp float;
uniform vec2  uRes;
uniform float uTime;
uniform mat4  uInvProj;
uniform mat4  uCamWorld;
uniform vec3  uCamPos;
uniform float uSeabedY, uEyeDepth;
uniform float floorScale, sandR, sandG, sandB, sandGrain;
uniform float causticStrength, causticSharp, causticSpeed, causticBeat, causticFade;
uniform float fogDensity, absR, absG, absB;
uniform float exposure, vignette, grain, quality;

${GLSL_NOISE}
${GLSL_CAUSTICS}
${GLSL_WATER_AT}
${GLSL_SCREEN_GRADE}

void main(){
  vec2 frag = gl_FragCoord.xy/uRes;
  vec2 ndc  = frag*2.0-1.0;
  vec4 vp = uInvProj*vec4(ndc, -1.0, 1.0); vp /= vp.w;
  vec3 rd = normalize((uCamWorld*vec4(vp.xyz, 0.0)).xyz);
  vec3 ro = uCamPos;

  vec3 col; float path;
  if (rd.y < -0.0005){
    /* Down onto the floor: sand with the caustic web, exactly as scene.ts
       section 3 builds it. The +vec2(53,17) offset and the floorScale*0.1
       are not decoration - the props reuse this mapping so their dapple and
       the floor's are one continuous field. */
    float t = (ro.y - uSeabedY)/max(-rd.y, 1e-4);
    vec3 p = ro + rd*t;
    vec2 fuv = (p.xz + vec2(53.0,17.0))*(floorScale*0.1);
    float c = caustics(fuv, uTime*causticSpeed);
    float g = fbm(fuv*6.0)*sandGrain;
    float cFade = mix(1.0, exp(-t*0.09), causticFade);
    col  = vec3(sandR,sandG,sandB)*(0.55+g);
    col += vec3(0.85,0.95,1.0)*c*causticStrength*cFade;
    path = t;
  } else {
    /* Up into the column. The lab sits at working depth looking roughly level,
       so this is backdrop, not subject: the open-water colour plus a hint of
       the lit surface overhead, at full optical path. */
    col = waterAt(max(uEyeDepth - 6.0, 0.0))*1.15;
    col += vec3(0.72,0.93,1.0)*pow(clamp(rd.y,0.0,1.0), 3.0)*0.10;
    path = 240.0;
  }

  vec3 ab = vec3(absR,absG,absB);
  ab /= max((ab.r+ab.g+ab.b)/3.0, 1e-4);
  col = mix(col, waterAt(uEyeDepth), clamp(1.0 - exp(-path*fogDensity*ab), 0.0, 1.0));

  /* SECTION 11 grade, verbatim ordering from scene.ts:423-430. */
  col *= exposure;
  col = col/(1.0 + col*0.55);
  float lum = dot(col, vec3(0.299,0.587,0.114));
  col = mix(vec3(lum), col, 1.18);
  col = screenGrade(col, frag, uCamPos.y, vignette, grain, uTime);
  gl_FragColor = vec4(clamp(col,0.0,1.0), 1.0);
}
`;

const COMPOSITE_FRAG = /* glsl */ `
precision highp float;
uniform sampler2D tShipped, tPatched;
uniform vec2 uRes;
uniform float uSeam, uMode;   // 0 off(patched) 1 wipe 2 blend 3 shipped
void main(){
  vec2 uv = gl_FragCoord.xy/uRes;
  vec3 a = texture2D(tShipped, uv).rgb;
  vec3 b = texture2D(tPatched, uv).rgb;
  vec3 c;
  if (uMode < 0.5)      c = b;
  else if (uMode < 1.5){
    c = uv.x < uSeam ? a : b;
    /* A hairline at the seam. Without it the eye anchors on the brightness step
       and reads the whole frame as one image, which is how a 30% error survives
       a review. */
    float d = abs(uv.x - uSeam)*uRes.x;
    c = mix(vec3(0.77,0.97,1.0), c, smoothstep(0.0, 1.2, d));
  }
  else if (uMode < 2.5) c = mix(a, b, uSeam);
  else                  c = a;
  gl_FragColor = vec4(c, 1.0);
}
`;

export type SceneHandle = {
  setUniform: (name: string, v: number) => void;
  setCompare: (mode: number, seam: number) => void;
  setPlaying: (p: boolean) => void;
  rebuild: (opts: BuildOpts, targets: TargetOpts) => void;
};

export function SeabedScene({
  values,
  build,
  targets,
  compare,
  seam,
  playing,
  onHandle,
}: {
  values: Record<string, number>;
  build: BuildOpts;
  targets: TargetOpts;
  compare: number;
  seam: number;
  playing: boolean;
  onHandle?: (h: SceneHandle) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const handleRef = useRef<SceneHandle | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;  // PCFSoft is deprecated in r185
    renderer.autoClear = false;

    const uniforms = makeUnderwaterUniforms(values);
    const SEABED_Y = -APPROVED_OPTICS.seabedDepth;

    /* ---------------------------------------------------------- backdrop */
    const bdUniforms: Record<string, THREE.IUniform> = {
      uRes: { value: new THREE.Vector2(1, 1) },
      uTime: { value: 0 },
      uInvProj: { value: new THREE.Matrix4() },
      uCamWorld: { value: new THREE.Matrix4() },
      uCamPos: { value: new THREE.Vector3() },
      uSeabedY: { value: SEABED_Y },
      uEyeDepth: { value: -WORK_Y },
      floorScale: { value: APPROVED_OPTICS.floorScale },
      sandR: { value: 0.45 }, sandG: { value: 0.44 }, sandB: { value: 0.78 },
      sandGrain: { value: 0.87 },
      causticStrength: { value: APPROVED_OPTICS.causticStrength },
      causticSharp: { value: APPROVED_OPTICS.causticSharp },
      causticSpeed: { value: APPROVED_OPTICS.causticSpeed },
      causticBeat: { value: APPROVED_OPTICS.causticBeat },
      causticFade: { value: APPROVED_OPTICS.causticFade },
      fogDensity: { value: APPROVED_OPTICS.fogDensity },
      absR: { value: APPROVED_OPTICS.absR },
      absG: { value: APPROVED_OPTICS.absG },
      absB: { value: APPROVED_OPTICS.absB },
      exposure: { value: 1.2 },
      vignette: { value: APPROVED_OPTICS.vignette },
      grain: { value: APPROVED_OPTICS.grain },
      quality: { value: APPROVED_OPTICS.quality },
    };
    const bdScene = new THREE.Scene();
    const bdCam = new THREE.Camera();
    const bdMat = new THREE.ShaderMaterial({
      uniforms: bdUniforms,
      vertexShader: "void main(){ gl_Position = vec4(position.xy, 0.0, 1.0); }",
      fragmentShader: BACKDROP_FRAG,
      depthTest: false,
      depthWrite: false,
    });
    bdScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), bdMat));

    /* ------------------------------------------------------------- scene */
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, 1, 0.4, 5000);

    /* Lights at the FULLY SUBMERGED end of the hero's schedule (scene.ts:961-967,
       sub=1 at working depth). Tuning props under the hero's air lighting would
       tune them for a frame they are never in. */
    const sun = new THREE.DirectionalLight(0xfff2dc, 2.6 - 1.5);
    sun.position.set(0, 0.115 * 400 + 120, -400);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.near = 1; sun.shadow.camera.far = 420;
    sun.shadow.camera.left = -60; sun.shadow.camera.right = 60;
    sun.shadow.camera.top = 60; sun.shadow.camera.bottom = -60;
    sun.shadow.bias = -0.0012; sun.shadow.normalBias = 0.35;
    scene.add(sun, sun.target);
    /* SUBMERGED hemisphere colours, not the air ones. scene.ts:964-965 swaps
       both at sub>0.5, and the ground half goes from 0x0a2740 to 0x16506f -
       nearly three times brighter. Lighting the props with the air values made
       them read as silhouettes here while the live hero shows them clearly,
       which is a lab bug, not a finding. */
    scene.add(new THREE.HemisphereLight(0x9fe0ff, 0x16506f, 1.1 + 1.5));
    const down = new THREE.DirectionalLight(0x9fd8f2, 1.35);
    down.position.set(0, 200, 0); scene.add(down);
    const rim = new THREE.DirectionalLight(0x7fc8ee, 0.85);
    rim.position.set(-160, 40, 120); scene.add(rim);

    /* ENV_WATER, verbatim stops from scene.ts:549. The props are dielectric so
       this matters less than it does for the hull, but leaving it out changes
       the ambient and the A/B would be measuring the wrong thing. */
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envCanvas = document.createElement("canvas");
    envCanvas.width = 8; envCanvas.height = 128;
    {
      const x = envCanvas.getContext("2d")!;
      const g = x.createLinearGradient(0, 0, 0, 128);
      for (const [at, col] of [[0, "#f2ffff"], [0.14, "#d6f2ff"], [0.32, "#7cc4e4"],
                               [0.62, "#2f73a0"], [1, "#15405e"]] as [number, string][]) {
        g.addColorStop(at, col);
      }
      x.fillStyle = g; x.fillRect(0, 0, 8, 128);
    }
    const envTex = new THREE.CanvasTexture(envCanvas);
    envTex.mapping = THREE.EquirectangularReflectionMapping;
    envTex.colorSpace = THREE.SRGBColorSpace;
    const envRT = pmrem.fromEquirectangular(envTex);
    envTex.dispose();
    scene.environment = envRT.texture;

    /* The floor is drawn by the backdrop shader, so there is no geometry for a
       shadow to land on - same problem and same answer as the hero. */
    const shadowCatcher = new THREE.Mesh(
      new THREE.PlaneGeometry(700, 700),
      new THREE.ShadowMaterial({ opacity: 0.3, transparent: true })
    );
    shadowCatcher.rotation.x = -Math.PI / 2;
    shadowCatcher.position.y = SEABED_Y;
    shadowCatcher.receiveShadow = true;
    scene.add(shadowCatcher);

    /* Two builds of the SAME layout. Same seeds, so the seam isolates material
       and tessellation and nothing else. */
    let shipped = buildSeabed(uniforms, { ...build, rockDetail: 0, headDetail: 0,
      branchRadial: 5, slabBevel: 0, hueJitter: 0, valueJitter: 0 }, false);
    let patched = buildSeabed(uniforms, build, true);
    /* The targets go in BOTH builds so the wipe still means something across
       them: the wreck is the largest single surface in the scene and therefore
       the clearest read on whether the absorption match is right. */
    let shipTargets = buildTargets(uniforms, targets, false);
    let patchTargets = buildTargets(uniforms, targets, true);
    shipped.group.add(shipTargets.group);
    patched.group.add(patchTargets.group);
    shipped.group.position.y = SEABED_Y;
    patched.group.position.y = SEABED_Y;
    scene.add(shipped.group, patched.group);
    scene.fog = new THREE.Fog(SHIPPED_FOG.color, SHIPPED_FOG.near, SHIPPED_FOG.far);

    /* ------------------------------------------------------ render targets */
    const mkRT = () => {
      const rt = new THREE.WebGLRenderTarget(1, 1, {
        type: THREE.UnsignedByteType,
        samples: 4,
      });
      /* sRGB on the TARGET, so the scene is encoded on the way in and the
         composite can sample and emit raw. A linear RT here would make the wipe
         darken one half and the comparison would be measuring a gamma bug. */
      rt.texture.colorSpace = THREE.SRGBColorSpace;
      return rt;
    };
    const rtShipped = mkRT(), rtPatched = mkRT();

    const cmpUniforms: Record<string, THREE.IUniform> = {
      tShipped: { value: rtShipped.texture },
      tPatched: { value: rtPatched.texture },
      uRes: { value: new THREE.Vector2(1, 1) },
      uSeam: { value: seam },
      uMode: { value: compare },
    };
    const cmpScene = new THREE.Scene();
    const cmpCam = new THREE.Camera();
    cmpScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
      uniforms: cmpUniforms,
      vertexShader: "void main(){ gl_Position = vec4(position.xy, 0.0, 1.0); }",
      fragmentShader: COMPOSITE_FRAG,
      depthTest: false, depthWrite: false,
    })));

    /* ------------------------------------------------------------- camera */
    /* FRAMED AS THE HERO FRAMES IT. The hero looks DOWN on the field from
       working depth (camY -16, floor -30, so ~14 m of altitude), and that is
       the only view these props are ever seen from. A low, near-level default
       put the camera under their horizon and every rock came back a silhouette
       - which says nothing about the material and would have had us tuning
       albedo to fix a camera. sin(0.30)*44 + (-29) = -16, the hero's eye. */
    const target = new THREE.Vector3(0, SEABED_Y + 1, -50);
    const orbit = { az: 0.0, el: 0.30, dist: 44 };
    function place() {
      camera.position.set(
        target.x + Math.sin(orbit.az) * Math.cos(orbit.el) * orbit.dist,
        target.y + Math.sin(orbit.el) * orbit.dist,
        target.z + Math.cos(orbit.az) * Math.cos(orbit.el) * orbit.dist
      );
      camera.lookAt(target);
      sun.target.position.copy(target);
      sun.target.updateMatrixWorld();
    }
    place();

    let dragging = false, lx = 0, ly = 0;
    const onDown = (e: PointerEvent) => { dragging = true; lx = e.clientX; ly = e.clientY;
      canvas.setPointerCapture(e.pointerId); };
    const onUp = (e: PointerEvent) => { dragging = false;
      try { canvas.releasePointerCapture(e.pointerId); } catch {} };
    const onMove = (e: PointerEvent) => {
      if (!dragging) return;
      orbit.az -= (e.clientX - lx) * 0.005;
      orbit.el = THREE.MathUtils.clamp(orbit.el + (e.clientY - ly) * 0.004, -0.35, 0.9);
      lx = e.clientX; ly = e.clientY; place();
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      orbit.dist = THREE.MathUtils.clamp(orbit.dist * (1 + Math.sign(e.deltaY) * 0.08), 6, 200);
      place();
    };
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("wheel", onWheel, { passive: false });

    /* --------------------------------------------------------------- loop */
    const resize = () => {
      const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
      renderer.setSize(w, h, false);
      const dpr = renderer.getPixelRatio();
      rtShipped.setSize(w * dpr, h * dpr);
      rtPatched.setSize(w * dpr, h * dpr);
      camera.aspect = w / h; camera.updateProjectionMatrix();
      (bdUniforms.uRes.value as THREE.Vector2).set(w * dpr, h * dpr);
      (cmpUniforms.uRes.value as THREE.Vector2).set(w * dpr, h * dpr);
      (uniforms.uRes.value as THREE.Vector2).set(w * dpr, h * dpr);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    let raf = 0, t0 = performance.now(), clock = 0, running = playing;

    function renderVariant(rt: THREE.WebGLRenderTarget, showPatched: boolean) {
      shipped.group.visible = !showPatched;
      patched.group.visible = showPatched;
      renderer.setRenderTarget(rt);
      renderer.clear();
      renderer.render(bdScene, bdCam);
      renderer.clearDepth();
      renderer.render(scene, camera);
      renderer.setRenderTarget(null);
    }

    function frame() {
      raf = requestAnimationFrame(frame);
      const now = performance.now();
      if (running) clock += (now - t0) / 1000;
      t0 = now;

      uniforms.uTime.value = clock;
      bdUniforms.uTime.value = clock;
      uniforms.uEyeDepth.value = Math.max(-camera.position.y, 0);
      bdUniforms.uEyeDepth.value = Math.max(-camera.position.y, 0);

      camera.updateMatrixWorld();
      (bdUniforms.uInvProj.value as THREE.Matrix4).copy(camera.projectionMatrixInverse);
      (bdUniforms.uCamWorld.value as THREE.Matrix4).copy(camera.matrixWorld);
      (bdUniforms.uCamPos.value as THREE.Vector3).copy(camera.position);

      const mode = cmpUniforms.uMode.value as number;
      if (mode === 0) { renderVariant(rtPatched, true); }
      else if (mode === 3) { renderVariant(rtShipped, false); }
      else { renderVariant(rtShipped, false); renderVariant(rtPatched, true); }

      renderer.clear();
      renderer.render(cmpScene, cmpCam);
    }
    frame();

    const handle: SceneHandle = {
      setUniform(name, v) {
        if (uniforms[name]) (uniforms[name] as THREE.IUniform).value = v;
      },
      setCompare(mode, s) {
        cmpUniforms.uMode.value = mode;
        cmpUniforms.uSeam.value = s;
      },
      setPlaying(p) { running = p; },
      rebuild(opts, tOpts) {
        scene.remove(shipped.group, patched.group);
        shipped.dispose(); patched.dispose();
        shipTargets.dispose(); patchTargets.dispose();
        shipped = buildSeabed(uniforms, { ...opts, rockDetail: 0, headDetail: 0,
          branchRadial: 5, slabBevel: 0, hueJitter: 0, valueJitter: 0 }, false);
        patched = buildSeabed(uniforms, opts, true);
        shipTargets = buildTargets(uniforms, tOpts, false);
        patchTargets = buildTargets(uniforms, tOpts, true);
        shipped.group.add(shipTargets.group);
        patched.group.add(patchTargets.group);
        shipped.group.position.y = SEABED_Y;
        patched.group.position.y = SEABED_Y;
        scene.add(shipped.group, patched.group);
      },
    };
    handleRef.current = handle;
    onHandle?.(handle);

    /* A debug handle, same courtesy the hero gives itself with
       window.__heroProgress. A lab you cannot interrogate from the console is a
       lab where every question costs a rebuild. */
    (window as unknown as Record<string, unknown>).__sb = {
      scene, renderer, camera, uniforms, shipped, patched, sun,
    };

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("wheel", onWheel);
      shipped.dispose(); patched.dispose();
      rtShipped.dispose(); rtPatched.dispose();
      bdMat.dispose(); envRT.dispose(); pmrem.dispose();
      shadowCatcher.geometry.dispose();
      (shadowCatcher.material as THREE.Material).dispose();
      renderer.dispose();
      handleRef.current = null;
    };
    // Mount once. Every live control goes through the handle, because
    // rebuilding a GL context on a slider drag is how a lab becomes unusable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const h = handleRef.current; if (!h) return;
    for (const [k, v] of Object.entries(values)) h.setUniform(k, v);
  }, [values]);

  useEffect(() => { handleRef.current?.setCompare(compare, seam); }, [compare, seam]);
  useEffect(() => { handleRef.current?.setPlaying(playing); }, [playing]);
  useEffect(() => { handleRef.current?.rebuild(build, targets); }, [build, targets]);

  return <canvas ref={canvasRef} className="h-full w-full touch-none" />;
}
