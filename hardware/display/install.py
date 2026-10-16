#!/usr/bin/env python3
"""Install the legacy CS1 display stack on RDK X5 kernel 6.1.83."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import urllib.request

HERE = Path(__file__).resolve().parent
STATE = Path('/var/lib/muse-display')
OLD_OVERLAYS = {'overlay-st7796s', 'overlay-gt911', 'muse-spi-panel', 'muse-spi-touch'}


def boot_config(text):
    lines = []
    for line in text.splitlines():
        match = re.match(r'^\s*dtoverlay\s*=\s*([^,\s#]+)', line)
        if match and match[1].removesuffix('.dtbo') in OLD_OVERLAYS:
            continue
        lines.append(line)
    return '\n'.join(lines).rstrip() + '\n\ndtoverlay=muse-spi-panel\ndtoverlay=muse-spi-touch\n'


def validate_module(data, entry, manifest):
    if hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError(f"Hash mismatch: {entry['name']}")
    if data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError(f"Not an ARM64 module: {entry['name']}")
    wanted = b'vermagic=' + manifest['vermagic'].encode() + b'\x00'
    if wanted not in data:
        raise ValueError(f"Unexpected module ABI: {entry['name']}")


def save_file(target, data, state=None, mode=0o644):
    """Preserve the original once, including the fact a file did not exist."""
    state = STATE if state is None else state
    index_path = state / 'files.json'
    records = json.loads(index_path.read_text()) if index_path.exists() else {}
    key = str(target)
    state.mkdir(parents=True, exist_ok=True)
    if key not in records:
        existed = target.exists()
        backup = state / 'original' / target.relative_to('/')
        if existed:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        records[key] = {'existed': existed, 'backup': str(backup)}
        index_path.write_text(json.dumps(records, indent=2) + '\n')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    target.chmod(mode)


def restore(state=None):
    state = STATE if state is None else state
    index = state / 'files.json'
    if not index.exists():
        raise ValueError('No saved display installation to restore.')
    for name, record in json.loads(index.read_text()).items():
        target = Path(name)
        if record['existed']:
            shutil.copy2(record['backup'], target)
        else:
            target.unlink(missing_ok=True)
    subprocess.run(['depmod', '-a'], check=True)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    services = state / 'services.json'
    if services.exists():
        for name, enabled in json.loads(services.read_text()).items():
            subprocess.run(['systemctl', 'enable' if enabled else 'disable', name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print('Previous files restored. Reboot when ready.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['wired-cs1'], default='wired-cs1')
    parser.add_argument('--drm-card', default='/dev/dri/card0')
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    if platform.system() != 'Linux' or os.geteuid() != 0:
        parser.error('Run this on the X5 with sudo, not on your development computer.')
    manifest = json.loads((HERE / 'drivers.json').read_text())
    if platform.machine() != manifest['machine'] or platform.release() != manifest['kernel']:
        parser.error('This driver bundle requires ARM64 kernel 6.1.83. Nothing was changed.')
    if args.restore:
        restore()
        return
    if not re.fullmatch(r'/dev/dri/card[0-9]+', args.drm_card):
        parser.error('--drm-card must be a DRM card path such as /dev/dri/card0')
    tree = Path('/sys/firmware/devicetree/base')
    model = (tree / 'model').read_text(errors='replace') if (tree / 'model').exists() else ''
    if 'x5' not in model.lower():
        parser.error('This installer is for an RDK X5 device tree.')
    for node in ['soc/a55_apb0/spi@34010000', 'soc/a55_apb0/i2c@341c0000',
                 '__symbols__/ls_gpio0_porta', '__symbols__/ls_gpio1_porta',
                 '__symbols__/dsp_gpio_porta', '__symbols__/i2c0']:
        if not (tree / node).exists():
            parser.error(f'Missing X5 device-tree node/symbol: {node}. Nothing was changed.')
    config_path = Path('/boot/config.txt')
    if not config_path.is_file() or not Path('/boot/overlays').is_dir():
        parser.error('Expected /boot/config.txt and /boot/overlays. Nothing was changed.')
    for command in ['systemctl', 'depmod']:
        if not shutil.which(command):
            parser.error(f'{command} is required. Nothing was changed.')
    if not Path('/usr/lib/xorg/modules/drivers/modesetting_drv.so').exists():
        parser.error('Install xserver-xorg-core first. Nothing was changed.')
    if not Path('/usr/lib/xorg/modules/input/libinput_drv.so').exists():
        parser.error('Install xserver-xorg-input-libinput first. Nothing was changed.')
    # Complete downloads and integrity checks before changing any target files.
    prebuilt = HERE / 'prebuilt' / args.profile
    assets = {}
    for name, digest in json.loads((prebuilt / 'sha256.json').read_text()).items():
        data = (prebuilt / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f'Prebuilt asset hash mismatch: {name}')
        assets[name] = data
    modules = {}
    for entry in manifest['modules']:
        print(f"Downloading {entry['name']} (6.1.83)", flush=True)
        with urllib.request.urlopen(entry['url'], timeout=60) as response:
            data = response.read()
        validate_module(data, entry, manifest)
        modules[entry['name']] = data
    STATE.mkdir(parents=True, exist_ok=True)
    service_state = STATE / 'services.json'
    if not service_state.exists():
        values = {}
        for name in ['st7796s-backlight.service', 'x11-to-spi.service']:
            result = subprocess.run(['systemctl', 'is-enabled', name], capture_output=True, text=True)
            values[name] = result.stdout.strip() in ['enabled', 'enabled-runtime']
        service_state.write_text(json.dumps(values, indent=2) + '\n')
    for name, data in modules.items():
        save_file(Path('/lib/modules') / manifest['kernel'] / 'extra' / name, data)
    save_file(Path('/lib/firmware/panel-mipi-dbi-spi.bin'), assets['st7796s.bin'])
    save_file(Path('/boot/overlays/muse-spi-panel.dtbo'), assets['panel.dtbo'])
    save_file(Path('/boot/overlays/muse-spi-touch.dtbo'), assets['touch.dtbo'])
    save_file(config_path, boot_config(config_path.read_text()).encode())
    xorg = Path('/etc/X11/xorg.conf.d')
    display = (HERE / 'xorg/99-muse-spi-lcd.conf.in').read_text().replace('@DRM_CARD@', args.drm_card)
    save_file(xorg / '99-muse-spi-lcd.conf', display.encode())
    save_file(xorg / '90-muse-touchscreen.conf', (HERE / 'xorg/90-muse-touchscreen.conf').read_bytes())
    # These known legacy Device sections compete with the selected SPI device.
    for name in ['1-resolution.conf', '2-dr-accel.conf', '99-spi-lcd.conf', '90-touchscreen.conf']:
        path = xorg / name
        if path.exists():
            save_file(path, path.read_bytes())
            path.unlink()
    save_file(Path('/usr/local/lib/muse-display/backlight.sh'), (HERE / 'backlight.sh').read_bytes(), mode=0o755)
    save_file(Path('/etc/systemd/system/st7796s-backlight.service'), (HERE / 'st7796s-backlight.service').read_bytes())
    subprocess.run(['depmod', '-a'], check=True)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', 'st7796s-backlight.service'], check=True)
    subprocess.run(['systemctl', 'disable', '--now', 'x11-to-spi.service'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print('Installed CS1 display drivers, firmware, overlays, backlight and Xorg configuration.')
    print('Touch reset reserves physical pin 28; this profile disables I2C0.')
    print('Original files: /var/lib/muse-display. Reboot with: sudo reboot')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f'Display setup failed: {exc}')
