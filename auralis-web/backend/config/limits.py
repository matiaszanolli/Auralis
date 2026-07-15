"""Centralised request/upload limits (#4033).

Single source of truth for the size and count caps enforced across the upload
routers. Previously ``_MAX_UPLOAD_BYTES`` was defined independently in
``routers/files.py`` and ``routers/processing_api.py`` (and ``_MAX_UPLOAD_FILES``
lived only in ``files.py``), so an ops/security change to a cap required editing
multiple files with no enforcement that they stayed in sync.
"""

# Maximum bytes accepted for a single uploaded file (500 MB). Enforced by
# reading at most MAX_UPLOAD_BYTES + 1 and rejecting on overflow (#2248, #3494).
MAX_UPLOAD_BYTES: int = 500 * 1024 * 1024

# Maximum number of files accepted in one multipart upload request (#4349).
MAX_UPLOAD_FILES: int = 200
