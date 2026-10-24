"""
Metadata router dependency plumbing, field mapping and path validation (split from metadata.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.library.metadata_editor import MetadataEditor
from collections.abc import Callable
from security.path_security import PathMissingError, PathValidationError, validate_file_path
from typing import Any

from .dependencies import RouterDeps, require_service
from .errors import BadRequestError, NotFoundError


# MetadataUpdateRequest fields whose Pydantic name is a mutagen tag name, not
# the Track DB column name (#4731). ``comment`` doubles as the file-tag name
# in write_metadata's tag dict and only diverges for the DB column.
_METADATA_FIELD_TO_COLUMN: dict[str, str] = {
    'track': 'track_number',
    'disc': 'disc_number',
    'comment': 'comments',
}


def _tag_dict_to_db_columns(tag_updates: dict[str, Any]) -> dict[str, Any]:
    """Translate a mutagen-tag-keyed update dict to Track DB column names.

    ``write_metadata`` needs the tag-named keys (``track``, ``disc``,
    ``comment``) verbatim; the repository's writable-columns allowlist is
    keyed on DB column names (``track_number``, ``disc_number``,
    ``comments``), so passing the tag-named dict straight through silently
    drops those three fields (#4731). Fields with no DB column (``artist``,
    ``album``, ``genre``, ...) pass through unchanged here and are dropped
    downstream by the repository's own allowlist — they're file-only tags,
    not a translation gap.
    """
    return {_METADATA_FIELD_TO_COLUMN.get(k, k): v for k, v in tag_updates.items()}


def _validate_track_filepath(track_id: int, filepath: Any) -> str:
    """Validate a DB-stored track filepath, mapping each failure class to its
    own HTTP status.

    #5080: all three single-track routes below used to collapse every
    ``PathValidationError`` into a 400, so a track whose file had been
    deleted, moved, or lives on an unplugged drive answered "Bad Request"
    instead of "Not Found" — indistinguishable, from the client's side, from a
    malformed path. ``validate_file_path()`` now raises the
    ``PathMissingError`` subclass for exactly the exists()/is_file() checks,
    which maps to 404 here; traversal/containment/unreadable rejections stay
    400.

    Both details are deliberately generic and path-free: ``PathValidationError``
    text names the resolved path and every allowed directory (#4807), and
    ``validate_file_path`` already logs the rejection once via
    ``_logs_rejections``, so nothing is lost by not reflecting it.
    """
    try:
        return str(validate_file_path(str(filepath)))
    except PathMissingError:
        raise NotFoundError(
            "Audio file", detail=f"Audio file not found for track {track_id}"
        )
    except PathValidationError:
        raise BadRequestError("Invalid track filepath")


class _MetadataDeps:
    def __init__(
        self,
        get_repository_factory: Callable[[], Any] = lambda: None,
        broadcast_manager: Any = None,
        metadata_editor: MetadataEditor | None = None,
    ) -> None:
        self.get_repository_factory = get_repository_factory
        self.broadcast_manager = broadcast_manager
        self.metadata_editor = metadata_editor


_deps = RouterDeps("metadata", _MetadataDeps())


def _get_repository_factory() -> Callable[[], Any]:
    return _deps.current().get_repository_factory


def _get_broadcast_manager() -> Any:
    return _deps.current().broadcast_manager


def _get_metadata_editor() -> MetadataEditor:
    metadata_editor = _deps.current().metadata_editor
    metadata_editor = require_service(metadata_editor, "Metadata editor")
    return metadata_editor
