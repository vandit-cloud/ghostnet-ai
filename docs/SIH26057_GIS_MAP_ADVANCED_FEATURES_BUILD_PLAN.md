# GhostNet-AI — Advanced GIS Map Enhancement Build Plan

Status: **proposal only — nothing in this file has been implemented.**

Scope: this plan covers the next upgrade of the existing GIS Map experience in GhostNet-AI. It focuses on making the map feel more like a real marine-survey investigation tool: clearer, more realistic, more analytical, and more useful during review and demo workflows. This file does **not** implement changes by itself.

Current base already available in the product:
- 2D GIS map page
- 3D survey view
- survey track line
- clustered detections
- class / priority / review filters
- right-side investigation panel
- sonar frame linking

The plan below is written to extend the existing map stack, not replace it.

---

## 1. Main Goal

Build a GIS page that supports three strong product outcomes:

1. `Operational clarity` — the user should understand where the vessel went, what area was scanned, and where detections are concentrated.
2. `Investigation workflow` — the user should be able to move from map point to sonar evidence to review decision with minimal friction.
3. `Demo impact` — the map should look clean, realistic, and domain-specific enough to stand out in SIH judging.

---

## 2. Product Direction

The GIS page should no longer feel like:
- a basic marker map
- a generic dark dashboard with pins
- a developer demo

It should feel like:
- a marine survey command view
- a real geospatial evidence interface
- a system built for route analysis, scan interpretation, and detection review

---

## 3. Design Direction For A Real And Clean Map

### 3.1 Visual style goals

- Use a realistic marine basemap instead of relying only on inverted standard tiles.
- Keep the water palette muted and professional: deep blue-gray, slate, and soft cyan accents.
- Reserve warm colors like red and orange only for critical detections or alerts.
- Make the route line elegant and readable, not noisy or overly decorative.
- Keep default markers compact; expand emphasis only for selected or critical detections.

### 3.2 Clean map layout

The screen should visually separate into:

1. `Top control bar`
   Survey selector, layer switcher, filters, view mode, playback toggle.

2. `Main map canvas`
   Large, uninterrupted working area for the 2D or 3D map.

3. `Compact floating controls`
   Fit survey, reset view, basemap switch, playback speed.

4. `Right investigation panel`
   Selected detection summary, sonar evidence, confidence, review state, nearby context.

### 3.3 Small details that make it feel like a real GIS system

- scale bar
- north arrow
- lat/lon coordinate readout on hover
- subtle contour or bathymetry layer when available
- collapsible legend instead of a permanently large legend box
- thin grid or depth reference only if it helps interpretation

---

## 4. Recommended Feature Set

## 4.1 Phase 1 — High-value visual and investigation upgrades

These are the best first additions because they improve both usability and demo quality.

### A. Detection uncertainty circles

Idea:
Show a soft radius ring around each detection using the stored positional error.

Why it matters:
- communicates confidence spatially, not only as text
- makes the system look more scientific and credible
- helps users understand whether two nearby detections may refer to the same object zone

Primary data:
- `position_error_m`
- detection coordinates

Expected user impact:
- faster trust in map output
- stronger operator understanding of location accuracy

### B. Survey coverage corridor / sonar swath

Idea:
Draw the scanned corridor around the vessel track using sonar range or swath width.

Why it matters:
- immediately shows what water area was actually scanned
- highlights coverage gaps
- gives a highly domain-specific visual that most student projects will not have

Primary data:
- track coordinates
- per-frame `range`

Expected user impact:
- users can distinguish route from real coverage
- helps future mission planning

### C. Better basemap and cleaner layers

Idea:
Replace the current map appearance with a more realistic marine-focused or satellite-plus-label view.

Why it matters:
- map instantly looks more professional
- improves perceived product maturity
- removes the "inverted tile" feel

Expected user impact:
- better readability
- stronger first impression

### D. Selected detection focus mode

