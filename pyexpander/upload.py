import os
import subprocess
import shutil
import random
import string

import logbook
from guessit import guessit
from showsformatter import format_show

from . import config

logger = logbook.Logger('uploader')


def _encrypt(encrypted_dir, plain_dir):
    """
    Encrypt the given plain directory.

    :param encrypted_dir: The encrypted directory to create.
    :param plain_dir: The plain directory to encrypt (recursively).
    :return: True if succeeded, and False otherwise.
    """
    logger.info('Encrypting directory tree...')
    # Verify config environment variable first.
    if not os.environ.get(config.ENCFS_ENVIRONMENT_VARIABLE):
        logger.info('{} environment variable is not defined. Defining: {}'.format(
            config.ENCFS_ENVIRONMENT_VARIABLE, config.ENCFS_CONFIG_PATH))
        os.environ[config.ENCFS_ENVIRONMENT_VARIABLE] = config.ENCFS_CONFIG_PATH
    # Encrypt!
    os.makedirs(encrypted_dir)
    return_code = subprocess.call('echo {} | {} -S "{}" "{}"'.format(
        config.ENCFS_PASSWORD, config.ENCFS_PATH, encrypted_dir, plain_dir), shell=True)
    if return_code != 0:
        logger.error('Bad return code ({}) for encryption. Stopping!'.format(return_code))
        return False
    return True


def _extract_ufc_path(file_name):
    """
    Extract UFC cloud dir and cloud file name from the given file name.

    :param file_name: The file name to extract data from.
    :return: A tuple of format (cloud_dir, cloud_file)
    """
    guess_results = guessit(file_name)

    # Get real episode number.
    episode_num = guess_results.get('episode')
    if not episode_num:
        return False
    season = guess_results.get('season')
    if season:
        episode_num += 100 * season

    # Get title.
    lowercase_file_name = file_name.lower()
    if 'fox' in lowercase_file_name:
        title = 'UFC On FOX'
    elif 'fight' in lowercase_file_name and 'night' in lowercase_file_name:
        title = 'UFC Fight Night'
    else:
        title = 'UFC'

    cloud_dir = os.path.join(config.CLOUD_UFC_PATH, '{} {}'.format(title, episode_num))
    cloud_file = '{} {}'.format(title, episode_num)
    if 'prelim' in lowercase_file_name:
        cloud_file += ' - Preliminaries'
    return cloud_dir, cloud_file


def _extract_masterclass_path(file_name):
    """
    Extract Masterclass cloud dir and cloud file name from the given file name.

    :param file_name: The file name to extract data from.
    :return: A tuple of format (cloud_dir, cloud_file)
    """
    cloud_dir = config.CLOUD_VIDEOS_PATH
    cloud_file = os.path.splitext(file_name)[0]
    return cloud_dir, cloud_file


def _guess_path(file_name):
    """
    Guess cloud dir and cloud file name from the given file name.

    :param file_name: The file name to guess on.
    :return: A tuple of format (cloud_dir, cloud_file)
    """
    cloud_dir = None
    cloud_file = None
    # Start guessing!
    guess_results = guessit(file_name)
    video_type = guess_results.get('type')
    title = guess_results.get('title')
    if isinstance(title, list):
        title = title[0]
    if video_type == 'episode' and title:
        # Translate show title if needed.
        title = format_show(title)
        season = guess_results.get('season')
        # Skip rare cases of weird episodes names.
        if season and not isinstance(season, list):
            episode = guess_results.get('episode')
            if episode:
                # Dirs that end with . are evil!
                fixed_dir_name = title.rstrip('.')
                cloud_dir = os.path.join(config.CLOUD_TV_PATH, fixed_dir_name, 'Season {:02d}'.format(season))
                if isinstance(episode, list):
                    episode_str = 'E{:02d}-E{:02d}'.format(episode[0], episode[-1])
                else:
                    episode_str = 'E{:02d}'.format(episode)
                cloud_file = '{} - S{:02d}{}'.format(title, season, episode_str)
    elif video_type == 'movie' and title:
        # Make sure every word starts with a capital letter.
        title = title.title()
        year = guess_results.get('year')
        if year:
            cloud_dir = os.path.join(config.CLOUD_MOVIES_PATH, '{} ({})'.format(title, year))
            cloud_file = '{} ({})'.format(title, year)
    return cloud_dir, cloud_file


