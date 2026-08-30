"""Guards on the training script's argument handling.

These do not train anything. They cover the failure that already cost a run:
--resume silently restarting from epoch 1 and deleting the results it was meant
to continue. A wrong flag that destroys ten minutes of GPU work is worth a test
even when the happy path is only checkable by running it for real.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

SCRIPT = AI_ROOT / "scripts" / "train.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("train_script", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def make_dataset(tmp_path: Path) -> Path:
    d = tmp_path / "processed"
    d.mkdir(parents=True, exist_ok=True)
    (d / "data.yaml").write_text("path: .\ntrain: train/images\nval: val/images\nnc: 1\nnames:\n  0: wreck\n")
    return d / "data.yaml"


def test_resume_without_a_checkpoint_fails_loudly(mod, tmp_path, monkeypatch, capsys):
    """Rather than quietly starting from scratch and overwriting the run."""
    data = make_dataset(tmp_path)
    monkeypatch.setattr(mod, "EXPERIMENTS", tmp_path / "experiments")
    monkeypatch.setattr(sys, "argv",
                        ["train.py", "--data", str(data), "--name", "nope", "--resume"])
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert "--resume needs a checkpoint" in out


def test_resume_points_at_the_checkpoint_not_the_pretrained_weights(mod, tmp_path, monkeypatch, capsys):
    """The optimiser state, epoch counter and LR schedule live in last.pt.
    Building the model from yolo11s.pt and passing resume=True restarts at
    epoch 1 -- which is exactly what happened the first time this ran."""
    data = make_dataset(tmp_path)
    exp = tmp_path / "experiments"
    ckpt = exp / "run1" / "weights" / "last.pt"
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    ckpt.write_bytes(b"not a real checkpoint")
    monkeypatch.setattr(mod, "EXPERIMENTS", exp)
    monkeypatch.setattr(sys, "argv",
                        ["train.py", "--data", str(data), "--name", "run1", "--resume", "--dry-run"])
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "resuming from" in out
    assert "last.pt" in out
    assert "yolo11s.pt" not in out.split("resuming from")[1]


def test_missing_dataset_is_reported_before_torch_is_imported(mod, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["train.py", "--data", str(tmp_path / "absent.yaml")])
    assert mod.main() == 1
    assert "run ai/scripts/build_dataset.py first" in capsys.readouterr().out


def test_dry_run_trains_nothing(mod, tmp_path, monkeypatch, capsys):
    data = make_dataset(tmp_path)
    monkeypatch.setattr(mod, "EXPERIMENTS", tmp_path / "experiments")
    monkeypatch.setattr(sys, "argv", ["train.py", "--data", str(data), "--dry-run"])
    assert mod.main() == 0
    assert "dry run: nothing trained" in capsys.readouterr().out
