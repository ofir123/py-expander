"""Read the environment supplied by Transmission's completion hook."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def get_environment_variables_from_transmission() -> str:
    """Return the completed torrent path, or fail when hook values are missing."""
    directory = os.environ.get("TR_TORRENT_DIR")
    name = os.environ.get("TR_TORRENT_NAME")
    if not directory or not name:
        raise ValueError("Transmission requires TR_TORRENT_DIR and TR_TORRENT_NAME")
    if Path(name).name != name or name in {".", ".."}:
        raise ValueError("Transmission torrent name must be a file or directory name")
    path = Path(directory) / name
    logger.info("Transmission completed %s", path)
    return str(path)
