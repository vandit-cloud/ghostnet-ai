# GhostNet-AI — Technical Ocean & Underwater Rendering Implementation Specification

Implement the GhostNet-AI ocean and underwater environment as a physically coherent, multi-scale real-time rendering system.

Do not interpret this as a request for a generic “realistic water shader.” Implement the individual physical phenomena described below as connected systems. The systems must share the same world coordinates, lighting direction, camera depth, water-depth model, and time source where appropriate.

The primary goal is physical coherence.

The rendered result must communicate a large Atlantic ocean surface above water and a deep, optically participating water volume below it.

The implementation must remain compatible with the existing GhostNet hero choreography.

Do not redesign the hero animation, towfish physics, sonar geometry, HUD, typography, contact logic, or page structure while implementing this system.

The objective is to make the ocean behave as one coherent physical environment rather than as a collection of unrelated visual effects.

## 1. Coordinate System and Physical Reference

Use the existing GhostNet world coordinate system.

Required constants:

```js
const TOW_DEPTH = 34;
const SEABED_Y = -52;
const SURVEY_SPEED = 2.0;
const TOWFISH_DISPLAY_SCALE = 2.6;
const TOW_POINT = new THREE.Vector3(0, 2.6, 13.2);
```

Waterline:

```js
const WATER_SURFACE_Y = 0;
```

Vessel:

- Approximate length: 28m
- Waterline: `y = 0`
- Longitudinal range: approximately `z = -14 to +14`

Towfish true physical size:

- Approximately 1.3m

Towfish display scale:

- 2.6x

Do not alter physical scene scale to compensate for rendering problems. Use rendering, lighting, attenuation, and camera composition to solve readability.

## 2. Scroll and Time Separation

Maintain a strict distinction between narrative animation and environmental animation.

Scroll progress:

```js
p = clamp(scrollProgress, 0, 1);
```

Scroll controls:

- Vessel narrative position
- Towfish depth
- Towfish layback
- Cable geometry
- Camera narrative position
- Sonar state
- Contact state

Elapsed time controls only environmental dynamics such as:

- Wave evolution
- Marine snow drift
- Bubble movement
- Caustic movement
- Subtle surface variation
- Subtle environmental motion
- Idle environmental movement

Do not allow elapsed time to modify the physical state of the survey operation.

Reverse scrolling must exactly reverse the narrative state.

Do not create irreversible animation state.

## 3. Ocean Surface Architecture

Do not implement the ocean using one sine wave.

Build the surface from multiple wave components.

Minimum conceptual structure:

- Large swell
- Medium wind waves
- Small surface waves
- Micro-normal detail

Each wave layer must have independent:

- Wavelength
- Amplitude
- Direction
- Phase
- Speed

Do not use identical direction and speed for every layer.

Use one dominant direction plus secondary directions.

Do not use completely random directions.

## 4. Large-Scale Swell

Implement low-frequency displacement.

Purpose:

- Establish ocean scale
- Create broad surface elevation
- Create horizon-scale movement
- Avoid a flat-plane appearance

Large waves must move slowly.

Do not create storm-sized waves.

Do not create surf waves.

The large-scale layer should primarily influence geometry.

Use low spatial frequency and relatively low amplitude.

The exact amplitude should be tuned visually so the 28m vessel remains correctly scaled.

Do not let the vessel appear to be riding giant waves.

## 5. Medium-Scale Wave System

Implement multiple medium-frequency wave components.

Purpose:

- Break the large swell
- Create natural local surface structure
- Generate changing reflection patterns
- Prevent visible sinusoidal repetition

Use multiple wavelengths and directions.

Do not use one repeated normal texture as the medium-scale solution.

Medium waves should influence:

- Vertex displacement
- Surface normals
- Reflection
- Sun glitter

where technically practical.

## 6. Small-Scale Surface Detail

Add high-frequency surface detail.

This layer should primarily affect:

- Normal orientation
- Roughness
- Specular response
- Reflection breakup

Do not rely exclusively on high-frequency geometry.

