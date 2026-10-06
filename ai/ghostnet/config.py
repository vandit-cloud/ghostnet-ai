"""Runtime configuration for the GhostNet-AI inference package.

Every path is resolved relative to this file, then overridable by environment
variable, so the package behaves identically on Windows, Linux, in Docker and
on Member 2's machine. No absolute paths are ever baked in.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# ai/ghostnet/config.py -> ai/ghostnet -> ai
PACKAGE_ROOT = Path(__file__).resolve().parent
AI_ROOT = PACKAGE_ROOT.parent
PROJECT_ROOT = AI_ROOT.parent


def _env_path(var: str, default: Path) -> Path:
    """Environment override wins; otherwise the repo-relative default."""
    raw = os.environ.get(var)
    return Path(raw).expanduser().resolve() if raw else default


def _env_float(var: str, default: float) -> float:
    """A numeric environment override, or the default when unset or unreadable.

    Unreadable falls back rather than raising: Settings is built at import
    time, and a typo in an env var must not stop the server starting.
    """
    try:
        return float(os.environ.get(var, default))
    except (TypeError, ValueError):
        return default


def _read_json(path: Path) -> dict:
    """Read a small JSON sidecar, or {} when it is missing or unreadable.

    Provenance must never be the thing that fails an inference run, so every
    failure here degrades to "unknown" rather than raising. A corrupt sidecar
    leaves the version fields at their sentinels, which reads as "we do not
    know" -- the one honest answer available.
    """
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def resolve_device(preference: str = "auto") -> str:
    """Pick a torch device without importing torch until we must.

    'auto' -> cuda when genuinely usable, else cpu. Member 2's laptop or a CI
    runner may have no GPU at all; inference must still run, just slower.
    """
    if preference != "auto":
        return preference
    if os.environ.get("GHOSTNET_DEVICE"):
        return os.environ["GHOSTNET_DEVICE"]
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


@dataclass
class Settings:
    # --- paths -------------------------------------------------------------
    models_dir: Path = field(default_factory=lambda: _env_path("GHOSTNET_MODELS_DIR", AI_ROOT / "models"))
    data_dir: Path = field(default_factory=lambda: _env_path("GHOSTNET_DATA_DIR", AI_ROOT / "data"))
    weights_path: Path | None = None
    #: Optional ghost_net SEGMENTATION model (ghostnet.netseg). When it
    #: resolves, it replaces the box detector's ghost_net output. Resolution:
    #: GHOSTNET_NET_WEIGHTS, then a promoted models/trained/ghostnet_net.pt,
    #: then nothing -- and nothing means detect() behaves exactly as before.
    net_weights_path: Path | None = None
    #: channels.json for a model trained on engineered input
    #: (build_net_seg_ridge.py). GHOSTNET_NET_CHANNELS, then
    #: `<net weights>.channels.json`; absent means plain greyscale input.
    net_channels_path: Path | None = None

    # --- inference ---------------------------------------------------------
    device: str = field(default_factory=resolve_device)
    #: auto | torch | onnx -- see ghostnet.runtime for the rule. Env
    #: GHOSTNET_RUNTIME. The RESOLVED choice is in `runtime_active` (and
    #: `net_runtime_active`), and provenance records it in every payload.
    runtime: str = field(default_factory=lambda: os.environ.get("GHOSTNET_RUNTIME", "auto"))
    #: Threads ONNX Runtime may use per session; None lets it pick (all
    #: physical cores). Env GHOSTNET_ONNX_THREADS.
    onnx_threads: int | None = field(
        default_factory=lambda: int(os.environ["GHOSTNET_ONNX_THREADS"])
        if os.environ.get("GHOSTNET_ONNX_THREADS", "").strip().isdigit() else None
    )
    imgsz: int = 640
    #: Frames per model call in detect_batch. 8 is where this GPU stops idling
    #: (see _predict_many): 3.6 frames/s at batch 1, 64 at batch 8. Higher
    #: barely helps and costs VRAM, of which there is 4 GB.
    batch_size: int = 8
    # 4 GB VRAM is the binding constraint on this machine.
    batch: int = 4
    # FP16 halves activation memory, which is what actually buys headroom here.
    half: bool = True

    # Deliberately low: the calibrated-confidence policy in infer.py decides
    # what is actually reported. Filtering twice hides recall problems.
    raw_conf_threshold: float = 0.10
    iou_threshold: float = 0.50
    max_detections: int = 300

    # --- decision policy ---------------------------------------------------
    # Floors applied to CALIBRATED confidence when deciding what reaches a
    # human reviewer. They are asymmetric on purpose: an artificial anomaly is
    # actionable and a miss is expensive, so it gets a low bar; a 'natural'
    # call is context rather than a task, so it only earns screen space when
    # the model is fairly sure.
    #
    # IMPORTANT: evaluation scripts must set both to 0.0. Metrics computed on
    # policy-filtered output measure recall after the very filter that damaged
    # it -- the "filtering twice hides recall problems" trap noted above.
    #
    # 0.20 -> 0.12 with per-class calibration, to keep what a reviewer sees
    # EXACTLY as it was. Under the old global T = 2.72 the lowest calibrated
    # score that could reach the policy was 0.309, so 0.20 never bound. The
    # per-class calibrator maps the raw gate (0.10) to 0.128 for wreck
    # (T = 1.145) and 0.139 for everything else (T = 1.202), and left at 0.20
    # this floor would have started binding silently -- measured on test:
    # ghost_pot recall 0.429 -> 0.303, wreck 0.355 -> 0.318, false alarms on
    # empty frames 7.75% -> 4.91%. 0.12 sits just under 0.128 and reproduces
    # the shipped recall and false-alarm rate to the box. The floor sweep is in
    # ai/experiments/calib-perclass/RESULTS.md: tightening it IS now a real
    # lever, but that is a policy decision to take on purpose, not a side
    # effect of a recalibration. tests/test_review_only.py fails if a refit
    # makes this floor bind again.
    review_floor_artificial: float = 0.12
    review_floor_natural: float = 0.45

    #: `ghost_net` clears a LOWER bar than the other artificial classes, and
    #: the output it produces is a review candidate rather than a detection
    #: claim (contract field `review_only`; decision.is_review_only).
    #:
    #: This is Track D / D5 in docs/EXPERIMENT_GV7_PLAN.md, and it is the Tier 1
    #: half of the two-tier rule in §10.5: shipping is lenient BECAUSE the
    #: output asserts nothing. gv5 measured recall 0.000 on nets at the normal
    #: floor, so the choice is between surfacing weak candidates for a human
    #: and surfacing nothing at all.
    #:
    #: NOTE this floor is NON-BINDING and kept only for symmetry; the lever
    #: that actually decides what a reviewer sees is raw_conf_threshold_net
    #: below. It was 0.10, which the old global T = 2.72 made inert (raw 0.03
    #: calibrated to 0.218). ghost_net falls back to the global T = 1.202 in
    #: the per-class calibrator (1 matched val box), which maps raw 0.03 to
    #: 0.053 -- so 0.10 would have started suppressing detector net boxes with
    #: raw 0.03-0.066 (21 test boxes, the one true net hit among them). 0.05
    #: keeps it inert. Setting a calibrated floor here and expecting it to
    #: surface more nets would be a no-op.
    review_floor_net: float = 0.05

    #: The lever that actually works. `conf` is passed to the detector, so a
    #: box scoring below it is never emitted and no downstream floor can
    #: recover it -- which is why review_floor_artificial (0.20 calibrated,
    #: ~0.0 raw-equivalent) has had no effect since calibration was fitted.
    #:
    #: Detection runs at min(raw_conf_threshold, raw_conf_threshold_net) and
    #: every non-review-only class is then re-gated to raw_conf_threshold in
    #: decision.apply_decision_policy. So the other four classes see EXACTLY
    #: the behaviour they saw before -- the background activation rates in
    #: docs/ are unchanged and remain quotable -- while nets get the wider net.
    #:
    #: 0.03 is chosen to sit below the raw scores gv5 produced on nets without
    #: opening the floodgates; it is a starting point, not a tuned value, and
    #: there is no net data to tune it against (11 test frames).
    raw_conf_threshold_net: float = 0.03

    #: Raw score floor for the net SEGMENTATION model, when one is configured.
    #: 0.25 is the threshold every published D2/D3 figure was measured at
    #: (centroid_metric.py --conf default), so what ships is what was measured.
    #: Replaces raw_conf_threshold_net for nets; that one stays for the
    #: detector-only path.
    net_conf_threshold: float = 0.25

    #: Pixel threshold for a U-Net net model: a pixel at or above it is "net",
    #: and each connected blob of such pixels is one candidate. 0.5 was fixed in
    #: ai/experiments/unet-scoring/PLAN.md before any U-Net was trained, and
    #: every published U-Net figure is at 0.5. It is also robust: gvU1n's Dice
    #: moves 0.589 / 0.588 / 0.583 across 0.25 / 0.5 / 0.75.
    #:
    #: Deliberately NOT zeroed by for_evaluation(). It is the segmentation
    #: boundary, not a reporting gate: at 0.0 every pixel is "net" and the
    #: whole frame becomes one blob, which is no measurement at all. U-Net
    #: evaluation sweeps it explicitly (evaluate_net_unet.py --conf).
    net_unet_threshold: float = 0.5

    # --- tile-edge artifacts ----------------------------------------------
    #: Suppress detections that are thin strips welded to a frame border.
    #: See decision.is_edge_sliver for what this costs and why it is on.
    suppress_edge_slivers: bool = True
    #: How close to the border counts as touching it, in pixels. A YOLO box on
    #: the border lands on 0 or W-1, so this only absorbs rounding.
    edge_touch_px: int = 2
    #: Max thickness perpendicular to the border, as a fraction of that axis.
    #: The observed artifacts are 34-38 px in a 640 px tile: 5-6%.
    edge_sliver_max_thickness: float = 0.08
    #: Min extent parallel to the border, as a fraction of that axis. A real
    #: object clipped by a seam is rarely also a near-full-length strip.
    edge_sliver_min_extent: float = 0.40

    # --- overlapping tiles and the seam merge -----------------------------
    #: Fraction of a 640 px tile shared with each neighbour. 0 (the default)
    #: is the original seamless tiling, tile for tile. With overlap a seam can
    #: no longer cut an object in half with no tile seeing the whole of it,
    #: and ghostnet.merge folds the duplicate sightings into one.
    #:
    #: OFF by default because the gain is unproven and the cost is not.
    #: Measured 6 Oct 2026 (ai/experiments/tile-overlap/measure.py), 0 -> 0.25:
    #:   NBP0505 demo line: 40 -> 65 tiles, 4.6 -> 7.9 s, 2 -> 1 detections
    #:   Klein 2019, 50 files: 1191 -> 1707 tiles, 169 -> 201 s, 48 -> 57
    #:   alarms (71 before 14 seam duplicates merged); 30 new, 16 lost.
    #: Moving the grid reshuffles alarms near the floor, and neither survey has
    #: ground truth to say the new ones are real -- Klein's are mostly rock.
    #: Turn it on (GHOSTNET_TILE_OVERLAP=0.25) once a labelled survey shows it
    #: recovers seam-cut targets.
    tile_overlap: float = field(
        default_factory=lambda: _env_float("GHOSTNET_TILE_OVERLAP", 0.0)
    )
    #: Merge detections of one object reported from two overlapping tiles.
    #: See ghostnet.merge for the rule. Off only for debugging the merge.
    seam_merge: bool = True
    #: Two same-class boxes from different tiles are one object when, in
    #: survey pixels, their IoU reaches this...
    seam_merge_iou: float = 0.30
    #: ...or the smaller box lies this much inside the larger -- the case of an
    #: object one tile clips at its border and the other sees whole, where IoU
    #: is low because the clipped box is small...
    seam_merge_containment: float = 0.60
    #: ...or their centres are this close. The same pixels scored in two tiles
    #: give near-identical boxes, so this only absorbs the detector placing a
    #: box a little differently with different context. Deliberately below the
    #: 50 px a rival pipeline uses: pots in a string sit tens of pixels apart,
    #: and merging two real pots is a lost detection, not a tidied duplicate.
    seam_merge_centre_px: float = 24.0

    # Uncertainty band edges on calibrated confidence.
    #
    # The edges are PROBABILITIES, and the rule that sets them is that each
    # band's held-out precision must fall inside the band: 'low' means "at
    # least 3 in 4 of these are right", 'high' means "fewer than 1 in 2 are".
    # Re-derived for the per-class calibrator (ai/experiments/calib-perclass/
    # RESULTS.md) and the values hold. On test, the 2,394 reported detections:
    #     low  (>= 0.75)       precision 0.939    15.1%
    #     medium (0.45-0.75)   precision 0.726    17.7%
    #     high (< 0.45)        precision 0.262    67.2%
    # (val: 0.5% / 10.6% / 88.8% -- 4 'low', all wrecks, all correct.)
    # What was broken was the CALIBRATION, not the edges: the global T = 2.72
    # capped every score at 0.728, so 'low' -- and with it Priority.HIGH for
    # non-nets and CRITICAL for nets -- was unreachable. The per-class map
    # reaches 0.79 on val and 0.91 on test.
    #
    # Not re-derived from val's precision curve, on purpose: "lowest score
    # above which val precision >= 0.80 / 0.50" gives 0.467 / 0.128, because
    # val's ghost_pot boxes are 69% correct against test's 30% (an
    # unrepresentative survey; see the calibrator's ghost_pot fallback). On
    # test those edges put 67% of detections in 'medium' at precision 0.27 and
    # call wrecks 'low' at 0.68 -- the bands stop meaning what they say.
    uncertainty_low_edge: float = 0.75
    uncertainty_medium_edge: float = 0.45

    def for_evaluation(self) -> "Settings":
        """A copy with EVERY reporting gate disabled, for metric computation.

        Evaluation must see unfiltered detector output: metrics computed on
        policy-filtered output measure recall after the very filter that
        damaged it. Scripts used to do this by hand with
        `replace(settings, review_floor_artificial=0.0, review_floor_natural=0.0)`,
        which silently went stale the moment a THIRD gate was added -- exactly
        what happened when raw_conf_threshold_net arrived, and the kind of
        quiet drift that makes a published number wrong.

        Adding a gate? Add it here. This method is the list.
        """
        from dataclasses import replace

        return replace(
            self,
            review_floor_artificial=0.0,
            review_floor_natural=0.0,
            review_floor_net=0.0,
            raw_conf_threshold=0.0,
            raw_conf_threshold_net=0.0,
            net_conf_threshold=0.0,
        )

    # --- versioning (§34: every inference identifies its provenance) -------
    model_id: str = "ghostnet-yolo11s"
    #: Filled in from the weights actually loaded -- see __post_init__. The
    #: literal below is what a payload reports when there are no weights at
    #: all, which is a real state (Member 2 can build the whole app before a
    #: model exists) and should be visibly labelled as such rather than
    #: claiming a version.
    model_version: str = "v0-stub"
    dataset_version: str = "none"
    #: Named filter from ghostnet.preprocess, applied before inference.
    #: "none" is deliberate and load-bearing: despeckling a model trained on
    #: raw frames costs 13% of mAP50. Change it only alongside a model trained
    #: the same way.
    preprocessing: str = "none"
    calibration_version: str = "none"
    #: Version of the net segmentation model, or "none" when not configured.
    net_model_version: str = "none"

    # Resolved in __post_init__ from `runtime`; never passed in.
    runtime_active: str = field(default="torch", init=False)
    net_runtime_active: str = field(default="torch", init=False)
    #: Why a requested runtime was not honoured, or None. detect() warns with it.
    runtime_note: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.weights_path is None:
            # GHOSTNET_WEIGHTS wins, then the promoted model, then nothing.
            #
            # The default used to be nothing at all, which meant detect()
            # returned empty detections plus a warning on any machine where
            # someone had not set an environment variable -- including Member
            # 2's, where the whole point is that the package works on import.
            # A trained run is promoted by copying it to models/trained/ and
            # refitting the calibrator against that path, so this default is
            # the model the project actually ships rather than whichever
            # experiment happened to be newest.
            env = os.environ.get("GHOSTNET_WEIGHTS")
            if env:
                self.weights_path = Path(env).expanduser().resolve()
            else:
                promoted = AI_ROOT / "models" / "trained" / "ghostnet.pt"
                self.weights_path = promoted if promoted.exists() else None
        else:
            self.weights_path = Path(self.weights_path)
        # Name the model in every payload it produces.
        #
        # This read "v0-stub" on every detection the project has ever emitted,
        # including the ones written into report.csv and handed to Member 2 --
        # so a stored result could not be traced back to the run that made it,
        # which is the entire purpose of a provenance block. The run name is
        # recoverable from the weights path (experiments/<run>/weights/best.pt),
        # and a promoted file falls back to its own stem.
        sidecar = (
            _read_json(Path(self.weights_path).with_suffix(".json"))
            if self.weights_path is not None
            else {}
        )

        if self.model_version == "v0-stub" and self.weights_path is not None:
            w = Path(self.weights_path)
            # A promoted file is a COPY, so its own name says nothing about
            # which run made it -- ghostnet.pt could be any of them. The
            # sidecar written at promotion time is the only thing that
            # knows, and it carries the source path and a hash so the claim
            # is checkable rather than asserted.
            if sidecar.get("model_version"):
                self.model_version = str(sidecar["model_version"])
            elif w.parent.name == "weights" and w.parent.parent.name:
                self.model_version = w.parent.parent.name
            else:
                self.model_version = w.stem

        # The DATASET is read from the sidecar, never from whichever build
        # happens to be sitting in data/processed right now.
        #
        # Those two diverge the moment anyone re-runs build_dataset.py, which
        # is exactly what staging a newly annotated class does. Reading the
        # live build_report.json would then stamp this model with a dataset it
        # was never trained on -- and a provenance block that is confidently
        # wrong is worse than one that admits ignorance, because nothing
        # downstream can tell the two apart.
        if self.dataset_version == "none" and sidecar.get("dataset_version"):
            self.dataset_version = str(sidecar["dataset_version"])

        # CALIBRATION, by contrast, is read live, because the temperature file
        # on disk is the one actually being applied to these scores. Naming the
        # temperature and the split it was fitted on puts the correction in the
        # payload itself, where a stored detection keeps it; decision.py's
        # mismatch warning only reaches whoever is watching at the time.
        if self.calibration_version == "none":
            cal = _read_json(Path(self.models_dir) / "calibrator" / "temperature.json")
            if cal.get("temperature") is not None:
                try:
                    # Format 2 names the classes that carry their own map, so
                    # a stored detection says whether its score went through
                    # the global T or a class-specific one:
                    #   T1.2020+wreck-val-n1239
                    own = sorted(
                        name for name, entry in (cal.get("classes") or {}).items()
                        if isinstance(entry, dict) and not entry.get("fallback")
                    )
                    self.calibration_version = "T%.4f%s-%s-n%s" % (
                        float(cal["temperature"]),
                        "".join("+" + name for name in own),
                        cal.get("fitted_on", "unknown"),
                        cal.get("n_predictions", "?"),
                    )
                except (TypeError, ValueError, AttributeError):
                    pass  # leave the sentinel; an unparseable file is "unknown"

        self._resolve_net_model()
        self._resolve_runtime()

        if self.device == "cpu":
            self.half = False  # fp16 on CPU is slower, not faster

    def _resolve_runtime(self) -> None:
        """Settle torch vs ONNX for the detector and the net model.

        ONNX Runtime here is the CPU path, so choosing it moves the whole
        pipeline to the CPU: a forced GHOSTNET_RUNTIME=onnx on a CUDA machine
        is how the CPU deployment is reproduced on the development laptop.
        The net model follows the detector onto ONNX only when its own export
        verifies; otherwise it runs under torch on the same (CPU) device.
        """
        from . import runtime as rt

        requested, note = rt.requested_runtime(self.runtime)
        problem = None
        if requested != "torch" and not (requested == "auto" and self.device != "cpu"):
            problem = rt.onnx_problem_for(self.weights_path)
        active, fallback = rt.choose(requested, self.device, problem)
        self.runtime_active = active
        self.runtime_note = note or fallback
        self.net_runtime_active = "torch"
        if active == "onnx":
            self.device = "cpu"
            if self.net_weights_path is not None and rt.verify_onnx(self.net_weights_path) is None:
                self.net_runtime_active = "onnx"

    @property
    def detector_model_path(self) -> Path | None:
        """The file the detector is actually loaded from: the .pt, or its
        verified .onnx export when the ONNX runtime is active."""
        if self.weights_path is None:
            return None
        if self.runtime_active == "onnx":
            from .runtime import onnx_path_for

            return onnx_path_for(self.weights_path)
        return Path(self.weights_path)

    def _resolve_net_model(self) -> None:
        """Same resolution order and naming rules as the detector's weights."""
        if self.net_weights_path is None:
            env = os.environ.get("GHOSTNET_NET_WEIGHTS")
            # An explicit OFF. Without it a promoted ghostnet_net.pt could only
            # be switched off by deleting the file: None and "" both mean
            # "resolve", and resolving finds the promoted model. The test suite
            # sets this (ai/tests/conftest.py) so results do not depend on
            # whether a model happens to be promoted on the machine running it.
            if env and env.strip().lower() in ("none", "off"):
                self.net_weights_path = None
                return
            if env:
                self.net_weights_path = Path(env).expanduser().resolve()
            else:
                promoted = AI_ROOT / "models" / "trained" / "ghostnet_net.pt"
                self.net_weights_path = promoted if promoted.exists() else None
        else:
            self.net_weights_path = Path(self.net_weights_path)
        if self.net_weights_path is None:
            return

        if self.net_channels_path is None:
            env = os.environ.get("GHOSTNET_NET_CHANNELS")
            sidecar = self.net_weights_path.with_suffix(".channels.json")
            if env:
                self.net_channels_path = Path(env).expanduser().resolve()
            elif sidecar.exists():
                self.net_channels_path = sidecar
        else:
            self.net_channels_path = Path(self.net_channels_path)

        if self.net_model_version == "none":
            w = self.net_weights_path
            meta = _read_json(w.with_suffix(".json"))
            if meta.get("model_version"):
                self.net_model_version = str(meta["model_version"])
            elif w.parent.name == "weights" and w.parent.parent.name:
                self.net_model_version = w.parent.parent.name
            else:
                self.net_model_version = w.stem

    def quantize(self) -> int:
        """Ultralytics >= 8.4 replaced the boolean `half` with `quantize`,
        which takes a bit width: 16 for FP16, 32 for FP32. Passing `half`
        still works but warns on every call. Translate here so the rest of
        the package keeps the readable boolean."""
        return 16 if self.half else 32

    def provenance(self) -> dict[str, str]:
        out = {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "dataset_version": self.dataset_version,
            "preprocessing_version": self.preprocessing,
            "calibration_version": self.calibration_version,
        }
        # Which executor produced the numbers. ONNX and torch agree to within
        # the parity gates in ghostnet.runtime, not bit for bit, so a stored
        # result must say which one it came from.
        from .runtime import label

        out["runtime"] = label(self.runtime_active, self.device)
        # Only when configured, so a detector-only payload is byte-for-byte
        # what it was before the net model existed.
        if self.net_weights_path is not None:
            out["net_model_version"] = self.net_model_version
            out["net_runtime"] = label(self.net_runtime_active, self.device)
        return out


SETTINGS = Settings()
