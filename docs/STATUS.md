# Snapshot: 18 October 2026

The GS130WI dual-channel camera has now been brought up on the RDK X5 at
1088×1280. The current repository adds the local pet interaction layer and the
ROS 2 integration boundary around that verified camera input.

## Implemented

- LVGL/SDL Muse avatar UI with captions, hold-to-talk, mute and desktop close/reopen.
- Python chat/audio bridge, Muse Linux SDK integration, Edge TTS, PulseAudio routing,
  desktop shortcut and XFCE autostart.
- Local pet state and `petctl` commands for wake, movement, feeding, petting,
  timers and the find-object activity.
- UI state for pet movement and activities, driven by the same local state
  machine used by touch, Muse commands and perception events.
- A `muse_pet_vision` ROS 2 bridge and no-camera launch file. Camera topics,
  gesture/object topics and optional pipeline startup are configurable.
- An opt-in colcon build and systemd service. It consumes a running camera and
  does not launch another `mipi_cam` instance.
- ST7796S kernel DRM + GT911 touch quick installer for kernel 6.1.83 / CS1 wiring.
  Precompiled overlays/firmware are included; the pinned module downloads are
  checked by SHA-256, ARM64 ELF metadata and vermagic. Source rebuilds are optional.
- V08 Fusion CAD, assembly STEP and six STL parts under `cad/`: corrected
  GS130WI fork seats, X5/upper-heatsink ratchet clamps, hidden shell snaps,
  retained M3 backup holes, bold front marking and USB front-lip clearance.
  The discarded discrete-audio components are removed from the current assembly.

## Not completed

- Board validation of the complete gesture-to-action and YOLO-to-feeding paths,
  including exact topics, installed models, latency and false triggers.
- GS130WI depth and IMU interactions.
- An upstream Meta contribution for the full pet example.
- Physical V08 assembly tests, pogo compression/contact and camera FOV checks.
- Measured mounts for the selected USB speaker and TRRS gooseneck microphone,
  concealed cable return, strain relief and thermal retention tests.
- Board validation of the derived Waveshare F pogo overlay profile.
- New microphone, USB speaker and Bluetooth end-to-end tests.

The native Fusion file contains editable geometry. No portable, one-command
Fusion model generator is claimed; the construction scripts from the local
iteration history are not presented as a reproducible CAD build system.

## Display distinction

The earlier manual-wired panel uses CS1 at physical pin 26. The screen's pogo
layout uses CS0 at physical pin 24 and does not expose the same reset contacts.
These are separate profiles, not interchangeable presets. Start with the
[display guide](SPI-LCD-SETUP.md) and the actual board/screen revision.

## Verification

- GS130WI dual-channel launch at 1088×1280: confirmed by the board user on
  17 October. The repository does not yet contain a captured topic/latency log.
- macOS ARM64 LVGL/SDL frontend build: passed on 18 October.
- 29 Python tests passed: pet state/timers, backend commands, real offline
  socket-to-frontend integration, vision gates, message parsing, launch
  construction and display installer fixtures.
- Headless renderer CTest passed: seven deterministic visual scenarios,
  invalid input checks, avatar/microphone touch routing and pet control buttons.
- Python syntax compilation, shell syntax and Git whitespace checks passed.
- Four isolated installer tests passed: repeat install/restore, incorrect-kernel
  rejection, corrupt-download rejection and incomplete-overlay repair.
- Both display profiles compile with dtc; duplicate-address warnings describe
  the disabled spidev node sharing the panel's chip select in an overlay.
- Generated firmware matches the original 109-byte binary byte-for-byte.

These checks do not prove the gesture/YOLO model installation, ROS topic mapping,
real audio, full display throughput or the assembled enclosure.

See [enclosure notes](ENCLOSURE.md) for the current mechanical revision, nominal
fasteners and audio limitations. The camera result does not validate the CAD,
audio layout or the remaining perception pipeline.

V08 CAD checks passed for six closed STEP solids and six manifold STL meshes,
49 sampled rigid shell-closing poses, seven clamp depth settings and the nominal
USB/TRRS plug clearance envelopes. Flexible snap behaviour and actual cable fit
are outside those checks.
