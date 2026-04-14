"""Discover bundled preset YAML configs and load metadata from user configs."""
from __future__ import annotations

from importlib import resources
from pathlib import Path

from py6502.sim.system import from_yaml_file as _load_config


def discover_presets() -> list[dict]:
    """Scan ``py6502.sim.assets.presets/`` for YAML files and return metadata."""
    presets_dir = resources.files("py6502.sim.assets").joinpath("presets")
    results: list[dict] = []
    for entry in presets_dir.iterdir():
        if not entry.name.endswith(".yaml"):
            continue
        meta = _load_metadata(entry)
        if meta is not None:
            meta["is_preset"] = True
            results.append(meta)
    return results


def load_user_config_metadata(path: str) -> dict | None:
    """Load a single YAML and return its metadata. Returns None if invalid."""
    meta = _load_metadata(Path(path))
    if meta is not None:
        meta["is_preset"] = False
    return meta


def _load_metadata(path: object) -> dict | None:
    """Extract metadata from a YAML config file."""
    try:
        config = _load_config(path)
        return {
            "id": config.id,
            "name": config.name,
            "description": config.description or "",
            "path": str(path),
            "tags": config.tags,
            "author": config.author or "",
        }
    except Exception:
        return None
