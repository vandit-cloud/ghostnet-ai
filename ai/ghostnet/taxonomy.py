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
    "debris",   # 2 -- miscellaneous man-made seabed objects: cables, small
                #      wreckage, unidentified artificial returns. The closest
                #      thing to actual marine debris in any side-scan data we
                #      have found, and therefore the class nearest the PS.
    "ghost_pot",  # 3 -- derelict crab pots. REAL derelict fishing gear in real
                #      side-scan sonar, from GhostVision. The closest thing to
                #      the problem statement that ground truth actually exists
                #      for, and it is NOT a net -- see the mapping below.
)

# `natural` is NOT a training class, and that is deliberate.
#
# Nobody has drawn boxes around rocks. Every natural example we have is a
# hard negative -- an image, or a tile, with no object on it -- and YOLO
# already expresses that as an empty label file. A `natural` class would
# therefore carry zero instances, exactly the NaN-in-every-metrics-table
# problem that keeps `ghost_net` out of the list above.
#
# The artificial-vs-natural separation is still measured, and measured more
# honestly than a class score would: it is the FALSE-POSITIVE RATE on the
# thousands of verified-empty seabed tiles in the validation and test splits.
# A model that cries wolf at rocks scores badly there, which is the claim the
# problem statement actually asks us to support.
#
# It stays in TRAINING_TO_CONTRACT below because the contract vocabulary is
# frozen and a future model, or a second-stage classifier, may yet emit it.

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
    # sonar_detect (Roboflow). "other" is a grab-bag of unidentified artificial
    # seabed returns -- cables, small wreckage, angular objects. Inspected by
    # sampling crops: they read as man-made, so `debris` is the honest mapping.
    # It still needs the section 11 annotation audit before it is trusted.
    "other": "debris",
    "debris": "debris",
    # Marine-PULSE and SubPipe: engineering structures on the seabed. They
    # are man-made objects, so `debris` is right within our closed contract
    # vocabulary -- but note that a live pipeline is infrastructure, not
    # litter. Say so in the report rather than implying every hit is waste.
    "pipeline": "debris",
    "pipeline or cable": "debris",
    "cable": "debris",
    "pipe": "debris",
    "engineering platform": "debris",
    "platform": "debris",
    # GhostVision. Derelict crab pots: genuine ghost fishing gear, manually
    # annotated on real side-scan sonar. Kept as its own class rather than
    # folded into debris, because "we detect derelict fishing gear" is a far
    # stronger and still truthful claim than "we detect debris".
    "crab pot": "ghost_pot",
    "crabpot": "ghost_pot",
    "ghost pot": "ghost_pot",
    "ghostpot": "ghost_pot",
    "pot": "ghost_pot",
    "litter": "debris",
    "trash": "debris",
}

