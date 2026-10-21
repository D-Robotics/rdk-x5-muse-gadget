# Snapshot: 21 October 2026

The shared-image and demand-driven preview changes were deployed to X5 / RDK
OS 3.5.0 / TROS Humble on 19 October. Both GS130WI channels, BPU inference and
the native preview were exercised. Application autostarts remain disabled
after the earlier overheating incident; current runs are manual tests.

## Implemented

- LVGL/SDL Muse avatar UI with captions, hold-to-talk, mute and desktop close/reopen.
- Python chat/audio bridge, Muse Linux SDK integration, Edge TTS, PulseAudio routing,
  desktop shortcut and XFCE autostart.
- Local pet state and `petctl` commands for wake, movement, feeding, petting,
  timers and the find-object activity.
- OK feeds a virtual snack when no food object is detected; a fresh detected
  banana takes priority. Feeding keeps its three-second cooldown.
- Open-palm approach emits `PalmApproach` and pets the avatar once. Retreat
  rearms it; stationary palms, brief jitter and missing/changed tracks do not
  repeatedly trigger. This is a relative 2-D size cue, not metric depth.
- UI state for pet movement and activities, driven by the same local state
  machine used by touch, Muse commands and perception events.
- Control buttons return to the avatar. Wake, feeding, searching, focus and
  sleep have distinct poses; search patrols with a magnifying glass and waits
  for a real object event before celebrating. Timer cancellation reacts briefly.
- A `muse_pet_vision` ROS 2 bridge and no-camera launch file. Camera topics,
  gesture/object topics and optional pipeline startup are configurable.
- An opt-in colcon build and systemd service. It consumes a running camera and
  does not launch another `mipi_cam` instance.
- A separate opt-in camera service with realtime timestamps and a common UDP
  profile for the root camera and desktop-user perception processes.
- A C++ stereo relay caps model inputs at 10 FPS before multi-node image copies.
- An optional hardware-JPEG/TROS web preview with separate object and gesture
  views, plus a native recognition page reached by swiping left. Results are
  matched to image timestamps; stale screen images disappear after three seconds.
- ST7796S kernel DRM + GT911 touch quick installer for kernel 6.1.83 / CS1 wiring.
  Precompiled overlays/firmware are included; the pinned module downloads are
  checked by SHA-256, ARM64 ELF metadata and vermagic. Source rebuilds are optional.
- V08 Fusion CAD, assembly STEP and six STL parts under `cad/`: corrected
  GS130WI fork seats, X5/upper-heatsink ratchet clamps, hidden shell snaps,
  retained M3 backup holes, bold front marking and USB front-lip clearance.
  The discarded discrete-audio components are removed from the current assembly.

## Not completed

- Full gesture/action coverage and YOLO-to-feeding tests, including latency,
  recognition accuracy and false triggers. Palm/ThumbUp input and the resulting
  backend state changes were observed on 19 October.
- Depth-based pet interactions and IMU support. The Depth preview is implemented.
- An upstream Meta contribution for the full pet example.
- Physical V08 assembly tests, pogo compression/contact and camera FOV checks.
- Measured mounts for the selected USB speaker and TRRS gooseneck microphone,
  concealed cable return, strain relief and thermal retention tests.
- Board validation of the derived Waveshare F pogo overlay profile.
- New microphone, USB speaker and Bluetooth end-to-end tests.

## Interaction update: 20 October

- Full-screen 480×320 Vision with in-image labels and no side list. Native-size
  decode preserves detail in the 272×320 stream. Portrait video keeps its full
  field of view with side margins instead of stretching or cropping it.
- Distinct cuddling, dancing, stretching and curious poses; idle periodically waves.
  Controls include Play, Look and Stretch. Victory now dances; Find banana stays
  available as a command/button.
- Open-palm gaze updates at up to 4 Hz, with 650 ms expiry. Gaze does not wake
  a sleeping pet and yields to active poses and chat.
- Gesture wake is ignored while awake. Reaction poses finish before conflicting
  gestures can interrupt them. Direct controls retain priority. OK and V require
  600 ms of continuous classification and are suppressed during tracked palm motion.

