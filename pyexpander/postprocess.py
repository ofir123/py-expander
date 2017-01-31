import errno
import os
import shutil
import subprocess

import logbook

from pyexpander.upload import upload_file
from . import config
from .subtitles import find_file_subtitles

logger = logbook.Logger('post_process')


def _create_destination_path(directory_path):
    """
    Verifies that current path exists and if it doesn't, creates the path.

    :param directory_path: The directory path to create.
    """
    if not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path)
            logger.info('Creating directory {}'.format(directory_path))
        except OSError as ex:
            if ex.errno != errno.EEXIST:
                logger.exception('Failed to create directory {}'.format(directory_path))
                raise


def process_file(torrent_name, file_path):
    """
    Processes a single file with the given handler.

    :param torrent_name: The relevant torrent name.
    :param file_path: The file path to process.
    """
    handler = shutil.move if config.SHOULD_DELETE else shutil.copyfile
    filename = os.path.basename(file_path)
    destination_dir = os.path.join(config.DATA_PATH, torrent_name)
    # Creates target directory (of category path).
    _create_destination_path(destination_dir)
    destination_path = os.path.join(destination_dir, filename)
    try:
        # Move/Copy all relevant files to their location (keep original files for uploading).
        handler(file_path, destination_path)
        logger.info('{} {} to {}'.format(handler.__name__, file_path, destination_path))
        if os.name != 'nt':
            subprocess.check_output(['chmod', config.EXTRACTION_FILES_MASK, '-R', destination_dir])
        # Get subtitles.
        subtitles_paths = None
        if config.SHOULD_FIND_SUBTITLES:
            subtitles_paths = find_file_subtitles(destination_path)
        # Upload files to Amazon.
        if config.SHOULD_UPLOAD:
            upload_file(destination_path)
            if subtitles_paths:
                for subtitles_path in subtitles_paths:
                    upload_file(subtitles_path)
    except OSError as ex:
        logger.exception('Failed to {} {}: {}'.format(handler.__name__, file_path, ex))


def process_directory(directory):
    """
    The main directory processing function.
    It searches for files in the directories matching the known extensions and moves/copies them to
    the relevant path in the destination (/path/category/torrent_name).

    :param directory: The directory to process.
    """
    torrent_name = os.path.basename(os.path.dirname(directory))
    logger.info('Processing directory {} for torrent {}'.format(directory, torrent_name))
    for directory_path, _, file_names in os.walk(directory):
        logger.info('Processing Directory {}'.format(directory_path))
        for filename in file_names:
            process_file(torrent_name, os.path.join(directory_path, filename))