Idea:
When a detection is clicked, dim unrelated map items slightly and highlight the selected detection, nearby detections, route context, and sonar evidence.

Why it matters:
- keeps investigation focused
- reduces clutter during analysis
- improves map-to-panel workflow

Expected user impact:
- easier review flow
- less visual overload

---

## 4.2 Phase 2 — Advanced analysis features

### A. Time playback / mission replay

Idea:
Add a time slider to replay the survey path and reveal detections in sequence.

Why it matters:
- makes the map feel alive
- shows vessel movement and detection chronology
- creates a powerful SIH demo moment

Best use:
- review progression of a survey
- explain when detections happened
- analyze route patterns

### B. Detection density / hotspot mode

Idea:
Switch from individual markers to heatmap, hexbin, or density clusters for crowded surveys.

Why it matters:
- gives strategic understanding of concentration zones
- improves readability when there are many detections
- supports reporting and summary analysis

### C. Nearby detection radius tool

Idea:
When one detection is selected, show detections within configurable distances like 50m, 100m, and 250m.

Why it matters:
- helps identify repeated sightings
- supports reviewer judgment
- can expose probable ghost-net fields or debris clusters

### D. Route age gradient

Idea:
Color the route by survey progression from older to newer positions.

Why it matters:
- cleaner than animated noise
- useful during playback and investigation
- improves temporal understanding at a glance

---

## 4.3 Phase 3 — Workflow and planning tools

### A. Draw AOI tool

Idea:
Let users draw a box or polygon directly on the map to filter detections inside that area.

Why it matters:
- more natural than dropdown-only filtering
- makes the product feel like a real GIS workstation
- supports review and reporting workflows

### B. Coverage gap mode

Idea:
Highlight parts of the survey region that were not covered well or where track spacing suggests missed areas.

Why it matters:
- useful for resurvey planning
- moves the page from visualization into decision support

### C. Investigation queue from map

Idea:
Allow users to step through unresolved detections directly from the map without switching to list pages.

Why it matters:
- fewer context switches
- faster analyst workflow

---

## 4.4 Phase 4 — Distinctive advanced capabilities

These features are excellent if time permits and can make the project feel competition-ready.

### A. Compare two surveys in the same area

Idea:
Overlay two survey tracks and compare detections between missions.

Why it matters:
- reveals change over time
- useful for monitoring cleanup effectiveness or repeated ghost-net presence

### B. Before / after detection view

Idea:
Show detections added, removed, or unchanged across different survey runs.

Why it matters:
- very strong for environmental monitoring use cases

### C. Planned next-survey recommendation layer

Idea:
Use coverage gaps and prior detections to suggest where the next survey should focus.

Why it matters:
- turns the map into a planning assistant, not just a viewer

---

## 5. Best Recommended Build Order

If the team wants maximum impact with realistic effort, build in this order:

1. `Coverage corridor / sonar swath`
2. `Detection uncertainty circles`
3. `Better basemap and clean control layout`
4. `Selected detection focus mode`
5. `Time playback`
6. `AOI drawing tool`
7. `Hotspot / density mode`
8. `Survey comparison`

This order balances:
- demo value
- implementation feasibility
- domain uniqueness
- visible improvement per sprint

---

## 6. Suggested User Workflow

The GIS page should support this investigation flow:

1. User selects survey.
2. Map loads route, coverage, and detections.
3. User filters by class, priority, or review status.
4. User clicks one detection.
5. Map zooms and highlights local context.
6. Right panel opens sonar evidence and confidence details.
7. User sees nearby detections and uncertainty radius.
8. User accepts, rejects, or flags the detection for follow-up.
9. User replays the route or draws an AOI for deeper analysis.

This workflow is stronger than a simple "click marker, open popup" pattern.

---

## 7. Data And Backend Enhancements Needed

Some features can be built with existing data, while others need small API upgrades.

### Can largely use existing data

