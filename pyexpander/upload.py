"""Name media and upload staged directory trees with rclone and optional EncFS."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from guessit import guessit
from showsformatter import format_show

from . import config
from .utils import PathLike, child_path

logger = logging.getLogger(__name__)
CloudPath = tuple[str | None, str | None]


def _encrypt(encrypted_dir: PathLike, plain_dir: PathLike) -> bool:
    """Mount EncFS, supplying its password on stdin without a shell."""
    env = os.environ.copy()
    env.setdefault(config.ENCFS_ENVIRONMENT_VARIABLE, str(config.ENCFS_CONFIG_PATH))
    Path(encrypted_dir).mkdir(parents=True)
    result = subprocess.run(
        [str(config.ENCFS_PATH), "-S", str(encrypted_dir), str(plain_dir)],
        input=f"{config.ENCFS_PASSWORD}\n",
        env=env,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _extract_ufc_path(file_name: str) -> CloudPath:
    """Keep the existing UFC event/preliminaries naming convention."""
    guess = guessit(file_name)
    episode, season = guess.get("episode"), guess.get("season", 0)
    if not isinstance(episode, int) or not isinstance(season, int):
        return None, None
    lower = file_name.lower()
    if "fox" in lower:
        title = "UFC On FOX"
    elif "espn" in lower:
        title = "UFC On ESPN"
    elif ("fight" in lower and "night" in lower) or "fn" in lower:
        title = "UFC Fight Night"
    else:
        title = "UFC"
    event = f"{title} {episode + 100 * season:03d}"
    name = f"{event} - Preliminaries" if "prelim" in lower else event
    return str(Path(config.CLOUD_UFC_PATH) / event), name


def _extract_masterclass_path(file_name: str) -> CloudPath:
    """Keep unstructured Masterclass videos in the configured video library."""
    return str(config.CLOUD_VIDEOS_PATH), Path(file_name).stem


def _guess_path(file_name: str) -> CloudPath:
    """Name movies and single/multiple TV episodes, including season zero."""
    guess = guessit(file_name)
    title = guess.get("title")
    if isinstance(title, list):
        title = title[0] if title else None
    if not isinstance(title, str) or not title:
        return None, None
    if guess.get("type") == "episode":
        season, episode = guess.get("season"), guess.get("episode")
        if not isinstance(season, int) or episode is None:
            return None, None
        title = format_show(title)
        if isinstance(episode, list) and episode and all(isinstance(number, int) for number in episode):
            episode_text = f"E{episode[0]:02d}-E{episode[-1]:02d}"
        elif isinstance(episode, int):
            episode_text = f"E{episode:02d}"
        else:
            return None, None
        directory = Path(config.CLOUD_TV_PATH) / title.rstrip(".") / f"Season {season:02d}"
        return str(directory), f"{title} - S{season:02d}{episode_text}"
    if guess.get("type") == "movie" and isinstance(guess.get("year"), int):
        name = f"{title.title()} ({guess['year']})"
        return str(Path(config.CLOUD_MOVIES_PATH) / name), name
    return None, None


def _target_path(source: Path) -> Path | None:
    """Build a relative cloud filename, preserving language and dubbed markers."""
    extension = source.suffix.lower()
    if extension not in config.EXTENSIONS_WHITE_LIST or any(
        word in source.stem.lower() for word in config.NAMES_BLACK_LIST
    ):
        return None
    name = source.name
    language = ""
    if extension in config.SUBTITLES_EXTENSIONS:
        stem = Path(source.stem)
        if stem.suffix.lower() in config.LANGUAGE_EXTENSIONS:
            language, name = stem.suffix.lower(), stem.stem + config.DEFAULT_VIDEO_EXTENSION
        else:
            language, name = config.DEFAULT_LANGUAGE_EXTENSION, source.stem + config.DEFAULT_VIDEO_EXTENSION
    if name.startswith("[") and "]" in name:
        name = name.split("]", 1)[1].strip()
    lower = str(source).lower()
    if "ufc" in lower and "rivals" not in name.lower():
        directory, filename = _extract_ufc_path(name)
    elif "masterclass" in lower:
        directory, filename = _extract_masterclass_path(name)
    else:
        directory, filename = _guess_path(name)
    if directory is None or filename is None:
        return None
    dubbed = any(marker in lower for marker in ("hebdub", "hebrew.dubbed", "hebrew dubbed"))
    if dubbed:
        cloud = Path(directory)
        for original, kids in [
            (Path(config.CLOUD_MOVIES_PATH), Path(config.CLOUD_KIDS_MOVIES_PATH)),
            (Path(config.CLOUD_TV_PATH), Path(config.CLOUD_KIDS_TV_PATH)),
        ]:
            if cloud.is_relative_to(original):
                directory = str(kids / cloud.relative_to(original))
                break
        filename += " - Hebrew"
    return Path(directory) / f"{filename}{language}{extension}"


def upload_file(file_path: PathLike) -> bool:
    """Upload one media file, restoring it on failed commands or retries."""
    source = Path(file_path).absolute()
    if not source.is_file() or source.is_symlink() or source.stat().st_size == 0:
        return False
    target = _target_path(source)
    if target is None:
        logger.info("Skipping unrecognized media %s", source)
        return False
    # Validate all configured children before moving any data.
    if target.is_absolute() or ".." in target.parts or config.MAX_UPLOAD_TRIES < 1:
        raise ValueError("Cloud targets must be relative paths and upload attempts must be positive")
    base = Path(tempfile.mkdtemp(prefix=".pyexpand-", dir=source.parent))
    staged: Path | None = None
    mounted = False
    successful = False
    removable = True
    try:
        plain = child_path(base, config.CLOUD_PLAIN_PATH)
        plain.mkdir(parents=True)
        upload_root = plain
        if config.SHOULD_ENCRYPT:
            encrypted = child_path(base, config.CLOUD_ENCRYPTED_PATH)
            if encrypted == plain:
                raise ValueError("Plain and encrypted staging paths must differ")
            if not _encrypt(encrypted, plain):
                return False
            mounted = True
            upload_root = encrypted
        staged = child_path(plain, target)
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), staged)
        remote = f"GDrive:{upload_root.relative_to(base).as_posix()}"
        for attempt in range(1, config.MAX_UPLOAD_TRIES + 1):
            result = subprocess.run(
                [
                    str(config.RCLONE_PATH),
                    "--config",
                    str(config.RCLONE_CONFIG_PATH),
                    "copy",
                    "--update",
                    str(upload_root),
                    remote,
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if result.returncode == 0:
                if source.suffix.lower() not in config.SUBTITLES_EXTENSIONS:
                    with Path(config.ORIGINAL_NAMES_LOG).open("a", encoding="utf-8") as log:
                        log.write(f"{source}\n")
                successful = True
                break
            logger.error(
                "Upload attempt %s/%s failed for %s: %s",
                attempt,
                config.MAX_UPLOAD_TRIES,
                source.name,
                result.stdout,
            )
    except (OSError, subprocess.SubprocessError, ValueError):
        logger.exception("Upload failed for %s", source)
    finally:
        if not successful and staged is not None and staged.exists():
            try:
                if source.exists():
                    raise FileExistsError(f"Refusing to overwrite restored source: {source}")
                shutil.move(str(staged), source)
            except OSError:
                removable = False
                logger.exception("Keeping recovery files in %s", base)
        if mounted:
            try:
                unmount = subprocess.run(
                    [str(config.UMOUNT_PATH), "-l", str(plain)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if unmount.returncode:
                    removable = False
                    logger.error("Unmount failed; keeping staging directory %s", base)
            except OSError:
                removable = False
                logger.exception("Could not unmount %s; keeping %s", plain, base)
        if removable:
            shutil.rmtree(base)
    return successful
