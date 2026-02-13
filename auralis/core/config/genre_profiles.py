"""
Genre Profiles
~~~~~~~~~~~~~

Genre-specific processing profiles and defaults

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


from ...utils.logging import debug
from .settings import GenreProfile


def create_default_genre_profiles() -> dict[str, GenreProfile]:
    """Create default genre processing profiles"""
    return {
        "rock": GenreProfile(
            name="rock",
            target_lufs=-12.0,
            bass_boost_db=2.0,
            midrange_clarity_db=1.5,
            treble_enhancement_db=1.0,
            compression_ratio=3.0,
            stereo_width=0.8,
            mastering_intensity=0.8
        ),
        "pop": GenreProfile(
            name="pop",
            target_lufs=-14.0,
            bass_boost_db=1.5,
            midrange_clarity_db=2.0,
            treble_enhancement_db=1.5,
            compression_ratio=2.5,
            stereo_width=0.7,
            mastering_intensity=0.7
        ),
        "classical": GenreProfile(
            name="classical",
            target_lufs=-18.0,
            bass_boost_db=0.0,
            midrange_clarity_db=0.5,
            treble_enhancement_db=0.0,
            compression_ratio=1.5,
            stereo_width=0.9,
            mastering_intensity=0.3
        ),
        "electronic": GenreProfile(
            name="electronic",
            target_lufs=-10.0,
            bass_boost_db=4.0,
            midrange_clarity_db=2.0,
            treble_enhancement_db=2.0,
            compression_ratio=4.0,
            stereo_width=1.0,
            mastering_intensity=0.9
        ),
        "jazz": GenreProfile(
            name="jazz",
            target_lufs=-16.0,
            bass_boost_db=0.5,
            midrange_clarity_db=1.0,
            treble_enhancement_db=0.5,
            compression_ratio=2.0,
            stereo_width=0.8,
            mastering_intensity=0.4
        ),
        "hip_hop": GenreProfile(
            name="hip_hop",
            target_lufs=-11.0,
            bass_boost_db=3.0,
            midrange_clarity_db=2.5,
            treble_enhancement_db=1.0,
            compression_ratio=3.5,
            stereo_width=0.6,
            mastering_intensity=0.8
        ),
        "acoustic": GenreProfile(
            name="acoustic",
            target_lufs=-16.0,
            bass_boost_db=0.0,
            midrange_clarity_db=1.5,
            treble_enhancement_db=1.0,
            compression_ratio=1.8,
            stereo_width=0.7,
            mastering_intensity=0.4
        ),
        "ambient": GenreProfile(
            name="ambient",
            target_lufs=-20.0,
            bass_boost_db=1.0,
            midrange_clarity_db=0.0,
            treble_enhancement_db=2.0,
            compression_ratio=1.2,
            stereo_width=1.2,
            mastering_intensity=0.2
        )
    }


def get_default_genre_profile() -> GenreProfile:
    """Get balanced default profile for unknown genres"""
    return GenreProfile(
        name="default",
        target_lufs=-14.0,
        bass_boost_db=1.0,
        midrange_clarity_db=1.0,
        treble_enhancement_db=1.0,
        compression_ratio=2.5,
        stereo_width=0.8,
        mastering_intensity=0.6
    )


def get_genre_profile(genre: str, profiles: dict[str, GenreProfile]) -> GenreProfile:
    """Get processing profile for a specific genre with fallback"""
    genre_lower = genre.lower()
    if genre_lower in profiles:
        return profiles[genre_lower]
    else:
        debug(f"Unknown genre '{genre}', using default profile")
        return get_default_genre_profile()
