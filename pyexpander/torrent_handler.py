"""Command line and torrent-completion entry points."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from importlib.metadata import version
from logging.handlers import RotatingFileHandler
from pathlib import Path

from filelock import FileLock

from pyexpander import config
from pyexpander.extract import cleanup, extract_all
from pyexpander.postprocess import process_directory, process_file
from pyexpander.subtitles import configure_subtitles_cache
from pyexpander.transmission import get_environment_variables_from_transmission
from pyexpander.utils import PathLike

logger = logging.getLogger("pyexpander.torrent_handler")


def _get_log_handlers() -> list[logging.Handler]:
    """Create console and rotating-file handlers after arguments are parsed."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if config.LOGFILE:
        logfile = Path(config.LOGFILE).expanduser()
        logfile.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(logfile, maxBytes=5 * 1024 * 1024, backupCount=1, encoding="utf-8")
        )
    return handlers


def _recreate_empty_torrent(current_path: PathLike, recreate_path: PathLike, is_file: bool) -> None:
    """Recreate torrent placeholders only when configured to discard source data."""
    current, target = Path(current_path), Path(recreate_path)
    if is_file:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"")
        return
    target.mkdir(parents=True, exist_ok=True)
    for path in current.rglob("*"):
        destination = target / path.relative_to(current)
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file() and not path.is_symlink():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"")


def expand_torrent(torrent_path: PathLike) -> bool:
    """Stage a torrent without overwriting previous work, then process it."""
    source = Path(torrent_path).expanduser()
    if source.is_symlink():
        raise ValueError("Torrent paths must not be symbolic links")
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if config.FINISHED_UPLOAD_PREFIX and source.name.startswith(config.FINISHED_UPLOAD_PREFIX):
        _recreate_empty_torrent(source, source, source.is_file())
        return True
    data = Path(config.DATA_PATH).expanduser().resolve()
    destination = data / source.name
    if destination == source or data.is_relative_to(source):
        raise ValueError("Download and staging directories must be separate")
    data.mkdir(parents=True, exist_ok=True)
    with FileLock(str(data / f".{source.name}.lock")):
        return _stage_torrent(source, destination)


def _stage_torrent(source: Path, destination: Path) -> bool:
    """Process one torrent while holding its staging lock."""
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Staged torrent already exists: {destination}")
    if source.is_dir() and any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("Torrent directories must not contain symbolic links")
    is_file = source.is_file()
    keep_source = not config.SHOULD_DELETE and not config.SHOULD_WIPE_CONTENT
    if keep_source:
        if is_file:
            shutil.copy2(source, destination)
        else:
            shutil.copytree(source, destination)
    else:
        shutil.move(str(source), destination)
        if not config.SHOULD_DELETE and config.SHOULD_WIPE_CONTENT:
            _recreate_empty_torrent(destination, source, is_file)
    if os.name != "nt":
        mode = int(str(config.EXTRACTION_FILES_MASK), 8)
        for path in [destination, *destination.rglob("*")] if destination.is_dir() else [destination]:
            if not path.is_symlink():
                path.chmod(mode)
    if is_file:
        return process_file(destination)
    extract_all(destination)
    successful = process_directory(destination)
    cleanup(destination)
    pending = any(
        path.is_file() and path.suffix.lower() in config.EXTENSIONS_WHITE_LIST
        for path in destination.rglob("*")
    )
    recovery = any(path.is_dir() for path in destination.rglob(".pyexpand-*"))
    return successful > 0 and not recovery and (not config.SHOULD_UPLOAD or not pending)


def expand_torrent_from_transmission() -> bool:
    """Process the torrent described by Transmission's environment."""
    return expand_torrent(get_environment_variables_from_transmission())


def main(argv: Sequence[str] | None = None) -> int:
    """Run a path, legacy uTorrent pair, or Transmission completion hook."""
    parser = argparse.ArgumentParser(
        description="Extract torrents, find subtitles, and upload organized media."
    )
    parser.add_argument("path", nargs="?", help="Completed torrent file or directory")
    parser.add_argument("filename", nargs="?", help="Legacy uTorrent filename argument")
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('pyexpander')}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args(argv)
    handlers: list[logging.Handler] = []
    package_logger = logging.getLogger("pyexpander")
    previous_level = package_logger.level
    try:
        handlers = _get_log_handlers()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        for handler in handlers:
            handler.setFormatter(formatter)
            package_logger.addHandler(handler)
        package_logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)
        if config.SHOULD_FIND_SUBTITLES:
            configure_subtitles_cache()
        if args.path is None:
            successful = expand_torrent_from_transmission()
        else:
            path = Path(args.path)
            if args.filename and path.resolve() == Path(config.DEFAULT_PATH).resolve():
                path /= args.filename
            successful = expand_torrent(path)
        return 0 if successful else 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        logger.exception("Torrent processing failed")
        return 1
    finally:
        for handler in handlers:
            package_logger.removeHandler(handler)
            handler.close()
        package_logger.setLevel(previous_level)


if __name__ == "__main__":
    sys.exit(main())
