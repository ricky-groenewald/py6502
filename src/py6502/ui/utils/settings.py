"""Settings persistence — loads and saves app preferences as JSON."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from py6502.ui.utils import paths


@dataclass
class AppSettings:
    startup_with_last_system: bool = False
    last_system_id: str | None = None
    last_system_path: str | None = None
    user_config_paths: list[str] = field(default_factory=list)
    halt_on_invalid_opcode: bool = True
    halt_on_unmapped_memory: bool = False


def load_settings(path: Path | None = None) -> AppSettings:
    """Read settings from *path* (defaults to the user data dir). Returns defaults on missing/corrupt file."""
    path = path or paths.settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppSettings(
            startup_with_last_system=data.get("startup_with_last_system", False),
            last_system_id=data.get("last_system_id"),
            last_system_path=data.get("last_system_path"),
            user_config_paths=data.get("user_config_paths", []),
            halt_on_invalid_opcode=data.get("halt_on_invalid_opcode", True),
            halt_on_unmapped_memory=data.get("halt_on_unmapped_memory", False),
        )
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    """Write settings to *path* (defaults to the user data dir) as pretty-printed JSON."""
    path = path or paths.settings_path()
    path.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
