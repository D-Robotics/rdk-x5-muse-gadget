#!/bin/sh
set -eu
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/sunrise/.Xauthority}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
exec /usr/bin/python3 /opt/muse-ui/launch-display.py
