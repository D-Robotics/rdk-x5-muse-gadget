"""Exercise the installer against an isolated target tree, never the host system."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

DISPLAY = Path(__file__).resolve().parents[1] / 'hardware/display'
spec = importlib.util.spec_from_file_location('display_install', DISPLAY / 'install.py')
installer = importlib.util.module_from_spec(spec)
sys.modules['display_install'] = installer
spec.loader.exec_module(installer)
REAL_PATH = Path


def module_bytes():
    value = bytearray(64)
    value[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', value, 18, 183)
    return bytes(value) + b'vermagic=6.1.83 SMP preempt mod_unload aarch64\x00'


class DisplayInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = REAL_PATH(self.temp.name)
        self.target = self.base / 'target'
        self.source = self.base / 'source'
        shutil.copytree(DISPLAY, self.source, ignore=shutil.ignore_patterns('build', '__pycache__'))
        self.payload = module_bytes()
        manifest = json.loads((self.source / 'drivers.json').read_text())
        for entry in manifest['modules']:
            entry['sha256'] = hashlib.sha256(self.payload).hexdigest()
        (self.source / 'drivers.json').write_text(json.dumps(manifest))
        self.original = 'dtparam=spi=on\ndtoverlay=overlay-st7796s\n# keep me\n'
        self.write('/boot/config.txt', self.original)
        (self.target / 'boot/overlays').mkdir()
        self.write('/sys/firmware/devicetree/base/model', 'D-Robotics RDK X5\x00')
        tree = self.target / 'sys/firmware/devicetree/base'
        for name in ['soc/a55_apb0/spi@34010000', 'soc/a55_apb0/i2c@341c0000']:
            (tree / name).mkdir(parents=True)
        for name in ['ls_gpio0_porta', 'ls_gpio1_porta', 'dsp_gpio_porta', 'i2c0']:
            self.write('/sys/firmware/devicetree/base/__symbols__/' + name, 'fixture')
        for name in ['/usr/lib/xorg/modules/drivers/modesetting_drv.so',
                     '/usr/lib/xorg/modules/input/libinput_drv.so']:
            self.write(name, '')
        self.write('/etc/X11/xorg.conf.d/1-resolution.conf', 'old config')
        self.calls = []

    def write(self, path, text):
        dest = self.target / path.lstrip('/')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)

    def mapped_path(self, value):
        path = REAL_PATH(value)
        if path.is_absolute() and not path.is_relative_to(self.base):
            return self.target / str(path).lstrip('/')
        return path

    def command(self, args, **kwargs):
        self.calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout='disabled\n', stderr='')

    def run_installer(self, argv=(), kernel='6.1.83'):
        with contextlib.ExitStack() as stack:
            for target, value in [
                ('HERE', self.source), ('STATE', self.target / 'var/lib/muse-display'),
                ('Path', self.mapped_path), ('os.geteuid', lambda: 0),
                ('platform.system', lambda: 'Linux'), ('platform.machine', lambda: 'aarch64'),
                ('platform.release', lambda: kernel), ('shutil.which', lambda name: '/usr/bin/' + name),
                ('subprocess.run', self.command),
                ('urllib.request.urlopen', lambda *a, **kw: io.BytesIO(self.payload)),
            ]:
                stack.enter_context(patch.object(installer, target, value) if '.' not in target
                                    else patch('display_install.' + target, value))
            stack.enter_context(patch.object(sys, 'argv', ['install.py', *argv]))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            installer.main()

    def test_install_repeat_and_restore(self):
        self.run_installer()
        config = self.target / 'boot/config.txt'
        installed = config.read_text()
        self.assertIn('# keep me', installed)
        self.assertNotIn('dtoverlay=overlay-st7796s', installed)
        self.assertEqual(installed.count('dtoverlay=muse-spi-panel'), 1)
        self.assertEqual(installed.count('dtoverlay=muse-spi-touch'), 1)
        self.assertFalse((self.target / 'etc/X11/xorg.conf.d/1-resolution.conf').exists())
        self.assertEqual((self.target / 'lib/firmware/panel-mipi-dbi-spi.bin').stat().st_size, 109)
        self.run_installer()
        self.assertEqual(config.read_text(), installed)
        self.run_installer(['--restore'])
        self.assertEqual(config.read_text(), self.original)
        self.assertEqual((self.target / 'etc/X11/xorg.conf.d/1-resolution.conf').read_text(), 'old config')
        self.assertFalse((self.target / 'boot/overlays/muse-spi-panel.dtbo').exists())

    def test_wrong_kernel_changes_nothing(self):
        with self.assertRaises(SystemExit):
            self.run_installer(kernel='6.6.0')
        self.assertEqual((self.target / 'boot/config.txt').read_text(), self.original)
        self.assertFalse((self.target / 'var/lib/muse-display').exists())
        self.assertEqual(self.calls, [])

    def test_corrupted_download_changes_nothing(self):
        self.payload += b'corruption'
        with self.assertRaises(ValueError):
            self.run_installer()
        self.assertEqual((self.target / 'boot/config.txt').read_text(), self.original)
        self.assertFalse((self.target / 'var/lib/muse-display').exists())

    def test_incomplete_existing_overlay_pair_is_repaired(self):
        text = 'dtoverlay=muse-spi-panel\n'
        result = installer.boot_config(text)
        self.assertEqual(result.count('dtoverlay=muse-spi-panel'), 1)
        self.assertEqual(result.count('dtoverlay=muse-spi-touch'), 1)
        self.assertEqual(installer.boot_config(result), result)


if __name__ == '__main__':
    unittest.main()
