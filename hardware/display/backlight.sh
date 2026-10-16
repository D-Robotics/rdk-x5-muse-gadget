#!/bin/sh
set -eu
# RDK X5 6.1.83: physical pin 12, legacy GPIO 421.
gpio=/sys/class/gpio/gpio421
if [ "$1" = on ]; then
    if [ ! -d "$gpio" ]; then echo 421 > /sys/class/gpio/export; fi
    echo out > "$gpio/direction"
    echo 1 > "$gpio/value"
elif [ -d "$gpio" ]; then
    echo 0 > "$gpio/value"
fi
