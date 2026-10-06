# gvN1-natural3-s0: chip-level seabed classifier (26 Sep 2026)

yolo11s-cls, 224 px, seed 0, on `E:\New folder\ai\data\natural` built by
`build_natural_dataset.py` (splits inherited from the detector's
`ai/data/processed`, so no detector test chip is in classifier train).

## The class decision

Vandit delegated `natural_class()`. It was decided after looking at 8 chips
per code across sites. Three classes, each spanning at least two sites:

| class | codes | chips | sites |
|---|---|---|---|
| sediment | SS + SW | 812 | dongying, quanzhou, shenzhen, yantai |
| erosion | TG + SM | 905 | quanzhou, shenzhen |
| rock_armour | RP | 355 | quanzhou, shenzhen |

SS is not plain seabed. Quanzhou's is flat, but Dongying's is textured
sediment with dune scarps, the same bedform family as SW. Riprap is placed
rock, so it is man-made: when served, it must map to contract class
`unknown`, never `natural`.

## Test result (n = 310)

| class | accuracy | by site |
|---|---|---|
| sediment | 0.964 (132/137) | dongying 91/93, quanzhou 15/17, shenzhen 9/9, yantai 17/18 |
| erosion | 0.939 (108/115) | shenzhen 101/108, quanzhou 7/7 |
| rock_armour | 0.862 (50/58) | quanzhou 27/27, **shenzhen 23/31** |

Overall 0.935. The main confusion is rock_armour -> erosion (8 chips), all at
Shenzhen.

## What this does and does not show

* One seed.
* Test chips come from the same sites and surveys as train. This is
  within-site accuracy, not transfer. Quanzhou erosion is 7 chips.
* The honest next measurement is a held-out site (`train_natural.py
  --holdout-site quanzhou`) before any cross-site claim.
* Not wired into the app. Serving it needs the rock_armour -> `unknown`
  mapping above.