# ---------------------------------------------------------------------------
# Source names that mean "plain seabed".
# ---------------------------------------------------------------------------
# These are NOT unmapped, and treating them as such would be actively harmful:
# an unmapped name quarantines its image, and these images are precisely the
# hard negatives we most want to keep. They are not a class either, for the
# reason given above. They are BACKGROUND -- an empty label file, which is how
# YOLO expresses "nothing here" and how the model learns not to cry wolf.
BACKGROUND_SOURCES: dict[str, str] = {
    "seafloor": "plain seabed: a hard negative, kept as an empty label rather than a class",
    "seabed": "see 'seafloor'",
    "seabed surface": "Marine-PULSE's plain-seabed class; 88 images across five different sonars",
    "sediment": "see 'seafloor'",
    "rock": "natural seabed feature; the thing the model must learn NOT to report",
    "ripple": "see 'rock'",
    "terrain": "see 'seafloor'",
    "background": "see 'seafloor'",
    "nothing": "see 'seafloor'",
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
    "fish": "WRONG MODALITY. The 208 'fish' boxes in sonar_detect are fish-finder / echosounder screenshots -- the classic arch a downward-looking single-beam sounder draws as a boat passes over a target. That is not side-scan seabed imagery, and several frames have the annotator's red circle burned into the pixels. Training on them teaches the detector to find drawn circles and sounder arches. Same principle that excludes MDT and UATD (docs/DATA.md).",
    "shoal": "see 'fish'",
    "underwater residual mound": "anthropogenic seabed MODIFICATION rather than a discrete object -- spoil and burial mounds left by engineering work. It is neither a man-made thing lying on the seabed nor untouched natural topology, so it sits astride the one distinction the whole metric rests on. Excluded until there is a reason to take a side.",
    "residual mound": "see 'underwater residual mound'",
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
    "debris": "debris",
    # A crab pot is fishing GEAR. It is not a NET.
    #
    # Mapping ghost_pot -> ghost_net would be the single most tempting lie
    # available to this project: it would make the headline metric look like it
    # measures the problem statement's exact words. It would also be inventing
    # ground truth, which both build plans forbid outright, and it would not
    # survive one informed question at judging.
    #
    # So it reports as `debris`, and infer.py carries "detector class:
    # ghost_pot" through in evidence_summary.notes, where a reviewer sees the
    # real finding without the contract claiming something it cannot support.
    # If the contract ever gains a `ghost_gear` value, this is the line to
    # change -- and that is a major version bump for Member 2.
    "ghost_pot": "debris",
    "natural": "natural",
    "ghost_net": "ghost_net",  # ready for when synthetic data exists
}

# A collapsed taxonomy for the binary framing. Not the default: with a few
# hundred images, whether finer classes help or merely split the data is an
# empirical question, and this makes it a one-flag experiment rather than a
# re-conversion.
COLLAPSE_MAPS: dict[str, dict[str, str]] = {
    "artificial": {"wreck": "artificial", "plane": "artificial",
                   "debris": "artificial", "ghost_pot": "artificial"},
}


def normalise_source(name: str) -> str:
    """Lower-case, strip, and unify separators so 'Ship-Wreck' == 'ship wreck'."""
    return " ".join(name.strip().lower().replace("-", " ").replace("_", " ").split())


def source_to_training(name: str) -> tuple[str | None, str]:
    """Map one source class name onto a training class.

    Returns (training_class, reason). training_class is None when the instance
    must not become a box, and `reason` says which of three cases applies:

      'excluded: ...'   a deliberate policy drop (victims, fish, mines).
      'background: ...' plain seabed -- becomes an empty label, not a class.
      'unmapped'        a name nobody has taught us yet.

    The three are kept distinct because the callers must act differently. An
    unmapped name is a bug in this table: it is reported loudly, and its image
    is quarantined rather than written as background, since asserting "nothing
    here" over an unrecognised real object is a false lesson. Excluded and
    background names are decisions, so their images ARE kept as negatives.
    """
    key = normalise_source(name)
    # "sea bed", "sea-bed" and "seabed" are the same word to a human and should
    # be the same key here. Try the spaced form, then the joined form, rather
    # than requiring every alias table to list both spellings.
    joined = key.replace(" ", "")
    for candidate in (key, joined):
        if candidate in EXCLUDED_SOURCES:
            return None, "excluded: " + EXCLUDED_SOURCES[candidate]
        if candidate in BACKGROUND_SOURCES:
            return None, "background: " + BACKGROUND_SOURCES[candidate]
        if candidate in SOURCE_ALIASES:
            return SOURCE_ALIASES[candidate], "mapped"
    return None, "unmapped"


#: Reasons whose images stay usable as negatives. Anything else is a bug in the
#: alias table and must quarantine its image rather than assert it is empty.
KEEP_AS_BACKGROUND = ("excluded", "background")


def training_to_contract(name: str) -> str:
    """Map a training class onto the frozen contract vocabulary."""
    return TRAINING_TO_CONTRACT.get(name, "unknown")
