from pathlib import Path

import pytest

from pyexpander import config, extract, torrent_handler, transmission, upload


@pytest.mark.parametrize(
    ("filename", "target"),
    [
        ("The.Wire.S01E01-E02.mkv", "TV/The Wire/Season 01/The Wire - S01E01-E02.mkv"),
        ("Man.of.Steel.2013.mkv", "Movies/Man Of Steel (2013)/Man Of Steel (2013).mkv"),
        ("The.Wire.S01E01.he.srt", "TV/The Wire/Season 01/The Wire - S01E01.he.srt"),
        ("The.Wire.S01E01.hebdub.mkv", "Kids TV/The Wire/Season 01/The Wire - S01E01 - Hebrew.mkv"),
        ("MasterClass.Example.mkv", "Videos/MasterClass.Example.mkv"),
        ("UFC.S03E01.Prelims.mkv", "UFC/UFC 301/UFC 301 - Preliminaries.mkv"),
        ("notes.nfo", None),
    ],
)
def test_library_naming(upload_config, filename, target):
    result = upload._target_path(upload_config / filename)
    assert result == (Path(target) if target else None)


@pytest.mark.parametrize("wipe", [False, True])
def test_source_retention_modes(tmp_path, monkeypatch, wipe):
    source = tmp_path / "downloads" / "movie.mkv"
    source.parent.mkdir()
    source.write_bytes(b"original video")
    data = tmp_path / "staging"
    monkeypatch.setattr(config, "DATA_PATH", str(data))
    monkeypatch.setattr(config, "SHOULD_DELETE", False)
    monkeypatch.setattr(config, "SHOULD_WIPE_CONTENT", wipe)
    monkeypatch.setattr(torrent_handler, "process_file", lambda path: True)
    assert torrent_handler.expand_torrent(source)
    assert source.read_bytes() == (b"" if wipe else b"original video")
    assert (data / source.name).read_bytes() == b"original video"


def test_invalid_cloud_target_leaves_media_intact(upload_config, monkeypatch):
    source = upload_config / "The.Wire.S01E01.mkv"
    source.write_bytes(b"original")
    monkeypatch.setattr(config, "CLOUD_TV_PATH", "../outside")
    with pytest.raises(ValueError):
        upload.upload_file(source)
    assert source.read_bytes() == b"original"


def test_plain_cleanup_removes_only_debris(tmp_path):
    extracted = tmp_path / config.EXTRACTION_TEMP_DIR_NAME
    extracted.mkdir()
    (extracted / "notes.txt").touch()
    extract.cleanup(tmp_path)
    assert not extracted.exists()


def test_transmission_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("TR_TORRENT_DIR", str(tmp_path))
    monkeypatch.setenv("TR_TORRENT_NAME", "episode")
    assert transmission.get_environment_variables_from_transmission() == str(tmp_path / "episode")
    monkeypatch.setenv("TR_TORRENT_NAME", "../escape")
    with pytest.raises(ValueError):
        transmission.get_environment_variables_from_transmission()
    monkeypatch.delenv("TR_TORRENT_NAME")
    with pytest.raises(ValueError):
        transmission.get_environment_variables_from_transmission()


def test_failed_cli_returns_nonzero_and_logs(tmp_path, monkeypatch):
    logfile = tmp_path / "logs" / "pyexpand.log"
    monkeypatch.setattr(config, "LOGFILE", str(logfile))
    monkeypatch.setattr(config, "SHOULD_FIND_SUBTITLES", False)
    assert torrent_handler.main([str(tmp_path / "missing")]) == 1
    assert "Torrent processing failed" in logfile.read_text()


def test_zero_byte_placeholder_is_not_uploaded(upload_config, monkeypatch):
    source = upload_config / "The.Wire.S01E01.mkv"
    source.touch()

    def unexpected(*args, **kwargs):
        pytest.fail("A torrent placeholder must not replace remote media")

    monkeypatch.setattr(upload.subprocess, "run", unexpected)
    assert upload.upload_file(source) is False


def test_retained_recovery_means_failed_directory_job(tmp_path, monkeypatch):
    source = tmp_path / "downloads" / "torrent"
    source.mkdir(parents=True)
    (source / "movie.mkv").write_bytes(b"video")
    monkeypatch.setattr(config, "DATA_PATH", str(tmp_path / "staging"))
    monkeypatch.setattr(config, "SHOULD_DELETE", False)
    monkeypatch.setattr(config, "SHOULD_WIPE_CONTENT", False)
    monkeypatch.setattr(config, "SHOULD_UPLOAD", True)
    monkeypatch.setattr(torrent_handler, "extract_all", lambda path: None)

    def process(directory):
        (directory / "movie.mkv").unlink()
        recovery = directory / config.EXTRACTION_TEMP_DIR_NAME / ".pyexpand-recovery"
        recovery.mkdir(parents=True)
        (recovery / "opaque").write_bytes(b"ciphertext")
        return 1

    monkeypatch.setattr(torrent_handler, "process_directory", process)
    assert torrent_handler.expand_torrent(source) is False