Prefer normal/shader detail for very small wavelengths.

Small-scale detail must become visually weaker with distance.

Do not allow the entire ocean to display maximum microdetail at every distance.

## 7. Wave Implementation

Use a physically plausible real-time wave approximation.

Gerstner-style waves are acceptable and preferred over simple sine displacement when practical.

For each wave component, conceptually calculate:

```text
phase = dot(direction, worldXZ) * frequency + time * angularFrequency
```

Use a nonlinear displacement model where appropriate.

The final surface position should be the sum of multiple wave components:

```text
position = basePosition
         + largeWave
         + mediumWaveA
         + mediumWaveB
         + smallWaveA
         + smallWaveB
```

Do not expose this formula as scientific UI. It is an implementation mechanism.

## 8. Wave Interference

The combined waves must naturally interfere.

Do not synchronize their phases.

Initialize different phase offsets.

Use different wavelengths and speeds.

The surface pattern should continuously evolve without the entire ocean appearing to translate as one rigid texture.

## 9. Wave Direction

Define a dominant ocean direction.

Add secondary directions.

Do not use perfectly radial waves.

Do not use fully independent random directions per vertex.

The ocean must have coherent directional energy.

Example conceptual configuration:

```js
const waves = [
  largeSwell,
  mediumWaveA,
  mediumWaveB,
  smallWaveA,
  smallWaveB
];
```

Each wave receives its own:

- Direction
- Wavelength
- Amplitude
- Speed
- Phase
- Steepness

## 10. Surface Normals

Generate normals from the final displaced surface where geometry allows.

Add shader-level normal detail for smaller scales.

Combine normal contributions:

- Large geometry normal
- Medium geometry normal
- Small normal detail
- Micro normal detail

Normalize the final normal.

Do not create a single high-strength normal map.

Do not create repeating texture patterns.

The normal field must appear statistically irregular.

## 11. Surface Roughness

Water roughness should not be perfectly uniform.

Use subtle spatial variation.

Large-scale roughness variation should be very low frequency.

Small-scale roughness variation can be higher frequency.

Keep the overall water surface relatively reflective.

Do not make it look like polished glass.

Do not make it look like matte plastic.

## 12. Fresnel Response

Implement view-angle-dependent reflection.

Calculate:

```js
NdotV = max(dot(normal, viewDirection), 0.0);
```

Use a Schlick-style approximation or equivalent:

```js
F = F0 + (1.0 - F0) * pow(1.0 - NdotV, 5.0);
```

Use an appropriate low base reflectance for water.

Do not exaggerate the result.

Reflection should become stronger at grazing angles.

Reflection should become less dominant when looking more directly into the surface.

Do not create a white outline around the ocean.

## 13. Environment Reflection

Use the available sky/environment representation as the reflection source.

Reflection must be distorted by the water normal.

Do not use a perfectly sharp reflection.

Apply roughness and normal-based breakup.

At grazing angles:

- Reflection contribution increases

At more downward viewing angles:

- Transmitted/scattered water contribution becomes more significant

Do not introduce unrelated HDRI colors.

Keep the reflected environment consistent with the GhostNet palette.

## 14. Sun-Glitter System

Implement a procedural sun-glitter response.

Do not draw a white line across the ocean.

The glitter should result from:

- Sun direction
- Surface normal
- Camera direction

Conceptually:

```js
sunReflectionAlignment =
  max(dot(reflectedSunDirection, viewDirection), 0.0);
```

Use a high-power response to create small bright facets.

Multiply this by:

- Surface roughness variation
- Wave normal variation
- Distance attenuation

The result should be:

- Broken
- Irregular
- Directional
- Multi-scale

Do not use uniform sparkle particles.

Do not use star-shaped highlights.

Do not add excessive bloom.

## 15. Surface Reflection Breakup

Reflection must change across the surface.

Do not allow a cloud, sky, or environment reflection to appear as one perfectly continuous image.

Wave normals must break it into irregular structures.

Large waves produce broad distortion.

Small waves produce fine breakup.

The combined result should be visually complex without requiring a photographic texture.

