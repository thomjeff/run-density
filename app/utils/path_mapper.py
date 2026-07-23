"""
Env-backed Runflow path settings and host↔container mapping (Issue #798 Phase 4).

Environment:
  RUNFLOW_ROOT            Host-side data root (Makefile, compose volume source, scripts)
  RUNFLOW_ROOT_HOST       Explicit host prefix for rewrite inside the container
                          (defaults to RUNFLOW_ROOT). Set by compose from the host mount.
  RUNFLOW_ROOT_CONTAINER  In-container mount target (default: /app/runflow)

Defaults never embed a machine-specific /Users/<name>/... path.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

from app.utils.env import env_str

PathLike = Union[str, Path]

DEFAULT_RUNFLOW_ROOT = "./runflow"
DEFAULT_RUNFLOW_ROOT_CONTAINER = "/app/runflow"


def get_host_runflow_root() -> Path:
    """Host (or rewrite) root for Runflow storage."""
    raw = env_str("RUNFLOW_ROOT_HOST", "") or env_str("RUNFLOW_ROOT", DEFAULT_RUNFLOW_ROOT)
    return Path(raw).expanduser()


def get_container_runflow_root() -> Path:
    """In-container Runflow mount path."""
    return Path(env_str("RUNFLOW_ROOT_CONTAINER", DEFAULT_RUNFLOW_ROOT_CONTAINER))


def is_container_runtime() -> bool:
    """True when running inside the app container."""
    if Path("/.dockerenv").exists() or Path("/app/.dockerenv").exists():
        return True
    container_root = get_container_runflow_root()
    return container_root.is_absolute() and container_root.exists()


def resolve_runflow_root() -> Path:
    """
    Active Runflow root for this process.

    Prefer the container mount when present; otherwise the configured host root.
    """
    container_root = get_container_runflow_root()
    if container_root.exists():
        return container_root
    return get_host_runflow_root()


def to_runtime_path(path: Optional[PathLike]) -> str:
    """
    Map a host Runflow path to the container mount when appropriate.

    - Relative paths, empty/None, already-container paths, and unrelated
      absolute paths are returned unchanged (as str).
    - When in a container and ``path`` is under the configured host root,
      the host prefix is replaced with the container root.
    """
    if path is None:
        return ""
    text = str(path)
    if not text:
        return text
    if not is_container_runtime():
        return text

    container_root = get_container_runflow_root()
    container_prefix = str(container_root)
    if text == container_prefix or text.startswith(container_prefix + os.sep):
        return text

    host_root = get_host_runflow_root()
    # Only rewrite absolute host roots (relative ./runflow is not a client path prefix)
    if not host_root.is_absolute():
        return text

    host_prefix = str(host_root)
    if text == host_prefix or text.startswith(host_prefix + os.sep):
        return container_prefix + text[len(host_prefix) :]
    return text
