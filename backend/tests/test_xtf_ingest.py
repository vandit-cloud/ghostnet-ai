"""Tests for splitting an uploaded .xtf into frames.

The happy path needs Member 1's AI package installed (it does the tiling), so
these cover the wiring and the three ways it degrades -- which are the paths a
developer or a demo machine will actually hit, and each one has to produce a
message an operator can act on rather than silence.

A .xtf upload that quietly creates no frames is the specific failure this
module exists to fix: the file is stored, the survey looks fine, and there is
simply nothing to process.
"""

import uuid

import pytest

from app.services.xtf_ingest import SUPPORTED, _parse_time, ingest_xtf


def test_only_xtf_is_claimed_as_supported():
    """.jsf is on the upload whitelist but there is no JSF reader. Claiming it
    here would mean accepting a file and producing nothing."""
    assert SUPPORTED == {".xtf"}


@pytest.mark.parametrize("name", ["survey.jsf", "notes.txt", "line01", "scan.tif"])
def test_a_container_we_cannot_split_says_so_and_names_the_alternative(name):
    created, warnings = ingest_xtf(None, uuid.uuid4(), uuid.uuid4(), name)
    assert created == 0
    assert warnings and len(warnings) == 1
    assert "only .xtf is supported" in warnings[0]


def test_a_missing_ai_package_is_reported_with_the_fix(monkeypatch):
    """The backend must stay usable without the AI environment installed --
    that is the whole point of the adapter seam -- but an .xtf upload has to
    explain why it produced nothing instead of appearing to succeed."""
    import builtins

    real_import = builtins.__import__

    def no_ghostnet(name, *args, **kwargs):
        if name == "ghostnet":
            raise ImportError("no module named ghostnet")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_ghostnet)
    created, warnings = ingest_xtf(None, uuid.uuid4(), uuid.uuid4(), "line01.xtf")
    assert created == 0
    assert "not installed" in warnings[0]
    assert "pip install" in warnings[0]


def test_an_unreadable_file_does_not_raise(tmp_path, monkeypatch):
    """A truncated or mislabelled upload is an operator message, not a 500."""
    fake = tmp_path / "broken.xtf"
    fake.write_bytes(b"not an xtf at all")

    def boom(path, **kwargs):
        raise ValueError("bad magic")

    monkeypatch.setitem(
        __import__("sys").modules,
        "ghostnet",
        type("m", (), {"iter_survey_frames": staticmethod(boom)}),
    )
    created, warnings = ingest_xtf(None, uuid.uuid4(), uuid.uuid4(), str(fake))
    assert created == 0
    assert "could not be read" in warnings[0]


def test_frames_are_created_with_navigation_from_the_ping_headers(tmp_path, monkeypatch):
    """The frame positions are the point: they draw the survey track, including
    across the stretches where nothing was detected."""
    from app.services import xtf_ingest

    class Pos:
        latitude, longitude, heading_deg = -46.3518, -73.7320, 348.5
        timestamp = "2005-07-01T05:54:51"

    class Frame:
        def __init__(self, i, pos):
            self.frame_id = f"LINE__p{i:06d}__x00000"
            self.image_path = tmp_path / f"{i}.png"
            self.meta = {}
            self.position = pos
            self.ping_offset = i

    frames = [Frame(0, Pos()), Frame(640, Pos()), Frame(1280, None)]
    monkeypatch.setitem(
        __import__("sys").modules,
        "ghostnet",
        type("m", (), {"iter_survey_frames": staticmethod(lambda p, **kw: iter(frames))}),
    )

    added = []
    db = type("Db", (), {"add": lambda self, row: added.append(row)})()
    created, warnings = ingest_xtf(db, uuid.uuid4(), uuid.uuid4(), str(tmp_path / "line.xtf"))

    assert created == 3
    assert added[0].latitude == pytest.approx(-46.3518)
    assert added[0].heading == pytest.approx(348.5)
    assert added[0].metadata_source == "xtf"
    assert added[0].timestamp.tzinfo is not None      # the track sorts on this

    # depth and range stay unset: they are not altitude and not range
    # resolution, and substituting them corrupts the geometry.
    assert added[0].depth is None
    assert added[0].range is None

    # A frame with no fix is still stored and still scored, but is marked so it
    # can be left off the track rather than drawn at (0, 0).
    assert added[2].quality_status == "no_navigation"
    assert any("no usable navigation" in w for w in warnings)


def test_a_frame_time_that_will_not_parse_still_sorts():
    """The track is ordered by timestamp, so a null would sort a frame to the
    end and draw a line that doubles back on itself."""
    assert _parse_time(None).tzinfo is not None
    assert _parse_time("not a date").tzinfo is not None
    assert _parse_time("2005-07-01T05:54:51").year == 2005


# ---------------------------------------------------------------------------
# The storage_reference / filesystem-path confusion (found 2026-09-04)
# ---------------------------------------------------------------------------
# `file_service` used to hand `ingest_xtf` the storage_reference -- a
# storage-relative key like "<survey_id>/<uuid>_name.xtf" -- instead of
# resolving it with `storage.path_for()`. Both end in ".xtf", so the extension
# check passed and the failure surfaced only as a FileNotFoundError swallowed
# into a warning: a real 40 MB survey stored VALID with ZERO frames.
#
# Every test above calls ingest_xtf with a real path, which is why none of them
# saw it. The bug lived entirely in the CALL SITE, so that is what these check.


def test_a_storage_reference_is_not_a_path_and_produces_no_frames(db_session):
    """Documents the trap directly: the reference SHAPE reaches the extension
    check intact and gets all the way to the reader before failing."""
    created, warnings = ingest_xtf(
        db_session,
        uuid.uuid4(),
        uuid.uuid4(),
        f"{uuid.uuid4()}/{uuid.uuid4().hex}_survey.xtf",  # a storage_reference
    )
    assert created == 0
    assert warnings and "could not be read" in warnings[0]


def test_file_service_hands_ingest_a_path_that_exists(db_session, monkeypatch, tmp_path):
    """The actual regression guard. Whatever file_service passes to ingest_xtf
    must be resolvable on disk -- not a storage key."""
    from app.services import file_service
    from app.storage.local import LocalStorageBackend

    seen: dict[str, object] = {}

    def _spy(db, survey_id, file_id, storage_path, max_pings=None):
        seen["path"] = storage_path
        return 0, []

    monkeypatch.setattr("app.services.xtf_ingest.ingest_xtf", _spy)

    storage = LocalStorageBackend(root=str(tmp_path))
    import io as _io

    # A real survey row: survey_files carries a FK to it.
    from app.models.survey import Survey

    survey = Survey(name="path-regression")
    db_session.add(survey)
    db_session.flush()

    file_service.upload_survey_file(
        db_session,
        storage,
        survey.id,
        "line01.xtf",
        _io.BytesIO(b"XTF\x00not-really-sonar-but-it-is-on-disk"),
        None,
    )

    assert "path" in seen, "file_service never called ingest_xtf for a .xtf upload"
    from pathlib import Path as _Path

    handed = _Path(str(seen["path"]))
    assert handed.is_absolute(), f"got a relative reference, not a path: {handed}"
    assert handed.exists(), f"path handed to ingest_xtf does not exist: {handed}"