## 16. Ocean Scale

The ocean surface must extend well beyond the camera's visible region.

Do not expose:

- Plane edges
- Corners
- Tiling boundaries
- Texture repetition
- Finite ocean patches

If using a tiled mesh:

- Use sufficient coverage
- Use continuous deformation
- Avoid visible tile transitions

If using shader displacement:

- Ensure the underlying geometry covers the full camera frustum

The ocean should visually behave as an effectively infinite surface.

## 17. Waterline

The water surface is:

```js
y = 0;
```

The transition between air and water must be continuous.

Do not switch between two unrelated materials at the waterline.

Do not simply fade a blue fullscreen overlay in.

The surface should physically occupy the waterline.

When the camera crosses the waterline, the optical transition must be smooth rather than binary.

## 18. Above-Water Optical Behavior

Above water:

- Sky visible
- Horizon visible
- Surface reflection dominant at grazing angles
- Vessel clearly illuminated
- Ocean surface strongly connected to sky

Do not apply strong underwater haze above the waterline.

Do not remove the horizon prematurely.

Do not tint the entire above-water scene blue.

## 19. Underwater Optical Model

Once submerged, model water as a participating medium.

For every relevant object/pixel, conceptually determine:

- Distance through water
- Camera depth
- Object depth

Use attenuation.

A useful model is:

```js
transmittance = exp(-extinctionCoefficient * opticalDistance);
```

where:

```text
extinctionCoefficient =
  absorptionCoefficient +
  scatteringCoefficient
```

Do not expose these as user-facing scientific claims.

They are rendering parameters.

## 20. Absorption

Implement wavelength-dependent attenuation conceptually.

Longer wavelengths should attenuate more strongly than wavelengths that remain visible at depth.

Do not simply multiply the scene by a uniform blue color.

Use the GhostNet water color ramp as the final visual constraint.

The implementation should create progressive loss of light with optical distance.

Near objects remain clearer.

Far objects become increasingly water-colored.

## 21. Scattering

Implement both:

- Forward scattering
- Back scattering

Forward scattering should contribute to directional underwater illumination.

Back scattering should contribute to atmospheric water visibility.

Do not make scattering uniform across the entire frame.

It should depend on:

- Light direction
- View direction
- Water depth
- Optical distance

## 22. Distance-Based Attenuation

For every underwater object, attenuation must depend on distance through the water.

Conceptually:

```js
visibility =
  exp(-density * underwaterPathLength);
```

Then blend the object toward the local water color:

```js
finalColor =
  objectColor * visibility +
  waterColor * (1.0 - visibility);
```

Use nonlinear attenuation.

Do not use a simple linear fade.

Do not use one global opacity value for the entire underwater scene.

## 23. Depth-Based Attenuation

In addition to optical distance, water color should vary with depth.

Use the existing GhostNet four-band depth system.

The exact source-specification RGB values must be retained.

Do not invent a new water palette.

Use:

```js
BAND_BLEND = 13;
```

for smooth transitions.

Interpolate between adjacent water bands rather than creating hard thresholds.

## 24. Combined Depth and Distance

Do not choose between depth fog and distance fog.

Use both.

An object can be:

- Deep but close
- Shallow but far
- Deep and far

These conditions must produce different visibility.

The controlling quantity is optical path length plus depth-dependent water behavior.

## 25. Water-Band Interpolation

Implement a smooth interpolation function.

Conceptually:

```js
function sampleWaterColor(depth) {
  // determine surrounding water bands
  // interpolate using smooth transition
  // use BAND_BLEND = 13m
}
```

Do not use hard `if depth > threshold` color switches.

Use smooth interpolation.

Avoid visible horizontal seams.

## 26. Atmospheric Haze

Underwater haze must be depth-aware and distance-aware.

Near camera:

- Low attenuation
- High detail

Mid-distance:

- Moderate attenuation
- Reduced contrast
- Water tint

Far distance:

- Strong attenuation
- Low contrast
- Blend toward water color

Do not blur everything equally.

Do not use uniform blue fog.

