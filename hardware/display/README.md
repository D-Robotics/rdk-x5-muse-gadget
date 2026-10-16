# SPI display files

See [the setup guide](../../docs/SPI-LCD-SETUP.md) before using these overlays.

Two separate profiles are kept here:

- `wired-cs1`: the earlier Cathay setup, with LCD CS on physical pin 26. It
  preserves that setup's touch reset GPIO at physical pin 28. This is not the
  plug-on wiring in the Muse enclosure.
- `waveshare-f-pogo`: a candidate derived from the Waveshare F schematic and
  V04 contact geometry. LCD CS is physical pin 24. Its touch overlay omits an
  external reset GPIO because the imported screen has no TP_RST pogo contact.
  This profile has not been tested on a board.

The build produces DTBOs and the existing 109-byte ST7796S initialization firmware:

```sh
sudo apt-get install device-tree-compiler
python3 hardware/display/build.py --profile wired-cs1
```

This only builds files; it does not change the host or a connected board. Do not
load both profiles or assume that matching controller names makes their wiring
interchangeable. Kernel modules are kernel-specific and are not bundled here.

The firmware generator and legacy overlays come from
[Cathay-Launch-UI at 623032d](https://github.com/shockley6668/Cathay-Launch-UI/tree/623032d56395b018387b8f262ac0693e2ca28e2d).
The panel's physical dimensions are corrected to a rounded 74 x 49 mm active area;
this does not change the 480 x 320 pixel mode. The derived pogo profile starts
at 32 MHz rather than assuming the legacy 40 MHz setting.
