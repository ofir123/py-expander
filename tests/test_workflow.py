from pathlib import Path
from types import SimpleNamespace

import pytest

from pyexpander import config, extract, torrent_handler, upload


def test_cli_help_never_starts_a_job(monkeypatch):
    monkeypatch.setattr(torrent_handler, "_get_log_handlers", lambda: pytest.fail("help opened logs"))
    with pytest.raises(SystemExit) as error:
        torrent_handler.main(["--help"])
    assert error.value.code == 0


def test_existing_destination_is_not_overwritten(tmp_path, monkeypatch):
    source = tmp_path / "downloads" / "movie.mkv"
    source.parent.mkdir()
    source.write_bytes(b"new download")
    data = tmp_path / "staging"
    data.mkdir()
    (data / source.name).write_bytes(b"previous failed upload")
    monkeypatch.setattr(config, "DATA_PATH", str(data))
    monkeypatch.setattr(config, "SHOULD_DELETE", True)
    with pytest.raises(FileExistsError):
        torrent_handler.expand_torrent(source)
    assert source.read_bytes() == b"new download"
    assert (data / source.name).read_bytes() == b"previous failed upload"


def test_cleanup_preserves_failed_media(tmp_path):
    unpacked = tmp_path / config.EXTRACTION_TEMP_DIR_NAME
    unpacked.mkdir()
    video = unpacked / "failed.mkv"
    video.write_bytes(b"only remaining copy")
    extract.cleanup(tmp_path)
    assert video.read_bytes() == b"only remaining copy"


def test_multipart_deletion_is_exact(tmp_path):
    wanted = [tmp_path / "show.part01.rar", tmp_path / "show.part02.rar"]
    unrelated = [tmp_path / "show.part01-extra.part02.rar", tmp_path / "show.rtf"]
    for path in wanted + unrelated:
        path.touch()
    extract._delete_archive(str(wanted[0]))
    assert not any(path.exists() for path in wanted)
    assert all(path.exists() for path in unrelated)


def test_uppercase_archives_detected(tmp_path):
    archive = tmp_path / "Release.RAR"
    archive.touch()
    assert [Path(p) for p in extract._find_target_archives(tmp_path)] == [archive]


def test_upload_uses_argument_list_and_copy_directory(upload_config, monkeypatch):
    source = upload_config / "The.Wire.S01E01.mkv"
    source.write_bytes(b"video")
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(upload.subprocess, "run", run)
    assert upload.upload_file(source)
    assert isinstance(calls[0][0], list)
    assert "copy" in calls[0][0]
    assert not calls[0][1].get("shell", False)
    assert not source.exists()


def test_upload_launch_failure_restores_source(upload_config, monkeypatch):
    source = upload_config / "The.Wire.S01E01.mkv"
    source.write_bytes(b"video")

    def missing_command(*args, **kwargs):
        raise FileNotFoundError("rclone missing")

    monkeypatch.setattr(upload.subprocess, "run", missing_command)
    assert upload.upload_file(source) is False
    assert source.read_bytes() == b"video"


def test_upload_retry_exhaustion_restores_source(upload_config, monkeypatch):
    source = upload_config / "The.Wire.S01E01.mkv"
    source.write_bytes(b"video")
    calls = []

    def failed(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stdout="failed")

    monkeypatch.setattr(upload.subprocess, "run", failed)
    assert upload.upload_file(source) is False
    assert len(calls) == 2
    assert source.read_bytes() == b"video"


def test_season_zero_is_named(upload_config):
    directory, name = upload._guess_path("The.Wire.S00E01.mkv")
    assert directory is not None
    assert name.endswith("S00E01")
