# Pet demo

The demo separates capture, perception and display:

- `mipi_cam` publishes the GS130WI channels.
- `muse_pet_vision` consumes existing ROS topics and sends timestamped events
  to the pet state machine.
- `muse-ui` owns the pet state, touch input, Muse chat, captions and audio.
- `muse-pet-preview` encodes the left image as JPEG with the hardware codec,
  serves the TROS web viewer and produces the small-screen recognition image.

The perception launch does not start or stop the camera.

## Prerequisites

- RDK X5 with Ubuntu 22.04 and TROS Humble. Current images normally provide
  `/opt/tros/setup.bash`; `/opt/tros/humble/setup.bash` is also supported.
- A working GS130WI dual-channel launch.
- `python3-colcon-common-extensions` for the local ROS workspace.
- D-Robotics `mono2d_body_detection`, `hand_lmk_detection`,
  `hand_gesture_detection` and `dnn_node_example` for the full pipeline.

The repository does not redistribute or fetch model assets. Install the
versions that match the board image and TROS release, then use absolute paths
in `/etc/default/muse-pet-vision` when overriding package defaults. The launch
resolves installed assets and makes a separate YOLO config with absolute model
and label paths. X5 Model Zoo models use Bayes-e `.bin`; some TROS gesture
packages retain `.hbm` filenames for their packaged X5 models. Use the X5
package assets, rather than renaming or substituting an S-series model.

