"""
Enhancement and mastering-recommendation payloads — wire payload contracts for backend WebSocket broadcasts (#6269).

Part of the ``websocket/outbound/`` payload split of ``outbound_messages.py``;
:func:`websocket.outbound_messages.broadcast_typed` and its overloads remain
the single broadcast entry point that ties these TypedDicts to their message
discriminators.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import NotRequired, TypedDict

from schemas import EnhancementPresetLiteral as EnhancementPreset

class EnhancementSettingsChangedPayload(TypedDict):
    enabled: bool
    preset: EnhancementPreset
    intensity: float


class WeightedProfilePayload(TypedDict):
    profile_id: str
    profile_name: str
    weight: float


class AlternativeProfilePayload(TypedDict):
    # The keys MasteringRecommendation.to_dict() emits (#5981); no confidence per alternative.
    id: str
    name: str


class MasteringRecommendationPayload(TypedDict):
    track_id: int
    primary_profile_id: str
    primary_profile_name: str
    confidence_score: float
    predicted_loudness_change: float
    predicted_crest_change: float
    predicted_centroid_change: float
    weighted_profiles: NotRequired[list[WeightedProfilePayload]]
    reasoning: str
    is_hybrid: bool
    alternative_profiles: NotRequired[list[AlternativeProfilePayload]]
    created: NotRequired[str]
