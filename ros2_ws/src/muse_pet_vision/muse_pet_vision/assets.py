"""Resolve installed TROS assets without depending on the launch directory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def require_file(value: str | Path, description: str) -> str:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{description} not found: {path}")
    return str(path)


def prepare_yolo_config(source: Path, package_root: Path, cache: Path) -> str:
    """Resolve model and label paths in a runtime copy, preserving vendor files."""
    source = Path(require_file(source, "YOLO workconfig"))
    config = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not config.get("model_file"):
        raise ValueError(f"YOLO workconfig needs model_file: {source}")
    for key in ("model_file", "cls_names_list"):
        value = config.get(key)
        if not value:
            continue
        path = Path(value).expanduser()
        candidates = ([path] if path.is_absolute() else
                      [source.parent / path, package_root / path])
        found = next((candidate for candidate in candidates if candidate.is_file()), None)
        if found is None:
            raise FileNotFoundError(f"YOLO {key} not found: {value} (config: {source})")
        config[key] = str(found.resolve())
    encoded = json.dumps(config, indent=2) + "\n"
    name = hashlib.sha256(encoded.encode()).hexdigest()[:16]
    cache.mkdir(parents=True, exist_ok=True)
    output = cache / f"yolo-{name}.json"
    output.write_text(encoded, encoding="utf-8")
    return str(output)