Deployed to X5. All 74 Python tests passed on the board; macOS passed 72
with two OpenCV tests skipped. Both native CTests passed on host and X5.
Live X11 input exercised Play, Stretch, Look, Feed and avatar-tap cuddling,
including return to the avatar and reopening Vision after each control.
Left/right gaze was checked with injected attention events. The final camera
sample had no hand in view, so real-hand gaze tracking is not verified by this
run. The earlier real-palm trial below tested the preceding happy reaction;
the new cuddle pose was exercised by touch and automated event tests.
No additional perception model was added.

## Depth stability update: 20 October

The first implementation restarted the camera and stopped gesture/YOLO services
on each depth-page transition. It also used a 15 FPS cap and the wrong camera
channel order. The brief initial swipe checks missed the sustained left/right
warning. That implementation has been replaced.

One GS130WI capture now provides calibrated 640×352 stereo and a raw 272×320
substream. Calibration comes from EEPROM. Channels 0/2 produced no left/right
warning in the subsequent 30-second sample. Gesture, YOLO and camera services
stay running during Depth, with unchanged service PIDs across repeated swipes.
A user-hand sample received 326 messages with 43 hand groups and 16 eligible
palms. During concurrent depth, logs also recorded 51 valid hand groups over
five seconds. These confirm data flow, not an overall accuracy score.

StereoNet V2.4 INT8 uses two workers and model parameters shared by the normal
ROS launch and the fast launcher. A 30-second concurrent sample returned
19.25–19.74 model FPS. Native BMP updates measured 18.12 FPS over eight seconds;
maximum sampled file age was 123 ms. Temperature reached about 83°C in that
sample and fell after leaving Depth; sustained thermal behavior is unverified.

Repeated ROS setup/launch and Python imports still cost 4–10 seconds, so these
are no longer part of page transitions. The ROS environment, preview renderer
and model are prepared once. Only a fresh UI lease lets the C++ adapter deliver
frames: outside Depth, model weights remain cached but inference receives no
new input. Closing the controller releases all cached depth workers.

## Unified vision runtime

The production refactor loads the camera, body detector, YOLO and StereoNet
through their installed component libraries. The official TROS 2.4.1 hand
landmark and gesture sources are compiled into the same C++ executable, keeping
the existing models and postprocessing. The runtime contains the shared-image
relay and lease-gated depth adapter as nodes in the same executor. Python remains
only for pet events and display rendering. During Depth, YOLO input pauses while
hand input continues. Camera/model processes are never restarted on a swipe.

Built and deployed on X5. The loaded-library map confirms camera, body, YOLO
and StereoNet components in the same process; both hand nodes are linked into
that executable. Three Vision → Depth → Vision cycles kept the same runtime
PID with no restarts. Time from swipe start to the first fresh Depth BMP was
1.412, 1.358 and 1.294 seconds, including the simulated swipe itself.

During the three-second Depth windows, StereoNet returned 38, 60 and 61 frames
(12.7 FPS initially, then about 20 FPS). Gesture messages stayed near 10 FPS;
some contained recognized targets. YOLO produced no messages during those
windows and resumed at about 10 FPS on return to Vision. After draining queued
frames, each three-second Vision window received zero depth input/output.
These are short data-flow samples, not gesture accuracy or physical LCD FPS.

All 83 Python tests passed on X5; macOS skipped three OpenCV tests. Both native
CTests passed on host and X5. The 236-file deployment manifest matched the
local sources.
Application autostarts remain disabled. The old depth controller is disabled
to prevent it from launching another pipeline.

## Gesture input compatibility

The TROS 2.4.1 hand landmark node retains body keypoints in its output. The
2.4.1 gesture preprocessor counts those groups alongside hand landmarks and can
reject a target because the ROI and landmark counts differ. The bridge now
publishes `/muse/gesture_input` with only hand ROIs and their 21-point landmark
groups. Ambiguous or malformed targets are dropped rather than paired by guesswork.
The original `/muse/hand_landmarks` stream remains available for diagnosis.

Both input fixes were deployed on X5 on 19 October. The camera now keeps its
1088×1280 main stream and adds a 544×640 VSE substream for perception and
preview. The full-size input exceeded the hand model's expanded ROI size limit
(less than 255 pixels), leaving detected hands without keypoints.

