"""Locate (and later download) the rhwp executable.

Skeleton: W1 replaces the body with explicit → RHWP_EXE → PATH → cache → pinned download.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

RHWP_VERSION = "v0.9.0"


def ensure_rhwp(explicit: Optional[str] = None, allow_download: bool = True) -> Path:
    """Return a usable rhwp executable path, downloading the pinned release if needed."""
    from hwp_edit_mcp.rhwp_backend import find_rhwp_exe

    return find_rhwp_exe(explicit)
