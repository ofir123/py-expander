import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pyexpander import config, extract, subtitles, torrent_handler, upload


def test_encfs_password_is_stdin_not_a_shell_command(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENCFS_PASSWORD", "test password; $(not-a-command)")
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(upload.subprocess, "run", run)
    assert upload._encrypt(tmp_path / "encrypted", tmp_path / "plain")
    args, kwargs = calls[0]
    assert isinstance(args, list)
    assert kwargs["input"] == "test password; $(not-a-command)\n"
    assert not kwargs.get("shell", False)
    assert "test password; $(not-a-command)" not in args


def test_direct_file_hook_help_starts():
    result = subprocess.run(
        [sys.executable, torrent_handler.__file__, "--help"], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr


def test_direct_hook_errors_use_configured_log(tmp_path, monkeypatch):
    logfile = tmp_path / "direct-hook.log"
    monkeypatch.setattr(config, "LOGFILE", str(logfile))
    monkeypatch.setattr(config, "SHOULD_FIND_SUBTITLES", False)
    monkeypatch.setattr(sys, "argv", [torrent_handler.__file__, str(tmp_path / "missing")])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(torrent_handler.__file__, run_name="__main__")
    assert error.value.code == 1
    assert "Torrent processing failed" in logfile.read_text()


def test_staging_rejects_dangling_symlink(tmp_path, monkeypatch):
    source = tmp_path / "downloads" / "movie.mkv"
    source.parent.mkdir()
    source.write_bytes(b"download")
    data = tmp_path / "staging"
    data.mkdir()
    outside = tmp_path / "outside.mkv"
    try:
        (data / source.name).symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation unavailable")
    monkeypatch.setattr(config, "DATA_PATH", str(data))
    monkeypatch.setattr(config, "SHOULD_DELETE", False)
    monkeypatch.setattr(config, "SHOULD_WIPE_CONTENT", False)
    monkeypatch.setattr(torrent_handler, "process_file", lambda path: True)
    with pytest.raises(FileExistsError):
        torrent_handler.expand_torrent(source)
    assert not outside.exists()
    assert source.read_bytes() == b"download"


def test_failed_mount_leaves_original_untouched(upload_config, monkeypatch):
    source = upload_config / "The.Wire.S01E01.mkv"
    source.write_bytes(b"video")
    monkeypatch.setattr(config, "SHOULD_ENCRYPT", True)
    monkeypatch.setattr(upload, "_encrypt", lambda *args: False)
    assert upload.upload_file(source) is False
    assert source.read_bytes() == b"video"
    assert not list(upload_config.glob(".pyexpand-*"))


def test_failed_unmount_keeps_staging(upload_config, monkeypatch):
    source = upload_config / "The.Wire.S01E01.mkv"
    source.write_bytes(b"video")
    monkeypatch.setattr(config, "SHOULD_ENCRYPT", True)
    monkeypatch.setattr(upload, "_encrypt", lambda *args: True)
    responses = iter([0, 1])
    monkeypatch.setattr(
        upload.subprocess, "run", lambda *args, **kw: SimpleNamespace(returncode=next(responses))
    )
    assert upload.upload_file(source) is True
    retained = list(upload_config.glob(".pyexpand-*/plain/TV/The Wire/Season 01/*.mkv"))
    assert len(retained) == 1
    assert retained[0].read_bytes() == b"video"


def test_failed_restore_keeps_both_copies(upload_config, monkeypatch):
    source = upload_config / "The.Wire.S01E01.mkv"
    source.write_bytes(b"original")

    def failed(*args, **kwargs):
        source.write_bytes(b"concurrent new data")
        return SimpleNamespace(returncode=1, stdout="failed")

    monkeypatch.setattr(upload.subprocess, "run", failed)
    assert upload.upload_file(source) is False
    assert source.read_bytes() == b"concurrent new data"
    retained = list(upload_config.glob(".pyexpand-*/plain/TV/The Wire/Season 01/*.mkv"))
    assert retained[0].read_bytes() == b"original"


def test_encrypted_recovery_survives_outer_cleanup(upload_config, monkeypatch):
    extracted = upload_config / config.EXTRACTION_TEMP_DIR_NAME / "unpacked_1"
    extracted.mkdir(parents=True)
    source = extracted / "The.Wire.S01E01.mkv"
    source.write_bytes(b"original")
    monkeypatch.setattr(config, "SHOULD_ENCRYPT", True)

    def mount(encrypted, plain):
        encrypted.mkdir()
        return True

    monkeypatch.setattr(upload, "_encrypt", mount)
    real_move = shutil.move

    def move(src, dest, *args, **kwargs):
        if Path(src) != source:
            raise PermissionError("restore failed")
        return real_move(src, dest, *args, **kwargs)

    monkeypatch.setattr(upload.shutil, "move", move)

    def command(args, **kwargs):
        if args[0] == str(config.UMOUNT_PATH):
            plain = Path(args[-1])
            (plain.parent / "encrypted" / "opaque").write_bytes(b"recoverable ciphertext")
            shutil.rmtree(plain)
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=1, stdout="failed")

    monkeypatch.setattr(upload.subprocess, "run", command)
    assert upload.upload_file(source) is False
    recovery = next(extracted.glob(".pyexpand-*/encrypted/opaque"))
    extract.cleanup(upload_config)
    assert recovery.read_bytes() == b"recoverable ciphertext"


def test_failed_original_name_log_restores_media(upload_config, monkeypatch):
    source = upload_config / "The.Wire.S01E01.mkv"
    source.write_bytes(b"original")
    monkeypatch.setattr(config, "ORIGINAL_NAMES_LOG", str(upload_config))
    monkeypatch.setattr(upload.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))
    assert upload.upload_file(source) is False
    assert source.read_bytes() == b"original"


