"""Subtitle retrieval using the modern Hebrew-enabled Subliminal API."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import babelfish
import subliminal
from dogpile.cache.backends.file import AbstractFileLock
from filelock import FileLock, Timeout
from platformdirs import user_cache_dir
from subliminal.cache import region

from .config import (
    DEFAULT_LANGUAGE_EXTENSION,
    LANGUAGE_EXTENSIONS,
    LANGUAGES_MAP,
    PROVIDER_CONFIGS,
    SUBTITLES_EXTENSIONS,
)
from .utils import PathLike

logger = logging.getLogger(__name__)


class SubtitleCacheLock(AbstractFileLock):
    """Serialize DBM access across threads and separate torrent-hook processes."""

    def __init__(self, filename: str) -> None:
        self._lock = FileLock(f"{filename}.lock")

    def acquire_read_lock(self, wait: bool) -> bool:
        try:
            self._lock.acquire(timeout=-1 if wait else 0)
        except Timeout:
            return False
        return True

    def acquire_write_lock(self, wait: bool) -> bool:
        return self.acquire_read_lock(wait)

    def release_read_lock(self) -> None:
        self._lock.release()

    def release_write_lock(self) -> None:
        self._lock.release()


def _check_hebits_dir(path: PathLike) -> bool:
    """Recognize the legacy marker for unlabelled Hebrew subtitles."""
    return any("hebits" in item.name.casefold() for item in Path(path).iterdir())


def find_file_subtitles(path: PathLike) -> list[str]:
    """Reuse existing sidecars, then search each missing language independently."""
    video_path = Path(path)
    if not video_path.is_file():
        return []
    missing = dict(LANGUAGES_MAP)
    paths: list[str] = []
    for sidecar in sorted(video_path.parent.iterdir()):
        if (
            not sidecar.is_file()
            or sidecar.is_symlink()
            or sidecar.suffix.lower() not in SUBTITLES_EXTENSIONS
        ):
            continue
        stem = Path(sidecar.stem)
        language_suffix = stem.suffix.lower()
        name = stem.stem
        if language_suffix not in LANGUAGE_EXTENSIONS:
            language_suffix = ".he" if _check_hebits_dir(video_path.parent) else DEFAULT_LANGUAGE_EXTENSION
            name = sidecar.stem
        if name.casefold() != video_path.stem.casefold():
            continue
        language = babelfish.Language.fromalpha2(language_suffix.lstrip("."))
        if language in missing:
            del missing[language]
            paths.append(str(sidecar))
    if not missing:
        return paths
    try:
        video = subliminal.scan_video(str(video_path))
    except (OSError, ValueError):
        logger.debug("Not a readable video: %s", video_path)
        return paths
    for language, providers in missing.items():
        try:
            results = subliminal.download_best_subtitles(
                {video}, languages={language}, providers=providers or None, provider_configs=PROVIDER_CONFIGS
            ).get(video, [])
            # A provider must not replace a sidecar in an unrelated language.
            results = [subtitle for subtitle in results if subtitle.language == language]
            saved = subliminal.save_subtitles(video, results, extension=".srt")
            paths.extend(subtitle.get_path(video, extension=".srt") for subtitle in saved)
        except Exception:
            logger.exception("Subtitle lookup failed for %s (%s)", video_path, language)
    return paths


def configure_subtitles_cache() -> None:
    """Configure a process-safe private cache once per interpreter."""
    requested = {provider for providers in LANGUAGES_MAP.values() if providers for provider in providers}
    unavailable = requested - set(subliminal.provider_manager.names())
    if unavailable:
        raise RuntimeError(
            f"Subtitle providers unavailable: {', '.join(sorted(unavailable))}. "
            "Install the configured Hebrew-enabled Subliminal fork."
        )
    if region.is_configured:
        return
    directory = Path(user_cache_dir("pyexpander"))
    directory.mkdir(parents=True, exist_ok=True)
    # Backend construction opens/creates DBM before dogpile's operation locks apply.
    with FileLock(str(directory / "initialize.lock")):
        if region.is_configured:
            return
        region.configure(
            "dogpile.cache.dbm",
            expiration_time=timedelta(days=30).total_seconds(),
            arguments={"filename": str(directory / "subliminal.dbm"), "lock_factory": SubtitleCacheLock},
        )
