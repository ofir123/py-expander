"""Post-process completed torrents and retrieve subtitles for organized media."""

from importlib.metadata import version

from .torrent_handler import expand_torrent, expand_torrent_from_transmission, main

__all__ = ["expand_torrent", "expand_torrent_from_transmission", "main"]
__version__ = version("pyexpander")
__author__ = "omerba, ohadr, ofir123"