def test_failed_extraction_preserves_archive(tmp_path, monkeypatch):
    archive = tmp_path / "release.rar"
    archive.write_bytes(b"archive")

    def fail(*args):
        raise subprocess.CalledProcessError(2, ["7z"])

    monkeypatch.setattr(extract, "_extract_archive", fail)
    with pytest.raises(subprocess.CalledProcessError):
        extract.extract_all(tmp_path)
    assert archive.read_bytes() == b"archive"


@pytest.mark.parametrize("child", [".", "../outside"])
def test_cleanup_refuses_root_or_escape(tmp_path, monkeypatch, child):
    (tmp_path / "notes.txt").write_text("keep")
    monkeypatch.setattr(config, "EXTRACTION_TEMP_DIR_NAME", child)
    with pytest.raises(ValueError):
        extract.cleanup(tmp_path)
    assert (tmp_path / "notes.txt").read_text() == "keep"


def test_empty_torrent_placeholders_include_root(tmp_path):
    current, target = tmp_path / "current", tmp_path / "target"
    current.mkdir()
    torrent_handler._recreate_empty_torrent(current, target, False)
    assert target.is_dir()


def test_cache_lock_coordinates_processes(tmp_path):
    name = str(tmp_path / "cache.dbm")
    lock = subtitles.SubtitleCacheLock(name)
    script = (
        "import sys; from pyexpander.subtitles import SubtitleCacheLock; "
        "lock=SubtitleCacheLock(sys.argv[1]); acquired=lock.acquire_write_lock(False); "
        "print(acquired); acquired and lock.release_write_lock()"
    )
    assert lock.acquire_write_lock(True)
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, name], capture_output=True, text=True, check=True, timeout=15
        )
        assert result.stdout.strip() == "False"
    finally:
        lock.release_write_lock()
    result = subprocess.run(
        [sys.executable, "-c", script, name], capture_output=True, text=True, check=True, timeout=15
    )
    assert result.stdout.strip() == "True"


def test_missing_wizdom_is_explained(monkeypatch):
    monkeypatch.setattr(subtitles.subliminal.provider_manager, "names", lambda: [])
    with pytest.raises(RuntimeError, match="Hebrew-enabled"):
        subtitles.configure_subtitles_cache()


def test_cli_legacy_pair(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_PATH", str(tmp_path))
    monkeypatch.setattr(config, "SHOULD_FIND_SUBTITLES", False)
    monkeypatch.setattr(torrent_handler, "_get_log_handlers", lambda: [])
    paths = []
    monkeypatch.setattr(torrent_handler, "expand_torrent", lambda path: paths.append(path) or True)
    assert torrent_handler.main([str(tmp_path), "movie.mkv"]) == 0
    assert paths == [tmp_path / "movie.mkv"]
