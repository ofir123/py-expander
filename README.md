# py-expander

Post-process completed Transmission or uTorrent downloads: stage the files,
extract nested archives with 7-Zip, find subtitles, and upload media to the
configured Google Drive library with rclone. Optional EncFS encryption and the
existing TV, movie, Hebrew-dubbed, UFC, and Masterclass naming rules are retained.

Requires **Python 3.10 or newer**. The application uses ordinary typed functions,
pathlib, standard logging, and an argparse command line.

## Install

Use an isolated environment. For Hebrew subtitles, install the tested Subliminal
fork with Wizdom support, then shows-formatter and py-expander:

~~~sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --no-cache-dir "git+https://github.com/ofir123/subliminal.git@1b70f0d8b8c03eb63fbe5f3d5e7547a5083257fd"
python -m pip install "git+https://github.com/ofir123/shows-formatter.git"
python -m pip install -e ".[dev]"
~~~

For sibling checkouts, the equivalent development install is:

~~~sh
python -m pip install -e ../subliminal -e ../shows-formatter -e ".[dev]"
~~~

On Windows, activate with .venv\Scripts\activate. Installing the upstream PyPI
Subliminal package alone does not provide Wizdom. Startup explains any configured
providers that are missing.

7-Zip with RAR support is needed for archives. Uploads need rclone and its remote
named GDrive. EncFS and an unmount executable are needed when encryption is enabled.
Executable paths and remote library names remain in pyexpander/config.py.

## Use

~~~sh
pyexpand --help
pyexpand --version
pyexpand /downloads/The.Wire.S01E01
pyexpand --verbose /downloads/Man.of.Steel.2013.mkv
python -m pyexpander /downloads/The.Wire.S01E01
~~~

Configure Transmission to run the installed console script:

~~~json
{
  "script-torrent-done-enabled": true,
  "script-torrent-done-filename": "/absolute/path/to/.venv/bin/pyexpand"
}
~~~

With no positional arguments, pyexpand reads TR_TORRENT_DIR and TR_TORRENT_NAME.
The legacy two-argument uTorrent form remains supported:

~~~text
pyexpand "%D" "%F"
~~~

When the first argument equals DEFAULT_PATH, it is joined to the filename.
Otherwise the first argument is treated as the completed directory. Direct-file
hooks also remain available after installing in the same Python environment:

~~~sh
python /absolute/path/to/pyexpander/torrent_handler.py --help
~~~

Exit status is 0 for successful processing and 1 for failed processing.
Argument errors use argparse's standard status 2. Help/version do not open log
files, configure the cache, or start a torrent job.

## Configuration and recovery

Your existing pyexpander/config.py values are retained. Review the paths,
language/provider preferences, and upload/encryption settings for your runtime.

- DATA_PATH must be separate from the download directory. Existing staging
  destinations are rejected so a retry cannot overwrite an earlier failed job.
- With SHOULD_DELETE and SHOULD_WIPE_CONTENT both false, source downloads are
  copied and retained for seeding. SHOULD_DELETE moves the source instead.
  With SHOULD_DELETE false and SHOULD_WIPE_CONTENT true, the original torrent
  tree is deliberately replaced with zero-byte placeholders. The configured
  FINISHED_UPLOAD_PREFIX also marks downloads for placeholder recreation.
- Videos are processed before sidecars. Existing Hebrew/English files are reused;
  each missing language is searched independently. Subtitles are saved with
  language suffixes such as .he.srt and .en.srt.
- Successful uploads consume the staged files. Failed commands/retries restore
  the original staged filename. If restoration or unmounting fails, the
  .pyexpand-* upload workspace is retained and its location is logged.
- Extraction cleanup preserves remaining media and every retained upload
  workspace, including opaque encrypted recovery data.
- Standard logging writes to the console and rotating LOGFILE when configured.
  ORIGINAL_NAMES_LOG retains the release paths needed by the subtitle monitor.

The DBM subtitle cache now belongs to py-expander's platform cache directory
(typically ~/.cache/pyexpander on Linux). It starts fresh rather than sharing
Subliminal CLI internals. File locks coordinate threads and separate hook
processes. A staging lock also serializes jobs with the same torrent name.
Lock files are coordination metadata; do not delete them while jobs are running.

## Development

~~~sh
python -m pytest
python -m pytest --cov=pyexpander --cov-report=term-missing
ruff check .
ruff format --check .
mypy pyexpander
python -m build
~~~

Tests use temporary files and fake external tools. They cover staging, naming,
multipart archives, subtitle preservation, upload rollback, encryption recovery,
CLI hooks, and cross-process cache locks. They do not run production uploads.
CI runs on Linux and Windows with Python 3.10, 3.12, and 3.14.

For a live Hebrew smoke check, use a disposable video copy and call
find_file_subtitles with only the desired language enabled; it writes sidecars
but does not invoke the uploader. Verify that the chosen release matches your
actual video before relying on audiovisual synchronization.
