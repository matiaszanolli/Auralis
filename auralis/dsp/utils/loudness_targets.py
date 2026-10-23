"""
Named loudness targets (#5795, #6226).

Bare LUFS literals at a dozen sites carried two different meanings, so
changing either meant a grep:

* ``DEFAULT_TARGET_LUFS`` -- what Auralis aims a master at when nothing more
  specific (a preset, the fingerprint, the user) says otherwise.
* ``STREAMING_TARGET_LUFS`` -- the loudness the major streaming platforms
  normalize to; used where a track is nudged *toward* "streaming standard".
* ``LOUD_MASTER_TARGET_LUFS`` -- the deliberately hotter "loud master"
  anchor (-11 LUFS): ``SimpleMasteringConfig.TARGET_LUFS`` (advisory
  evaluation), ``AdaptiveLoudnessControl.TARGET_LUFS`` (makeup gain) and
  the soft-clip ramp in ``mastering_branches/soft_clip_params.py`` must
  move together, so they all read this one constant.

The first two are equal today, which is why they were never separated. They live in
``dsp/utils`` (not ``core/config``) because ``dsp`` is the lower layer and must
not import ``core``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

DEFAULT_TARGET_LUFS = -14.0
STREAMING_TARGET_LUFS = -14.0
LOUD_MASTER_TARGET_LUFS = -11.0