The official [gesture install guide](https://github.com/D-Robotics/hand_gesture_detection)
uses `sudo apt install -y tros-humble-hand-gesture-detection` for TROS Humble.
Check all four ROS packages with `ros2 pkg prefix <package>` before enabling
the complete pipeline. Match the TROS release to your board image.

## 1. Start the camera

```sh
source /opt/tros/setup.bash 2>/dev/null || source /opt/tros/humble/setup.bash
./scripts/start-camera.sh
```

This wraps the user's working dual-channel launch with 1088×1280 images,
`mipi_frame_ts_type:=realtime` and `dual_combine:=0`. Realtime timestamps are
required by the bridge's stale-frame checks; default sensor timestamps use a
different clock. Leave this terminal running.

Both launchers use `scripts/fastdds.xml`: UDPv4 with data sharing disabled.
The camera needs root access while perception runs as `sunrise`; TROS's default
shared-memory profile did not deliver frames between these users on the test X5.
Use the same profile for diagnostic subscribers:

```sh
source scripts/ros-transport.sh
```

Check the topics before starting perception:

```sh
ros2 topic list -t
```

Topic names and message types can differ across TROS images. Set the actual
left and right topic names instead of relying on auto-discovery.

Check each X5 model before enabling a pipeline:

```sh
hrt_model_exec model_info --model_file /absolute/path/to/model.bin
```

## 2. Build the optional ROS bridge

From the repository checkout:

```sh
sudo apt-get install -y python3-colcon-common-extensions
sudo env INSTALL_PET_VISION=1 bash install.sh
```

This copies the project to `/opt/muse-ui`, builds `muse_pet_vision` and its image relay, and
enables `muse-pet-vision.service`. It does not install TROS, launch the camera,
or download gesture and YOLO models.

For camera autostart, stop the foreground camera and install with both flags:

```sh
sudo env INSTALL_PET_CAMERA=1 INSTALL_PET_VISION=1 bash install.sh
```

This also enables `muse-pet-camera.service`. Do not run a second camera launch.
Resolution, frame-rate request and combined-image settings are in
`/etc/default/muse-pet-camera`.

For a foreground run, stop the service and launch the same no-camera stack:

```sh
sudo systemctl stop muse-pet-vision
source /opt/tros/setup.bash 2>/dev/null || source /opt/tros/humble/setup.bash
source /opt/muse-ui/ros2_ws/install/setup.bash
source /opt/muse-ui/scripts/ros-transport.sh
ros2 launch muse_pet_vision muse_pet_vision.launch.py \
  left_topic:=/image_left_raw right_topic:=/image_right_raw \
  gesture_topic:=/muse/gestures object_topic:=/muse/objects \
  socket_path:=/run/muse-ui/input.sock \
  start_gesture:=true start_yolo:=true auto_discover:=false
```

This starts YOLOv8 and the body → hand landmarks → static gesture pipeline on
the left image. It never starts another camera. If perception is already
running, set both `start_*` flags to `false` and supply its output topics.
Model overrides are listed in `muse-pet-vision.env`.

For systemd, edit `/etc/default/muse-pet-vision` and restart the service:

```sh
sudoedit /etc/default/muse-pet-vision
# Set MUSE_PET_START_GESTURE=true and MUSE_PET_START_YOLO=true.
sudo systemctl restart muse-pet-vision
systemctl status muse-pet-vision --no-pager
journalctl -u muse-pet-vision -n 80 --no-pager
```

## 3. Recognition preview

Install with `INSTALL_PET_PREVIEW=1` in addition to the vision flag. This needs
the installed TROS `hobot_codec` and `websocket` packages; the installer adds
Python OpenCV. The service reuses the camera and inference results.

```sh
sudo env INSTALL_PET_VISION=1 INSTALL_PET_PREVIEW=1 bash install.sh
systemctl status muse-pet-preview --no-pager
```

On the SPI screen, swipe left to **Vision**. The image shows detection boxes,
hand landmarks and current matched labels. **Controls** opens the pet buttons;
**Vision** returns to the preview. Images expire after three seconds, so a
stopped camera is not shown as live.

Open `http://<X5-IP>:8000/TogetheROS/` for two views of the same left image:
YOLO objects on the left and hands/gestures on the right. HTTP uses port 8000;
the image sockets use 8080 and 8082. Nginx runs in the service rather than
being left behind by the vendor launch file. Installed viewer files are not edited.

The preview matches AI results to their original frame timestamps, tolerating
up to one millisecond of model timestamp rounding. Unmatched results are not
painted onto a different frame. Empty results keep the image moving when no
hand or object is detected. The matching window is 250 ms, not a latency claim.
The native screen is limited by the UI's 8 Hz refresh; its JPEG decoder uses
quarter-resolution decoding and one OpenCV thread.

The service launcher limits image delivery to the model nodes to a target of
10 FPS through a small C++ relay. The sensor may still capture at 30 FPS.
Settings are `MUSE_PET_THROTTLE`, `MUSE_PET_INFERENCE_FPS` and
`MUSE_PET_BODY_IMAGE_GAP` in `/etc/default/muse-pet-vision`. The relay preserves
resolution and timestamps and uses depth-one queues before the expensive
multi-node fan-out. A foreground perception launch can enable it with
`start_throttle:=true mono2d_image_gap:=0`.

The models run on the BPU and JPEG encoding uses the hardware codec. ROS image
copies, model pre/postprocessing, the small-screen JPEG decoder and drawing
still use CPU. Check temperature and CPU frequency when judging smoothness;
a busy BPU is not required for the image pipeline to be CPU-bound.

## 4. Check the pet without vision

`petctl` is useful before enabling models:

```sh
petctl wake
petctl pet
petctl move left
petctl move right
petctl move stop
petctl feed banana
petctl timer start 25
petctl timer cancel
petctl find banana
petctl status
```

## Demo sequence

1. Hold an open palm to wake the pet.
2. Use ThumbLeft or ThumbRight to move it; losing the gesture stops movement.
3. Show a supported food object such as a banana, then hold the OK gesture to
   confirm feeding.
4. Start a study timer through Muse or `petctl timer start 25`.
5. Use `petctl find banana` to start the find-object game.

The state machine filters short detections, expires stale camera events and
applies a cooldown after feeding. Movement and timers run locally when Muse is
offline.

Voice notes include instructions for Muse to call `petctl` through the paired
Linux gadget's `system.run` tool. Try “Start a 25 minute focus timer” or
“帮我找一下杯子”. Device command permission must be granted in Muse; voice
recognition and this tool call have not been verified on the assembled unit.

## Model Zoo extensions

The [X5 Model Zoo](https://github.com/D-Robotics/rdk_model_zoo) has useful next
steps beyond COCO feeding and finding:

- [YOLOWorld](https://github.com/D-Robotics/rdk_model_zoo/tree/main/samples/vision/yoloworld):
  a scavenger hunt with a prepared vocabulary. Its X5 sample requires offline
  text embeddings; arbitrary spoken words are not immediately new classes.
- [YOLO pose](https://github.com/D-Robotics/rdk_model_zoo/tree/main/samples/vision/ultralytics_yolo):
  copy a pose or take a stretch break with the pet.
- [ByteTrack](https://github.com/D-Robotics/rdk_model_zoo/tree/main/samples/vision/bytetrack):
  keep following the same person through a brief occlusion.

Those three games are extension ideas, not enabled pipelines in this revision.
The bridge accepts additional `ai_msgs/PerceptionTargets` detector topics via
`extra_detector_topics:='yoloworld:/muse/world,tracker:/muse/tracks'`.
Model Zoo Python outputs need an explicit ROS publisher adapter before they
can use that interface; a model filename alone is not an interchangeable plugin.

## Host replay

To exercise local interaction without a camera or Muse credentials:

```sh
mkdir -p /tmp/muse-pet-demo
export MUSE_UI_RUNTIME=/tmp/muse-pet-demo
PYTHONPATH=sdk MUSE_UI_CHAT=off python3 backend.py
# In another terminal, using the same MUSE_UI_RUNTIME:
MUSE_UI_RUNTIME=/tmp/muse-pet-demo ./build/muse_simulator
python3 scripts/replay-pet-demo.py --runtime /tmp/muse-pet-demo
```

Replay generates synthetic events. It does not run a model. Pet state and
timers currently reset when the backend restarts.

## Runtime checks

```sh
petctl status
systemctl status muse-ui muse-pet-camera muse-pet-vision --no-pager
journalctl -u muse-ui -u muse-pet-camera -u muse-pet-vision -n 100 --no-pager
pactl info
pactl list short sources
pactl list short sinks
```

On the test X5, both image topics and all four perception topics delivered
messages; YOLO detected a person and the bridge reported `vision=ready`.
This confirms data flow, not recognition accuracy. Physical gesture-to-action,
food confirmation and the selected audio hardware still need a live user test.

Check the actual image orientation before testing gestures: 1088×1280 is a
portrait-sized stream. Do not change rotation until you have inspected a frame.
Start at the camera's default rate, then measure latency and BPU load with both
algorithms enabled. This revision does not infer stereo depth or use the IMU.

Implementation references: [camera](https://github.com/D-Robotics/hobot_mipi_cam),
[gesture nodes](https://github.com/D-Robotics/hand_gesture_detection),
[DNN nodes](https://github.com/D-Robotics/hobot_dnn), and
[RDK Device Skills](https://github.com/D-Robotics/rdk-device-skills).
