#!/usr/bin/python3
"""Start Muse after XFCE is ready, or focus the existing native window."""
import fcntl
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import time

BINARY = Path('/opt/muse-ui/build/muse_simulator')
LOG_DIR = Path.home() / '.cache/muse-ui'
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=LOG_DIR / 'launcher.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')


def run(*args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.TimeoutExpired):
        return None


def desktop_ready():
    wm = run('xprop', '-root', '_NET_SUPPORTING_WM_CHECK')
    desktop = run('xdotool', 'search', '--class', '^Xfdesktop$')
    match = re.search(r'window id # 0x([0-9a-fA-F]+)', wm.stdout) if wm else None
    if not (match and int(match[1], 16) and desktop and desktop.returncode == 0):
        return False
    for window in desktop.stdout.split():
        kind = run('xprop', '-id', window, '_NET_WM_WINDOW_TYPE')
        if kind and '_NET_WM_WINDOW_TYPE_DESKTOP' in kind.stdout:
            return True
    return False


def native_pids():
    result = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():
            continue
        try:
            executable = os.readlink(proc / 'exe').removesuffix(' (deleted)')
            if proc.stat().st_uid == os.getuid() and executable == str(BINARY):
                result.append(int(proc.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            pass
    return result


def focus(pid):
    found = run('xdotool', 'search', '--all', '--pid', str(pid), '--name', '^Muse RDK X5$')
    if not found or found.returncode:
        return False
    for window in found.stdout.split():
        active = run('xdotool', 'getactivewindow')
        if active and active.stdout.strip() == window:
            logging.info('Muse is already focused pid=%s window=%s', pid, window)
            return True
        shown = run('xdotool', 'windowmap', window, 'windowactivate', '--sync', window,
                    'windowraise', window)
        active = run('xdotool', 'getactivewindow')
        if shown and shown.returncode == 0 and active and active.stdout.strip() == window:
            logging.info('Focused existing Muse pid=%s window=%s', pid, window)
            return True
    return False


def main():
    if any(focus(pid) for pid in native_pids()):
        return 0
    deadline = time.monotonic() + 45
    while not desktop_ready():
        if time.monotonic() >= deadline:
            logging.error('XFCE desktop did not become ready')
            return 1
        time.sleep(0.25)

    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/1000'))
    fd = os.open(runtime / 'muse-ui-display.lock', os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + 8
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            pids = native_pids()
            if any(focus(pid) for pid in pids):
                return 0
            if time.monotonic() >= deadline:
                # Recover only this user's known native UI; leave the backend alone.
                logging.warning('Restarting Muse with no focusable window: %s', pids)
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                time.sleep(1)
                for pid in set(pids) & set(native_pids()):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    logging.error('Display lock is still held after UI recovery')
                    return 1
                break
            time.sleep(0.1)

    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode())
    os.set_inheritable(fd, True)
    log = os.open(LOG_DIR / 'display.log', os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    os.dup2(log, 1)
    os.dup2(log, 2)
    os.close(log)
    logging.info('Starting native Muse pid=%s', os.getpid())
    os.execv(BINARY, [str(BINARY)])


if __name__ == '__main__':
    raise SystemExit(main())
