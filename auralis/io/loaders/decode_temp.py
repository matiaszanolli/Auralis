"""Name of the intermediate WAV FFmpeg decodes into when no temp folder is given.

A SIGKILL or OOM kill mid-decode leaves the file behind, so the backend's startup sweep
(config/startup/decode_temps.py) globs this exact prefix and removes the ones old enough not to be a
live decode (#5734).
"""

DECODE_TEMP_PREFIX = 'auralis_decode_'