With the user's hand in view, real messages contained 21 hand keypoints and
gesture attributes `5` (Palm) and `2` (ThumbUp). Backend state recorded both
names; ThumbUp produced `pet_mode=happy` and increased happiness. A preview
capture showed the finger skeleton and gesture name. Model output remained
about 10 FPS, with preview delivery about 30 FPS when requested. Some larger
hand boxes still exceed the model limit; recognition accuracy, all other
gestures and sustained thermals are not established by this test.

The native Fusion file contains editable geometry. No portable, one-command
Fusion model generator is claimed; the construction scripts from the local
iteration history are not presented as a reproducible CAD build system.

The subsequent close-hand preset uses a 272×320 VSE substream, preserving the
1088×1280 aspect ratio. The palm-motion bridge and backend were deployed, with
tests for approach/retreat cycles, hold, jitter, lost tracks, multiple palms,
clipping and OK rejection. A live user trial on 20 October received 350 gesture
messages over 35 seconds, containing 288 hand landmark groups and 135 eligible
palm samples. Three real approaches emitted `PalmApproach`; each reached the
backend, entered `happy` and added five happiness points. One `Okay` classification
also triggered virtual-snack feeding during the sequence; whether that pose was
intentional was not confirmed, so this trial does not establish false-trigger
rates. The device was temporarily lying sideways; the user requested keeping
the current camera orientation.

## Display distinction

The earlier manual-wired panel uses CS1 at physical pin 26. The screen's pogo
layout uses CS0 at physical pin 24 and does not expose the same reset contacts.
These are separate profiles, not interchangeable presets. Start with the
[display guide](SPI-LCD-SETUP.md) and the actual board/screen revision.

## Verification

- On-board image and perception subscription check on 18 October: both image
  streams, `/muse/body`, `/muse/hand_landmarks`, `/muse/gestures` and
  `/muse/objects` received. YOLO returned `person`; the backend reported ready.
- X5 native frontend build, ROS colcon build and renderer CTest passed.
- On-board Desktop close, launcher reopen and repeated-launch singleton checks
  passed. The old display systemd service is disabled; XFCE starts the window.
- macOS ARM64 LVGL/SDL frontend build: passed on 18 October.
- 36 Python tests passed on X5: pet state/timers, backend commands, real offline
  socket-to-frontend integration, vision gates, message parsing, launch
  construction and display installer fixtures.
- Preview tests cover viewer isolation, timestamp rounding/expiry, JPEG rendering
  and model-input throttling. Host tests skip the OpenCV rendering test when
  OpenCV is absent; that test passed on X5.
- Headless renderer CTest passed: seven deterministic visual scenarios,
  invalid input checks, avatar/microphone touch routing, pet control buttons,
  native preview image loading and stale-image hiding.
- Python syntax compilation, shell syntax and Git whitespace checks passed.
- Four isolated installer tests passed: repeat install/restore, incorrect-kernel
  rejection, corrupt-download rejection and incomplete-overlay repair.
- Both display profiles compile with dtc; duplicate-address warnings describe
  the disabled spidev node sharing the panel's chip select in an overlay.
- Generated firmware matches the original 109-byte binary byte-for-byte.

Installed TROS models load, with runtime/model compiler version warnings. These
checks do not establish model accuracy, real audio, full display throughput or
the assembled enclosure.

Reboot verification passed after preserving the vision launcher's executable
permission: the window opened automatically with one frontend process; backend,
camera and perception services were active with no vision-service restarts.
The bridge reported `vision=ready` and received a real `person` detection.

## Performance snapshot

The unbounded preview run reached roughly 94–95°C and CPU frequency fell to
600 MHz. BPU sysfs listed the body and YOLO processes using the accelerator
(about 9–11% aggregate in those samples); image transport and CPU processing
remained expensive.

In the earlier relay build, runtime logs showed roughly 10 FPS for YOLO and gesture
output. YOLO inference samples ranged from 9–23 ms, with complete pipeline
samples around 93–146 ms. These are live log samples, not a sustained benchmark.
JPEG encoding uses the hardware codec. The native preview uses quarter-size
JPEG decode with one OpenCV thread; that build limited UI refresh to 8 Hz.

The board has a heatsink without a fan. Temperature remained around 93°C under
that combined workload. After the applications were stopped, it fell to about
77°C, with a subsequent idle sample around 72°C. Thermal protection was not changed.

