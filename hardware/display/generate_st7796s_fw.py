#!/usr/bin/env python3
"""Generate st7796s.bin firmware for panel-mipi-dbi-spi driver.

Firmware format:
  15 bytes: magic "MIPI DBI\0\0\0\0\0\0\0"
   1 byte:  file_format_version (0x01)
   N bytes: commands[]
     Each command: [cmd, num_params, param1, param2, ...]
     Delay:        [0x00, 0x01, delay_ms]  (NOP with 1 param = sleep)

From x11-to-spi.c lcd_init() sequence.
"""

import struct

# ST7796S initialization commands from x11-to-spi.c
commands = [
    # Reset is handled by GPIO in the driver, not via firmware
    (0x11, []),                         # Sleep Out
    (0x00, [120]),                      # delay 120ms
    (0x36, [0xE8]),                     # MADCTL: Landscape (MY=1,MX=1,MV=1), BGR
    (0x3A, [0x05]),                     # Pixel Format: 16bpp RGB565
    (0xF0, [0xC3]),                     # Command Set Control (enable extended cmds)
    (0xF0, [0x96]),
    (0xB4, [0x01]),                     # Display Inversion Control: 1-dot
    (0xB7, [0xC6]),                     # Entry Mode Set
    (0xC0, [0x80, 0x45]),              # Power Control 1
    (0xC1, [0x13]),                     # Power Control 2
    (0xC2, [0xA7]),                     # Power Control 3
    (0xC5, [0x0A]),                     # VCOM Control
    (0xE8, [0x40, 0x8A, 0x00, 0x00,   # Display Output Timing Control
            0x29, 0x19, 0xA5, 0x33]),
    (0xE0, [0xD0, 0x08, 0x0F, 0x06,   # Positive Gamma Correction
            0x06, 0x33, 0x30, 0x33,
            0x47, 0x17, 0x13, 0x13,
            0x2B, 0x31]),
    (0xE1, [0xD0, 0x0A, 0x11, 0x0B,   # Negative Gamma Correction
            0x09, 0x07, 0x2F, 0x33,
            0x47, 0x38, 0x15, 0x16,
            0x2C, 0x32]),
    (0xF0, [0x3C]),                     # Command Set Control (disable extended)
    (0xF0, [0x69]),
    (0x21, []),                         # Display Inversion On
    (0x11, []),                         # Sleep Out (again, per datasheet)
    (0x00, [100]),                      # delay 100ms
    (0x29, []),                         # Display On
]

# Build firmware binary
magic = b'MIPI DBI' + b'\x00' * 7  # 15 bytes
version = b'\x01'                    # 1 byte

cmd_bytes = b''
for cmd, params in commands:
    cmd_bytes += struct.pack('BB', cmd, len(params))
    cmd_bytes += bytes(params)

firmware = magic + version + cmd_bytes

output_path = 'st7796s.bin'
with open(output_path, 'wb') as f:
    f.write(firmware)

print(f"Generated {output_path} ({len(firmware)} bytes)")
print(f"Commands: {len(commands)}")
