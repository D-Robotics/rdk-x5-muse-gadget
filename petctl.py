#!/usr/bin/env python3
"""Control the local RDK X5 desktop pet through the Muse UI backend."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
from typing import Sequence


def runtime_dir() -> Path:
    return Path(os.environ.get("MUSE_UI_RUNTIME", "/run/muse-ui"))


def read_state(path: Path | None = None) -> dict[str, str]:
    values: dict[str, str] = {}
    source = path or runtime_dir() / "state"
    for line in source.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


def pet_status(path: Path | None = None) -> dict[str, str]:
    return {key.removeprefix("pet_"): value
            for key, value in read_state(path).items() if key.startswith("pet_") or key == "vision"}


def send_command(command: dict, path: Path | None = None) -> None:
    target = path or runtime_dir() / "input.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.sendto(json.dumps(command, separators=(",", ":")).encode("utf-8"), str(target))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="petctl", description="Control the Muse desktop pet")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("wake", "sleep", "pet", "status"):
        commands.add_parser(name)

    move = commands.add_parser("move")
    move.add_argument("direction", choices=("left", "right", "stop"))

    feed = commands.add_parser("feed")
    feed.add_argument("food", nargs="?", default="banana")

    timer = commands.add_parser("timer")
    timer_commands = timer.add_subparsers(dest="operation", required=True)
    start = timer_commands.add_parser("start")
    start.add_argument("minutes", nargs="?", type=float, default=25)
    timer_commands.add_parser("cancel")
    timer_commands.add_parser("stop")
    timer_commands.add_parser("status")

    find = commands.add_parser("find")
    find.add_argument("target", nargs="?", default="banana")
    return result


def command_from_args(args: argparse.Namespace) -> dict:
    command = {"action": "pet_command", "command": args.command}
    if args.command == "move":
        command["direction"] = args.direction
    elif args.command == "feed":
        command["food"] = args.food
    elif args.command == "timer":
        command["operation"] = args.operation
        if args.operation == "start":
            command["minutes"] = args.minutes
    elif args.command == "find":
        command["target"] = args.target
    return command


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "status" or (args.command == "timer" and args.operation == "status"):
        try:
            status = pet_status()
        except OSError as exc:
            parser().error(f"cannot read pet state: {exc}")
        if not status:
            parser().error("backend state has no pet fields")
        print(json.dumps(status, ensure_ascii=False, sort_keys=True))
        return 0
    try:
        send_command(command_from_args(args))
    except OSError as exc:
        parser().error(f"cannot reach Muse UI backend: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
