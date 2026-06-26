"""Helpers for local NewUnivers sibling-package integrations.

The OpenMontage checkout often sits next to shared NewUnivers libraries during
development. These helpers prefer a normal installed package, then fall back to
``../<sibling>/src`` so the tools can run from a multi-repo workspace without
requiring editable installs.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class IntegrationStatus:
    package: str
    available: bool
    source: str
    path: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "available": self.available,
            "source": self.source,
            "path": self.path,
            "error": self.error,
        }


def sibling_src_path(sibling_dir_name: str) -> Path:
    """Return the expected ``src`` directory for a sibling checkout."""
    return PROJECT_ROOT.parent / sibling_dir_name / "src"


def ensure_sibling_src(package_name: str, sibling_dir_name: str) -> Path | None:
    """Add a sibling ``src`` directory to ``sys.path`` when needed.

    Returns the path that was added, or ``None`` if the package is already
    importable or the sibling checkout is absent.
    """
    if importlib.util.find_spec(package_name) is not None:
        return None
    src = sibling_src_path(sibling_dir_name)
    if not src.is_dir():
        return None
    src_text = str(src)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)
    return src


def ensure_package(package_name: str, sibling_dir_name: str) -> ModuleType:
    """Import a package, falling back to the sibling checkout when present."""
    ensure_sibling_src(package_name, sibling_dir_name)
    return importlib.import_module(package_name)


def package_status(package_name: str, sibling_dir_name: str) -> IntegrationStatus:
    """Return import availability and source details for an integration."""
    src = sibling_src_path(sibling_dir_name)
    try:
        module = ensure_package(package_name, sibling_dir_name)
    except Exception as exc:  # noqa: BLE001 - surfaced as tool status detail
        hint = f"pip install -e ../{sibling_dir_name}"
        return IntegrationStatus(
            package=package_name,
            available=False,
            source="unavailable",
            path=str(src),
            error=f"{exc}. Install with `{hint}` or place the sibling checkout next to this repo.",
        )

    origin = getattr(module, "__file__", "") or ""
    source = "installed"
    if origin:
        try:
            if Path(origin).resolve().is_relative_to(src.resolve()):
                source = "sibling_checkout"
        except OSError:
            pass
    return IntegrationStatus(
        package=package_name,
        available=True,
        source=source,
        path=origin,
    )
