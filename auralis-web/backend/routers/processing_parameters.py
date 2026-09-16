"""
Processing Preset and Parameter Endpoints

GET /api/processing/presets and GET /api/processing/parameters. Split out of
routers/processing_api.py (#5472), whose create_processing_router()
registers them.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import Callable
from typing import Any

# The mastering engine's real preset definitions — the presets endpoint
# projects these rather than restating them (#5220).
from auralis.core.config.preset_profiles import PresetProfile, create_preset_profiles
from fastapi import Depends, HTTPException

from .processing_deps import _get_enhancement_settings

logger = logging.getLogger(__name__)

# GET /parameters placeholder values, returned (as a copy) until a live
# ChunkedAudioProcessor profile exists. `is_default: True` lets clients tell
# them from real measurements that happen to land on the same numbers (#3779).
_DEFAULT_PARAMETERS: dict[str, Any] = {
    "is_default": True,
    "spectral_balance": 0.5,
    "dynamic_range": 0.5,
    "energy_level": 0.5,
    "target_lufs": -14.0,
    "peak_target_db": -1.0,
    "bass_boost": 0.0,
    "air_boost": 0.0,
    "compression_amount": 0.0,
    "expansion_amount": 0.0,
    "stereo_width": 0.75,
}


def _preset_to_payload(profile: PresetProfile) -> dict[str, Any]:
    """Project a `PresetProfile` onto the public presets payload.

    Units are the profile's own: EQ gains and compressor/limiter thresholds in
    dB, attack/release in ms, ratio as N:1, blends and intensities in 0.0-1.0.
    """
    return {
        "name": profile.name,
        "description": profile.description,
        # Every profile is applied through the adaptive mastering path;
        # PresetProfile has no mode of its own.
        "mode": "adaptive",
        "settings": {
            "eq": {
                "enabled": profile.eq_blend > 0.0,
                "blend": profile.eq_blend,
                "low": profile.low_shelf_gain,
                "low_mid": profile.low_mid_gain,
                "mid": profile.mid_gain,
                "high_mid": profile.high_mid_gain,
                "high": profile.high_shelf_gain,
            },
            "dynamics": {
                "enabled": profile.dynamics_blend > 0.0,
                "blend": profile.dynamics_blend,
                "compressor": {
                    "threshold": profile.compression_threshold,
                    "ratio": profile.compression_ratio,
                    "attack": profile.compression_attack,
                    "release": profile.compression_release,
                },
                "limiter": {
                    "threshold": profile.limiter_threshold,
                    "release": profile.limiter_release,
                },
            },
            "level_matching": {
                "enabled": True,
                "target_lufs": profile.target_lufs,
                "peak_target_db": profile.peak_target_db,
            },
        },
    }


async def get_processing_presets() -> dict[str, Any]:
    """Get available processing presets.

    #5220: this used to return a hand-typed dict of presets whose EQ and
    compressor numbers were invented — unitless integers that matched nothing
    the mastering engine applies. The catalog is now projected from
    `create_preset_profiles()`, the same source `HybridProcessor` masters
    with, so the two cannot drift apart; today that is 'adaptive' alone.
    """
    return {
        "presets": {
            name: _preset_to_payload(profile)
            for name, profile in create_preset_profiles().items()
        }
    }


async def get_processing_parameters(
    get_enhancement_settings: Callable[[], dict[str, Any]] | None = Depends(
        _get_enhancement_settings
    ),
) -> dict[str, Any]:
    """
    Get current processing parameters from the continuous space system.
    This shows what the auto-mastering engine is doing in real-time.

    Reads from the global content profile cache populated by ChunkedAudioProcessor
    during streaming playback.

    Moved here from routers/enhancement.py (#5073) so GET /api/processing/parameters
    is gated behind HAS_PROCESSING like its 8 siblings under this router, instead
    of being unconditionally registered while the rest of the /api/processing
    namespace can be absent in a degraded build.

    Returns:
        dict: Processing parameters including coordinates, targets, and adjustments
    """
    if get_enhancement_settings is None:
        raise HTTPException(status_code=503, detail="Enhancement settings not available")

    try:
        from core.chunk_content_profile import get_last_content_profile

        # Get current preset
        preset = get_enhancement_settings().get("preset", "adaptive")

        # Try to get profile from ChunkedAudioProcessor global cache
        profile = get_last_content_profile(preset)

        if profile is None:
            # No processing data yet - return default values.
            # #3779: include `is_default: True` so clients can
            # distinguish "no data yet" from "real measurements
            # that coincidentally landed at the default values".
            logger.debug(f"No processing profile found for preset '{preset}' - returning defaults")
            return dict(_DEFAULT_PARAMETERS)

        # Extract coordinates (ProcessingCoordinates dataclass or dict)
        coords = profile.get('coordinates')
        params = profile.get('parameters')

        if coords is None or params is None:
            # Legacy mode or no continuous space data.
            # #3779: same is_default marker as the no-profile branch.
            logger.debug(f"Profile for preset '{preset}' missing coordinates or parameters")
            return dict(_DEFAULT_PARAMETERS)

        # Extract values (handle both dataclass and dict formats)
        def get_attr(obj: Any, attr: str, default: Any = 0.0) -> Any:
            """Get attribute from dataclass or dict"""
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return getattr(obj, attr, default)

        # Convert ProcessingCoordinates and ProcessingParameters to dict
        # #3779: `is_default: False` confirms these are measured values
        # from a live ChunkedAudioProcessor profile, not the defaults.
        result = {
            "is_default": False,
            "spectral_balance": get_attr(coords, 'spectral_balance', 0.5),
            "dynamic_range": get_attr(coords, 'dynamic_range', 0.5),
            "energy_level": get_attr(coords, 'energy_level', 0.5),
            "target_lufs": get_attr(params, 'target_lufs', -14.0),
            "peak_target_db": get_attr(params, 'peak_target_db', -1.0),
            "bass_boost": get_attr(params, 'eq_curve', {}).get('low_shelf_gain', 0.0),
            "air_boost": get_attr(params, 'eq_curve', {}).get('high_shelf_gain', 0.0),
            "compression_amount": get_attr(params, 'compression_params', {}).get('amount', 0.0),
            "expansion_amount": get_attr(params, 'expansion_params', {}).get('amount', 0.0),
            "stereo_width": get_attr(params, 'stereo_width_target', 0.75)
        }

        logger.debug(f"📊 Returning processing parameters for preset '{preset}': {result}")
        return result

    except HTTPException:
        raise
    except Exception:
        # Don't silently mask the failure as 'all-systems-nominal' —
        # surface it as 500 so operators see a real error count
        # increment and clients can decide whether to retry (#3562 /
        # BE-NEW-104). The legitimate empty-profile case still falls
        # through the normal 200-OK path above.
        logger.exception("Failed to get processing parameters")
        raise HTTPException(
            status_code=500,
            detail="Failed to get processing parameters",
        )
