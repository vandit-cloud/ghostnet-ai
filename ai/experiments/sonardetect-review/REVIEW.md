# SONARDETECT: every frame reviewed by eye (26 Sep 2026)

All 70 SONARDETECT frames in `E:\New folder\ai\data\processed` (47 train,
16 val, 7 test) were viewed at 320 px on labelled contact sheets. The review
was asked for on 20 Sep, after `marker_paint` flagged six frames. This source
carries the only independent (non-SubPipe) debris test boxes.

## Not clean sonar: 14 of 70

| frame | split | what is wrong | found |
|---|---|---|---|
| 000162 | train | slide: sonar panels plus photographs of a bicycle and a tyre | 20 Sep |
| 000192 | train | acquisition-software gain / TVG panel burned in | 20 Sep |
| 000207 | train | full acquisition-software screenshot with red boxes | 20 Sep |
| 000204 | train | photo inset (reef module) in the top-right corner | **26 Sep** |
| 000205 | train | the same photo inset, bottom-left | **26 Sep** |
| 000209 | train | screenshot: inset window plus a drawn cyan box | **26 Sep** |
| 000213 | train | range-scale ticks ("2 4 6 8") and UI triangle markers | **26 Sep** |
| 000172 | train | solid white ellipse over towed trawl gear, likely drawn (uncertain) | **26 Sep** |
| 000189 | val | screenshot with a blue UI scale bar (passes all five screens) | 20 Sep |
| 000210 | val | slide / screenshot with a photograph | 20 Sep |
| 000216 | val | acquisition-software gain / TVG panel burned in | 20 Sep |
| 000223 | val | photograph strip across the top | **26 Sep** |
| 000163 | test | slide / screenshot with photographs | 20 Sep |
| 000183 | test | composed figure: zoomed inset panel over the frame | **26 Sep** |

Borderline, kept: `000194` (train) is a rotated, georeferenced mosaic on a
white canvas. It is real sonar, but not a waterfall.

## Label problem

`000016` (val) shows an aircraft with **no box**. Its one `debris` box is on a
different object (x 0.37, y 0.79). A real plane therefore sits in val as
background.

## What it does to the independent-debris claim

The 7 test frames carry exactly the 14 independent debris boxes
(000151: 1, 000157: 2, 000163: 3, 000169: 2, 000177: 1, 000183: 4,
000188: 1). **7 of the 14 (000163 and 000183) are in slide or composite
frames.** Any figure quoted on "independent debris" rests on 7 clean boxes
from 5 frames, not 14.

## Not done here, deliberately

No frame was removed or relabelled. Dropping test frames moves the test
ruler that every earlier run was scored on, so it is a decision, not a
cleanup. The options are to exclude the 14 and re-score gv5 on the reduced
split, or to keep them and footnote the claim.
