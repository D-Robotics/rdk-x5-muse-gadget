# Snapshot: 17 October 2026

This update organizes existing work for the D-Robotics organization. No board
connection or deployment is part of this update.

## Implemented

- LVGL/SDL Muse avatar UI with captions, hold-to-talk, mute and desktop close/reopen.
- Python chat/audio bridge, Muse Linux SDK integration, Edge TTS, PulseAudio routing,
  desktop shortcut and XFCE autostart.
- ST7796S kernel DRM + GT911 touch quick installer for kernel 6.1.83 / CS1 wiring.
  Precompiled overlays/firmware are included; the pinned module downloads are
  checked by SHA-256, ARM64 ELF metadata and vermagic. Source rebuilds are optional.
- V08 Fusion CAD, assembly STEP and six STL parts under `cad/`: corrected
  GS130WI fork seats, X5/upper-heatsink ratchet clamps, hidden shell snaps,
  retained M3 backup holes, bold front marking and USB front-lip clearance.
  The discarded discrete-audio components are removed from the current assembly.

## Not completed

- GS130WI capture/depth/IMU integration, YOLO, gesture control and pet interactions.
- Desktop mini-apps and an upstream Meta contribution for those features.
- Physical V08 assembly tests, pogo compression/contact and camera FOV checks.
- Measured mounts for the selected USB speaker and TRRS gooseneck microphone,
  concealed cable return, strain relief and thermal retention tests.
- Board validation of the derived Waveshare F pogo overlay profile.
- New microphone, speaker and Bluetooth end-to-end tests.

The native Fusion file contains editable geometry. No portable, one-command
Fusion model generator is claimed; the construction scripts from the local
iteration history are not presented as a reproducible CAD build system.

## Display distinction

The earlier manual-wired panel uses CS1 at physical pin 26. The screen's pogo
layout uses CS0 at physical pin 24 and does not expose the same reset contacts.
These are separate profiles, not interchangeable presets. Start with the
[display guide](SPI-LCD-SETUP.md) and the actual board/screen revision.

## Software verification from 16 October

- Fresh macOS ARM64 LVGL/SDL frontend build: passed.
- Existing backend unit tests: 2 passed.
- Existing headless renderer CTest: passed.
- Four isolated installer tests passed: repeat install/restore, incorrect-kernel
  rejection, corrupt-download rejection and incomplete-overlay repair.
- Both display profiles compile with dtc; duplicate-address warnings describe
  the disabled spidev node sharing the panel's chip select in an overlay.
- Generated firmware matches the original 109-byte binary byte-for-byte.

These checks do not test device-tree application, the X5 kernel, real touch,
audio, display throughput or a printed enclosure.

See [enclosure notes](ENCLOSURE.md) for the current mechanical revision, nominal
fasteners and audio limitations. No new X5 connection or hardware test was made
for the CAD update.

V08 CAD checks passed for six closed STEP solids and six manifold STL meshes,
49 sampled rigid shell-closing poses, seven clamp depth settings and the nominal
USB/TRRS plug clearance envelopes. Flexible snap behaviour and actual cable fit
are outside those checks.
