"""
Artist Name Normalizer

Provides utilities for normalizing and parsing artist names:
- Normalize variations (AC/DC, ACDC, AC-DC) to canonical form
- Parse featured artists ("Artist A feat. Artist B" -> ["Artist A", "Artist B"])

@module auralis.library.utils.artist_normalizer
"""

import re
import unicodedata
from typing import List

# Patterns that indicate featured/collaborative artists
# Order matters - more specific patterns first
FEATURING_PATTERNS = [
    r'\s+featuring\s+',    # "featuring" (full word)
    r'\s+feat\.?\s+',      # "feat." or "feat"
    r'\s+ft\.?\s+',        # "ft." or "ft"
    r'\s+vs\.?\s+',        # "vs" or "vs."
    r'\s+with\s+',         # "with"
    r'\s+x\s+',            # "x" (common in hip-hop collaborations)
]

# Pattern for splitting multiple featured artists
# e.g., "Artist B & Artist C" or "Artist B, Artist C"
MULTI_ARTIST_PATTERN = r'\s*[,&]\s*'

# Artists that should NOT be split (duo/group names with &)
# These are kept as single entities
PRESERVED_DUOS = {
    'simon & garfunkel',
    'hall & oates',
    'peaches & herb',
    'ike & tina turner',
    'captain & tennille',
    'sonny & cher',
    'brooks & dunn',
    'peter, paul and mary',
    'crosby, stills & nash',
    'crosby, stills, nash & young',
    'emerson, lake & palmer',
    'earth, wind & fire',
    'blood, sweat & tears',
}


def normalize_artist_name(name: str) -> str:
    """
    Normalize artist name for duplicate detection.

    Transforms artist name to a canonical form for matching:
    - Lowercase
    - Remove non-alphanumeric characters (preserve unicode letters)
    - Collapse multiple spaces to single space
    - Strip leading/trailing whitespace

    Examples:
        >>> normalize_artist_name("AC/DC")
        'acdc'
        >>> normalize_artist_name("AC-DC")
        'acdc'
        >>> normalize_artist_name("  The   Beatles  ")
        'the beatles'
        >>> normalize_artist_name("Bjork")
        'bjork'

    Args:
        name: Raw artist name from metadata

    Returns:
        Normalized name suitable for duplicate detection
    """
    if not name:
        return ''

    # Convert to lowercase
    normalized = name.lower()

    # Normalize unicode (NFC form)
    normalized = unicodedata.normalize('NFC', normalized)

    # Remove non-alphanumeric characters except spaces and unicode letters
    # This handles: AC/DC -> ACDC, AC-DC -> ACDC
    # But preserves: Bjork, Cafe del Mar (unicode letters)
    result = []
    for char in normalized:
        if char.isalnum() or char.isspace():
            result.append(char)
    normalized = ''.join(result)

    # Collapse multiple spaces to single space
    normalized = re.sub(r'\s+', ' ', normalized)

    # Strip leading/trailing whitespace
    normalized = normalized.strip()

    return normalized


def parse_featured_artists(artist_string: str) -> List[str]:
    """
    Parse artist string to extract all artists (main + featured).

    Handles common featuring patterns:
    - "Artist A feat. Artist B" -> ["Artist A", "Artist B"]
    - "Artist A ft. Artist B" -> ["Artist A", "Artist B"]
    - "Artist A featuring Artist B" -> ["Artist A", "Artist B"]
    - "Artist A vs Artist B" -> ["Artist A", "Artist B"]
    - "Artist A feat. Artist B & Artist C" -> ["Artist A", "Artist B", "Artist C"]

    Special cases:
    - "Simon & Garfunkel" -> ["Simon & Garfunkel"] (preserved duo)
    - Empty string -> ["Unknown Artist"]

    Args:
        artist_string: Raw artist string from audio metadata

    Returns:
        List of individual artist names
    """
    if not artist_string or not artist_string.strip():
        return ['Unknown Artist']

    artist_string = artist_string.strip()

    # Check if this is a preserved duo/group name
    if artist_string.lower() in PRESERVED_DUOS:
        return [artist_string]

    # Try each featuring pattern
    for pattern in FEATURING_PATTERNS:
        match = re.search(pattern, artist_string, re.IGNORECASE)
        if match:
            # Split on the featuring pattern
            parts = re.split(pattern, artist_string, flags=re.IGNORECASE)

            artists = []
            for part in parts:
                part = part.strip()
                if not part:
                    continue

                # Check if this part has multiple artists (& or ,)
                # But first check if the whole part is a preserved duo
                if part.lower() in PRESERVED_DUOS:
                    artists.append(part)
                else:
                    # Split on & or , for multiple featured artists
                    sub_artists = re.split(MULTI_ARTIST_PATTERN, part)
                    for sub in sub_artists:
                        sub = sub.strip()
                        if sub:
                            artists.append(sub)

            # Return if we found artists
            if artists:
                return artists

    # No featuring pattern found - return as single artist
    # But check for & that might indicate collaboration
    # Only if NOT a preserved duo
    if artist_string.lower() not in PRESERVED_DUOS:
        # Check for " & " or " and " that might be a collaboration
        # Be conservative - only split on " & " surrounded by spaces
        if ' & ' in artist_string or ' and ' in artist_string.lower():
            # Check if any part would be a preserved duo
            # If so, don't split
            potential_parts = re.split(r'\s+&\s+|\s+and\s+', artist_string, flags=re.IGNORECASE)
            if len(potential_parts) > 1:
                # This might be a collaboration, but we'll be conservative
                # Only split if it looks like "Artist A & Artist B" (both short names)
                # Don't split things like "Tom Petty and the Heartbreakers"
                all_short = all(len(p.split()) <= 3 for p in potential_parts)
                no_the = not any(p.lower().startswith('the ') for p in potential_parts)

                if all_short and no_the:
                    return [p.strip() for p in potential_parts if p.strip()]

    return [artist_string]


def is_same_artist(name1: str, name2: str) -> bool:
    """
    Check if two artist names refer to the same artist.

    Uses normalized comparison to detect duplicates.

    Examples:
        >>> is_same_artist("AC/DC", "ACDC")
        True
        >>> is_same_artist("The Beatles", "Beatles")
        False
        >>> is_same_artist("AC-DC", "AC/DC")
        True

    Args:
        name1: First artist name
        name2: Second artist name

    Returns:
        True if names normalize to the same value
    """
    return normalize_artist_name(name1) == normalize_artist_name(name2)
