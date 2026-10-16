# Snapshot: 16 October 2026

This update organizes existing work for the D-Robotics organization. No board
connection or deployment is part of this update.

## Implemented

- LVGL/SDL Muse avatar UI with captions, hold-to-talk, mute and desktop close/reopen.
- Python chat/audio bridge, Muse Linux SDK integration, Edge TTS, PulseAudio routing,
  desktop shortcut and XFCE autostart.
- Earlier ST7796S kernel DRM + GT911 touch setup, now documented with corrected
  physical pin numbering. Source overlays and firmware generator are included.
- Current Fusion CAD, assembly STEP and STL parts under `cad/`.
  The X5 orientation is corrected and provisional audio is on the right to clear
  the left USB/Ethernet approach.

## Not completed

- GS130WI capture/depth/IMU integration, YOLO, gesture control and pet interactions.
- Desktop mini-apps and an upstream Meta contribution for those features.
- Physical V04 print/fit tests, pogo compression/contact and camera FOV checks.
- Final mounts for Waveshare 2030, PAM8302, microphone, wiring and cooling.
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

## Local verification for this snapshot

- Fresh macOS ARM64 LVGL/SDL frontend build: passed.
- Existing backend unit tests: 2 passed.
- Existing headless renderer CTest: passed.
- Both display profiles compile with dtc; duplicate-address warnings describe
  the disabled spidev node sharing the panel's chip select in an overlay.
- Generated firmware matches the original 109-byte binary byte-for-byte.

These checks do not test device-tree application, the X5 kernel, real touch,
audio, display throughput or a printed enclosure.
