"""
Bundled-asset manifest.

``list_binaries()`` returns the binaries shipped under
``py6502.sim.assets/`` according to ``assets/manifest.yaml``. The UI
uses it to populate the "Bundled" side of the binary-source picker;
tests use it as a stable reference to the wozmon ROM without
hard-coding filesystem paths.

The manifest is loaded exactly once on first access.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from importlib import resources

import yaml


SUPPORTED_MANIFEST_VERSIONS = (1,)


@dataclass(frozen=True)
class BinaryAsset:
    name: str
    description: str
    source: str
    default_address: int
    tags: tuple[str, ...] = ()
    size_bytes: int = 0

    def data(self) -> bytes:
        """Return the asset's raw bytes. Only ``resource:`` URIs are supported."""
        if not self.source.startswith("resource:"):
            raise ValueError(
                f"BinaryAsset.data only handles resource: URIs, got {self.source!r}"
            )
        body = self.source[len("resource:") :]
        package, _, filename = body.partition("/")
        if not filename:
            raise ValueError(
                f"malformed resource URI {self.source!r} "
                f"— expected 'resource:<package>/<filename>'"
            )
        return resources.files(package).joinpath(filename).read_bytes()


@lru_cache(maxsize=1)
def list_binaries() -> tuple[BinaryAsset, ...]:
    """Return the bundled binaries described by the asset manifest."""
    text = (
        resources.files("py6502.sim.assets").joinpath("manifest.yaml").read_text()
    )
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("manifest.yaml top-level must be a mapping")

    version = raw.get("version")
    if version not in SUPPORTED_MANIFEST_VERSIONS:
        supported = ", ".join(str(v) for v in SUPPORTED_MANIFEST_VERSIONS)
        raise ValueError(
            f"unsupported manifest version {version!r}; supported: {supported}"
        )

    entries = raw.get("binaries")
    if not isinstance(entries, list):
        raise ValueError("manifest.yaml 'binaries' must be a list")

    out: list[BinaryAsset] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"manifest binaries[{i}] must be a mapping")
        source = str(entry["source"])
        asset = BinaryAsset(
            name=str(entry["name"]),
            description=str(entry["description"]),
            source=source,
            default_address=int(entry["default_address"]),
            tags=tuple(entry.get("tags") or ()),
        )
        # Eagerly resolve size so the UI can show it without re-reading
        # the resource on every combo change. Manifest is small in v0.1.
        out.append(replace(asset, size_bytes=len(asset.data())))
    return tuple(out)
