"""
Tests for ``py6502.sim.manifest`` — the bundled-asset manifest loader.

Covers the Python-side contract: ``list_binaries()`` returns a tuple of
``BinaryAsset`` records sourced from ``assets/manifest.yaml``, and
``BinaryAsset.data()`` reads bytes back via ``importlib.resources``
against the same ``resource:`` URI shape the YAML loader uses.
"""
from __future__ import annotations

from py6502.sim.manifest import BinaryAsset, list_binaries


def test_list_binaries_exposes_wozmon() -> None:
    assets = list_binaries()
    assert isinstance(assets, tuple)
    names = {a.name for a in assets}
    assert "apple1-wozmon" in names

    wozmon = next(a for a in assets if a.name == "apple1-wozmon")
    assert wozmon.default_address == 0xFF00
    assert wozmon.source == "resource:py6502.sim.assets.bios/apple1-wozmon.bin"
    assert wozmon.size_bytes == 256
    assert "apple1" in wozmon.tags


def test_binary_asset_data_returns_rom_bytes() -> None:
    wozmon = next(a for a in list_binaries() if a.name == "apple1-wozmon")
    data = wozmon.data()
    assert isinstance(data, bytes)
    assert len(data) == 256  # wozmon ROM is exactly one page


def test_list_binaries_is_cached() -> None:
    """Repeated calls return the same tuple object — the manifest is read once."""
    assert list_binaries() is list_binaries()


def test_binary_asset_data_rejects_non_resource_uri() -> None:
    asset = BinaryAsset(
        name="x",
        description="",
        source="file:/tmp/does-not-exist.bin",
        default_address=0,
    )
    try:
        asset.data()
    except ValueError as exc:
        assert "resource:" in str(exc)
    else:  # pragma: no cover — the call above is expected to raise
        raise AssertionError("expected ValueError for non-resource URI")