## 27. Haze and Object Sharpness

Do not destroy object edges unnecessarily.

Preserve geometric silhouettes.

Reduce:

- Contrast
- Saturation
- Brightness
- Fine detail

before completely removing the object.

The towfish and ghost-net contact must retain useful shape information.

## 28. Underwater Color Grading

Do not apply a generic underwater LUT.

Do not use:

- Teal/orange grading
- Cinematic blue
- Green scuba filter
- Deep black abyss

Use the GhostNet palette and physically motivated attenuation.

The final color should be the result of:

- Object material
- Lighting
- Absorption
- Scattering
- Water-band color
- Distance attenuation

## 29. Underwater Sunlight

Create a dominant directional sunlight source.

Use the same direction for:

- Surface highlights
- Underwater illumination
- God rays
- Caustics
- Seabed lighting
- Object shading

Do not create independent lighting directions for each effect.

All effects must appear to originate from the same sun/environment.

## 30. God Rays

Implement volumetric-looking light shafts.

The effect should approximate:

```text
directional sunlight
× water scattering
× depth attenuation
× distance attenuation
```

Do not use hard cone geometry.

Do not use solid spotlight meshes.

Do not create rectangular volumetric boundaries.

The shafts must be:

- Soft
- Irregular
- Low contrast
- Depth-dependent
- Directional

## 31. God-Ray Attenuation

God rays should weaken as:

- Water depth increases
- Camera-to-volume distance increases
- Light contribution decreases

Do not keep the same ray brightness from the surface to the seabed.

Use smooth attenuation.

The approximate visual influence should extend on the order of:

```text
96m
```

Treat 96m as the approximate useful visual range, not as a hard cutoff.

## 32. God-Ray Variation

Do not use perfectly uniform beams.

Add subtle spatial variation.

Possible implementation:

```text
low-frequency noise
+
directional gradient
+
depth attenuation
+
soft radial/volume attenuation
```

The noise must not create obvious texture patterns.

## 33. Caustics

Implement animated underwater caustic illumination.

Caustics should be generated from moving surface information or a convincing procedural approximation.

They must not be a static image.

The caustic contribution should depend on:

- Sun direction
- Surface movement
- Depth
- Surface orientation

Apply caustic influence primarily to:

- Seabed
- Large underwater surfaces
- Selected physical objects

Do not illuminate the entire scene equally.

## 34. Caustic Scale

Use multiple spatial frequencies:

- Large caustic structures
- Medium structures
- Small breakup

Avoid repeating square patterns.

Avoid obvious UV tiling.

## 35. Caustic Animation

Animate caustics slowly.

Use:

- Multiple phases
- Multiple directions
- Multiple frequencies

Do not simply translate one texture.

Do not synchronize caustics perfectly with the ocean mesh.

The surface and caustics should be correlated enough to feel related but not so synchronized that the procedural pattern becomes obvious.

## 36. Caustic Attenuation

Reduce caustic strength with:

- Depth
- Distance
- Water attenuation

Caustics should be stronger where sufficient sunlight reaches the seabed.

They should become softer and weaker with increasing depth.

## 37. Marine Snow

Create a volumetric particle field.

Use multiple particle populations.

Recommended conceptual populations:

- Micro particles
- Small particles
- Occasional medium particles

Each population should have different:

- Size
- Speed
- Density
- Opacity
- Drift

Do not use one uniform particle system.

## 38. Marine-Snow Motion

Use predominantly downward drift with current influence.

Conceptually:

```js
velocity =
  downwardDrift +
  horizontalCurrent +
  lowFrequencyNoise;
```

Do not make every particle move vertically at exactly the same velocity.

Do not make all particles orbit the camera.

Do not lock particles to screen space.

They should exist in world space.

## 39. Marine-Snow Lighting

Particle brightness should depend on the underwater lighting field.

Do not render all particles as white emissive dots.

Use subdued water-colored scattering.

Near-camera particles can be slightly more visible.

Distant particles should attenuate.

## 40. Marine-Snow Density

Keep density restrained.

