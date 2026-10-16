#!/usr/bin/env python3
"""Build the selected display overlays and known ST7796S init firmware."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, choices=['wired-cs1', 'waveshare-f-pogo'])
    parser.add_argument('--output', type=Path, default=ROOT / 'build')
    args = parser.parse_args()
    if not shutil.which('dtc'):
        parser.error('dtc is required: sudo apt-get install device-tree-compiler')
    output = args.output.resolve() / args.profile
    output.mkdir(parents=True, exist_ok=True)
    for name in ['panel', 'touch']:
        subprocess.run(['dtc', '-@', '-I', 'dts', '-O', 'dtb',
                        '-o', str(output / (name + '.dtbo')),
                        str(ROOT / 'profiles' / args.profile / (name + '.dts'))], check=True)
    subprocess.run([sys.executable, str(ROOT / 'generate_st7796s_fw.py')], cwd=output, check=True)
    (output / 'profile.txt').write_text(args.profile + '\n')
    print(output)

if __name__ == '__main__':
    main()
