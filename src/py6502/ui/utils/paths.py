"""OS-standard per-user paths for py6502 state (settings, DPG layout, saved configs)."""
from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_path


def user_data_dir() -> Path:
    """Per-user data directory. Created on first access.

    macOS:   ~/Library/Application Support/py6502/
    Linux:   $XDG_DATA_HOME/py6502 (fallback ~/.local/share/py6502)
    Windows: %LOCALAPPDATA%\\py6502
    """
    return user_data_path("py6502", appauthor=False, ensure_exists=True)


def settings_path() -> Path:
    return user_data_dir() / "py6502_settings.json"


def dpg_init_path() -> Path:
    return user_data_dir() / "py6502.ini"


def user_configs_dir() -> Path:
    """Default directory for user-saved system configs. Created on first access."""
    path = user_data_dir() / "configs"
    path.mkdir(exist_ok=True)
    return path
