# SPI display

Start with the [screen quick start](../../docs/SPI-LCD-SETUP.md).

```sh
sudo python3 hardware/display/install.py
```

The quick installer is for RDK X5 kernel 6.1.83 and manual **CS1 / physical pin 26**
wiring. `drivers.json` pins the two downloaded ARM64 kernel modules by immutable
source revision, SHA-256 and vermagic. They are fetched at install time, not
redistributed in this repository. `prebuilt/wired-cs1` contains the two compiled
overlays and the 109-byte controller initialization firmware with checksums.

It also installs the backlight service, Xorg modesetting selection and Goodix
landscape calibration. Originals are retained for `install.py --restore`.
The wired touch reset uses pin 28, so that profile disables I2C0.

## Source rebuild

Only needed when changing an overlay or the firmware:

```sh
sudo apt-get install device-tree-compiler
python3 hardware/display/build.py --profile wired-cs1
```

Copy the three outputs to `prebuilt/wired-cs1` and regenerate `sha256.json` before
shipping changes to the installer.

`profiles/waveshare-f-pogo` is retained as an untested CS0 candidate. It is not
selectable in the quick installer. Do not use it as a drop-in replacement for the
CS1 wiring.

The generator and legacy overlay sources come from
[Cathay-Launch-UI, revision 623032d](https://github.com/shockley6668/Cathay-Launch-UI/tree/623032d56395b018387b8f262ac0693e2ca28e2d).
Physical pin labels are corrected in the guide. The panel's active dimensions
are rounded to 74 x 49 mm without changing its 480 x 320 pixel mode.
