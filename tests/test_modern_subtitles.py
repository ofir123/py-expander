from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import babelfish
from dogpile.cache import make_region
from subliminal.subtitle import Subtitle


def make_subtitle(language, text="subtitle"):
    subtitle = Subtitle(babelfish.Language(language), language)
    subtitle.set_content(
        ("1\n00:00:01,000 --> 00:00:02,000\n" + text + "\n\n").encode()
    )
    return subtitle


def configure(monkeypatch):
    from pyexpander import subtitles

    monkeypatch.setattr(
        subtitles,
        "LANGUAGES_MAP",
        {
            babelfish.Language("heb"): ["wizdom"],
            babelfish.Language("eng"): None,
        },
    )
    monkeypatch.setattr(subtitles, "PROVIDER_CONFIGS", {})
    return subtitles


def test_cache_roundtrip(tmp_path, monkeypatch):
    subtitles = configure(monkeypatch)
    monkeypatch.setattr(subtitles, "user_cache_dir", lambda *args: str(tmp_path))
    monkeypatch.setattr(subtitles, "region", make_region())
    subtitles.configure_subtitles_cache()
    subtitles.region.set("movie", "tt0770828")
    assert subtitles.region.get("movie") == "tt0770828"

    def cache_video(index):
        subtitles.region.set(str(index), "video-" + str(index))
        return subtitles.region.get(str(index))

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(cache_video, range(20))) == [
            "video-" + str(i) for i in range(20)
        ]


def test_download_and_upload_staging(tmp_path, monkeypatch):
    subtitles = configure(monkeypatch)
    from pyexpander import postprocess

    video = tmp_path / "The.Wire.S01E01.720p.HDTV.x264-LOL.mkv"
    video.write_bytes(b"disposable video copy")
    hebrew, english = make_subtitle("heb", "שלום"), make_subtitle("eng", "Hello")

    def download(videos, languages, **kwargs):
        return {
            next(iter(videos)): [
                hebrew if babelfish.Language("heb") in languages else english
            ]
        }

    monkeypatch.setattr(subtitles.subliminal, "download_best_subtitles", download)
    monkeypatch.setattr(postprocess.config, "SHOULD_FIND_SUBTITLES", True)
    monkeypatch.setattr(postprocess.config, "SHOULD_UPLOAD", True)
    uploads = []
    monkeypatch.setattr(
        postprocess, "upload_file", lambda path: uploads.append(Path(path)) or True
    )
    assert postprocess.process_directory(str(tmp_path)) == 1
    assert uploads == [
        video.with_suffix(".he.srt"),
        video.with_suffix(".en.srt"),
        video,
    ]
    assert "שלום" in video.with_suffix(".he.srt").read_text()
    assert video.read_bytes() == b"disposable video copy"


def test_existing_subtitles_preserved_without_download(tmp_path, monkeypatch):
    subtitles = configure(monkeypatch)
    video = tmp_path / "Movie.2013.mkv"
    video.touch()
    hebrew, english = video.with_suffix(".he.srt"), video.with_suffix(".en.srt")
    hebrew.write_text("existing Hebrew")
    english.write_text("existing English")

    def unexpected_download(*args, **kwargs):
        raise AssertionError("Existing languages must not be downloaded again")

    monkeypatch.setattr(
        subtitles.subliminal, "download_best_subtitles", unexpected_download
    )
    assert set(subtitles.find_file_subtitles(str(video))) == {str(hebrew), str(english)}
    assert hebrew.read_text() == "existing Hebrew"


def test_existing_language_returned_when_other_language_unavailable(
    tmp_path, monkeypatch
):
    subtitles = configure(monkeypatch)
    video = tmp_path / "Movie.2013.mkv"
    video.touch()
    hebrew = video.with_suffix(".he.srt")
    hebrew.write_text("existing Hebrew")
    monkeypatch.setattr(
        subtitles.subliminal, "download_best_subtitles", lambda videos, **kw: {}
    )
    assert subtitles.find_file_subtitles(str(video)) == [str(hebrew)]


def test_existing_language_returned_when_provider_fails(tmp_path, monkeypatch):
    subtitles = configure(monkeypatch)
    video = tmp_path / "Movie.2013.mkv"
    video.touch()
    hebrew = video.with_suffix(".he.srt")
    hebrew.write_text("existing Hebrew")

    def failed_download(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        subtitles.subliminal, "download_best_subtitles", failed_download
    )
    assert subtitles.find_file_subtitles(str(video)) == [str(hebrew)]
