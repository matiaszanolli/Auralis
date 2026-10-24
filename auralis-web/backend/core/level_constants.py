#!/usr/bin/env python3

"""
Level Constants
~~~~~~~~~~~~~~~

The LevelManager tuning constants, shared by ``level_manager.py`` (RMS
bookkeeping) and ``level_transition.py`` (smoothing) since the #6270 split.
Import them from here; level_manager re-imports the ones its body uses.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


# Configuration
MAX_LEVEL_CHANGE_DB = 1.5  # Maximum allowed level change between chunks in dB
# Window over which a triggered gain adjustment ramps in from the previous
# chunk's gain, so the boundary stays continuous instead of stepping (#3831).
GAIN_RAMP_SECONDS = 0.05  # 50 ms

# A chunk's RMS at or below this gate carries no real level information —
# it's effectively digital silence (or calculate_rms's log(0)-avoiding floor
# for a truly empty/zero chunk). Treating a floored RMS as a real level to
# smooth against produces a runaway correction (#4729): a silent chunk next
# to a normal one computes a ~180 dB adjustment, which then gets stored and
# ramped into the following real chunk as a full-scale burst followed by
# near-total silence. Below this gate, level differences are ignored.
#
# Named *_GATE_DB, not SILENCE_FLOOR_DB: that name is the codebase-wide
# 16-bit noise-floor convention (-96 dB, auralis/dsp/utils/conversion.py,
# #5785). This is a different, higher threshold with a different job —
# deciding when level smoothing may compare two chunks at all — and
# importing the dsp constant here would silently move the #4729
# runaway-gain guard threshold by 36 dB (#6223).
LEVEL_SMOOTHING_GATE_DB = -60.0

# Hard ceiling on any single gain correction, applied as a last-resort safety
# net (#4729) in case a runaway value reaches this point despite the
# LEVEL_SMOOTHING_GATE_DB guard above. Set far below the ~180 dB a floored-RMS
# pairing can otherwise produce, but well above any legitimate adjustment —
# real adjacent-chunk level swings (loud verse to quiet bridge, etc.) stay
# under ~30 dB in practice, so this should not clip real corrections.
MAX_GAIN_CORRECTION_DB = 40.0


def _clamp_gain_db(db: float) -> float:
    """Bound a gain correction to +/-MAX_GAIN_CORRECTION_DB (#4729)."""
    return max(-MAX_GAIN_CORRECTION_DB, min(MAX_GAIN_CORRECTION_DB, db))


