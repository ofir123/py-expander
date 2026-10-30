"""Extract nested archives without discarding unprocessed media."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

from . import config
from .utils import PathLike, child_path, find_executable

ARCHIVE_EXTENSIONS = {".rar", ".zip", ".7z"}
PART_PATTERN = re.compile(r"^(.*)\.part(\d+)\.rar$", re.IGNORECASE)
logger = logging.getLogger(__name__)


def _extract_archive(archive_path: PathLike, destination: PathLike) -> None:
    """Flatten an archive using 7-Zip; leave it intact if extraction fails."""
    subprocess.run(
        [find_executable(config.EXTRACTION_EXECUTABLE), "e", "-y", str(Path(archive_path).resolve())],
        cwd=destination,
        check=True,
        capture_output=True,
    )


def _delete_archive(archive_path: PathLike) -> None:
    """Delete only matching multipart archive siblings."""
    archive = Path(archive_path)
    part = PART_PATTERN.fullmatch(archive.name)
    files = {archive}
    for sibling in archive.parent.iterdir():
        if not sibling.is_file():
            continue
        if part:
            candidate = PART_PATTERN.fullmatch(sibling.name)
            if candidate and candidate[1].casefold() == part[1].casefold():
                files.add(sibling)
        elif archive.suffix.lower() == ".rar":
            if sibling.stem == archive.stem and re.fullmatch(r"\.r\d{2,}", sibling.suffix, re.IGNORECASE):
                files.add(sibling)
    for path in sorted(files):
        logger.info("Deleting extracted archive %s", path)
        path.unlink()


def _find_target_archives(directory: PathLike) -> list[Path]:
    """Find archives recursively, excluding redundant multipart volumes."""
    archives = []
    for path in sorted(Path(directory).rglob("*")):
        if not path.is_file() or path.is_symlink() or path.suffix.lower() not in ARCHIVE_EXTENSIONS:
            continue
        part = PART_PATTERN.fullmatch(path.name)
        if part is None or int(part[2]) == 1:
            archives.append(path)
    return archives


def extract_all(directory: PathLike) -> None:
    """Extract nested archives into numbered directories in the staging tree."""
    root = Path(directory)
    archives = _find_target_archives(root)
    if not archives:
        return
    extracted = child_path(root, config.EXTRACTION_TEMP_DIR_NAME)
    extracted.mkdir()
    iteration = 1
    while archives:
        destination = extracted / f"unpacked_{iteration}"
        destination.mkdir()
        for archive in archives:
            logger.info("Extracting %s", archive)
            _extract_archive(archive, destination)
            _delete_archive(archive)
        archives = _find_target_archives(destination)
        iteration += 1


def cleanup(directory: PathLike) -> None:
    """Remove extraction debris only when no media or subtitles remain."""
    root = Path(directory)
    extracted = child_path(root, config.EXTRACTION_TEMP_DIR_NAME)
    if not extracted.exists():
        return
    if extracted.resolve() == root.resolve() or extracted.is_symlink():
        raise ValueError("Extraction cleanup requires a separate real subdirectory")
    if any(path.is_dir() for path in extracted.rglob(".pyexpand-*")):
        logger.info("Keeping upload recovery workspace inside %s", extracted)
        return
    extensions = {extension.lower() for extension in config.EXTENSIONS_WHITE_LIST}
    if any(path.suffix.lower() in extensions for path in extracted.rglob("*") if path.is_file()):
        logger.info("Keeping extracted files for retry: %s", extracted)
        return
    shutil.rmtree(extracted)
