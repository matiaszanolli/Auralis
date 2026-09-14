"""
ContentAnalyzer no longer promotes dead fingerprint keys to content_profile (#5426).

`analyze_content()` used to copy `spectral_centroid_normalized` and
`lufs_fingerprint` onto the top-level `content_profile` "for backward
compatibility", and overwrite `crest_factor_db` with the fingerprint's
`crest_db` -- none of which had any reader. The overwrite was also a latent
inconsistency: `content_profile["crest_factor_db"]` silently changed
provenance (time-domain vs. fingerprint-derived) depending on whether
fingerprinting ran. All three are now gone; `crest_factor_db` stays the
single, consistent time-domain value regardless of fingerprint analysis.
"""

import numpy as np
import pytest

from auralis.core.analysis.content_analyzer import ContentAnalyzer


@pytest.fixture
def audio():
    sr = 44100
    t = np.linspace(0, 3, sr * 3, dtype=np.float32)
    tone = 0.4 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    return np.column_stack([tone, tone])


def _analyzer(use_fingerprint_analysis):
    return ContentAnalyzer(
        use_ml_classification=False,
        use_fingerprint_analysis=use_fingerprint_analysis,
        use_tempo_detection=False,
    )


def test_promoted_keys_are_absent(audio):
    profile = _analyzer(use_fingerprint_analysis=True).analyze_content(audio)
    assert profile.get("fingerprint") is not None, "fixture should exercise the fingerprint path"
    assert "spectral_centroid_normalized" not in profile
    assert "lufs_fingerprint" not in profile


def test_crest_factor_db_consistent_with_and_without_fingerprint(audio):
    """crest_factor_db must be the same time-domain value regardless of
    whether fingerprint analysis ran (it used to be overwritten by the
    fingerprint's crest_db only when fingerprinting was enabled)."""
    profile_with_fp = _analyzer(use_fingerprint_analysis=True).analyze_content(audio)
    profile_without_fp = _analyzer(use_fingerprint_analysis=False).analyze_content(audio)

    assert profile_with_fp.get("fingerprint") is not None
    assert profile_without_fp.get("fingerprint") is None
    assert profile_with_fp["crest_factor_db"] == pytest.approx(
        profile_without_fp["crest_factor_db"], abs=1e-9
    )
