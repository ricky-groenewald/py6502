"""Tests for per-user path resolution."""
from pathlib import Path

from py6502.ui.utils import paths


def test_user_data_dir_returns_existing_path():
    p = paths.user_data_dir()
    assert isinstance(p, Path)
    assert p.exists()
    assert p.is_dir()
    assert "py6502" in p.parts


def test_settings_path_lives_under_user_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    assert paths.settings_path() == tmp_path / "py6502_settings.json"


def test_dpg_init_path_uses_renamed_filename(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    assert paths.dpg_init_path() == tmp_path / "py6502.ini"


def test_user_configs_dir_is_created(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    target = paths.user_configs_dir()
    assert target == tmp_path / "configs"
    assert target.exists()
    assert target.is_dir()
