import babelfish

# Directories settings.
DATA_PATH = '/data/directory'
DEFAULT_PATH = '/'
# Cloud directories settings.
CLOUD_ENCRYPTED_PATH = 'Encrypted'
CLOUD_PLAIN_PATH = 'Media'
CLOUD_TV_PATH = 'TV'
CLOUD_MOVIES_PATH = 'Movies'
CLOUD_KIDS_PATH = 'Kids'
CLOUD_UFC_PATH = 'UFC'
CLOUD_VIDEOS_PATH = 'Videos'

# Post-process settings.
SHOULD_DELETE = True

# Log settings.
LOGFILE = '/var/log/pyexp.log'
ORIGINAL_NAMES_LOG = '/var/log/original_names.log'

# Extraction settings.
EXTRACTION_FILES_MASK = '770'
EXTRACTION_TEMP_DIR_NAME = '_extracted'
EXTRACTION_EXECUTABLE = '7z'

# Subtitle settings.
SHOULD_FIND_SUBTITLES = True
# A map between each language and its favorite Subliminal providers (None for all providers).
LANGUAGES_MAP = {
    babelfish.Language('heb'): ['wizdom', 'cinemast'],
    babelfish.Language('eng'): []
}
# A map between each provider and its credentials.
PROVIDER_CONFIGS = {
    'cinemast': {
        'username': 'subliminal@gmail.com',
        'password': 'subliminal'
    }
}

# Upload settings.
SHOULD_UPLOAD = True
MAX_UPLOAD_TRIES = 3
RCLONE_PATH = '/usr/bin/rclone'
RCLONE_CONFIG_PATH = '/rclone/config/path.conf'
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
EXTENSIONS_WHITE_LIST = ['.srt', '.mkv', '.avi', '.mp4', '.m4v', '.wmv', '.mpg']
NAMES_BLACK_LIST = ['sample']
