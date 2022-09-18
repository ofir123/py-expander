#!/usr/local/bin/python3.5
import os
import shutil
import subprocess
import sys

import logbook

from pyexpander import config
from pyexpander.extract import extract_all, cleanup
from pyexpander.postprocess import process_directory, process_file
from pyexpander.subtitles import configure_subtitles_cache
from pyexpander.transmission import get_environment_variables_from_transmission

logger = logbook.Logger('handler')


def _get_log_handlers():
    """
    Initializes all relevant log handlers.

    :return: A list of log handlers.
    """
    return [
        logbook.NullHandler(),
        logbook.StreamHandler(sys.stdout, level=logbook.DEBUG, bubble=True),
        logbook.RotatingFileHandler(config.LOGFILE, level=logbook.DEBUG, max_size=5 * 1024 * 1024, backup_count=1,
                                    bubble=True)
    ]


def _recreate_empty_torrent(current_path, recreate_path, is_file):
    logger.debug("Recreating empty torrent...")
    if is_file:
        open(recreate_path, "wb").truncate()
    else:
        for dir_path, dir_names, file_names in os.walk(current_path):
            base_path = dir_path.replace(current_path, recreate_path)
            os.makedirs(base_path, exist_ok=True)
            for dir_name in dir_names:
                os.makedirs(os.path.join(base_path, dir_name), exist_ok=True)
            for file_name in file_names:
                open(os.path.join(base_path, file_name), "wb").truncate()


def expand_torrent(torrent_path):
    """
    Perform torrent expansion steps - extraction, copying/moving to relevant directory and cleanup.

    :param torrent_path: The torrent path to expand.
    """
    logger.info('Processing torrent {}'.format(torrent_path))
    torrent_path = os.path.abspath(torrent_path)
    is_file = os.path.isfile(torrent_path)

    # If upload was finished in the past, recreate and skip upload.
    if os.path.basename(torrent_path).startswith(config.FINISHED_UPLOAD_PREFIX):
        _recreate_empty_torrent(torrent_path, torrent_path, is_file)
        logger.info('File was uploaded in the past. Skipping!')
        return

    # Move/Copy all relevant files to their location (keep original files for uploading).
    handler = shutil.move
    if not config.SHOULD_DELETE and not config.SHOULD_WIPE_CONTENT:
        handler = shutil.copy if is_file else shutil.copytree
    new_path = os.path.join(config.DATA_PATH, os.path.basename(torrent_path))
    logger.info('{} {} to {}'.format(handler.__name__, torrent_path, new_path))
    try:
        handler(torrent_path, new_path)
        # Leave an empty file if requested, to avoid hit & runs.
        if not config.SHOULD_DELETE and config.SHOULD_WIPE_CONTENT:
            _recreate_empty_torrent(new_path, torrent_path, is_file=is_file)

        # Set relevant permissions.
        if os.name != 'nt':
            subprocess.check_output(['chmod', config.EXTRACTION_FILES_MASK, '-R', new_path])
        # Handle new path.
        if is_file:
            process_file(new_path)
        else:
            extract_all(new_path)
            # Perform cleanup only if at least one file was processed successfully. Otherwise, there was a problem.
            if process_directory(new_path) > 0:
                cleanup(new_path)
    except OSError as ex:
        logger.exception('Failed to {} {}: {}'.format(handler.__name__, torrent_path, ex))
    logger.info('Done!')


def expand_torrent_from_transmission():
    """
    Expand a torrent when called directly from transmission (by using environment variables).
    """
    torrent_path = get_environment_variables_from_transmission()
    expand_torrent(torrent_path)


def main():
    """
    This function is designed to be called from command line.
    If an argument (either as the full path, or as a base dir and a file) is provided,
    the script will try to expand it.
    Else, we assume transmission is calling the script.
    """
    with logbook.NestedSetup(_get_log_handlers()).applicationbound():
        logger.info('Py-expander started!')
        try:
            # Set subliminal cache first.
            if config.SHOULD_FIND_SUBTITLES:
                logger.debug('Setting subtitles cache...')
                configure_subtitles_cache()
            # Parse input arguments.
            if len(sys.argv) == 3:
                directory = sys.argv[1]
                filename = sys.argv[2]
                if directory == config.DEFAULT_PATH:
                    torrent_path = os.path.join(directory, filename)
                    logger.info('Input is a file: {}'.format(torrent_path))
                else:
                    torrent_path = directory
                    logger.info('Input is a dir: {}'.format(torrent_path))
                expand_torrent(torrent_path)
            elif len(sys.argv) == 2:
                expand_torrent(sys.argv[1])
            else:
                expand_torrent_from_transmission()
        except:
            logger.exception('Critical exception occurred!')
            raise


if __name__ == '__main__':
    main()
