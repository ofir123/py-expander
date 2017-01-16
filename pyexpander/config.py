import shutil

import babelfish

# Directories settings.
DATA_PATH = '/data/directory'
DEFAULT_PATH = '/'
# Cloud directories settings.
CLOUD_ENCRYPTED_PATH = 'Encrypted'
CLOUD_PLAIN_PATH = 'Media'
CLOUD_TV_PATH = 'TV'
CLOUD_MOVIE_PATH = 'Movies'

# Post-process settings.
# Change shutil.move to shutil.copy in order to preserve original downloads.
FILE_HANDLER = shutil.move

# Log settings.
LOGFILE = '/var/log/pyexp.log'
ORIGINAL_NAMES_LOG = '/var/log/original_names.log'

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
# encfs settings.
SHOULD_ENCRYPT = True
ENCFS_PATH = '/usr/bin/encfs'
FUSERMOUNT_PATH = '/usr/bin/fusermount'
ENCFS_ENVIRONMENT_VARIABLE = 'ENCFS6_CONFIG'
ENCFS_CONFIG_PATH = '/encfs6/config/path.xml'
ENCFS_PASSWORD = 'Password1'

# Lists.
EXTENSIONS_WHITE_LIST = ['.srt', '.mkv', '.avi', '.mp4', '.mov', '.m4v', '.wmv']
NAMES_BLACK_LIST = ['sample']
