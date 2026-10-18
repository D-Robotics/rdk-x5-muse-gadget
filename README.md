# Muse Gadget on RDK X5

A small desktop pet for the RDK X5. It combines the Muse chat interface, a
480×320 touch UI, local pet actions and an optional ROS 2 perception bridge for
the GS130WI stereo camera.

<img src="docs/images/rdk-x5-muse-cad.png" alt="Muse RDK X5 enclosure CAD preview" width="640">

## Quick start

Use an RDK X5 running Ubuntu 22.04 with XFCE and the `sunrise` desktop account.

1. [Set up the SPI screen](docs/SPI-LCD-SETUP.md). The quick installer supports kernel **6.1.83** and **CS1 wiring**. Skip this if display and touch already work.
2. Install and pair the [Muse Linux SDK](https://github.com/facebookincubator/muse-gadget-sdk/tree/main/linux) using your own SDK token.
3. Install the UI and pet core:

```sh
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/D-Robotics/rdk-x5-muse-gadget.git
cd rdk-x5-muse-gadget
sudo bash install.sh
```

The installer builds the UI in `/opt/muse-ui`, installs `petctl`, adds the
**Muse** desktop shortcut and enables autostart. It also installs the chat/audio
backend and configures the desktop user's PulseAudio output.

For a foreground camera run:

```sh
source /opt/tros/setup.bash 2>/dev/null || source /opt/tros/humble/setup.bash
./scripts/start-camera.sh
```

The launcher uses 1088×1280, realtime timestamps and UDP transport so the root
camera process can communicate with the desktop user's perception service.
The pet uses the left image for perception and monitors both channels.

The perception bridge is optional. It needs TROS Humble and `colcon`; gesture
and YOLO packages and their model files must already be installed on the X5.
The installer does not download those model assets.

```sh
sudo apt-get install -y python3-colcon-common-extensions
sudo env INSTALL_PET_VISION=1 bash install.sh
```

This builds `ros2_ws` and enables `muse-pet-vision.service`. The service runs
the project's no-camera launch file and only consumes existing ROS topics; it
never starts a second `mipi_cam`. Topic and model settings live in
`/etc/default/muse-pet-vision`. See [Pet demo](docs/PET-DEMO.md) for foreground
launch and model configuration.

To start the camera at boot too, stop any manually launched camera first, then
run `sudo env INSTALL_PET_CAMERA=1 INSTALL_PET_VISION=1 bash install.sh`.
Camera settings live in `/etc/default/muse-pet-camera`.

For the small-screen recognition page and web preview, install with
`sudo env INSTALL_PET_CAMERA=1 INSTALL_PET_VISION=1 INSTALL_PET_PREVIEW=1 bash install.sh`.
This also requires the TROS `hobot_codec` and `websocket` packages. Open
`http://<X5-IP>:8000/TogetheROS/` for separate object and hand/gesture views.
Enable the installed models in `/etc/default/muse-pet-vision` as described in
[Pet demo](docs/PET-DEMO.md).

A compatible microphone and speaker are needed for voice. The current plan uses a CTIA 3.5 mm TRRS microphone and a USB audio speaker. Set the recording device with `PULSE_SOURCE` and the playback device with `PULSE_SINK` in [muse-ui.service](muse-ui.service). The newly selected audio hardware has not been tested on the X5.

## Controls

- Tap the avatar to pet it. Hold the microphone icon to record; release to send.
- Swipe left for the live recognition view. Tap **Controls** for feeding,
  sleep, focus timer and find-object controls; **Vision** returns to the image.
- Tap the speaker button to mute or unmute.
- Tap **Desktop** or press **Esc** to close the window.
- Double-click **Muse** on the desktop to reopen it.

Local pet commands use the same state machine as gestures and Muse actions:

```sh
petctl wake
petctl move left
petctl move stop
petctl feed banana
petctl timer start 25
petctl status
```

Palm wakes the pet; ThumbLeft/ThumbRight move it. Show a banana, then make
an OK sign to feed it. ThumbUp pets it; Victory starts a banana search.
These local actions work without Muse internet access. Voice still uses Muse
and requires permission to run commands on the paired Linux gadget.

## CAD and development

- [CAD files](cad/): editable Fusion model, assembly STEP and six STL parts.
- [Enclosure assembly and fasteners](docs/ENCLOSURE.md).
- [Build and renderer tests](simulator/README.md).
- [Camera, perception and pet demo](docs/PET-DEMO.md).
- [Project status](docs/STATUS.md).

V08 adds corrected GS130WI seats, adjustable X5/heatsink clamps, hidden shell
snaps and optional screw closure. It remains a fit prototype: audio mounts,
concealed cable routing and pogo contact need physical checking.

## Logs

```sh
systemctl status muse-ui musegadget muse-pet-camera muse-pet-vision muse-pet-preview
journalctl -u muse-ui -u muse-pet-vision -u muse-pet-preview -n 60 --no-pager
```

## License

[Apache-2.0](LICENSE). See [third-party notices](THIRD_PARTY.md) for fonts, dependencies and vendor CAD.
