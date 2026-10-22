"""
Enhancement router request/response bodies (split from enhancement.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel, field_validator
from schemas import EnhancementIntensity, EnhancementPresetLiteral
from typing import Any


class ToggleEnhancementRequest(BaseModel):
    enabled: bool


class SetPresetRequest(BaseModel):
    # Lowercase before validation; Literal still enforces canonical form.
    preset: EnhancementPresetLiteral

    @field_validator('preset', mode='before')
    @classmethod
    def lowercase_preset(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v


class SetIntensityRequest(BaseModel):
    # Shared constraint (#4600). This used to silently clamp and return 200 with
    # a value the caller never sent, while PUT /api/settings 422'd the same
    # input. Worse, `max(0.0, min(1.0, nan))` is `1.0` — a NaN intensity became
    # MAXIMUM enhancement in the runtime settings dict rather than an error.
    # Both REST surfaces now share one definition, as `preset` already does.
    intensity: EnhancementIntensity


class EnhancementSettings(BaseModel):
    """Current enhancement settings.

    #4424 made ``EnhancementPresetLiteral`` the single source of truth and
    migrated the request side; the response side kept a bare ``str`` until
    #4710. That mattered because the frontend narrows on the same closed union
    (``EnhancementSettingsChangedMessage.data.preset``), so a non-canonical
    value serialized straight through and dropped the enhancement UI out of
    its switch — and OpenAPI advertised a free-form string for a closed enum.
    """
    enabled: bool
    preset: EnhancementPresetLiteral
    # EnhancementIntensity carries the canonical ge=0.0/le=1.0 bound (#4600),
    # which also rejects NaN and ±inf for free.
    intensity: EnhancementIntensity


class EnhancementSettingsResponse(BaseModel):
    """Response for enhancement mutation endpoints."""
    message: str
    settings: EnhancementSettings
