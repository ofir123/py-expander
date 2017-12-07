from copy import deepcopy
import datetime
import os

import babelfish
import logbook
import subliminal
from subliminal.cache import region
from subliminal.cli import dirs, cache_file, MutexLock
from subliminal.subtitle import get_subtitle_path

from .config import LANGUAGES_MAP, PROVIDER_CONFIGS, LANGUAGE_EXTENSIONS, SUBTITLES_EXTENSIONS, \
    DEFAULT_LANGUAGE_EXTENSION

logger = logbook.Logger('subtitles')


def find_file_subtitles(path):
    """
    Finds subtitles for the given video file path.

    :param path: The path of the video file to find subtitles to.
    :return: The list of subtitles file paths, or None if a problem occurred.
    """
    results_list = []
    # We don't want to mess with the original map.
    languages_map = deepcopy(LANGUAGES_MAP)
    # Check for existing subtitle files first.
    logger.debug('Checking for existing subtitles for file: {}'.format(path))
    video_name = os.path.splitext(os.path.basename(path))[0]
    for file_name, file_extension in [os.path.splitext(p) for p in os.listdir(os.path.dirname(path))]:
        if file_extension in SUBTITLES_EXTENSIONS:
            file_name, language_extension = os.path.splitext(file_name)
            # Switch empty extension with default one.
            if not language_extension:
                language_extension = DEFAULT_LANGUAGE_EXTENSION
            if file_name == video_name and language_extension in LANGUAGE_EXTENSIONS:
                language = babelfish.Language.fromalpha2(language_extension.strip('.'))
                if language in languages_map:
                    subtitles_path = os.path.join(os.path.dirname(path), file_name + file_extension)
                    languages_map.pop(language)
                    results_list.append(subtitles_path)
                    logger.info('Found existing subtitles ({}) file: {}'.format(language, subtitles_path))
    if not languages_map:
        return results_list
    # Get new ones if needed.
    logger.info('Searching subtitles for file: {}'.format(path))
    try:
        # Get required video information.
        video = subliminal.scan_video(path)
        other_languages = []
        subtitle_results = []
        for language, providers in languages_map.items():
            # Filter providers the user didn't ask for.
            if not providers:
                other_languages.append(language)
            else:
                current_result = subliminal.download_best_subtitles(
                    {video}, languages={language}, providers=providers, provider_configs=PROVIDER_CONFIGS).values()
                if len(current_result) > 0:
                    subtitle_results.extend(list(current_result)[0])
        # Download all other languages.
        for language in other_languages:
            current_result = subliminal.download_best_subtitles(
                {video}, languages={language}, provider_configs=PROVIDER_CONFIGS).values()
            if len(current_result) > 0:
                subtitle_results.extend(list(current_result)[0])
        # Handle results.
        if len(subtitle_results) == 0:
            logger.info('No subtitles were found. Moving on...')
        else:
            logger.info('Found {} subtitles. Saving files...'.format(len(subtitle_results)))
            # Save subtitles alongside the video file.
            for subtitles in subtitle_results:
                # Filter empty subtitles files.
                if subtitles.content is None:
                    logger.debug('Skipping subtitle {}: no content'.format(subtitles))
                    continue
                subtitles_path = get_subtitle_path(video.name, subtitles.language)
                logger.info('Saving {} to: {}'.format(subtitles, subtitles_path))
                open(subtitles_path, 'wb').write(subtitles.content)
                results_list.append(subtitles_path)
            return results_list
    except ValueError:
        # Subliminal raises a ValueError if the given file is not a video file.
        logger.info('Not a video file. Moving on...')
        return []
    except Exception:
        # Subliminal crashes randomly sometimes.
        logger.exception('Error while searching for subtitles. Moving on...')
        return []


def configure_subtitles_cache():
    """
    Configure the subliminal cache settings.
    Should be called once when the program starts.
    """
    # Configure the subliminal cache.
    cache_dir = dirs.user_cache_dir
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    cache_file_path = os.path.join(cache_dir, cache_file)
    region.configure('dogpile.cache.dbm', expiration_time=datetime.timedelta(days=30),
                     arguments={'filename': cache_file_path, 'lock_factory': MutexLock})
