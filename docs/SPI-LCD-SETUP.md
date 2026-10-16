# SPI screen quick start

Bring up a 480 x 320 ST7796S display and GT911 touch on **RDK X5, Ubuntu 22.04 desktop image (XFCE),
ARM64 kernel 6.1.83**. Run `uname -r` to check the kernel first.

The installer uses the prebuilt drivers from the earlier
[Cathay setup](https://github.com/shockley6668/Cathay-Launch-UI/tree/623032d56395b018387b8f262ac0693e2ca28e2d).
It downloads and verifies both kernel modules, and installs the included overlays,
firmware, backlight service and Xorg settings. **No driver compilation is needed.**

## 1. Connect the screen

Use the **13-pin cable interface**, with LCD chip select wired to **CS1 / physical
pin 26**. All X5 numbers below are physical header positions, not BCM numbers.
Power off the board while wiring.

For the Waveshare **3.5inch RPi LCD (F)**:

```text
Screen cable pin / signal       X5 physical pin
13  VCC                         4   (5 V module supply)
12  GND                         6
11  MISO                        21  (optional; display is write-only)
10  MOSI                        19
 9  SCLK                        23
 8  LCD_CS                      26  (CS1)
 7  LCD_DC                      15
 6  LCD_RST                     13
 5  LCD_BL                      12
 4  TP_SDA                       3
 3  TP_SCL                       5
 2  TP_INT                       7
 1  TP_RST                      28
```

This Waveshare module takes 5 V power and uses 3.3 V logic. Other ST7796S modules
may have different power requirements. Pin 28 is reserved for touch reset here;
the installer disables I2C0 to release that pin.

The screen's **pogo connection uses CS0 / physical pin 24** instead. That profile
has not been tested on hardware and is not offered by the quick installer.

## 2. Install

Run on the X5 with internet access:

```sh
sudo apt-get update
sudo apt-get install -y git python3 ca-certificates kmod \
    xserver-xorg-core xserver-xorg-input-libinput

git clone https://github.com/D-Robotics/rdk-x5-muse-gadget.git
cd rdk-x5-muse-gadget
sudo python3 hardware/display/install.py
sudo reboot
```

If already cloned, use `git pull --ff-only` instead of cloning again.

The installer checks the X5 device tree and kernel version before writing files.
It keeps originals in `/var/lib/muse-display`, replaces old equivalent display
settings, and disables the old `x11-to-spi` service. It does not reboot itself.

## 3. Check the result

After reboot, the XFCE desktop should appear on the screen. Check the four touch
corners and the centre. These commands help verify the driver and backlight:

```sh
cat /sys/class/graphics/fb*/name
systemctl status st7796s-backlight --no-pager
grep -A5 -i goodix /proc/bus/input/devices
```

Look for the MIPI DBI framebuffer, an active backlight service and a Goodix input
device. Once display and touch work, [install Muse](../README.md#quick-start).

## If it does not work

- **Wrong kernel:** the installer stops. This bundle is only for 6.1.83; do not
  force-load it on another kernel.
- **Blank screen:** confirm CS is pin 26, then inspect
  `journalctl -k -b | grep -Ei 'mipi|goodix|spi|vermagic'`.
- **Different DRM card:** the legacy setup uses `/dev/dri/card0`. Identify the SPI
  card under `/sys/class/drm/`, then rerun with
  `sudo python3 hardware/display/install.py --drm-card /dev/dri/card1` if needed.
- **Revert:** run `sudo python3 hardware/display/install.py --restore`, then reboot.

The installer and bundled files are checked locally. This update has not been
run on an X5, so it is not a new hardware validation of the screen or pogo layout.

[Screen pinout](https://www.waveshare.com/wiki/3.5inch_RPi_LCD_%28F%29) ·
[Overlay and firmware sources](../hardware/display/README.md)
