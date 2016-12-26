import babelfish

# Directories settings.
TV_PATH = '/tv/directory'
MOVIE_PATH = '/movies/directory'
APP_PATH = '/apps/directory'
MUSIC_PATH = '/music/directory'
DEFAULT_PATH = '/'

# Log settings.
LOGFILE = '/var/log/pyexp.log'

# Extraction settings.
EXTRACTION_FILES_MASK = '770'
EXTRACTION_TEMP_DIR_NAME = '_extracted'
EXTRACTION_EXECUTABLE = '7z'

# Subtitle settings.
SHOULD_FIND_SUBTITLES = True
# A map between each language and its favorite subliminal providers (None for all providers).
LANGUAGES_MAP = {
    babelfish.Language('heb'): ['subscenter'],
    babelfish.Language('eng'): []
}

# Upload settings.
SHOULD_UPLOAD = True
MAX_UPLOAD_TRIES = 3
ACD_CLI_PATH = '/usr/bin/acd_cli'
DEFAULT_VIDEO_EXTENSION = '.mkv'
DEFAULT_LANGUAGE_EXTENSION = '.en'
SUBTITLES_EXTENSIONS = ['.srt']
LANGUAGE_EXTENSIONS = ['.he', '.en']
# Lists.
EXTENSIONS_WHITE_LIST = ['.srt', '.mkv', '.avi', '.mp4', '.mov', '.m4v', '.wmv']
NAMES_BLACK_LIST = ['sample']
# Directories settings.
AMAZON_TV_PATH = '/amazon/tv/path'
AMAZON_MOVIE_PATH = '/amazon/movies/path'
ORIGINAL_NAMES_LOG = '/var/log/original_names.log'