The user should notice the presence of suspended matter subconsciously.

If individual particles become the primary visual subject, density is too high.

## 41. Marine-Snow Depth Behavior

Marine snow should remain more visible where there is enough illumination.

At greater depth and distance:

- Lower visibility
- Lower contrast
- More water-color blending

Avoid an even layer of particles filling every part of the frame.

## 42. Bubble Columns

Implement exactly three bubble-column regions.

Each column should contain particles of variable size.

Bubble motion:

```text
upward velocity
+
small horizontal drift
+
small noise-based lateral motion
```

Do not make the columns perfectly straight.

Do not use identical spacing.

Do not use identical bubble sizes.

Do not use bright white emissive bubbles.

## 43. Bubble Optical Response

Bubbles should be brighter than surrounding marine snow when appropriately illuminated, but remain subtle.

Use:

- Soft highlight
- Partial transparency
- Water interaction
- Depth attenuation

Avoid cartoon outlines.

## 44. Seabed Emergence

The seabed must emerge progressively during descent.

Do not reveal it suddenly.

At shallow camera depth:

- Mostly haze
- Large seabed structure barely visible

At intermediate depth:

- Large relief visible
- Medium structure beginning to resolve

At deep camera position:

- Seabed structure
- Debris
- Ghost net
- Sonar relationship

become readable.

## 45. Seabed Dimensions

Maintain approximately:

```text
1500m × 1500m
```

and approximately:

```text
150 × 150
```

subdivision structure where already part of the implementation.

Maintain:

```text
SEABED_Y = -52
```

Do not move the seabed upward to compensate for incorrect atmospheric rendering.

## 46. Seabed Displacement

Use low-frequency procedural displacement.

Combine:

- Large relief noise
- Medium relief
- Small local variation

Keep amplitude restrained.

The seabed should look like marine terrain, not mountainous terrain.

## 47. Seabed Material

Use primarily diffuse/rough material response.

Do not make the seabed glossy.

Allow subtle lighting variation.

Apply water attenuation based on:

- Camera-to-seabed distance
- Depth

Distant seabed should lose contrast.

## 48. Environmental Scale Objects

Retain the specified environmental objects:

- Boulders
- Drum
- Tyre
- Trap
- Floats
- Ghost net

Their physical scale must remain plausible.

Do not scale objects arbitrarily to fill the composition.

These objects exist partly to provide scale references.

## 49. Contact-Object Visibility

The ghost net must remain physically grounded.

Do not make it float.

Do not illuminate it with a fake circular spotlight.

Do not make it emissive.

Use:

- Environment lighting
- Caustic contribution
- Soft shadow
- Sonar context
- Detection marker

to make it readable.

## 50. Shadow System

Use soft underwater shadows where feasible.

Shadows should communicate:

- Object height above seabed
- Contact with seabed
- Relative position

Do not create hard black shadows.

Do not use shadows as decorative shapes.

## 51. Contact Lighting

If additional local contact illumination is required, use a very broad, low-intensity contribution.

It must not appear as:

- Spotlight
- Flashlight
- Glowing circle
- Game-object highlight

The viewer should believe the contact is naturally visible because the environment and detection system reveal it.

## 52. Surface/Subsurface Continuity

The same world must be rendered above and below the surface.

Do not create separate above-water and underwater scenes with a hard transition.

The vessel, cable, towfish, water volume, sunlight, and seabed must exist in one continuous coordinate system.

## 53. Vessel-Water Integration

The vessel must intersect the water surface correctly.

Verify:

- Hull waterline
- Reflection
- Surface displacement
- Shadowing
- Wake
- Camera visibility

The hull must not:

- Float above water
- Sink through water
- Clip visibly through waves

## 54. Vessel Wake

If a wake exists or is added, keep it physically restrained for:

```text
SURVEY_SPEED = 2.0m/s
```

Do not create a speedboat wake.

The wake should be:

- Subtle
- Wide relative to hull
- Low contrast
- Integrated with surface waves

Foam is optional and must remain restrained.

