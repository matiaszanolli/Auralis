"""A cached fingerprint comes back with all 25 dimensions under the schema's names (#5918).

_record_to_dict looked for 'tempo' and 'loudness_variation' behind hasattr guards; the model
columns are tempo_bpm and loudness_variation_std, so a cache hit silently lacked both.
"""

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from analysis.fingerprint_generator import FingerprintGenerator  # noqa: E402

from auralis.analysis.fingerprint.schema import DIMENSION_NAMES  # noqa: E402
from auralis.library.models import TrackFingerprint  # noqa: E402


def test_cache_hit_dict_has_exactly_the_schema_dimensions():
    record = TrackFingerprint(**{name: float(i) for i, name in enumerate(DIMENSION_NAMES)})

    result = FingerprintGenerator._record_to_dict(record)

    assert list(result) == list(DIMENSION_NAMES)
    assert result["tempo_bpm"] == float(DIMENSION_NAMES.index("tempo_bpm"))
    assert result["loudness_variation_std"] == float(DIMENSION_NAMES.index("loudness_variation_std"))
