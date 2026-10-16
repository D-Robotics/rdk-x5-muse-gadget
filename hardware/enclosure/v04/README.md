# Muse on RDK X5 — enclosure V04

V04 fixes the speaker obstruction visible through V03's left port opening.
V03's GPIO orientation and LCD standoff registration are retained.

## Changes

- Remove the left internal speaker holder from the USB/Ethernet approach area.
- Move the provisional round speaker, holder, grille and clamp to the right.
  Its centre is head-local Y32, Z-40 mm. Offset the lower clamp fastener and
  preserve the case screw channel through the new holder.
- Close the abandoned left grille and reshape the right opening into a slot
  above the audio area. The front styling and camera position are unchanged.

## Checks

`reports/port-access-audit.json` checks straight insertion corridors from outside
X=-20 mm to 0.5 mm before each connector mouth. The RJ45 allowance is 18 x 16 mm;
each stacked USB allowance is 16.5 x 20 mm. All three corridors clear the included
case, fasteners and hardware geometry. These are design allowances, not measured
purchased cable heads. The sockets remain approximately 30 mm recessed; finger
grip and Ethernet latch release still require an actual cable trial.

`reports/validation.json` checks the five printed solids and their interference
with the included hardware. All five solids and their checked features pass,
with no unresolved pairs or intersections above 0.01 mm3. Audio versus nominal
case fasteners was checked separately and has no intersection above this limit.
All five millimetre STL files pass the independent manifold/volume audit.

`reports/audio-clearance.json` retains both studied routes and their results.
The straight 30+10 mm audio envelope is the active option and passes. The elbow
and rearward cable route collides with the new audio holder and is explicitly
an unsupported alternative for this revision. The Adafruit 2914 adapter itself
has not been modelled or fit-tested.

GPIO placement is unchanged from V03. The eleven modelled pogo contacts match
the X5 header tails with a maximum XY offset of 0.182 mm. The nominal mating PCB
face meets the LCD standoff ends at Z=-15 mm. Imported pogo bodies are rigid;
the roughly 2 mm free-tip overlap with header tails does not certify spring
working stroke. Verify contact and compression on hardware before tightening.

## Remaining hardware work

The round 28 x 12 mm speaker and 6 mm mic are placeholders. Their holders are
not a finished design for the proposed rectangular Waveshare 2030 speaker or
the Same Sky capsule. No amplifier PCB, final audio wiring or heatsink mounting
is included. Physical fit, electrical operation and acoustic performance have
not been tested.

## Deliverables

- `fusion/Muse-RDK-X5-enclosure-v04.f3d`: editable Fusion archive.
- `step/Muse-RDK-X5-assembly.step`: assembly exchange file.
- `stl/01_*.stl` through `stl/05_*.stl`: five print parts, in millimetres.
- `images/10-left-port-access.png`: cleared USB/Ethernet side.
- `images/11-right-audio-placement.png`: relocated audio side.
- `images/design-board.png`: assembled, orthographic and exploded views.

V04 is the only CAD revision shipped here. See ../README.md for earlier revision history. Use V04 for further edits.
