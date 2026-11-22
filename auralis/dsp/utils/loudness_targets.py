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

The first two are equal today, which is why they were never separated.

Two more anchors the content rules share (#6647):

* ``QUIET_MATERIAL_TARGET_LUFS`` -- the gentler target for quiet or highly dynamic
  material (classical-style), and the fallback when no preset profile resolves.
* ``LOUD_THRESHOLD_LUFS`` -- where material counts as already loud: the adaptive
  loudness control's "very loud" regime, the cap on a boosted target for quiet
  input, and the reference the dynamics generator measures the loudness gap to.

The output ceiling and the final limiter's timing live here too (#6635):

* ``OUTPUT_PEAK_CEILING_DB`` -- how hot the rendered output may get (-0.3 dBFS,
  headroom for inter-sample peaks): HybridProcessor's brick-wall limiter, the
  continuous mode's final peak control, the reference-profile check and the
  backend's target-level headroom all read it.
* ``LIMITER_LOOKAHEAD_MS`` / ``LIMITER_RELEASE_MS`` -- that limiter's timing, also
  the defaults of ``BrickWallLimiterSettings`` and the realtime
  ``StreamingPeakCeiling``.

Deliberately different, and left as they are: ``BrickWallLimiterSettings``'
-0.5 dB threshold default (a generic limiter, not the output stage), the
realtime ``PlayerConfig.realtime_safety_peak`` 0.95 (the realtime path is not
necessarily behind the brick-wall limiter, see its comment), auto-master's
0.98 makeup-gain cap, and ``LOUDNESS_LIMITER_CEILING_DB`` (-1.0, a separate
stage in mastering_presets).

They live in ``dsp/utils`` (not ``core/config``) because ``dsp`` is the lower
layer and must not import ``core``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

DEFAULT_TARGET_LUFS = -14.0
STREAMING_TARGET_LUFS = -14.0
LOUD_MASTER_TARGET_LUFS = -11.0
QUIET_MATERIAL_TARGET_LUFS = -16.0
LOUD_THRESHOLD_LUFS = -12.0

OUTPUT_PEAK_CEILING_DB = -0.3
LIMITER_LOOKAHEAD_MS = 2.0
LIMITER_RELEASE_MS = 50.0
