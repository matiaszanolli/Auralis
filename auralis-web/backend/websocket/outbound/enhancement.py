"""
Enhancement payloads — wire payload contracts for backend WebSocket broadcasts (#6269).

Part of the ``websocket/outbound/`` payload split of ``outbound_messages.py``;
:func:`websocket.outbound_messages.broadcast_typed` and its overloads remain
the single broadcast entry point that ties these TypedDicts to their message
discriminators.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import TypedDict

from schemas import EnhancementPresetLiteral as EnhancementPreset

class EnhancementSettingsChangedPayload(TypedDict):
    enabled: bool
    preset: EnhancementPreset
    intensity: float
