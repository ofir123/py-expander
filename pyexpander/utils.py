"""Small executable and path helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PathLike = str | os.PathLike[str]


def find_executable(filename: PathLike) -> str:
    """Resolve a program using the platform's executable search rules."""
    executable = shutil.which(os.fspath(filename))
    if executable is None:
        raise FileNotFoundError(f"Executable not found: {filename}")
    return executable


def child_path(root: Path, relative: PathLike) -> Path:
    """Resolve a configured child path without allowing it outside its root."""
    candidate = root / relative
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path must stay inside {root}: {relative}")
    return candidate