Changes deployed on 19 October:

- Camera health uses compact metadata instead of two raw Python subscriptions.
- Preview JPEG delivery is demand-driven. Native JPEG decode/BMP writes stop
  when Vision is hidden; web output stops when the viewer disconnects.
- Preview queues keep the latest eligible frame after a stall.
- Unchanged backend state is written every five seconds instead of ten times
  per second; state changes still write immediately.
- The native UI uses a monotonic clock and a 30 FPS target. On Linux X11 it
  updates changed pixel regions. Static labels are not redrawn. Per-frame
  model warnings are off by default.
- Preview polling now follows the frame timer, separate from the 250 ms
  status-icon timer. The codec and native consumer no longer impose 10/8 FPS
  caps. Model FPS and preview FPS remain independent.
- A shared-image branch now connects camera, bounded loaned-buffer relay, body/
  landmark/YOLO nodes and codec using `HbmMsg1080P`. It rejects unavailable image
  loans. A profile selector writes a common transport config and matching root
  UIDs for the image services, with an explicit UDP rollback. It starts nothing.
- A 544×640 GS130WI hardware substream now feeds capture, inference and preview.
  It preserves the main stream's aspect ratio and was validated with real hands.

Verification:

- The 19 October build passed 67 Python tests on X5; macOS passed 66 with
  one OpenCV test skipped. See the interaction update above for current results.
  Coverage includes shared model/codec wiring, stale environment overrides,
  matching service identities, rollback, viewer demand, backend writes and
  hand-only classifier input with malformed/ambiguous landmark rejection,
  plus palm approach/retreat and its backend pet action.
- Current renderer scenarios cover each action pose. All nine control buttons
  are checked for command dispatch and return to the avatar page.
- Native frontend build and both host CTests passed. The C++ stream core also
  passed UndefinedBehaviorSanitizer checks for 30→10/8 FPS scheduling, lease
  expiry, bounded copying, timestamp preservation and invalid-size rejection.
- The actual relay and its test probes built under ARM64 Linux / ROS 2 Humble.
  Both ROS CTests passed, including separate source/relay/observer processes.
  Synthetic input was about 30 FPS; relay delivery was 10 FPS. Over seven
  seconds the observer received 70 model-input frames and 16 preview frames
  during a two-second request window, with none after preview shutdown. Both
  compact health channels arrived. Disabling message loans failed explicitly.

The container test used official `hbm_img_msgs` at
`228ff9ac43b07a955cb99eccd4448319c4e08f53`. The subsequent X5 build used the
installed TROS package. All three target ROS CTests passed, including an
independent 30 FPS preview with model delivery held at 10 FPS. Native X11
screenshots from the original renderer and changed-region renderer matched
exactly in the listening scenario.

Real X5 samples with the left preview open and all BPU models enabled:

- Over 22 seconds, each perception topic delivered 220 results (10 FPS).
  Capture-stamp-to-receipt medians were 61 ms for YOLO and 74 ms for gestures.
- JPEG output was 29.8 FPS and native BMP production 29.2 FPS. Actual native
  rendering was about 21–25 FPS, limited by the changing SPI image region.
  The avatar page rendered at about 30 FPS.
- With Vision hidden for a separate 22-second sample, JPEG output and BMP
  writes were both zero while perception continued at about 10 FPS.
- BPU load was 8–10% and CPU frequency 1.5 GHz in that sample. CPU temperature
  was 82–83°C; continued preview reached 84.4°C and the test guard stopped
  perception/preview. Thermal protection was not changed. Sustained thermal
  behavior with passive cooling remains unresolved.

These are short runtime samples, not an accuracy test or a matched thermal
benchmark against the previous build. The camera's full-rate capture/copy
path remains; the downstream relay does not eliminate it. Autostarts remain
disabled during validation.

See [enclosure notes](ENCLOSURE.md) for the current mechanical revision, nominal
fasteners and audio limitations. The camera result does not validate the CAD,
audio layout or the complete physical interaction demo.

V08 CAD checks passed for six closed STEP solids and six manifold STL meshes,
49 sampled rigid shell-closing poses, seven clamp depth settings and the nominal
USB/TRRS plug clearance envelopes. Flexible snap behaviour and actual cable fit
are outside those checks.
