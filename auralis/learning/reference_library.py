"""
Reference Library for World-Class Mastering Standards

This module defines a curated library of professionally mastered tracks
from legendary mastering engineers across different genres. These serve
as quality benchmarks for Auralis's adaptive processing.

The goal: Match or exceed the standards set by the best in the industry.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class MasteringEngineer(Enum):
    """Legendary mastering engineers and producers."""
    # Progressive Rock / Audiophile
    STEVEN_WILSON = "steven_wilson"  # Porcupine Tree, King Crimson remasters

    # Rock / Alternative
    BUTCH_VIG = "butch_vig"  # Nirvana, Garbage, Smashing Pumpkins
    STEVE_ALBINI = "steve_albini"  # In Utero, Pixies
    ANDY_WALLACE = "andy_wallace"  # Nirvana Nevermind, Rage Against the Machine

    # Pop / R&B
    QUINCY_JONES = "quincy_jones"  # Michael Jackson, Frank Sinatra
    HUMBERTO_GATICA = "humberto_gatica"  # Celine Dion, Michael Buble

    # Electronic / Dance
    THOMAS_BANGALTER = "thomas_bangalter"  # Daft Punk
    DEADMAU5 = "deadmau5"  # Progressive House

    # Metal
    ANDY_SNEAP = "andy_sneap"  # Megadeth, Testament, Judas Priest
    JENS_BOGREN = "jens_bogren"  # Opeth, Katatonia, Amon Amarth

    # Classical / Jazz
    BOB_LUDWIG = "bob_ludwig"  # Legendary mastering, all genres
    BERNIE_GRUNDMAN = "bernie_grundman"  # Steely Dan, Prince

    # Hip Hop / Urban
    DR_DRE = "dr_dre"  # West Coast sound
    MIKE_DEAN = "mike_dean"  # Kanye West, Travis Scott


class Genre(Enum):
    """Music genres with distinct mastering characteristics."""
    PROGRESSIVE_ROCK = "progressive_rock"
    ALTERNATIVE_ROCK = "alternative_rock"
    GRUNGE = "grunge"
    METAL = "metal"
    DOOM_METAL = "doom_metal"
    PROGRESSIVE_METAL = "progressive_metal"
    POP = "pop"
    RNB = "rnb"
    ELECTRONIC = "electronic"
    HOUSE = "house"
    AMBIENT = "ambient"
    CLASSICAL = "classical"
    JAZZ = "jazz"
    HIP_HOP = "hip_hop"
    INDIE = "indie"
    SHOEGAZE = "shoegaze"


@dataclass
class ReferenceTrack:
    """A professionally mastered reference track."""
    title: str
    artist: str
    album: str
    year: int
    genre: Genre
    engineer: MasteringEngineer
    file_path: Path | None = None

    # Measured characteristics (to be filled by analyzer)
    target_lufs: float | None = None
    target_rms: float | None = None
    dynamic_range: float | None = None
    crest_factor: float | None = None

    # Quality markers
    is_remaster: bool = False
    remaster_year: int | None = None
    bit_depth: int = 16
    sample_rate: int = 44100

    # Mastering characteristics
    notes: str = ""


# =============================================================================
# REFERENCE LIBRARY - Curated by Genre
# =============================================================================

REFERENCE_LIBRARY: dict[Genre, list[ReferenceTrack]] = {

    # =========================================================================
    # PROGRESSIVE ROCK - Steven Wilson Standard
    # =========================================================================
    Genre.PROGRESSIVE_ROCK: [
        ReferenceTrack(
            title="Prodigal",
            artist="Porcupine Tree",
            album="In Absentia (Deluxe Remaster)",
            year=2002,
            remaster_year=2021,
            genre=Genre.PROGRESSIVE_ROCK,
            engineer=MasteringEngineer.STEVEN_WILSON,
            is_remaster=True,
            bit_depth=24,
            sample_rate=96000,
            notes="""
            Steven Wilson's 2021 remaster of In Absentia is considered
            reference-quality for progressive rock. Characteristics:
            - Excellent dynamic range preservation (DR12-14)
            - Extended frequency response (careful high-freq air)
            - Transparent limiting (no audible pumping)
            - Wide stereo imaging
            - Natural bass response (not over-hyped)
            - Clear midrange without harshness
            """
        ),
        ReferenceTrack(
            title="Arriving Somewhere But Not Here",
            artist="Porcupine Tree",
            album="Deadwing",
            year=2005,
            genre=Genre.PROGRESSIVE_ROCK,
            engineer=MasteringEngineer.STEVEN_WILSON,
            notes="Epic prog track with excellent dynamics and build-up"
        ),
        ReferenceTrack(
            title="Anesthetize",
            artist="Porcupine Tree",
            album="Fear of a Blank Planet",
            year=2007,
            genre=Genre.PROGRESSIVE_ROCK,
            engineer=MasteringEngineer.STEVEN_WILSON,
            notes="Heavy but dynamic, great reference for prog metal crossover"
        ),
    ],

    # =========================================================================
    # GRUNGE / ALTERNATIVE - The Butch Vig / Andy Wallace Standard
    # =========================================================================
    Genre.GRUNGE: [
        ReferenceTrack(
            title="Smells Like Teen Spirit",
            artist="Nirvana",
            album="Nevermind",
            year=1991,
            genre=Genre.GRUNGE,
            engineer=MasteringEngineer.ANDY_WALLACE,
            notes="""
            Andy Wallace's mix/master of Nevermind defined the grunge sound:
            - Aggressive but not over-compressed
            - Punchy drums (especially snare)
            - Thick guitar wall but clear vocals
            - DR11 - good dynamic range for rock
            """
        ),
        ReferenceTrack(
            title="Heart-Shaped Box",
            artist="Nirvana",
            album="In Utero",
            year=1993,
            genre=Genre.GRUNGE,
            engineer=MasteringEngineer.STEVE_ALBINI,
            notes="""
            Steve Albini's raw production philosophy:
            - Minimal compression
            - Natural dynamics (DR13+)
            - Raw, unpolished sound (intentional)
            - Excellent for studying dynamic preservation
            """
        ),
    ],

    # =========================================================================
    # METAL - Modern Metal Standards
    # =========================================================================
    Genre.METAL: [
        ReferenceTrack(
            title="Deliverance",
            artist="Opeth",
            album="Deliverance",
            year=2002,
            genre=Genre.PROGRESSIVE_METAL,
            engineer=MasteringEngineer.STEVEN_WILSON,
            notes="Death metal meets prog - heavy but dynamic"
        ),
        ReferenceTrack(
            title="Ghost of Perdition",
            artist="Opeth",
            album="Ghost Reveries",
            year=2005,
            genre=Genre.PROGRESSIVE_METAL,
            engineer=MasteringEngineer.JENS_BOGREN,
            notes="""
            Jens Bogren's metal mastering:
            - DR7-9 (typical modern metal)
            - Tight low end
            - Clear guitar separation
            - Powerful but controlled
            """
        ),
    ],

    # =========================================================================
    # POP - Quincy Jones / Michael Jackson Standard
    # =========================================================================
    Genre.POP: [
        ReferenceTrack(
            title="Billie Jean",
            artist="Michael Jackson",
            album="Thriller",
            year=1982,
            genre=Genre.POP,
            engineer=MasteringEngineer.QUINCY_JONES,
            notes="""
            Quincy Jones production perfection:
            - Pristine clarity
            - Perfect vocal presence
            - Tight bass (that iconic bassline)
            - DR12+ (excellent dynamics for pop)
            - Timeless sound that still holds up
            """
        ),
    ],

    # =========================================================================
    # ELECTRONIC - Daft Punk Standard
    # =========================================================================
    Genre.ELECTRONIC: [
        ReferenceTrack(
            title="Giorgio by Moroder",
            artist="Daft Punk",
            album="Random Access Memories",
            year=2013,
            genre=Genre.ELECTRONIC,
            engineer=MasteringEngineer.THOMAS_BANGALTER,
            notes="""
            Random Access Memories won 'Best Engineered Album':
            - Organic electronic sound
            - Real instruments + synths
            - DR8-10 (rare for modern EDM)
            - Analog warmth with digital precision
            - Excellent low-end control
            """
        ),
    ],

    # =========================================================================
    # AUDIOPHILE REFERENCES - Bob Ludwig / Bernie Grundman
    # =========================================================================
    Genre.PROGRESSIVE_ROCK: [
        ReferenceTrack(
            title="Aja",
            artist="Steely Dan",
            album="Aja",
            year=1977,
            genre=Genre.PROGRESSIVE_ROCK,  # Jazz-rock fusion
            engineer=MasteringEngineer.BERNIE_GRUNDMAN,
            notes="""
            Bernie Grundman's masterpiece:
            - Audiophile reference standard
            - Impeccable tonal balance
            - DR14+ (exceptional dynamic range)
            - Studio perfection
            - Every instrument perfectly placed
            """
        ),
    ],
}


# =============================================================================
# Engineer Profiles - What Makes Each Master Unique
# =============================================================================

ENGINEER_PROFILES: dict[MasteringEngineer, dict[str, str]] = {
    MasteringEngineer.STEVEN_WILSON: {
        "philosophy": "Audiophile-quality remasters with dynamic range preservation",
        "signature": "Extended frequency response, transparent limiting, wide stereo",
        "typical_dr": "12-14",
        "typical_lufs": "-14 to -11",
        "frequency_balance": "Extended highs and lows, clear midrange",
        "compression_style": "Minimal, preserves transients",
        "learning_priority": "HIGH - Best reference for adaptive processing",
    },

    MasteringEngineer.QUINCY_JONES: {
        "philosophy": "Perfection in production - every element pristine",
        "signature": "Crystal clarity, perfect vocal presence, timeless sound",
        "typical_dr": "11-13",
        "typical_lufs": "-12 to -10",
        "frequency_balance": "Balanced with slight midrange emphasis for vocals",
        "compression_style": "Musical, enhances groove without pumping",
        "learning_priority": "HIGH - Pop production gold standard",
    },

    MasteringEngineer.ANDY_WALLACE: {
        "philosophy": "Powerful rock sound without sacrificing clarity",
        "signature": "Punchy drums, thick guitars, clear vocals",
        "typical_dr": "9-11",
        "typical_lufs": "-11 to -9",
        "frequency_balance": "Mid-focused with tight low end",
        "compression_style": "Aggressive but controlled",
        "learning_priority": "MEDIUM - Good for rock/alternative",
    },

    MasteringEngineer.JENS_BOGREN: {
        "philosophy": "Modern metal clarity with power",
        "signature": "Separation in heavy mix, tight bass, controlled",
        "typical_dr": "7-9",
        "typical_lufs": "-9 to -7",
        "frequency_balance": "Scooped mids, tight lows, controlled highs",
        "compression_style": "Heavy but transparent",
        "learning_priority": "MEDIUM - Metal mastering reference",
    },

    MasteringEngineer.THOMAS_BANGALTER: {
        "philosophy": "Organic electronic - analog warmth meets digital precision",
        "signature": "Rare dynamics in EDM, real instruments + synths",
        "typical_dr": "8-10",
        "typical_lufs": "-10 to -8",
        "frequency_balance": "Warm lows, present mids, extended highs",
        "compression_style": "Moderate for electronic music",
        "learning_priority": "HIGH - Electronic music with dynamics",
    },
}


if __name__ == "__main__":
    # Print reference library summary
    print("=== AURALIS REFERENCE LIBRARY ===\n")
    print("World-Class Mastering Standards for Quality Validation\n")

    for genre, refs in REFERENCE_LIBRARY.items():
        print(f"\n{genre.value.upper().replace('_', ' ')}:")
        print(f"  References: {len(refs)}")
        for ref in refs:
            print(f"  - {ref.artist} - {ref.title} ({ref.year})")
            print(f"    Engineer: {ref.engineer.value}")
            if ref.is_remaster:
                print(f"    Remaster: {ref.remaster_year} ({ref.bit_depth}-bit/{ref.sample_rate}Hz)")

    print(f"\n\nTotal references: {sum(len(refs) for refs in REFERENCE_LIBRARY.values())}")

    print("\n\n=== ENGINEER PROFILES ===\n")
    for engineer, profile in ENGINEER_PROFILES.items():
        print(f"\n{engineer.value.upper().replace('_', ' ')}:")
        for key, value in profile.items():
            print(f"  {key}: {value}")
