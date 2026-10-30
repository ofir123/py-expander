"""Find subtitles and upload staged media."""

from __future__ import annotations

import logging
from pathlib import Path

from . import config
from .subtitles import find_file_subtitles
from .upload import upload_file
from .utils import PathLike

logger = logging.getLogger(__name__)


def process_file(file_path: PathLike) -> bool:
    """Process one media file; report failed sidecars as failed processing."""
    path = Path(file_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        return False
    if path.suffix.lower() not in {suffix.lower() for suffix in config.EXTENSIONS_WHITE_LIST}:
        return False
    is_subtitle = path.suffix.lower() in config.SUBTITLES_EXTENSIONS
    sidecars = find_file_subtitles(path) if config.SHOULD_FIND_SUBTITLES and not is_subtitle else []
    if not config.SHOULD_UPLOAD:
        return True
    subtitles_ok = True
    for sidecar in sidecars:
        if not upload_file(sidecar):
            subtitles_ok = False
    return upload_file(path) and subtitles_ok


def process_directory(directory: PathLike) -> int:
    """Process videos before existing sidecars, retaining failed files for retry."""
    paths = sorted(
        (path for path in Path(directory).rglob("*") if path.is_file() and not path.is_symlink()),
        key=lambda path: (path.suffix.lower() in config.SUBTITLES_EXTENSIONS, str(path)),
    )
    successful = 0
    for path in paths:
        if path.exists() and process_file(path):
            successful += 1
    logger.info("Processed %s files in %s", successful, directory)
    return successful
