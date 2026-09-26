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
    # train.py imports its siblings (_fingerprint) the way a script does, from
    # its own directory. Loading it by path does not put that directory on
    # sys.path, so do it here, exactly as `python ai/scripts/train.py` would.
    # Removed again on teardown, so script modules (_screening, _fingerprint)
    # cannot shadow same-named imports in whatever test module runs next.
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("train_script", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    yield m
    sys.path.remove(str(SCRIPT.parent))
    sys.modules.pop(spec.name, None)


def fake_pretrained(tmp_path: Path) -> Path:
    """A --model path that exists. A dry run checks the file is there but never
    loads it, and the real yolo11s.pt lives only in the training tree -- so
    without this the dry-run tests fail on any other checkout."""
    p = tmp_path / "yolo11s.pt"
    p.write_bytes(b"placeholder: a dry run never loads it")
    return p


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
    # A run killed mid-flight: optimiser state and a 0-indexed epoch are still
    # in last.pt. train.py refuses anything else (a finished, stripped run, or
    # an unreadable file), so a placeholder byte string no longer stands in.
    torch = pytest.importorskip("torch")
    torch.save({"optimizer": {"state": {}}, "epoch": 4}, ckpt)
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
    monkeypatch.setattr(sys, "argv", ["train.py", "--data", str(data), "--model", str(fake_pretrained(tmp_path)), "--dry-run"])
    assert mod.main() == 0
    assert "dry run: nothing trained" in capsys.readouterr().out


def test_relaunching_an_existing_run_without_resume_is_refused(mod, tmp_path, monkeypatch, capsys):
    """The reboot case, and it fails in the direction nobody expects.

    Resuming is safe. What destroys work is retyping the ORIGINAL launch
    command after a restart: ultralytics reopens the directory (exist_ok=True),
    starts at epoch 1 and overwrites last.pt with a fresh network. Ten hours of
    GPU vanish with no error and no prompt.
    """
    data = make_dataset(tmp_path)
    exp = tmp_path / "experiments"
    ckpt = exp / "gv5" / "weights" / "last.pt"
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    ckpt.write_bytes(b"ten hours of training")
    (exp / "gv5" / "results.csv").write_text("epoch\n1\n2\n3\n", encoding="utf-8")

    monkeypatch.setattr(mod, "EXPERIMENTS", exp)
    monkeypatch.setattr(sys, "argv", ["train.py", "--data", str(data), "--name", "gv5"])
    assert mod.main() == 1

    out = capsys.readouterr().out
    assert "already has a checkpoint" in out
    assert "3 epochs trained" in out
    assert "continue from epoch 4" in out
    assert ckpt.read_bytes() == b"ten hours of training", "the checkpoint was touched"


def test_force_allows_the_overwrite_when_it_is_deliberate(mod, tmp_path, monkeypatch, capsys):
    """The guard must be escapable, or the next person deletes the directory by
    hand and loses the results.csv alongside it."""
    data = make_dataset(tmp_path)
    exp = tmp_path / "experiments"
    ckpt = exp / "gv5" / "weights" / "last.pt"
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    ckpt.write_bytes(b"discard me")

    monkeypatch.setattr(mod, "EXPERIMENTS", exp)
    monkeypatch.setattr(sys, "argv",
                        ["train.py", "--data", str(data), "--name", "gv5", "--force",
                         "--model", str(fake_pretrained(tmp_path)), "--dry-run"])
    assert mod.main() == 0
    assert "already has a checkpoint" not in capsys.readouterr().out