## 55. Do Not Simulate Unnecessary Foam

Do not add white foam everywhere.

Foam should appear only where physically justified:

- Breaking wave
- Turbulent wake
- Strong surface disturbance

For the GhostNet survey environment, restrained surface conditions are preferable.

## 56. Camera-Relative Effects

Do not implement important world effects entirely in screen space unless unavoidable.

Marine snow should be world-space.

Bubbles should be world-space.

Surface waves should be world-space.

Seabed caustics should be world/object-space or world-coherent.

Screen-space effects may be used for:

- Subtle atmospheric post-process
- Carefully controlled god-ray approximation
- Vignette

but should not replace physical world relationships.

## 57. No Fullscreen Blue Overlay

Do not solve underwater appearance with a fullscreen blue overlay or transparent blue plane.

Underwater color must come from the rendering model.

A subtle global post-process may support the result, but it cannot be the primary water system.

## 58. No Video or Photographic Cheat

Do not use:

- Underwater video
- Looped ocean video
- Photographic fullscreen background
- Pre-rendered underwater sequence

The scene must remain interactive and physically connected to the 3D world.

## 59. No Fake Horizon

Do not create a hard horizontal line separating water and background.

Above water:

- Natural atmospheric horizon

Underwater:

- Progressive volumetric attenuation

The transition must be continuous.

## 60. No Rectangular Lighting Boundaries

Absolutely avoid visible:

- Rectangles
- Boxes
- Planes
- Hard cones
- Square caustic patches

in:

- Fog
- God rays
- Caustics
- Surface reflection
- Underwater light

Every effect must fade smoothly.

## 61. No Uniform Procedural Noise

Do not use the same noise function with the same scale for:

- Waves
- Caustics
- Fog
- Marine snow
- Seabed

Each phenomenon needs an appropriate spatial and temporal scale.

## 62. Shared Lighting Direction

Create one authoritative sun/light direction.

Every environmental effect must derive from it.

Conceptually:

```js
const SUN_DIRECTION = ...;
```

Use it for:

- Surface glitter
- Surface reflection context
- Underwater scattering
- God rays
- Caustics
- Seabed illumination
- Object shading

Do not create conflicting directions.

## 63. Shared Time Source

Use one consistent elapsed-time source.

Conceptually:

```js
const t = elapsedTime;
```

Use this for environmental animation.

Different effects may use different frequency multipliers:

```js
waveTime = t * waveSpeed;
snowTime = t * snowSpeed;
bubbleTime = t * bubbleSpeed;
causticTime = t * causticSpeed;
```

but they must originate from the same time source.

## 64. Surface Detail Distance Management

Fine surface detail should diminish with distance.

Do not waste shader complexity rendering microscopic detail at the horizon.

Use, where practical:

- LOD
- Distance fade
- Normal-strength attenuation

Large waves remain visible at long distance.

Small waves primarily affect near-camera regions.

## 65. Underwater Effect Distance Management

Similarly:

```text
near = detail
mid = atmosphere
far = water color
```

Do not render expensive particles, caustics, or detailed geometry at unnecessary distances.

Use distance-based optimization.

## 66. Rendering Priority

If performance becomes constrained, preserve systems in this order:

1. Surface geometry
2. Water depth/attenuation
3. Underwater haze
4. Vessel/towfish/cable visibility
5. Seabed
6. Sonar
7. Lighting/scattering
8. Caustics
9. Marine snow
10. Bubbles
11. Secondary microdetail

Do not sacrifice physical scene coherence to preserve decorative effects.

## 67. Transparency Discipline

Avoid excessive transparent meshes.

Transparent rendering can cause:

- Sorting problems
- Overdraw
- Incorrect depth
- Darkening
- Edge artifacts

Prefer shader-based effects where appropriate.

For particles:

- Depth-aware fade
- Bounded particle count
- Appropriate blending
- Distance culling

Do not create dozens of stacked transparent fullscreen surfaces.

## 68. Avoid Emissive Realism Cheats

Do not use emission to make:

