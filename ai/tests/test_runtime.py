"""Runtime selection (torch vs ONNX), export verification, parity helpers and
the verified weights download.

What is pinned, in order of how much damage breaking it does:

1. A stale or tampered export is never served: the .onnx must hash to its
   sidecar AND the sidecar must name the CURRENT .pt, or PyTorch runs instead.
2. auto never trades a GPU for ONNX-on-CPU, and an unhonoured request for
   ONNX says so in the payload rather than silently running something else.
3. Provenance names the runtime that ran.
4. Both runtimes go through ONE post-processing path for the U-Net.
5. A download that does not hash to its sidecar is deleted, not installed.

No onnxruntime needed: availability is mocked wherever it matters.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))
sys.path.insert(0, str(AI_ROOT / "scripts"))

from ghostnet import infer, runtime as rt, unet  # noqa: E402
from ghostnet.config import Settings  # noqa: E402

import fetch_weights  # noqa: E402


def _export(tmp_path: Path, stem: str = "ghostnet", passed: bool = True) -> Path:
    """A .pt, an .onnx and a sidecar that verifies -- the export_onnx.py layout."""
    pt = tmp_path / f"{stem}.pt"
    pt.write_bytes(b"torch weights v1")
    onnx = rt.onnx_path_for(pt)
    onnx.write_bytes(b"onnx graph v1")
    rt.sidecar_path_for(onnx).write_text(json.dumps({
        "source_sha256": rt.sha256(pt), "onnx_sha256": rt.sha256(onnx),
        "parity": {"passed": passed}}), encoding="utf-8")
    return pt


# ------------------------------------------------------------ the rule

@pytest.mark.parametrize("requested, device, problem, want, noted", [
    ("torch", "cpu", None, "torch", False),
    ("torch", "cuda", None, "torch", False),
    ("onnx", "cpu", None, "onnx", False),
    ("onnx", "cuda", None, "onnx", False),          # forced: reproduce CPU deployment on a GPU box
    ("onnx", "cpu", "no export", "torch", True),    # asked and not honoured -> say so
    ("auto", "cuda", None, "torch", False),         # never trade a GPU for CPU ONNX
    ("auto", "0", None, "torch", False),            # Ultralytics-style GPU index
    ("auto", "cpu", None, "onnx", False),
    ("auto", "cpu", "no export", "torch", False),   # expected on a clone without exports: not news
])
def test_choose(requested, device, problem, want, noted):
    got, note = rt.choose(requested, device, problem)
    assert got == want
    assert (note is not None) == noted
    if noted:
        assert problem in note


def test_invalid_request_degrades_to_auto_with_a_note():
    assert rt.requested_runtime("tensorrt")[0] == "auto"
    assert "tensorrt" in rt.requested_runtime("tensorrt")[1]
    assert rt.requested_runtime(" ONNX ") == ("onnx", None)


# ----------------------------------------------- Settings integration

def test_auto_on_cpu_with_a_verified_export_runs_onnx(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "onnxruntime_available", lambda: True)
    pt = _export(tmp_path)
    s = Settings(weights_path=pt, runtime="auto", device="cpu")
    assert s.runtime_active == "onnx"
    assert s.detector_model_path == pt.with_suffix(".onnx")
    assert s.provenance()["runtime"] == "onnxruntime-cpu"
    assert s.runtime_note is None


def test_auto_on_gpu_stays_torch_and_does_not_hash_anything(tmp_path, monkeypatch):
    def boom(_):
        raise AssertionError("auto on a GPU must not even look for an export")
    monkeypatch.setattr(rt, "onnx_problem_for", boom)
    s = Settings(weights_path=_export(tmp_path), runtime="auto", device="cuda")
    assert s.runtime_active == "torch"
    assert s.detector_model_path.suffix == ".pt"
    assert s.provenance()["runtime"] == "torch-cuda"


def test_forced_onnx_moves_the_pipeline_to_cpu(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "onnxruntime_available", lambda: True)
    s = Settings(weights_path=_export(tmp_path), runtime="onnx", device="cuda")
    assert s.runtime_active == "onnx"
    assert s.device == "cpu" and s.half is False


def test_onnx_without_onnxruntime_falls_back_and_says_why(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "onnxruntime_available", lambda: False)
    s = Settings(weights_path=_export(tmp_path), runtime="onnx", device="cpu")
    assert s.runtime_active == "torch"
    assert "onnxruntime is not installed" in s.runtime_note
    assert s.provenance()["runtime"] == "torch-cpu"


def test_env_var_selects_the_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("GHOSTNET_RUNTIME", "torch")
    monkeypatch.setattr(rt, "onnxruntime_available", lambda: True)
    assert Settings(weights_path=_export(tmp_path), device="cpu").runtime_active == "torch"


def test_net_model_follows_onto_onnx_only_with_its_own_verified_export(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "onnxruntime_available", lambda: True)
    det = _export(tmp_path)
    net_ok = _export(tmp_path, "ghostnet_net")
    s = Settings(weights_path=det, net_weights_path=net_ok, runtime="auto", device="cpu")
    assert s.net_runtime_active == "onnx"
    assert s.provenance()["net_runtime"] == "onnxruntime-cpu"

    rt.onnx_path_for(net_ok).unlink()
    s = Settings(weights_path=det, net_weights_path=net_ok, runtime="auto", device="cpu")
    assert s.runtime_active == "onnx" and s.net_runtime_active == "torch"
    assert s.provenance()["net_runtime"] == "torch-cpu"


def test_for_evaluation_keeps_the_resolved_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "onnxruntime_available", lambda: True)
    s = Settings(weights_path=_export(tmp_path), runtime="auto", device="cpu")
    assert s.for_evaluation().runtime_active == "onnx"


def test_unhonoured_request_is_a_payload_warning(tmp_path, monkeypatch):
    import cv2

    monkeypatch.setattr(rt, "onnxruntime_available", lambda: False)
    s = Settings(weights_path=_export(tmp_path), runtime="onnx", device="cpu")
    frame = tmp_path / "f.png"
    cv2.imwrite(str(frame), np.full((64, 64), 90, np.uint8))

    class _Detector:
        names = {0: "wreck"}

    monkeypatch.setattr(infer, "load_model", lambda settings: _Detector())
    payload = infer.detect(frame, {}, s, _prediction=type("P", (), {"boxes": []})())
    assert any("GHOSTNET_RUNTIME=onnx requested" in w for w in payload["warnings"])
    assert payload["provenance"]["runtime"] == "torch-cpu"


# --------------------------------------------------- sidecar verification

def test_verified_export_passes(tmp_path):
    assert rt.verify_onnx(_export(tmp_path)) is None


def test_stale_export_is_refused(tmp_path):
    """The re-promoted .pt with a forgotten re-export."""
    pt = _export(tmp_path)
    pt.write_bytes(b"torch weights v2 -- a new run")
    assert "exported from a different" in rt.verify_onnx(pt)


def test_tampered_onnx_is_refused(tmp_path):
    pt = _export(tmp_path)
    rt.onnx_path_for(pt).write_bytes(b"onnx graph, edited")
    assert "does not match the hash" in rt.verify_onnx(pt)


def test_failed_parity_is_refused(tmp_path):
    assert "parity" in rt.verify_onnx(_export(tmp_path, passed=False))


def test_missing_pieces_are_refused(tmp_path):
    pt = _export(tmp_path)
    rt.sidecar_path_for(rt.onnx_path_for(pt)).unlink()
    assert "unverified" in rt.verify_onnx(pt)
    rt.onnx_path_for(pt).unlink()
    assert "no ghostnet.onnx" in rt.verify_onnx(pt)
    assert rt.verify_onnx(None) is not None


def test_sidecar_name_does_not_collide_with_the_pt_sidecar():
    assert rt.sidecar_path_for(rt.onnx_path_for("m/ghostnet.pt")).name == "ghostnet.onnx.json"


# ---------------------------------------------------------------- parity

def _b(cls, score, xyxy):
    return {"cls": cls, "score": score, "xyxy": xyxy}


def test_identical_detections_match():
    a = [_b("wreck", 0.8, [10, 10, 110, 60]), _b("debris", 0.3, [200, 200, 240, 260])]
    m = rt.match_detections(a, list(reversed(a)), conf_floor=0.03)
    assert m["ok"] and m["paired"] == 2 and m["min_iou"] == 1.0


def test_shifted_box_fails_iou_gate():
    m = rt.match_detections([_b("wreck", 0.8, [10, 10, 110, 60])],
                            [_b("wreck", 0.8, [16, 10, 116, 60])], conf_floor=0.03)
    assert not m["ok"]


def test_score_drift_fails():
    m = rt.match_detections([_b("wreck", 0.80, [10, 10, 110, 60])],
                            [_b("wreck", 0.78, [10, 10, 110, 60])], conf_floor=0.03)
    assert not m["ok"] and m["failures"][0][0] == "score"


def test_class_change_fails():
    m = rt.match_detections([_b("wreck", 0.8, [10, 10, 110, 60])],
                            [_b("plane", 0.8, [10, 10, 110, 60])], conf_floor=0.03)
    assert not m["ok"]


def test_box_at_the_floor_may_cross_it():
    """0.035 against a 0.03 floor can land either side from 1e-5 of numeric
    noise; that is the threshold working, not the export changing the model."""
    m = rt.match_detections([_b("wreck", 0.035, [10, 10, 110, 60])], [], conf_floor=0.03)
    assert m["ok"]
    m = rt.match_detections([_b("wreck", 0.5, [10, 10, 110, 60])], [], conf_floor=0.03)
    assert not m["ok"] and m["failures"][0][0] == "missing"


def test_dice():
    a = np.zeros((10, 10), bool)
    a[2:6, 2:6] = True
    assert rt.dice(a, a) == 1.0
    assert rt.dice(np.zeros_like(a), np.zeros_like(a)) == 1.0
    assert rt.dice(a, ~a) == 0.0


# ------------------------------------- one U-Net post-processing path

def test_onnx_and_torch_unet_share_post_processing():
    """A fake ONNX session computing the SAME logits must give the same
    probability map, bit for bit apart from the sigmoid's float noise --
    which only holds if letterbox, crop and resize are shared."""
    torch = pytest.importorskip("torch")

    class Net(torch.nn.Module):
        def forward(self, x):
            return x * 3.0 + 0.5

    net = Net()

    class FakeOnnx:
        session = object()

        def logits(self, x):
            return net(torch.from_numpy(x)).numpy()

    gray = (np.arange(300 * 500) % 251).astype(np.uint8).reshape(300, 500)
    a = unet.predict_prob(net, gray, "cpu")
    b = unet.predict_prob(FakeOnnx(), gray, "cpu")
    assert a.shape == b.shape == gray.shape
    assert np.abs(a - b).max() < 1e-6


# ------------------------------------------------- verified download

def _serve(files: dict[str, bytes]):
    def fetch(url, target):
        name = url.rsplit("/", 1)[1]
        if name not in files:
            raise OSError("404 " + name)
        Path(target).write_bytes(files[name])
    return fetch


def test_download_matching_its_sidecar_is_installed(tmp_path):
    import hashlib

    blob = b"weights"
    side = json.dumps({"sha256": hashlib.sha256(blob).hexdigest()}).encode()
    msg = fetch_weights.fetch_verified("https://x/y", "ghostnet.pt", tmp_path,
                                       fetch=_serve({"ghostnet.pt": blob, "ghostnet.json": side}))
    assert msg.startswith("verified")
    assert (tmp_path / "ghostnet.pt").read_bytes() == blob


def test_download_not_matching_is_deleted(tmp_path):
    side = json.dumps({"sha256": "0" * 64}).encode()
    with pytest.raises(ValueError, match="does not match"):
        fetch_weights.fetch_verified("https://x/y", "ghostnet.pt", tmp_path,
                                     fetch=_serve({"ghostnet.pt": b"evil", "ghostnet.json": side}))
    assert not (tmp_path / "ghostnet.pt").exists()
    assert not list(tmp_path.glob("*.download"))


def test_local_sidecar_wins_over_the_servers(tmp_path):
    """The committed sidecar is the anchor: a server that swaps the weights
    AND their sidecar still fails against the hash from git."""
    import hashlib

    (tmp_path / "ghostnet.json").write_text(
        json.dumps({"sha256": hashlib.sha256(b"released").hexdigest()}), encoding="utf-8")
    forged = json.dumps({"sha256": hashlib.sha256(b"swapped").hexdigest()}).encode()
    with pytest.raises(ValueError):
        fetch_weights.fetch_verified("https://x/y", "ghostnet.pt", tmp_path,
                                     fetch=_serve({"ghostnet.pt": b"swapped", "ghostnet.json": forged}))


def test_onnx_is_checked_against_its_own_sidecar_key(tmp_path):
    import hashlib

    blob = b"graph"
    side = json.dumps({"onnx_sha256": hashlib.sha256(blob).hexdigest()}).encode()
    msg = fetch_weights.fetch_verified("https://x/y", "ghostnet.onnx", tmp_path,
                                       fetch=_serve({"ghostnet.onnx": blob, "ghostnet.onnx.json": side}))
    assert msg.startswith("verified")


def test_no_url_is_a_clear_refusal(monkeypatch, capsys):
    monkeypatch.delenv("GHOSTNET_WEIGHTS_URL", raising=False)
    assert fetch_weights.main(["--trained"]) == 1
    assert "PUBLISHING_WEIGHTS" in capsys.readouterr().out
