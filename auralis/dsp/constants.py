"""
Shared DSP constants
~~~~~~~~~~~~~~~~~~~~

Single owner for numeric conventions used across dsp, analysis, and the
core config. Import this instead of retyping the literal (#6229).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

# Canonical processing FFT size. The live value is `UnifiedConfig.fft_size`
# (its default reads this constant); the settings classes below the config
# (EQSettings, SpectrumSettings, SpectrumOperations) default to the same
# constant so a bare construction can never silently disagree with the
# configured pipeline. The genre classifier's FeatureExtractor keeps its
# own separate contract constants (see auralis/analysis/ml).
DEFAULT_FFT_SIZE: int = 4096
