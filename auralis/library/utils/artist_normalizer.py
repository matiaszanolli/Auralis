"""
Artist Name Normalizer

Provides utilities for normalizing and parsing artist names:
- Normalize variations (AC/DC, ACDC, AC-DC) to canonical form
- Parse featured artists ("Artist A feat. Artist B" -> ["Artist A", "Artist B"])

@module auralis.library.utils.artist_normalizer
"""

import re
import unicodedata

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


def _split_part(part: str) -> list[str]:
    """One featuring-split part -> its artists (a preserved duo stays whole)."""
    # Check if the whole part is a preserved duo before splitting on & or ,
    if part.lower() in PRESERVED_DUOS:
        return [part]
    return [sub.strip() for sub in re.split(MULTI_ARTIST_PATTERN, part) if sub.strip()]


def _split_featuring(artist_string: str) -> list[str]:
    """Artists split on the first matching FEATURING_PATTERN, or [] when none match."""
    for pattern in FEATURING_PATTERNS:
        if not re.search(pattern, artist_string, re.IGNORECASE):
            continue
        parts = re.split(pattern, artist_string, flags=re.IGNORECASE)
        artists = [
            artist
            for part in (p.strip() for p in parts)
            if part
            for artist in _split_part(part)
        ]
        # Return if we found artists; otherwise try the next pattern
        if artists:
            return artists
    return []


def _split_collaboration(artist_string: str) -> list[str]:
    """Split "Artist A & Artist B" collaborations conservatively, or [] to keep it whole.

    Only splits on " & " / " and " when every part is a short name and none
    starts with "the " -- so "Tom Petty and the Heartbreakers" stays intact.
    """
    if artist_string.lower() in PRESERVED_DUOS:
        return []
    if ' & ' not in artist_string and ' and ' not in artist_string.lower():
        return []
    potential_parts = re.split(r'\s+&\s+|\s+and\s+', artist_string, flags=re.IGNORECASE)
    if len(potential_parts) <= 1:
        return []
    all_short = all(len(p.split()) <= 3 for p in potential_parts)
    no_the = not any(p.lower().startswith('the ') for p in potential_parts)
    if all_short and no_the:
        return [p.strip() for p in potential_parts if p.strip()]
    return []


def parse_featured_artists(artist_string: str) -> list[str]:
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

    featured = _split_featuring(artist_string)
    if featured:
        return featured

    collaboration = _split_collaboration(artist_string)
    if collaboration:
        return collaboration

    # No featuring pattern or collaboration found - return as a single artist
    return [artist_string]
