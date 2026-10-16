# ST7796S display and GT911 touch on RDK X5

This is the SPI display work previously used by
[Cathay-Launch-UI](https://github.com/shockley6668/Cathay-Launch-UI/blob/623032d56395b018387b8f262ac0693e2ca28e2d/SPI-LCD-SETUP.md),
organized for this project. The Muse frontend uses SDL/X11; the kernel display
and touch drivers must work before installing Muse.

No X5 was connected for this repository update. The legacy setup is retained as
reference, and the Waveshare pogo profile is a candidate for the current CAD.
Neither profile was newly tested on hardware in this update.

## Display path

The legacy userspace `x11-to-spi` program copied desktop frames through spidev.
The later setup uses the kernel's `panel-mipi-dbi` DRM driver for ST7796S and
`goodix_ts` for GT911. Xorg uses its `modesetting` driver on the SPI DRM device;
libinput supplies touch events to the Muse window. Framebuffer, DRM card and
input event numbers depend on the installed image and probe order.

There is no new LCD driver in the Muse application itself. The files under
`hardware/display` provide overlays, controller initialization data and Xorg
configuration. The former performance figures are not a benchmark of this repo.

## Pick the wiring profile first

All pin numbers below are **physical 40-pin header positions**, not BCM labels,
Hobot GPIO numbers or offsets inside a GPIO controller.

### Legacy manual wiring: `wired-cs1`

This follows the old overlay sources:

- LCD clock -> 23; MOSI -> 19; CS1 -> 26.
- LCD DC -> 15; reset -> 13; backlight -> 12.
- Touch SDA -> 3; SCL -> 5; interrupt -> 7.
- Touch reset -> 28, matching `ls_gpio1_porta` offset 7 / legacy GPIO 354.
- Use a common ground. The earlier module was documented for 3.3 V; check the
  voltage rating of the actual module before wiring power.

The old guide called the touch interrupt “Physical 4 (BCM 4)” and reset
“Physical 1 (BCM 1)”. Those mix two numbering systems. Physical pin 4 is 5 V;
physical pin 1 is 3.3 V. Neither is a GPIO reset/interrupt line. The corrected
legacy mapping above follows its actual DTS and X5 GPIO definitions.

Physical pin 28 is also I2C0 SCL. If using it as legacy touch reset, disable that
pin's I2C0 mux first. Check all other pin muxes against your RDK image.

### Current screen in CAD: `waveshare-f-pogo`

The Waveshare **3.5inch RPi LCD (F)** uses ST7796S + GT911, a 5 V module supply,
and 3.3 V logic. Its plug-on connection is different from the legacy wiring:

- Module supply -> physical 4 (5 V); ground -> 6.
- Display clock -> 23; MOSI -> 19; CS0 -> 24.
- Display DC -> 15; backlight -> 12.
- Touch SDA -> 3; SCL -> 5; interrupt -> 7.

The vendor STEP contains eleven pogo contacts. V04's CAD report matches them to
3, 4, 6, 5, 7, 12, 13, 15, 19, 23 and 24. This verifies geometry, not electrical
contact or spring working stroke.

Do not assume the vendor's 13-wire cable mapping is a list of pogo contacts.
There is no separate TP_RST pogo in that STEP. The schematic shows a touch
power-on reset network and marks the LCD GPIO reset link R21 as `0R/NC`.
The candidate touch overlay therefore does not drive the legacy pin-28 reset;
the candidate LCD overlay does not assume R21 is populated.

This candidate is **not a verified plug-and-play configuration**. Confirm the
actual PCB revision, R21 state, GT911 address and reset behavior. Its GT911
node uses 0x5d; a different detected address needs a corresponding DTS change.

CS0 may already have an enabled peripheral. Inspect the live device tree and
RDK interface configuration before enabling this profile. It disables spidev@0,
but does not automatically disable every possible CS0 device. If CS0 is occupied,
use the cable interface and an explicitly remapped CS1 connection instead.

## Build the overlays and firmware

On a development machine with Python 3 and `dtc`:

```sh
# Ubuntu: sudo apt-get install device-tree-compiler
# macOS: brew install dtc
python3 hardware/display/build.py --profile wired-cs1
# Or, for the untested plug-on candidate:
python3 hardware/display/build.py --profile waveshare-f-pogo
```

Outputs are under `hardware/display/build/<profile>/`: `panel.dtbo`, `touch.dtbo`,
`st7796s.bin` and `profile.txt`. `st7796s.bin` must be installed with the name
`panel-mipi-dbi-spi.bin`, matching the overlay's compatible string. Its 109-byte
command stream is preserved from the earlier implementation (480 x 320, RGB565).
Initialization/color order may need changing for a different panel revision.

Both overlays target the legacy X5 node paths for SPI1 and I2C5. Confirm those
paths and GPIO controller symbols exist in the running image before loading them.

## Kernel support

The previous board used kernel 6.1.83. It needed `panel_mipi_dbi` and
`drm_mipi_dbi`, while the image already included the Goodix touch driver.
A newer RDK image may package these differently. Check the target first:

```sh
uname -r
modinfo panel_mipi_dbi
modinfo drm_mipi_dbi
modinfo goodix_ts
```

A built-in driver may not appear in `lsmod` or `modinfo`; check the kernel config
and boot log too. If missing, build against the **exact source, configuration and
Module.symvers of the installed RDK kernel**, through the
[RDK X5 build system](https://github.com/D-Robotics/x5-manifest). Enable
`CONFIG_DRM_PANEL_MIPI_DBI=m` and its dependencies, then use that build system's
kernel/module build procedure.

The old project has prebuilt 6.1.83 modules, but version-string equality alone is
not ABI proof. They are not copied into this repo. The old notes also describe a
10–15 ms reset pulse adjustment in `drm_mipi_dbi.c`; verify the actual source and
panel requirements rather than assuming every current X5 tree has that change.

## Install on the target

These are manual board-side commands, not commands for your Mac. Substitute the
profile directory after checking wiring, kernel support and pin muxes. Keep SSH
or serial access available while changing the display configuration.

```sh
# Run from the chosen hardware/display/build/<profile> directory on X5.
sudo install -m 644 st7796s.bin /lib/firmware/panel-mipi-dbi-spi.bin
sudo install -m 644 panel.dtbo /boot/overlays/muse-spi-panel.dtbo
sudo install -m 644 touch.dtbo /boot/overlays/muse-spi-touch.dtbo
sudo cp -an /boot/config.txt /boot/config.txt.before-muse-spi
```

Add these lines once to `/boot/config.txt`, following the overlay mechanism used
by that RDK image. Remove the old equivalent panel/touch overlay entries so the
same device is not registered twice:

```ini
dtoverlay=muse-spi-panel
dtoverlay=muse-spi-touch
```

If you built external modules, install them into the target kernel's module tree
and run `sudo depmod -a`. Do not copy arbitrary `.ko` files into a different image.
Stop/disable the old `x11-to-spi` service if it still owns the SPI display.

## Backlight and desktop

The legacy kernel's backlight GPIO is 421 (physical 12). GPIO numbering is
image-dependent. Prefer the kernel PWM/backlight interface when available;
otherwise the documented sysfs method for that legacy image is:

```sh
# On the legacy X5 image only, after checking this GPIO mapping.
test -d /sys/class/gpio/gpio421 || echo 421 | sudo tee /sys/class/gpio/export
printf 'out\n' | sudo tee /sys/class/gpio/gpio421/direction
printf '1\n' | sudo tee /sys/class/gpio/gpio421/value
```

After loading the panel, identify its DRM card; do not assume `card0`:

```sh
for card in /sys/class/drm/card[0-9]; do
    printf '%s -> ' "$card"
    readlink -f "$card/device/driver"
done
```

Copy `hardware/display/xorg/99-muse-spi-lcd.conf.in` to an Xorg configuration file
and replace `@DRM_CARD@` with the identified device, for example `/dev/dri/card0`.
The template uses `modesetting`. Review other Xorg Device sections for conflicts;
do not blindly delete the image's display configuration.

`hardware/display/xorg/90-muse-touchscreen.conf` contains the old portrait-to-
landscape calibration matrix. Use it only if the display orientation matches:
`screen_x = 1 - touch_y`, `screen_y = touch_x`, with normalized touch coordinates.
Do not apply another 90-degree swap in the kernel at the same time. Test all four
corners and the centre; change the matrix if the physical screen is rotated.

## Verify before installing Muse

Reboot the board only when ready, then inspect:

```sh
journalctl -k -b | grep -Ei 'mipi.?dbi|st7796|goodix|spi'
ls /dev/dri/ /dev/fb*
cat /sys/class/graphics/fb*/name
cat /proc/bus/input/devices
DISPLAY=:0 xrandr --query
DISPLAY=:0 xinput list
```

Check the actual Goodix device by name rather than a fixed input ID. Display a
simple desktop image and test touch at the edges. Once the 480 x 320 desktop and
touch work, follow [the Muse installation](../README.md#install). Muse itself
limits animation refresh to 8 fps; panel throughput and Muse refresh differ.

## Sources

- [Original Cathay setup, pinned revision](https://github.com/shockley6668/Cathay-Launch-UI/tree/623032d56395b018387b8f262ac0693e2ca28e2d)
- [Waveshare F manual](https://www.waveshare.com/wiki/3.5inch_RPi_LCD_%28F%29)
- [Waveshare F schematic, March 2025](https://files.waveshare.com/wiki/3.5inch%20RPi%20LCD%20(F)/3.5inch_RPi_LCD_(F).pdf)
- [X5 SPI physical pins](https://developer.d-robotics.cc/rdk_x_doc/Basic_Application/01_40pin_user_sample/spi)
- [X5 I2C physical pins](https://developer.d-robotics.cc/rdk_x_doc/Basic_Application/01_40pin_user_sample/i2c)
- [X5 GPIO numbering](https://developer.d-robotics.cc/rdk_x_doc/en/Advanced_development/linux_development/driver_development_x5/driver_gpio_dev)
