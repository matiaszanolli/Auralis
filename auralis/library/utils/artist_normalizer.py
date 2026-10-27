"""
Artist Name Normalizer

Provides utilities for normalizing and parsing artist names:
- Normalize variations (AC/DC, ACDC, AC-DC) to canonical form
- Parse featured artists ("Artist A feat. Artist B" -> ["Artist A", "Artist B"])

@module auralis.library.utils.artist_normalizer
"""

import re
import unicodedata

# Longest artist string parse_featured_artists will look at (#6154). Tag frames
# can be megabytes, and the \s+-led patterns below are quadratic on a long
# whitespace run while holding the GIL; no real artist credit is anywhere near
# this, and the repository truncates each name to 200 characters anyway.
MAX_ARTIST_STRING_CHARS = 500

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

# Duo/group names with "&" that must stay whole when they appear as a credit
# after a featuring marker ("X feat. Hall & Oates"). An override list only:
# bare tags are never split, so it is not what keeps "Iron & Wine" intact.
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
    - A name with no letters or digits ("!!!", "+/-") keeps its NFKC-casefolded
      symbols, so distinct symbol-only artists stay distinct

    Examples:
        >>> normalize_artist_name("AC/DC")
        'acdc'
        >>> normalize_artist_name("AC-DC")
        'acdc'
        >>> normalize_artist_name("  The   Beatles  ")
        'the beatles'
        >>> normalize_artist_name("Bjork")
        'bjork'
        >>> normalize_artist_name("!!!")
        '!!!'

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

    # Symbol-only names ("!!!", "+/-") have no alphanumerics and would all
    # normalise to '', collapsing onto whichever was stored first. Key them on
    # the NFKC-casefolded name instead so they stay distinct (#5720).
    if not normalized.strip():
        normalized = re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', name).casefold())

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
    """Artists split on the first matching FEATURING_PATTERN, or [] when none match.

    The credit before the marker is the main artist and stays whole, so a band
    name containing "&" survives ("Iron & Wine feat. Sam Beam"); only the
    credits after the marker are split further on "," / "&" (#5720).
    """
    for pattern in FEATURING_PATTERNS:
        if not re.search(pattern, artist_string, re.IGNORECASE):
            continue
        parts = [p.strip() for p in re.split(pattern, artist_string, flags=re.IGNORECASE) if p.strip()]
        artists = parts[:1] + [artist for part in parts[1:] for artist in _split_part(part)]
        # Return if we found artists; otherwise try the next pattern
        if artists:
            return artists
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
    - A tag with no explicit marker is ONE artist, however it is spelled:
      "Iron & Wine", "Belle and Sebastian", "Simon & Garfunkel" stay whole.
      Co-credited artists arrive as separate tag values, parsed one by one.
    - The credit before a marker stays whole ("Iron & Wine feat. Sam Beam"
      -> ["Iron & Wine", "Sam Beam"]); only credits after it are split on "," / "&".
    - Empty string -> ["Unknown Artist"]

    Args:
        artist_string: Raw artist string from audio metadata

    Returns:
        List of individual artist names
    """
    if not artist_string or not artist_string.strip():
        return ['Unknown Artist']

    # Bound the input before any regex sees it, then collapse whitespace runs so
    # the \s+-led patterns stay linear (#6154). strip() first: it is linear and
    # keeps a leading run of blanks from eating the whole budget.
    artist_string = re.sub(r'\s+', ' ', artist_string.strip()[:MAX_ARTIST_STRING_CHARS]).strip()

    featured = _split_featuring(artist_string)
    if featured:
        return featured

    # No explicit marker: the whole tag is one artist, however it is spelled
    # ("Iron & Wine", "Belle and Sebastian"). Separate artists arrive as
    # separate tag values, which the caller parses one by one.
    return [artist_string]
