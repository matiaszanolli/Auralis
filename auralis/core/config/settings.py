"""
Configuration Settings
~~~~~~~~~~~~~~~~~~~~~

Configuration dataclasses for audio processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import dataclass
from typing import Literal, get_args


#: The processing-mode vocabulary, defined once (#6218): every Literal copy,
#: validation list and job-builder dispatch imports these two names.
ProcessingMode = Literal["reference", "adaptive", "hybrid"]
PROCESSING_MODES: tuple[str, ...] = get_args(ProcessingMode)


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive processing features"""
    # Processing mode
    mode: ProcessingMode = "adaptive"

    # Content analysis settings
    enable_genre_detection: bool = True

    # Adaptation settings
    adaptation_strength: float = 0.8  # 0.0 = no adaptation, 1.0 = full adaptation

    # Real-time processing
    chunk_size_ms: float = 20.0  # Processing chunk size in milliseconds
    latency_budget_ms: float = 20.0  # Maximum allowed latency

    # No `critical_bands` knob (#4613): the EQ's band layout is the fixed
    # 25-band Bark-scale table in auralis/dsp/eq/critical_bands.py, which
    # PsychoacousticEQ builds with no arguments. A validated-but-ignored field
    # (default 26, range 8-64) used to sit here and looked tunable.
    #
    # #5302 removed seven more fields that nothing read, so each looked like a
    # switch that did nothing: enable_tempo_analysis, enable_energy_analysis,
    # parameter_smoothing (and its 0-1 assert), enable_quality_monitoring,
    # auto_quality_adjustment, min_quality_level and enable_psychoacoustic_eq.
    # #5763 removed enable_user_learning and learning_rate with the unreachable
    # preference-learning engine they configured.
    # Re-add one only together with the code that honours it.

    def __post_init__(self) -> None:
        # Real raises, not asserts: -O strips an assert, and these bound live DSP
        # parameters (#6126).
        if not (0.0 <= self.adaptation_strength <= 1.0):
            raise ValueError(f"Adaptation strength must be 0-1, got {self.adaptation_strength!r}")
        if not (5.0 <= self.chunk_size_ms <= 100.0):
            raise ValueError(f"Chunk size must be 5-100ms, got {self.chunk_size_ms!r}")
        if not (10.0 <= self.latency_budget_ms <= 100.0):
            raise ValueError(f"Latency budget must be 10-100ms, got {self.latency_budget_ms!r}")


@dataclass
class GenreProfile:
    """Processing profile for a specific genre"""
    name: str
    target_lufs: float
    bass_boost_db: float
    midrange_clarity_db: float
    treble_enhancement_db: float
    compression_ratio: float
    stereo_width: float
    mastering_intensity: float

    def __post_init__(self) -> None:
        if not (-30.0 <= self.target_lufs <= 0.0):
            raise ValueError(f"Target LUFS must be -30 to 0, got {self.target_lufs!r}")
        if not (-12.0 <= self.bass_boost_db <= 12.0):
            raise ValueError(f"Bass boost must be -12 to +12 dB, got {self.bass_boost_db!r}")
        if not (-12.0 <= self.midrange_clarity_db <= 12.0):
            raise ValueError(f"Midrange clarity must be -12 to +12 dB, got {self.midrange_clarity_db!r}")
        if not (-12.0 <= self.treble_enhancement_db <= 12.0):
            raise ValueError(f"Treble enhancement must be -12 to +12 dB, got {self.treble_enhancement_db!r}")
        if not (1.0 <= self.compression_ratio <= 10.0):
            raise ValueError(f"Compression ratio must be 1-10, got {self.compression_ratio!r}")
        if not (0.0 <= self.stereo_width <= 2.0):
            raise ValueError(f"Stereo width must be 0-2, got {self.stereo_width!r}")
        if not (0.0 <= self.mastering_intensity <= 1.0):
            raise ValueError(f"Mastering intensity must be 0-1, got {self.mastering_intensity!r}")
