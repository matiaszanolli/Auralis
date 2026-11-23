"""
Sidecar signatures: only a ``.25d`` file this installation wrote is trusted (#6522).

A sidecar lives beside the audio, so a music folder from somewhere else (a
downloaded archive, a shared drive) can ship one. Every field it is checked
against (versions, the audio's size and mtime, the 25 values) is chosen by
whoever wrote it, so a crafted sidecar with plausible values used to be stored
as this track's fingerprint, steering its mastering, similarity and the
reference cloud. A content digest of the audio would not help: the folder's
author can compute it too.

Each sidecar now carries an HMAC-SHA256, under a per-installation key kept
owner-only in the data directory, of its canonical JSON. A sidecar without a
valid one, whether foreign or written before this check, is ignored and the
track is re-analysed, which writes a signed sidecar in its place.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import hashlib
import hmac
import json
import os
import secrets
import threading
from pathlib import Path
from typing import Any

from ..utils.logging import debug
from .data_dir import default_data_dir

KEY_FILENAME = "sidecar.key"
SIGNATURE_FIELD = "signature"
_KEY_BYTES = 32

_keys: dict[Path, bytes] = {}
_keys_lock = threading.Lock()


def _read_key(path: Path) -> bytes | None:
    try:
        key = path.read_bytes()
    except FileNotFoundError:
        return None
    return key if len(key) == _KEY_BYTES else None


def _create_key(path: Path) -> bytes:
    """Create the key owner-only; a concurrent creator's key wins, so every process agrees."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = secrets.token_bytes(_KEY_BYTES)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        existing = _read_key(path)
        if existing is not None:
            return existing
        # Present but unusable (truncated, foreign): replace it. Sidecars signed
        # with the old key are re-analysed once.
        temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
        os.replace(temp, path)
        return key
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key


def _key() -> bytes:
    path = default_data_dir() / KEY_FILENAME
    with _keys_lock:
        key = _keys.get(path)
        if key is None:
            key = _read_key(path) or _create_key(path)
            _keys[path] = key
        return key


def _digest(data: dict[str, Any]) -> str:
    payload = {k: v for k, v in data.items() if k != SIGNATURE_FIELD}
    # allow_nan: a NaN written as JSON's NaN token round-trips to the same canonical text, so the
    # signature stays total; the value checks after it refuse non-finite dimensions.
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(_key(), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_sidecar(data: dict[str, Any]) -> dict[str, Any]:
    """``data`` with its signature added (a signature already in it is replaced)."""
    return {**data, SIGNATURE_FIELD: _digest(data)}


def sidecar_signed_here(data: dict[str, Any]) -> bool:
    """True if ``data`` carries this installation's signature over exactly its contents."""
    signature = data.get(SIGNATURE_FIELD)
    try:
        if isinstance(signature, str) and hmac.compare_digest(signature, _digest(data)):
            return True
    except (TypeError, ValueError):  # a non-ASCII "signature", or a value json cannot encode
        pass
    debug("Sidecar was not written by this installation; the track will be re-analysed")
    return False