- selected detection focus
- cleaner marker styles
- better basemap
- route age gradient
- nearby detections based on current coordinates

### Needs backend or data-contract support

- uncertainty circles if positional error is missing on some records
- coverage corridor based on reliable sonar `range` or swath metadata
- AOI filtering using map-drawn geometry
- survey-to-survey comparison endpoints
- aggregated density endpoints if large datasets need server-side support

### Backend planning tasks

1. expose any missing GIS fields consistently
2. support bounding-box or polygon-based filtering
3. add comparison query support for multi-survey analysis
4. consider geospatial indexing optimization for larger datasets

---

## 8. Frontend Build Areas

The GIS upgrade will likely touch these frontend areas:

- map page layout and controls
- 2D map rendering layer stack
- marker styling system
- right-side investigation workflow
- 3D view behavior
- playback timeline UI
- AOI drawing interactions
- layer toggles and legend design

The key rule should be:

`Do not overload the screen with many floating cards at once.`

Every addition should either:
- improve investigation speed
- improve spatial understanding
- improve map realism

If it does not do one of those, it should not be added.

---

## 9. UI Rules To Keep The Map Clean

- Keep one primary accent color for navigation and selection.
- Use alert colors only for alert meaning.
- Avoid too many simultaneous marker labels.
- Collapse advanced controls by default.
- Use subtle transparency for overlays so the basemap stays readable.
- Use consistent stroke weights for route, coverage, and AOI boundaries.
- Let the selected detection be visually strongest.
- Prefer side-panel detail over oversized popups.

---

## 10. Sprint-Style Delivery Plan

## Sprint 1 — Visual realism foundation

Deliver:
- improved basemap strategy
- cleaner map controls
- compact legend
- scale bar and north arrow
- improved marker design

Outcome:
- immediate visual quality jump

## Sprint 2 — Spatial intelligence

Deliver:
- uncertainty circles
- route cleanup
- selected detection focus mode
- nearby detection highlighting

Outcome:
- stronger investigation usability

## Sprint 3 — Marine survey uniqueness

Deliver:
- coverage corridor / sonar swath
- route age gradient
- better survey context overlays

Outcome:
- domain-specific GIS identity

## Sprint 4 — Interactive analysis

Deliver:
- time playback
- AOI drawing and filtering
- density / hotspot mode

Outcome:
- advanced analyst workflow

## Sprint 5 — Premium advanced layer

Deliver:
- survey comparison
- before/after view
- coverage-gap support

Outcome:
- standout feature set for judging and future expansion

---

## 11. SIH Demo Recommendation

If time is limited, the most impactful demo version is:

1. realistic basemap
2. coverage corridor
3. uncertainty circles
4. selected detection workflow
5. time playback

Why this set is best:
- it looks advanced immediately
- it is easy to explain to judges
- it directly matches the marine-sonar problem statement
- it makes the product feel original, not template-based

---

## 12. Acceptance Criteria

The GIS upgrade is successful if:

- the map looks professional without feeling cluttered
- users can understand survey path, coverage, and detections quickly
- users can investigate a detection without jumping between many pages
- the map has at least one clearly unique, domain-specific feature
- the UI remains smooth on desktop and usable on laptop-sized screens
- demo viewers can understand the purpose of each map layer in under one minute

---

## 13. Final Recommendation

If only one enhanced GIS direction is chosen, build this combination first:

`Coverage corridor + uncertainty circles + cleaner realistic basemap + time playback`

That combination gives the best balance of:
- uniqueness
- practical usefulness
- visual quality
- SIH presentation strength

---

## 14. Implementation Note

This plan is intentionally written as a product and engineering roadmap, not as final code tasks. Before development starts, it should be converted into:

1. UI wireframe tasks
2. backend/API tasks
3. frontend component tasks
4. testing checklist
5. demo checklist

That breakdown can be created as the next planning document when the team is ready to execute.