- Water
- Towfish
- Cable
- Marine snow
- Bubbles
- Seabed
- Ghost net

look readable.

Use actual illumination, reflection, scattering, material properties, and controlled detection graphics.

## 69. Post-Processing

Keep post-processing minimal.

Allowed/appropriate:

- Very subtle vignette
- Very subtle exposure adjustment
- Carefully controlled atmospheric treatment

Avoid:

- Heavy bloom
- Strong chromatic aberration
- Film grain dominating the scene
- Strong depth of field
- Heavy motion blur
- Cinematic LUT
- Teal/orange grading

The experience should retain technical precision.

## 70. GhostNet Grain

The specification calls for SVG turbulence grain at approximately:

```text
opacity ≈ 0.14
```

If this grain exists as a global visual treatment, keep it separate from the physical water simulation.

Do not add grain directly into the water shader unless required.

Do not increase grain to hide rendering artifacts.

## 71. Color Management

Verify renderer color management.

Ensure:

- Textures
- Materials
- Lighting
- Environment
- Post-processing
- CSS overlays

are not unintentionally using inconsistent color spaces.

Avoid double color conversion.

Avoid washed-out highlights.

Avoid crushed underwater blacks.

The final output should retain the intended GhostNet palette.

## 72. Debugging the Water

Create temporary development diagnostics where useful.

Useful debug modes:

- Show water surface only
- Show wave displacement
- Show surface normals
- Show Fresnel
- Show reflection
- Show sun glitter
- Show water depth
- Show attenuation
- Show haze
- Show god rays
- Show caustics
- Show marine snow
- Show bubbles
- Show seabed
- Show shadow
- Show contact

These controls should not ship in the production UI.

## 73. Debug Optical Depth

If possible, visualize development-only:

- Camera depth
- Object depth
- Optical path length
- Attenuation

This will help diagnose why the towfish or seabed becomes invisible.

## 74. Required Visual Behavior at p = 0

At the start:

- Camera above water
- Horizon visible
- Vessel clearly visible
- Ocean surface dominant
- Large-scale swell readable
- Surface reflection present
- Sun glitter present but restrained
- No deep underwater fog

The ocean must already look convincing before descent begins.

## 75. Required Visual Behavior During Deployment

As `p` progresses through deployment:

- Camera approaches water
- Towfish descends
- Cable length increases
- Waterline becomes visually important
- Underwater volume begins appearing
- Surface reflection remains coherent
- Horizon gradually loses dominance

Do not suddenly activate all underwater effects at one frame.

## 76. Required Visual Behavior Around p = 0.50

Around the end of deployment:

- Towfish approaches operating depth
- Water column dominates
- Underwater scattering increases
- Surface becomes less visually dominant
- Seabed begins to become structurally visible

The transition must remain smooth.

## 77. Required Visual Behavior Around p = 0.56

The camera-anchor transition occurs around the existing GhostNet transition range.

Use the established smooth camera interpolation.

The environment must not reveal the transition.

The towfish should become the dominant physical subject.

## 78. Required Visual Behavior Around p = 0.66

At this stage:

- Towfish established underwater
- Sonar active
- Underwater atmosphere fully established
- Seabed increasingly readable
- Cable still visible
- Water depth obvious

The environment should feel stable rather than cinematic.

## 79. Required Visual Behavior at p = 0.76

Contact/search phase begins.

The environment should support:

- Sonar search
- Seabed observation
- Towfish operation
- Detection preparation

The underwater scene should not suddenly become dramatically darker.

## 80. Required Visual Behavior at p = 1.00

Final state:

- Towfish at operating depth
- Cable physically connected
- Seabed visible
- Ghost net visible
- Associated debris/environment visible
- Sonar relationship coherent
- Detection marker visible
- `review_only` visible
- Underwater atmosphere retained

Do not turn the final frame into a special-effects climax.

## 81. Physical Coherence Test

At every scroll checkpoint verify:

