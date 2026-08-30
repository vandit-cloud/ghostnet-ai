"""The single source of truth for class names, across every dataset.

Three vocabularies exist in this project and they are not the same thing:

  1. SOURCE classes   -- whatever each dataset happens to call things. SCTD says
                         "ship", KLSG says "wreck", another says "shipwreck".
  2. TRAINING classes -- what the detector actually learns. Their ORDER is the
                         YOLO class id, so it is load-bearing and must not be
                         reshuffled casually.
  3. CONTRACT classes -- the four values Member 2's database accepts, defined in
                         contract.py and frozen.

Keeping them separate is what lets a new dataset be added by editing one alias
table, instead of retraining vocabulary assumptions scattered through the code.

Why not one flat mapping straight from source to contract: it would throw away
the distinction between a wreck and an aircraft at conversion time, and that is
not recoverable afterwards. Converting at the finest granularity the source
offers and collapsing later is reversible; the reverse is not.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 2. Training classes. Index == YOLO class id. Order is a wire format.
# ---------------------------------------------------------------------------
#
# `ghost_net` is deliberately ABSENT, despite being the headline object.
#
# No public side-scan dataset contains ghost nets -- confirmed by the Oct-2025
# sonar dataset survey, and the reason the project metric is artificial-vs-
# natural (see docs/DATA.md). A class with zero training examples cannot be
# learned, and it puts a NaN in every per-class metrics table for the whole
# project. When synthetic ghost nets exist (plan J2, copy-paste), add it here
# and re-run the converter: labels are generated, so renumbering costs one
# command.
TRAINING_CLASSES: tuple[str, ...] = (
    "wreck",    # 0 -- ships, shipwrecks, large man-made hulls
    "plane",    # 1 -- submerged aircraft
    "natural",  # 2 -- plain seabed, rock, ripple. The hard negatives.
)

CLASS_TO_ID: dict[str, int] = {name: i for i, name in enumerate(TRAINING_CLASSES)}

# ---------------------------------------------------------------------------
# 1. Source aliases -> training class.
# ---------------------------------------------------------------------------
# Lower-cased, punctuation normalised before lookup. Add a dataset by adding
# its names here and nothing else.
SOURCE_ALIASES: dict[str, str] = {
    # SCTD (VOC XML)
    "ship": "wreck",
    "shipwreck": "wreck",
    "wreck": "wreck",
    "boat": "wreck",
    "vessel": "wreck",
    "aircraft": "plane",
    "plane": "plane",
    "airplane": "plane",
    # KLSG / sediment sets (folder-name classes)
    "seafloor": "natural",
    "seabed": "natural",
    "sediment": "natural",
    "rock": "natural",
    "ripple": "natural",
    "background": "natural",
    "nothing": "natural",
}

# ---------------------------------------------------------------------------
# Deliberately excluded source classes.
# ---------------------------------------------------------------------------
# Excluded, not forgotten: the converter reports every instance it drops, so a
# silent data loss is impossible. Removing a name from here re-includes it.
EXCLUDED_SOURCES: dict[str, str] = {
    "victim": "human remains; outside a marine-debris problem statement, and a body is not an artificial object -- including it muddies the artificial-vs-natural framing the whole metric rests on",
    "human": "see 'victim'",
    "drowning victim": "see 'victim'",
    "diver": "a live diver is not seabed debris",
    "mine": "ordnance; out of scope, and KLSG withholds the mine images from public release anyway",
}

# ---------------------------------------------------------------------------
# 3. Training class -> contract class.
# ---------------------------------------------------------------------------
# The contract vocabulary is closed at four values and frozen (changing it is a
# major version bump for Member 2). Wrecks and aircraft are both reported as
# `debris`: within this contract "debris" means "an artificial object on the
# seabed that is not specifically a net". The finer training class is not lost
# -- infer.py records it in evidence_summary.notes, which is free text and
# needs no schema change.
TRAINING_TO_CONTRACT: dict[str, str] = {
    "wreck": "debris",
    "plane": "debris",
    "natural": "natural",
    "ghost_net": "ghost_net",  # ready for when synthetic data exists
}

# A collapsed taxonomy for the binary framing. Not the default: with ~357
# images, whether finer classes help or merely split the data is an empirical
# question, and this makes it a one-flag experiment rather than a re-conversion.
COLLAPSE_MAPS: dict[str, dict[str, str]] = {
    "artificial": {"wreck": "artificial", "plane": "artificial", "natural": "natural"},
}


def normalise_source(name: str) -> str:
    """Lower-case, strip, and unify separators so 'Ship-Wreck' == 'ship wreck'."""
    return " ".join(name.strip().lower().replace("-", " ").replace("_", " ").split())


def source_to_training(name: str) -> tuple[str | None, str]:
    """Map one source class name onto a training class.

    Returns (training_class, reason). training_class is None when the instance
    must not be used, and `reason` always explains why -- 'excluded: ...' for a
    deliberate policy drop, 'unmapped' for a name nobody has taught us yet.

    The two are kept distinct on purpose. An unmapped name is a bug in this
    table and should be loud; an excluded one is a decision and should be quiet
    but counted.
    """
    key = normalise_source(name)
    # "sea bed", "sea-bed" and "seabed" are the same word to a human and should
    # be the same key here. Try the spaced form, then the joined form, rather
    # than requiring every alias table to list both spellings.
    joined = key.replace(" ", "")
    for candidate in (key, joined):
        if candidate in EXCLUDED_SOURCES:
            return None, "excluded: " + EXCLUDED_SOURCES[candidate]
        if candidate in SOURCE_ALIASES:
            return SOURCE_ALIASES[candidate], "mapped"
    return None, "unmapped"


def training_to_contract(name: str) -> str:
    """Map a training class onto the frozen contract vocabulary."""
    return TRAINING_TO_CONTRACT.get(name, "unknown")
