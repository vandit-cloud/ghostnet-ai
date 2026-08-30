# Annotation quality audit — sonar_detect (Roboflow)

Plan §11 asks for a sampled annotation audit before training. This is the
evidence behind the class decisions taken in `ghostnet/taxonomy.py`, kept so the
reasoning can be challenged rather than taken on trust.

Sampled 2026-08-30 from `ai/data/raw/research/SONARDETECT/`.

| Sheet | Class | Verdict |
|---|---|---|
| `aircraft.jpg` | `aircraft` → `plane` | **Clean.** Genuine side-scan, clear aircraft silhouettes with acoustic shadows. The best-quality class here. |
| `shipwreck.jpg` | `shipwreck` → `wreck` | **Mixed — screen before use.** Roughly half genuine SSS. The rest are screenshots of sonar acquisition *software*, complete with toolbars, buttons and numeric readouts, plus at least one circular sector-scan display and one frame with a red border drawn on it. |
| `other.jpg` | `other` → `debris` | **Usable, needs an audit.** Reads as genuine unidentified artificial seabed returns: cables or linear features, small wreckage, angular objects, depressions. One frame has a cyan annotation rectangle burned into the pixels. |
| `fish.jpg` | `fish` → **excluded** | **Wrong modality.** These are fish-finder / echosounder arches — the shape a downward-looking single-beam sounder draws as a boat passes over a target — not side-scan seabed imagery. One frame has the annotator's red circle burned in. |

## Why `fish` is excluded

208 boxes, 22% of the dataset, and every one of them the wrong instrument.

The concern is not only the modality mismatch. Several frames carry annotation
graphics burned into the image pixels, so a detector trained on them can learn
*"red circle means fish"* — a shortcut that scores well in validation and is
worthless on real sonar. Combined with the sounder-arch shape having no
equivalent in side-scan imagery, there is nothing here for the model to
transfer.

Same principle that excludes MDT and UATD in `docs/DATA.md`: an instrument that
does not form acoustic shadows the way side-scan does is not side-scan training
data, however tempting the labels look.

## Outstanding

**Burned-in overlays are not yet screened out of the classes we keep.** At least
one `other` frame and one `shipwreck` frame carry them, and the sonar-software
screenshots in `shipwreck` are a separate problem: UI chrome is highly
distinctive and a detector will happily latch onto it.

Before training on `shipwreck`, filter for saturated non-greyscale pixel
regions and for the straight high-contrast edges typical of window borders.
