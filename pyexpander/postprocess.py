import os

import logbook

from pyexpander.upload import upload_file
from . import config
from .subtitles import find_file_subtitles

logger = logbook.Logger('post_process')


def process_file(file_path):
    """
    Processes a single file.

    :param file_path: The file path to process.
    """
    # Get subtitles.
    subtitles_paths = None
    if config.SHOULD_FIND_SUBTITLES:
        subtitles_paths = find_file_subtitles(file_path)
    # Upload files to Amazon.
    if config.SHOULD_UPLOAD:
        upload_file(file_path)
        if subtitles_paths:
            for subtitles_path in subtitles_paths:
                upload_file(subtitles_path)


def process_directory(directory):
    """
    The main directory processing function.
    It searches for files in the directories matching the known extensions and moves/copies them to
    the relevant path in the destination (/path/category/torrent_name).

    :param directory: The directory to process.
    """
    logger.info('Processing directory {}'.format(directory))
    for directory_path, _, file_names in os.walk(directory):
        logger.info('Processing Directory {}'.format(directory_path))
        for filename in file_names:
            process_file(os.path.join(directory_path, filename))