def upload_file(file_path):
    """
    Upload the given file to its proper Google Drive directory.

    :param: file_path: The file to upload.
    :return: True if the file was upload successfully, and False otherwise.
    """
    logger.info('Uploading file: {}'.format(file_path))
    fixed_file_path = file_path
    file_parts = os.path.splitext(file_path)

    # Verify file name.
    if len(file_parts) != 2:
        logger.info('File has no extension! Skipping...')
        return False
    file_name, file_extension = file_parts
    if file_extension not in config.EXTENSIONS_WHITE_LIST:
        logger.info('File extension is not in white list! Skipping...')
        return False
    for black_list_word in config.NAMES_BLACK_LIST:
        if black_list_word in file_name.lower():
            logger.info('File name contains a black listed word ({})! Skipping...'.format(black_list_word))
            return False
    language_extension = None
    is_subtitles = file_extension in config.SUBTITLES_EXTENSIONS

    # Fake extension for subtitles in order to help guessit.
    if is_subtitles:
        # Remove language extensions if needed.
        file_parts = os.path.splitext(file_name)
        if len(file_parts) == 2:
            fixed_file_name, language_extension = file_parts
            if language_extension in config.LANGUAGE_EXTENSIONS:
                fixed_file_path = fixed_file_name + config.DEFAULT_VIDEO_EXTENSION
            else:
                language_extension = config.DEFAULT_LANGUAGE_EXTENSION
                fixed_file_path = file_name + config.DEFAULT_VIDEO_EXTENSION

    # Create cloud path based on guessit results.
    fixed_file_name = os.path.basename(fixed_file_path)
    # Remove brackets group name prefix.
    if fixed_file_name.startswith('[') and ']' in fixed_file_name:
        fixed_file_name = fixed_file_name.split(']', 1)[1]

    if 'ufc' in fixed_file_name.lower():
        cloud_dir, cloud_file = _extract_ufc_path(fixed_file_name)
    elif 'masterclass' in fixed_file_name.lower():
        cloud_dir, cloud_file = _extract_masterclass_path(fixed_file_name)
    else:
        cloud_dir, cloud_file = _guess_path(fixed_file_name)

    if cloud_dir and cloud_file:
        if language_extension:
            cloud_file += language_extension
        cloud_file += file_extension
        logger.info('Cloud path: {}'.format(os.path.join(cloud_dir, cloud_file)))
        # Create a temporary random cloud dir structure.
        original_dir = os.path.dirname(file_path)
        random_dir_name = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        base_dir = os.path.join(original_dir, random_dir_name)
        plain_base_dir = os.path.join(base_dir, config.CLOUD_PLAIN_PATH)
        os.makedirs(plain_base_dir)
        cloud_temp_path = os.path.join(plain_base_dir, cloud_dir)
        final_file_path = os.path.join(cloud_temp_path, cloud_file)
        # Use the plain directory when uploading, unless encryption is enabled.
        upload_base_dir = plain_base_dir
        # Set up encryption if needed.
        if config.SHOULD_ENCRYPT:
            encrypted_base_dir = os.path.join(base_dir, config.CLOUD_ENCRYPTED_PATH)
            encryption_successful = _encrypt(encrypted_base_dir, plain_base_dir)
            if not encryption_successful:
                # Delete directories and stop.
                shutil.rmtree(base_dir)
                return False
            # Upload the encrypted directory tree instead of the plain one.
            upload_base_dir = encrypted_base_dir
        gdrive_dir = upload_base_dir.split(base_dir)[1].strip(os.path.sep)
        logger.info('Moving file to temporary path: {}'.format(cloud_temp_path))
        os.makedirs(cloud_temp_path)
        shutil.move(file_path, cloud_temp_path)
        os.rename(os.path.join(cloud_temp_path, os.path.basename(file_path)), final_file_path)

        # Upload!
        upload_tries = 0
        return_code = 1
        while return_code != 0 and upload_tries < config.MAX_UPLOAD_TRIES:
            logger.info('Uploading file...')
            upload_tries += 1
            return_code = subprocess.call('{} --config {} copyto "{}" "GDrive:{}"'.format(
                config.RCLONE_PATH, config.RCLONE_CONFIG_PATH, upload_base_dir, gdrive_dir), shell=True)
            # Check results.
            if return_code != 0:
                logger.error('Bad return code ({}) for file: {}'.format(return_code, cloud_file))
                if upload_tries < config.MAX_UPLOAD_TRIES:
                    logger.info('Trying again!')
                else:
                    logger.error('Max retries with no success! Skipping...')
        # If everything went smoothly, add the file name to the original names log.
        if return_code == 0:
            upload_succeeded = True
            logger.info('Upload succeeded! Deleting original file...')
            if not is_subtitles:
                open(config.ORIGINAL_NAMES_LOG, 'a', encoding='UTF-8').write(file_path + '\n')
        else:
            upload_succeeded = False
            # Reverse everything.
            logger.info('Upload failed! Reversing all changes...')
            shutil.move(final_file_path, original_dir)
            os.rename(os.path.join(original_dir, cloud_file), file_path)
        # Unmount ENCFS directory.
        if config.SHOULD_ENCRYPT:
            subprocess.call('{} -u "{}"'.format(config.FUSERMOUNT_PATH, plain_base_dir), shell=True)
        # Delete all temporary directories.
        shutil.rmtree(base_dir)
        return upload_succeeded
    else:
        logger.info('Couldn\'t guess file info. Skipping...')
        return False