- Does the cable connect to the towfish?
- Does the towfish remain at the correct depth?
- Does the seabed remain at the correct world coordinate?
- Does sonar remain beneath the towfish?
- Does the contact remain at the same world coordinate?
- Does the camera follow the intended subject?
- Does water attenuation correspond to camera depth?
- Does the lighting direction remain consistent?

If any answer is no, fix the physical relationship before adding visual effects.

## 82. Realism Test

The ocean should pass these tests:

- No single repeating wave pattern is obvious.
- No single texture is visually responsible for the entire ocean.
- No hard horizon seam is visible.
- No water-band seam is visible.
- No blue fullscreen overlay is visible.
- No rectangular god-ray boundary is visible.
- No square caustic pattern is visible.
- No uniform particle field is visible.
- No duplicate environmental objects exist for visual cheating.
- No object appears to float because of incorrect attenuation.
- No seabed edge is visible.
- No ocean-plane edge is visible.
- No cinematic color grade dominates.

## 83. Scale Test

Check relative scale between:

- 28m vessel
- 1.3m towfish
- 2.6x display scale
- 34m tow depth
- 52m seabed reference
- 1500m seabed extent
- 96m approximate light influence

The environment must feel large enough that these relationships make sense visually.

## 84. Performance Test

Measure performance after integrating the complete water system.

Test:

- Surface only
- Surface + underwater
- Full underwater
- Full contact scene

Monitor:

- Frame rate
- GPU frame time
- CPU frame time
- Draw calls
- Transparent objects
- Particle count
- Render-target resolution
- Shader cost

If the full scene is too expensive, reduce secondary effects before reducing physical scene quality.

## 85. Responsive Test

At approximately:

- 1440px
- 1200px
- 1000px
- 768px
- 400px

verify:

- No horizontal overflow
- Canvas remains contained
- Copy remains readable
- Water remains visually coherent
- Desktop chrome hides according to specification

Do not allow the canvas to create layout overflow.

## 86. Reduced-Motion Test

When:

```css
@media (prefers-reduced-motion: reduce)
```

is active:

- Do not run narrative animation
- Do not leave hero blank
- Show final contact/poster frame
- Keep HUD static
- Preserve accessible information

Environmental animation may also be disabled.

The static image must still communicate:

- Vessel
- Towfish
- Water
- Seabed
- Ghost net
- Contact state

## 87. Final Implementation Principle

Do not optimize for the number of effects.

Optimize for physical relationships.

The final water should behave as if these relationships exist:

```text
waves → surface normals

surface normals → reflection

surface normals + sunlight → glitter

sunlight + water → scattering

water distance → attenuation

water depth → spectral/color response

surface movement + sunlight → caustics

water volume → marine snow visibility

water volume + sunlight → god rays

distance + water → atmospheric perspective

seabed + lighting → contact visibility

vessel + water → surface interaction

towfish + water → underwater attenuation

cable + water → depth-dependent visibility
```

All of these systems must exist inside the same world-space physical model.

The final result should not look like a collection of visual effects layered on top of one another.

It should look like one ocean producing many observable optical phenomena.

## 88. Final Acceptance Condition

Do not mark the implementation complete until the following statement is visually true:

When the user slowly scrubs from the beginning of the GhostNet hero to the final contact state, the viewer perceives one continuous ocean with consistent scale, lighting, depth, water optics, surface behavior, underwater atmosphere, seabed visibility, vessel movement, towfish movement, cable geometry, sonar position, and contact location.

The scene must remain believable when scrubbed slowly in either direction.

If the result looks like a generic Three.js ocean, a blue fog effect, an underwater game environment, or a collection of disconnected effects, continue implementation and refinement.

Do not solve visual problems by adding more effects.

First inspect:

- Scale
- Camera
- Lighting direction
- Wave hierarchy
- Surface normals
- Fresnel
- Reflection
- Absorption
- Scattering
- Distance attenuation
- Depth attenuation
- Seabed visibility

Only after those are correct should secondary effects such as:

- Marine snow
- Bubbles
- Caustics
- God rays
- Microdetail

be increased.

The final system must prioritize physical coherence, scale, depth perception, optical attenuation, and restrained visual detail over spectacle.
