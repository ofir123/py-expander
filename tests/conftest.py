import pytest

from pyexpander import config


@pytest.fixture
def upload_config(tmp_path, monkeypatch):
    for name, value in {
        "SHOULD_ENCRYPT": False,
        "CLOUD_PLAIN_PATH": "plain",
        "CLOUD_ENCRYPTED_PATH": "encrypted",
        "CLOUD_TV_PATH": "TV",
        "CLOUD_MOVIES_PATH": "Movies",
        "CLOUD_KIDS_TV_PATH": "Kids TV",
        "CLOUD_KIDS_MOVIES_PATH": "Kids Movies",
        "CLOUD_UFC_PATH": "UFC",
        "CLOUD_VIDEOS_PATH": "Videos",
        "MAX_UPLOAD_TRIES": 2,
        "ORIGINAL_NAMES_LOG": str(tmp_path / "names.log"),
    }.items():
        monkeypatch.setattr(config, name, value)
    return tmp_path
