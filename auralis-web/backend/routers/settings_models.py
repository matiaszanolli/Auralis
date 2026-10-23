"""
Settings router bodies and the enhancement-settings field list (split from settings.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from pydantic import BaseModel, ConfigDict, Field, field_validator
from schemas import DEFAULT_PRESET, EnhancementIntensity, EnhancementPresetLiteral
import math

logger = logging.getLogger(__name__)


# Fields that also live in the runtime `enhancement_settings` dict (#4409),
# under different names (see seed_enhancement_settings). A PUT that touches
# any of these must re-seed the live dict and broadcast — otherwise a
# Settings-dialog save only takes effect at the next backend restart (#4587).
_ENHANCEMENT_SETTINGS_FIELDS = frozenset({
    'default_preset', 'auto_enhance', 'enhancement_intensity',
})


class _ScanFolderRequest(BaseModel):
    folder: str


class SettingsUpdateRequest(BaseModel):
    """Typed, validated body for ``PUT /api/settings`` (#3837 / BE-SCH-2).

    Every field is optional so the endpoint remains a partial update. ``extra='forbid'``
    turns a misspelled field name into a 422 instead of a silent no-op (the
    SettingsRepository whitelist would otherwise drop unknown keys without complaint).
    Field set mirrors ``SettingsRepository.update_settings`` whitelist plus the
    separately-handled ``scan_folders`` (JSON) and ``file_types`` (CSV) columns.
    """

    model_config = ConfigDict(extra="forbid")

    # Library
    scan_folders: list[str] | None = None
    file_types: list[str] | None = None
    auto_scan: bool | None = None
    scan_interval: int | None = Field(default=None, ge=0)
    # Playback
    crossfade_enabled: bool | None = None
    crossfade_duration: float | None = Field(default=None, ge=0)
    gapless_enabled: bool | None = None
    replay_gain_enabled: bool | None = None
    # 0.0-1.0, NOT the 0-100 scale used by SetVolumeRequest and PlayerState
    # (#4711). Two different scales share the field name across this API; the
    # persisted UserSettings.volume column is normalised (default 0.8), so the
    # scale is stated here rather than renamed — a rename would need a column
    # migration and a stored 0.8 misread as 0-100 is near-silent.
    volume: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Default playback volume, normalised 0.0-1.0. Note this is "
                    "NOT the 0-100 scale used by POST /api/player/volume.",
    )
    # Audio output
    output_device: str | None = None
    bit_depth: int | None = None
    sample_rate: int | None = Field(default=None, gt=0)
    # Interface
    theme: str | None = None
    language: str | None = None
    show_visualizations: bool | None = None
    mini_player_on_close: bool | None = None
    # Enhancement
    # Constrained to the shared preset enum so an invalid value 422s at the
    # boundary instead of silently falling back to adaptive downstream (#4424).
    default_preset: EnhancementPresetLiteral | None = None
    auto_enhance: bool | None = None
    # Shared constraint (#4600) — same definition the enhancement router uses,
    # so the two cannot drift back apart.
    enhancement_intensity: EnhancementIntensity | None = None
    # Advanced
    cache_size: int | None = Field(default=None, ge=0)
    max_concurrent_scans: int | None = Field(default=None, ge=1)
    enable_analytics: bool | None = None
    debug_mode: bool | None = None


class SettingsResponse(BaseModel):
    """Response shape for settings endpoints (mirrors ``UserSettings.to_dict()``).

    ``extra='allow'`` keeps forward-compatibility with the dict the repository emits
    (e.g. ``id`` / ``created_at`` / ``updated_at``) without having to enumerate them.
    """

    model_config = ConfigDict(extra="allow")

    scan_folders: list[str] = Field(default_factory=list)
    file_types: list[str] = Field(default_factory=list)
    auto_scan: bool | None = None
    scan_interval: int | None = None
    crossfade_enabled: bool | None = None
    crossfade_duration: float | None = None
    gapless_enabled: bool | None = None
    replay_gain_enabled: bool | None = None
    # Same normalised 0.0-1.0 scale as SettingsUpdateRequest.volume, and
    # bounded identically (#4711) — it was unconstrained `float | None`, so
    # the scale was enforced on the way in but not on the way out.
    volume: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Default playback volume, normalised 0.0-1.0. Note this is "
                    "NOT the 0-100 scale used by POST /api/player/volume.",
    )
    output_device: str | None = None
    bit_depth: int | None = None
    sample_rate: int | None = None
    theme: str | None = None
    language: str | None = None
    show_visualizations: bool | None = None
    mini_player_on_close: bool | None = None
    # #4647: these mirror SettingsUpdateRequest's constraints, so OpenAPI
    # advertises the same closed preset enum and 0.0-1.0 intensity on the way
    # out as on the way in. The preset is always set (schema v23 normalized
    # every row, #5824); the intensity validator below keeps a hand-edited
    # out-of-range row from turning into a response-validation 500 on
    # GET /api/settings.
    default_preset: EnhancementPresetLiteral = DEFAULT_PRESET
    auto_enhance: bool | None = None
    enhancement_intensity: EnhancementIntensity | None = None
    cache_size: int | None = None
    max_concurrent_scans: int | None = None
    enable_analytics: bool | None = None
    debug_mode: bool | None = None

    @field_validator("enhancement_intensity", mode="before")
    @classmethod
    def _degrade_invalid_intensity(cls, value: object) -> object:
        if value is None:
            return None
        try:
            as_float = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            as_float = math.nan
        if isinstance(value, bool) or not math.isfinite(as_float) or not 0.0 <= as_float <= 1.0:
            logger.warning(
                f"Stored enhancement_intensity {value!r} is outside 0.0-1.0; "
                "reporting it as null"
            )
            return None
        return as_float


class SettingsUpdateResponse(BaseModel):
    """Envelope returned by mutating settings endpoints."""

    model_config = ConfigDict(extra="forbid")

    message: str
    settings: SettingsResponse
