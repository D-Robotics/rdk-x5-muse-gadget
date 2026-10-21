#!/usr/bin/env python3
"""Write a coherent transport profile and service identities; never start services."""
import argparse
import os
from pathlib import Path
import re
import shutil


def configure(root: Path, mode: str):
    if mode not in ("udp", "shm"):
        raise ValueError("mode must be udp or shm")
    common = root / "etc/default/muse-pet-transport"
    template = Path(__file__).resolve().parents[1] / "muse-pet-transport.env"
    source = common.read_text() if common.exists() else template.read_text()
    selection = f"MUSE_PET_TRANSPORT={mode}"
    if re.search(r"^MUSE_PET_TRANSPORT=.*$", source, flags=re.M):
        source = re.sub(r"^MUSE_PET_TRANSPORT=.*$", selection, source, flags=re.M)
    else:
        source = selection + "\n" + source
    files = {common: source}
    for service in ("camera", "vision", "preview"):
        # The camera currently needs root. Keep image consumers on the same UID
        # for shared buffers, while the desktop UI stays with sunrise.
        user = "root" if mode == "shm" or service == "camera" else "sunrise"
        home = "/root" if user == "root" else "/home/sunrise"
        target = root / f"etc/systemd/system/muse-pet-{service}.service.d/20-muse-transport.conf"
        files[target] = ("[Service]\nEnvironmentFile=-/etc/default/muse-pet-transport\n"
                         f"User={user}\nGroup={user}\nEnvironment=HOME={home}\n")
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text() == content:
            continue
        backup = path.with_name(path.name + ".before-muse-transport")
        if path.exists() and not backup.exists():
            shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(content)
        temporary.chmod(0o644)
        os.replace(temporary, path)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("udp", "shm"), required=True)
    parser.add_argument("--root", type=Path, default=Path("/"),
                        help="Filesystem root; use a temporary folder to inspect generated files")
    args = parser.parse_args()
    configure(args.root, args.mode)
    print(f"Saved {args.mode} profile. No services were started or restarted.")


if __name__ == "__main__":
    main()
