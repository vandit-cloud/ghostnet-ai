"""The optional net segmentation model (ghostnet.netseg) and how detect() uses it.

The guarantees pinned here, in order of how much damage breaking them does:

1. OFF means off. With nothing configured, payloads are exactly what they were
   before the module existed -- no provenance key, no mask, detector nets kept.
2. ON replaces the detector's nets instead of adding to them, and leaves every
   other class alone.
3. A net from the segmentation model is still review_only, carries its
   polygon, and never claims "low" uncertainty on an uncalibrated score.
4. Configured-but-broken degrades to the detector's nets and SAYS so.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

cv2 = pytest.importorskip("cv2")

from ghostnet import infer, netseg  # noqa: E402
from ghostnet.config import Settings  # noqa: E402
from ghostnet.contract import validate  # noqa: E402

DETECTOR_NAMES = {0: "wreck", 1: "plane", 2: "debris", 3: "ghost_pot", 4: "ghost_net"}


class _Box:
    def __init__(self, xyxy, cls, conf):
        self.xyxy = np.array([xyxy], dtype=float)
        self.cls = np.array([cls])
        self.conf = np.array([conf])


class _Pred:
    def __init__(self, boxes, polys=None):
        self.boxes = boxes
        self.masks = type("M", (), {"xy": polys})() if polys is not None else None


class _Detector:
    names = DETECTOR_NAMES


@pytest.fixture
def frame(tmp_path) -> Path:
    rng = np.random.default_rng(0)
    img = (rng.normal(140, 20, (400, 600))).clip(0, 255).astype(np.uint8)
    path = tmp_path / "frame.png"
    cv2.imwrite(str(path), img)
    return path


@pytest.fixture
def detector_pred():
    """A confident debris box and a detector ghost_net box that should vanish."""
    return _Pred([_Box([100, 100, 180, 160], 2, 0.9), _Box([300, 50, 500, 250], 4, 0.2)])


NET_POLY = [[320, 240], [335, 246], [470, 90], [458, 82]]


@pytest.fixture
def fake_net(monkeypatch):
    monkeypatch.setattr(infer, "load_model", lambda settings: _Detector())
    monkeypatch.setattr(infer, "load_net_model", lambda settings: object())
    monkeypatch.setattr(infer, "predict_nets", lambda model, gray, settings, lock=None: [{
        "cls": "ghost_net", "score": 0.93, "bbox": [320, 82, 150, 164],
        "centre": (395.0, 164.0), "mask": NET_POLY, "source": "net_seg"}])


# ------------------------------------------------------------------ OFF

def test_nothing_configured_means_no_net_model(monkeypatch):
    monkeypatch.delenv("GHOSTNET_NET_WEIGHTS", raising=False)
    s = Settings()
    if (AI_ROOT / "models" / "trained" / "ghostnet_net.pt").exists():
        pytest.skip("a net model has been promoted on this machine")
    assert s.net_weights_path is None
    assert "net_model_version" not in s.provenance()


def test_off_keeps_the_detector_nets_and_emits_no_mask(monkeypatch, frame, detector_pred):
    monkeypatch.setattr(infer, "load_model", lambda settings: _Detector())
    s = Settings(net_weights_path=None)
    s.net_weights_path = None   # __post_init__ may have resolved a promoted file
    payload = infer.detect(frame, {}, s, _prediction=detector_pred)
    classes = sorted(d["class"] for d in payload["detections"])
    assert classes == ["debris", "ghost_net"]
    assert all(d["mask"] is None for d in payload["detections"])
    assert validate(payload) == []


# ------------------------------------------------------------------- ON

def test_on_replaces_detector_nets_and_keeps_other_classes(fake_net, frame, detector_pred, tmp_path):
    s = Settings(net_weights_path=tmp_path / "gv9r.pt")
    payload = infer.detect(frame, {}, s, _prediction=detector_pred)
    nets = [d for d in payload["detections"] if d["class"] == "ghost_net"]
    others = [d for d in payload["detections"] if d["class"] != "ghost_net"]

    assert len(nets) == 1 and nets[0]["bbox"] == [320, 82, 150, 164], "detector net must be gone"
    assert [d["class"] for d in others] == ["debris"], "other classes must be untouched"
    assert validate(payload) == []


def test_a_segmented_net_is_a_review_candidate_with_its_outline(fake_net, frame, detector_pred, tmp_path):
    s = Settings(net_weights_path=tmp_path / "gv9r.pt")
    net = next(d for d in infer.detect(frame, {}, s, _prediction=detector_pred)["detections"]
               if d["class"] == "ghost_net")
    assert net["mask"] == NET_POLY
    assert net["review_only"] is True
    assert net["uncertainty"] != "low", "0.93 uncalibrated must not read as a low-uncertainty claim"
    assert net["calibrated_confidence"] == pytest.approx(0.93)
    assert net["model_version"] == "gv9r"
    assert "uncalibrated" in net["evidence_summary"]["notes"]


def test_provenance_names_the_net_model_when_configured(tmp_path):
    run = tmp_path / "gv9r-netseg-ridge3-s0" / "weights"
    run.mkdir(parents=True)
    s = Settings(net_weights_path=run / "best.pt")
    assert s.provenance()["net_model_version"] == "gv9r-netseg-ridge3-s0"


def test_the_payload_with_a_polygon_satisfies_the_published_schema(fake_net, frame, detector_pred, tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((AI_ROOT.parent / "contracts" / "ai-output.schema.json").read_text())
    s = Settings(net_weights_path=tmp_path / "gv9r.pt")
    jsonschema.validate(infer.detect(frame, {}, s, _prediction=detector_pred), schema)


# -------------------------------------------------------------- degrade

def test_configured_but_missing_weights_fall_back_and_say_so(monkeypatch, frame, detector_pred, tmp_path):
    monkeypatch.setattr(infer, "load_model", lambda settings: _Detector())
    monkeypatch.setattr(netseg, "_NET_MODEL", None)
    monkeypatch.setattr(netseg, "_NET_ERROR", None)
    s = Settings(net_weights_path=tmp_path / "does-not-exist.pt")
    payload = infer.detect(frame, {}, s, _prediction=detector_pred)
    assert any(d["class"] == "ghost_net" for d in payload["detections"]), "fell back to detector nets"
    assert any("not found" in w for w in payload["warnings"])
    assert validate(payload) == []


def test_a_net_model_crash_on_one_frame_keeps_the_payload(monkeypatch, frame, detector_pred, tmp_path):
    monkeypatch.setattr(infer, "load_model", lambda settings: _Detector())
    monkeypatch.setattr(infer, "load_net_model", lambda settings: object())

    def boom(*a, **k):
        raise RuntimeError("cuda went away")

    monkeypatch.setattr(infer, "predict_nets", boom)
    payload = infer.detect(frame, {}, Settings(net_weights_path=tmp_path / "x.pt"), _prediction=detector_pred)
    assert any("net segmentation model failed" in w for w in payload["warnings"])
    assert validate(payload) == []


# ------------------------------------------------------ polygon / input

def test_polygons_are_simplified_capped_and_integer():
    t = np.linspace(0, 2 * np.pi, 2000, endpoint=False)
    wiggly = np.stack([300 + 100 * np.cos(t) + 3 * np.sin(40 * t), 200 + 50 * np.sin(t)], 1)
    poly = netseg._polygon(wiggly)
    assert 3 <= len(poly) <= netseg.POLYGON_MAX_POINTS
    assert all(isinstance(v, int) for p in poly for v in p)


def test_degenerate_contours_yield_no_polygon():
    assert netseg._polygon(np.array([[1.0, 1.0], [2.0, 2.0]])) is None


def test_predict_nets_feeds_engineered_channels_when_a_spec_exists(tmp_path):
    spec = tmp_path / "best.channels.json"
    spec.write_text(json.dumps({"scales": {"ridge": 14.0, "blackhat": 120.6}}))
    seen = {}

    class _Seg:
        def predict(self, source, **kw):
            seen["image"] = source
            poly = np.array(NET_POLY, dtype=float)
            return [_Pred([_Box([320, 82, 470, 246], 0, 0.8)], [poly])]

    gray = np.full((300, 500), 150, np.uint8)
    s = Settings(net_weights_path=tmp_path / "best.pt")
    assert s.net_channels_path == spec, "sidecar beside the weights must be found"
    out = netseg.predict_nets(_Seg(), gray, s)

    img = seen["image"]
    assert img.shape == (300, 500, 3)
    assert (img[..., 0] == gray).all(), "channel 0 must stay the raw frame"
    assert out[0]["mask"] and out[0]["source"] == "net_seg"


def test_predict_nets_feeds_plain_grey_without_a_spec(tmp_path):
    seen = {}

    class _Seg:
        def predict(self, source, **kw):
            seen["image"] = source
            return []

    gray = np.random.default_rng(1).integers(0, 255, (120, 160), dtype=np.uint8)
    netseg.predict_nets(_Seg(), gray, Settings(net_weights_path=tmp_path / "best.pt"))
    img = seen["image"]
    assert (img[..., 0] == img[..., 1]).all() and (img[..., 1] == img[..., 2]).all()


# ---------------------------------------------------------------- U-Net
#
# The shipped net model since 26 Sep 2026 is a U-Net (ghostnet.unet). The
# guarantees below: it is recognised by what is in the file, loaded without
# executing pickled code, run at its own pixel threshold, and turned into the
# same raw-item shape as the YOLO path, so everything downstream is shared.

from ghostnet import unet  # noqa: E402


def _tiny_unet_checkpoint(path: Path, encoder: str = "resnet18") -> Path:
    torch = pytest.importorskip("torch")
    pytest.importorskip("segmentation_models_pytorch")
    model = unet.build_model(encoder, weights=None)
    torch.save({"model": model.state_dict(), "encoder": encoder, "imgsz": 640}, path)
    return path


class _FakeUNet:
    kind, model, device, imgsz = "unet", None, "cpu", 640


def _patch_prob(monkeypatch, prob):
    monkeypatch.setattr(unet, "predict_prob", lambda model, gray, device, size=640: prob)


def test_a_unet_checkpoint_is_recognised_by_content_not_name(tmp_path):
    ck = _tiny_unet_checkpoint(tmp_path / "anything.pt")
    assert unet.read_checkpoint(ck)["encoder"] == "resnet18"


def test_non_unet_files_are_left_for_the_yolo_loader(tmp_path):
    torch = pytest.importorskip("torch")
    junk = tmp_path / "junk.pt"
    junk.write_bytes(b"not a torch file")
    pickled = tmp_path / "pickled.pt"
    torch.save({"model": torch.nn.Linear(2, 2)}, pickled)   # a pickled module, as YOLO saves
    assert unet.read_checkpoint(junk) is None
    assert unet.read_checkpoint(pickled) is None, "weights_only must refuse a pickled class"


def test_load_net_model_builds_a_unet(monkeypatch, tmp_path):
    monkeypatch.setattr(netseg, "_NET_MODEL", None)
    monkeypatch.setattr(netseg, "_NET_ERROR", None)
    ck = _tiny_unet_checkpoint(tmp_path / "ghostnet_net.pt")
    model = netseg.load_net_model(Settings(net_weights_path=ck, device="cpu"))
    assert getattr(model, "kind", None) == "unet" and model.encoder == "resnet18"
    assert netseg.net_model_error() is None


def test_a_unet_refuses_an_engineered_channels_spec(monkeypatch, tmp_path):
    monkeypatch.setattr(netseg, "_NET_MODEL", None)
    monkeypatch.setattr(netseg, "_NET_ERROR", None)
    ck = _tiny_unet_checkpoint(tmp_path / "best.pt")
    (tmp_path / "best.channels.json").write_text(json.dumps({"scales": {"ridge": 14.0, "blackhat": 120.6}}))
    assert netseg.load_net_model(Settings(net_weights_path=ck, device="cpu")) is None
    assert "could not be loaded" in netseg.net_model_error()


def test_unet_blobs_become_pixel_space_candidates(monkeypatch):
    prob = np.zeros((300, 500), np.float32)
    prob[40:60, 100:300] = 0.9       # a net, 200 x 20 px
    prob[250, 20] = 0.99             # one-pixel speckle, under MIN_BLOB_SHARE
    _patch_prob(monkeypatch, prob)

    out = netseg.predict_nets(_FakeUNet(), np.zeros((300, 500), np.uint8), Settings())
    assert len(out) == 1, "speckle must be dropped"
    net = out[0]
    assert net["bbox"] == [100, 40, 200, 20]
    assert net["centre"] == pytest.approx((200.0, 50.0))
    assert net["score"] == pytest.approx(0.9)
    assert net["cls"] == "ghost_net" and net["source"] == "net_seg"
    xs, ys = zip(*net["mask"])
    assert 100 <= min(xs) and max(xs) <= 299 and 40 <= min(ys) and max(ys) <= 59


def test_the_unet_threshold_is_the_pixel_boundary(monkeypatch):
    prob = np.zeros((300, 500), np.float32)
    prob[40:60, 100:300] = 0.9
    prob[200:220, 400:420] = 0.4     # a real-sized blob below 0.5
    _patch_prob(monkeypatch, prob)
    gray = np.zeros((300, 500), np.uint8)
    s = Settings()
    assert s.net_unet_threshold == 0.5, "0.5 is what every published U-Net figure used"
    assert len(netseg.predict_nets(_FakeUNet(), gray, s)) == 1
    s.net_unet_threshold = 0.3
    assert len(netseg.predict_nets(_FakeUNet(), gray, s)) == 2


def test_for_evaluation_keeps_the_unet_pixel_threshold():
    """At 0.0 every pixel is 'net' and the frame becomes one blob; the
    threshold is a segmentation boundary, not a reporting gate."""
    s = Settings()
    assert s.for_evaluation().net_unet_threshold == s.net_unet_threshold
    assert s.for_evaluation().net_conf_threshold == 0.0


def test_a_unet_net_flows_through_detect_as_a_review_candidate(monkeypatch, frame, detector_pred, tmp_path):
    prob = np.zeros((400, 600), np.float32)
    prob[100:130, 200:420] = 0.85
    _patch_prob(monkeypatch, prob)
    monkeypatch.setattr(infer, "load_model", lambda settings: _Detector())
    monkeypatch.setattr(infer, "load_net_model", lambda settings: _FakeUNet())
    s = Settings(net_weights_path=tmp_path / "gvU1n-unet-hardneg-s1" / "weights" / "best.pt")

    payload = infer.detect(frame, {}, s, _prediction=detector_pred)
    nets = [d for d in payload["detections"] if d["class"] == "ghost_net"]
    assert len(nets) == 1 and nets[0]["bbox"] == [200, 100, 220, 30], "detector net replaced by the U-Net's"
    assert nets[0]["mask"] and nets[0]["review_only"] is True
    assert nets[0]["uncertainty"] != "low"
    assert nets[0]["model_version"] == "gvU1n-unet-hardneg-s1"
    assert [d["class"] for d in payload["detections"] if d["class"] != "ghost_net"] == ["debris"]
    assert validate(payload) == []


def test_warmup_reports_a_broken_net_model_at_startup(monkeypatch, caplog, tmp_path):
    monkeypatch.setattr(infer, "load_model", lambda settings: object())
    monkeypatch.setattr(infer, "load_net_model", lambda settings: None)
    monkeypatch.setattr(infer, "net_model_error", lambda: "net segmentation weights configured but not found (x.pt)")
    with caplog.at_level("WARNING", logger="ghostnet.infer"):
        assert infer.warmup(Settings(net_weights_path=tmp_path / "x.pt")) is True
    assert "not found" in caplog.text


# The served path must reproduce the published U-Net numbers exactly, not
# approximately: same blobs, same boxes, on the real test chips. Skipped on a
# machine without the promoted model or the training data.
_PROMOTED = AI_ROOT / "models" / "trained" / "ghostnet_net.pt"
_TEST_CHIPS = Path("E:/New folder/ai/data/net_seg_hardneg/test/images")


@pytest.mark.skipif(not (_PROMOTED.exists() and _TEST_CHIPS.exists()),
                    reason="needs the promoted U-Net and the net_seg_hardneg test chips")
def test_the_served_unet_matches_the_evaluation_harness(monkeypatch):
    monkeypatch.setattr(netseg, "_NET_MODEL", None)
    monkeypatch.setattr(netseg, "_NET_ERROR", None)
    meta = json.loads(_PROMOTED.with_suffix(".json").read_text())
    source = AI_ROOT.parent / meta["promoted_from"]
    if not source.exists():
        pytest.skip("the promoted model's source checkpoint is not on this machine")

    s = Settings(net_weights_path=_PROMOTED, device="cpu")
    served = netseg.load_net_model(s)
    reference, _ = unet.load_checkpoint(source, "cpu")
    for chip in sorted(_TEST_CHIPS.iterdir()):
        gray = cv2.imread(str(chip), cv2.IMREAD_GRAYSCALE)
        h, w = gray.shape
        want = sorted([round(b["box"][0] * w), round(b["box"][1] * h)]
                      for b in unet.blobs(unet.predict_prob(reference, gray, "cpu"), 0.5))
        got = sorted(d["bbox"][:2] for d in netseg.predict_nets(served, gray, s))
        assert got == want, chip.name


# ------------------------------------------------ review fixes, 26 Sep 2026

@pytest.mark.parametrize("value", ["none", "off", "NONE"])
def test_an_explicit_off_disables_even_a_promoted_model(monkeypatch, value):
    monkeypatch.setenv("GHOSTNET_NET_WEIGHTS", value)
    s = Settings()
    assert s.net_weights_path is None
    assert "net_model_version" not in s.provenance()


def test_provenance_does_not_name_a_net_model_that_did_not_run(monkeypatch, frame, detector_pred, tmp_path):
    monkeypatch.setattr(infer, "load_model", lambda settings: _Detector())
    monkeypatch.setattr(netseg, "_NET_MODEL", None)
    monkeypatch.setattr(netseg, "_NET_FAILED_KEY", None)
    s = Settings(net_weights_path=tmp_path / "gvU1n-unet-hardneg-s1" / "weights" / "best.pt")  # absent
    payload = infer.detect(frame, {}, s, _prediction=detector_pred)
    assert payload["provenance"]["net_model_version"].startswith("none"), \
        "the nets in this payload came from the box detector"


def test_provenance_names_the_net_model_when_it_ran(monkeypatch, frame, detector_pred, tmp_path):
    prob = np.zeros((400, 600), np.float32)
    prob[100:130, 200:420] = 0.85
    _patch_prob(monkeypatch, prob)
    monkeypatch.setattr(infer, "load_model", lambda settings: _Detector())
    monkeypatch.setattr(infer, "load_net_model", lambda settings: _FakeUNet())
    s = Settings(net_weights_path=tmp_path / "gvU1n-unet-hardneg-s1" / "weights" / "best.pt")
    payload = infer.detect(frame, {}, s, _prediction=detector_pred)
    assert payload["provenance"]["net_model_version"] == "gvU1n-unet-hardneg-s1"


def test_asking_for_different_weights_loads_them_instead_of_reusing_the_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(netseg, "_NET_MODEL", None)
    monkeypatch.setattr(netseg, "_NET_KEY", None)
    monkeypatch.setattr(netseg, "_NET_FAILED_KEY", None)
    a = _tiny_unet_checkpoint(tmp_path / "a.pt")
    b = _tiny_unet_checkpoint(tmp_path / "b.pt")
    first = netseg.load_net_model(Settings(net_weights_path=a, device="cpu"))
    second = netseg.load_net_model(Settings(net_weights_path=b, device="cpu"))
    assert first is not None and second is not first
    assert netseg.load_net_model(Settings(net_weights_path=b, device="cpu")) is second, "same path is cached"


def test_a_broken_file_is_read_once_until_it_changes(monkeypatch, tmp_path):
    monkeypatch.setattr(netseg, "_NET_MODEL", None)
    monkeypatch.setattr(netseg, "_NET_FAILED_KEY", None)
    monkeypatch.setattr(netseg, "_NET_ERROR", None)
    calls = []
    real = unet.read_checkpoint
    monkeypatch.setattr(unet, "read_checkpoint", lambda p: calls.append(p) or real(p))
    monkeypatch.setitem(sys.modules, "ultralytics", None)   # the YOLO fallback fails too
    bad = tmp_path / "ghostnet_net.pt"
    bad.write_bytes(b"truncated")
    s = Settings(net_weights_path=bad, device="cpu")

    assert netseg.load_net_model(s) is None and netseg.load_net_model(s) is None
    assert len(calls) == 1, "the same broken file must not be re-read on every frame"
    assert "could not be loaded" in netseg.net_model_error()

    bad.write_bytes(b"truncated, but a different file now")   # size changes -> new key
    netseg.load_net_model(s)
    assert len(calls) == 2, "a replaced file must be retried"


def test_the_detector_floor_is_normal_when_a_net_model_replaces_its_nets(monkeypatch, tmp_path):
    s = Settings(net_weights_path=tmp_path / "x.pt")
    monkeypatch.setattr(infer, "load_net_model", lambda settings: _FakeUNet())
    assert infer._detector_conf(s) == s.raw_conf_threshold
    monkeypatch.setattr(infer, "load_net_model", lambda settings: None)
    assert infer._detector_conf(s) == min(s.raw_conf_threshold, s.raw_conf_threshold_net)
