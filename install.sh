#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo bash install.sh'; exit 1; }
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
target_dir=/opt/muse-ui
[[ -r /var/lib/musegadget/pairing.json ]] || { echo 'Pair the Linux Muse SDK first.'; exit 1; }
id sunrise >/dev/null
export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends libsdl2-dev ninja-build build-essential pkg-config cmake python3-venv python3-cryptography ffmpeg pulseaudio-utils xdotool x11-utils
mkdir -p "$target_dir"
if [[ "$source_dir" != "$target_dir" ]]; then
    tar -C "$source_dir" --exclude="./.git" --exclude="./build" --exclude="./venv" --exclude="./.venv" --exclude="./cad" --exclude="./.vscode" --exclude="__pycache__" -cf - . | tar -C "$target_dir" -xf -
fi
python3 -m venv --system-site-packages "$target_dir/venv"
"$target_dir/venv/bin/python" -m pip install 'websockets==16.0' 'edge-tts==7.2.8'
cmake -S "$target_dir/simulator" -B "$target_dir/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
cmake --build "$target_dir/build" --parallel 4
cd "$target_dir"
PYTHONPATH="$target_dir/sdk" "$target_dir/venv/bin/python" -m unittest test_backend -v
chmod 755 start-display.sh launch-display.py send.py
install -d -o sunrise -g sunrise /home/sunrise/.local/share/applications /home/sunrise/.config/autostart
install -m 644 -o sunrise -g sunrise muse-ui.desktop /home/sunrise/.local/share/applications/muse-ui.desktop
install -m 644 -o sunrise -g sunrise muse-ui-autostart.desktop /home/sunrise/.config/autostart/muse-ui.desktop
if [[ -d /home/sunrise/Desktop ]]; then
    install -m 755 -o sunrise -g sunrise muse-ui.desktop /home/sunrise/Desktop/Muse.desktop
fi
install -m 644 muse-ui.service muse-ui-display.service /etc/systemd/system/
install -d -m 700 -o sunrise -g sunrise /home/sunrise/.config/pulse
if [[ -f /home/sunrise/.config/pulse/default.pa ]] && ! grep -q 'sink_name=muse_output' /home/sunrise/.config/pulse/default.pa; then
    cp -an /home/sunrise/.config/pulse/default.pa /home/sunrise/.config/pulse/default.pa.before-muse
    sed 's|.include /etc/pulse/default.pa|.include /home/sunrise/.config/pulse/default.pa.before-muse|' pulse-default.pa > /home/sunrise/.config/pulse/default.pa
    chown sunrise:sunrise /home/sunrise/.config/pulse/default.pa
elif [[ ! -f /home/sunrise/.config/pulse/default.pa ]]; then
    install -m 644 -o sunrise -g sunrise pulse-default.pa /home/sunrise/.config/pulse/default.pa
fi
systemctl --user --machine=sunrise@.host restart pulseaudio.service
systemctl daemon-reload
systemctl enable muse-ui.service
systemctl disable --now muse-ui-display.service
systemctl restart muse-ui.service
runuser -u sunrise -- env DISPLAY=:0 XAUTHORITY=/home/sunrise/.Xauthority XDG_RUNTIME_DIR=/run/user/1000 sh -c 'nohup /opt/muse-ui/start-display.sh >/dev/null 2>&1 </dev/null &'
systemctl is-active muse-ui.service
