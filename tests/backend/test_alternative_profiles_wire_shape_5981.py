"""alternative_profiles' declared item shape is what the emitter sends (#5981).

AlternativeProfilePayload and the TS type declared {profile_id, profile_name, confidence_score};
MasteringRecommendation.to_dict() emits {id, name} -- and the broadcast site casts a plain dict,
so mypy could not see the disagreement.
"""

import sys
from pathlib import Path
from typing import get_type_hints

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from websocket.outbound.enhancement import AlternativeProfilePayload  # noqa: E402

from auralis.analysis.mastering_profiles_builtin import (  # noqa: E402
    PROFILE_BRIGHT_MASTERS,
    PROFILE_QUIET_REFERENCE,
    PROFILE_SODA_STEREO,
)
from auralis.analysis.mastering_recommendation import MasteringRecommendation  # noqa: E402


def test_declared_keys_match_the_emitted_alternative_items():
    recommendation = MasteringRecommendation(
        primary_profile=PROFILE_SODA_STEREO,
        confidence_score=0.9,
        predicted_loudness_change=0.0,
        predicted_crest_change=0.0,
        predicted_centroid_change=0.0,
        alternative_profiles=[PROFILE_QUIET_REFERENCE, PROFILE_BRIGHT_MASTERS],
    )

    emitted = recommendation.to_response(track_id=1)["alternative_profiles"]

    assert len(emitted) == 2
    assert all(set(item) == set(get_type_hints(AlternativeProfilePayload)) for item in emitted)
