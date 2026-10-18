# Enclosure — V08

[Fusion source](../cad/muse-rdk-x5.f3d) · [Assembly STEP](../cad/muse-rdk-x5.step) · [STL parts](../cad/stl/)

Fit prototype for the RDK X5, GS130WI and Waveshare 3.5inch RPi LCD (F). STL units are millimetres. Keep the camera module intact and retain the screen's existing standoffs and board orientation.

## Assembly

1. Install the camera on its yoke, then attach the yoke to the rear shell. The two camera seats use the official STEP's 106 mm pitch and fit inside its fork-shaped mounting ears.
2. Place the X5 and upper metal heatsink together behind the screen. Fit the two adjustable clamps to the front-shell rails. They bear on the metal mounting lands; keep the centre fins clear. The actual upper heatsink profile and clamping force need a trial fit.
3. Connect the lower shell hooks, then close the concealed side snaps. Release slots allow reopening. The four original M3 screw holes and nut pockets remain available for backup fastening.
4. Fit the bottom cover after wiring. Do not force the shell closed against a plug or cable.

Print a camera seat and clamp/rail sample before another full enclosure. The corrected revision has not been physically assembled.

## Fasteners

- Bottom cover: four nominal 3 × 8 mm plastic screws.
- Yoke to rear shell: two nominal 3 × 8 mm plastic screws.
- Camera to yoke: two M2.5 × 14 mm socket screws, two M2.5 nuts and two thin washers.
- Optional shell reinforcement: four M3 × 60 mm socket screws and four M3 nuts.
- X5/heatsink clamps: no additional screws.

These are CAD selections. Check actual head dimensions, engagement and printed pilot fit before tightening; the 2.5 mm plastic pilots are not tapped metal threads. Keep the screen's supplied fasteners.

## Audio and cables

Current hardware choice: a USB sound-card speaker and a CTIA four-contact 3.5 mm microphone. USB must carry audio, rather than power alone. Recording and playback are selected independently in `muse-ui.service`.

The earlier PAM8302, loose speaker, capsule microphone and TRRS pigtail study is retired. Its separate mounting parts are not included in the print set. The purchased speaker and gooseneck microphone still need their own measured mounts.

The USB sockets sit about 30.3 mm inside the left side; the audio jack sits about 25.6 mm inside the right side. V08 relieves the front-shell lip at the USB opening and retains the TRRS clearance. Checks use assumed plug envelopes, not measurements of the purchased cables. A 30 mm exposed audio-plug body would project about 4.4 mm outside the side, before its cable bend.

**Fully internal cable routing and strain relief are unfinished.** The side openings remain accessible; the preview does not show installed audio cables. This revision does not establish audio quality, acoustic isolation, microphone compatibility or physical plug fit.

## Verification boundary

Exported solids, STL meshes and nominal assembly/connector clearances are checked before publication. Printed latch force, thermal retention, real heatsink contact, screen pogo compression, camera field of view and audio operation require hardware testing.
