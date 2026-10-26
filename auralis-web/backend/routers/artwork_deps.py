"""
Artwork router dependency plumbing and the artwork_updated broadcast (split from artwork.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, Literal
from websocket.outbound.library import ArtworkUpdatedPayload
from websocket.outbound_messages import broadcast_typed

from .dependencies import RouterDeps
from .repo_deps import RepositoryFactoryDeps


class _ArtworkDeps:
    def __init__(self, connection_manager: Any = None) -> None:
        self.connection_manager = connection_manager


_repo_deps = RepositoryFactoryDeps("artwork")
_deps = RouterDeps("artwork", _ArtworkDeps())


def _get_connection_manager() -> Any:
    return _deps.current().connection_manager


async def _broadcast_artwork_updated(
    connection_manager: Any,
    action: Literal["extracted", "downloaded", "deleted"],
    album_id: int,
    artwork_url: str | None = None,
) -> None:
    """Broadcast `artwork_updated` from the one place all three emit sites
    share, so the payload cannot drift out of sync with the frontend's
    ``ArtworkUpdatedMessage`` contract (types/ws/enhancement.ts:71-78, #4676).
    ``artwork_url`` is omitted for 'deleted', matching that contract's
    `artwork_url?: string; // absent for 'deleted'`.
    """
    data: ArtworkUpdatedPayload = {"action": action, "album_id": album_id}
    if artwork_url is not None:
        data["artwork_url"] = artwork_url
    await broadcast_typed(connection_manager, "artwork_updated", data)
