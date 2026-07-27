"""One intensity, one contract (#4600).

The same quantity was validated three different ways:

* ``POST /api/player/enhancement/intensity`` silently CLAMPED and returned 200
  with a value the caller never sent;
* ``PUT /api/settings`` rejected out-of-range with 422;
* the WebSocket ``play_enhanced`` path silently discarded and fell back to the
  stored setting.

The clamp was the dangerous one. ``max(0.0, min(1.0, nan))`` evaluates to
**1.0**, not ``nan`` — ``nan < 1.0`` is False so ``min`` returns 1.0 — so a NaN
intensity was silently coerced to MAXIMUM enhancement and written into the
runtime settings dict, while the settings route rejected the identical input.

Both REST surfaces now share ``EnhancementIntensity`` from ``schemas.py``,
mirroring how ``preset`` was unified in #4424. The WS path deliberately keeps
its fallback — refusing to start playback over a bad slider value is worse than
playing at the stored intensity — but routes its bounds check through the same
shared predicate so the two cannot drift.
"""

import math
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.enhancement import SetIntensityRequest  # noqa: E402
from routers.settings import SettingsUpdateRequest  # noqa: E402
from schemas import INTENSITY_MAX, INTENSITY_MIN, is_valid_intensity  # noqa: E402

# Every value that must be refused, including the three non-finite cases.
REJECTED = [1.5, -0.2, 100.0, float("nan"), float("inf"), float("-inf")]
ACCEPTED = [0.0, 0.25, 0.5, 1.0]


class TestClampIsGone:
    """The exact coercion that made NaN mean 'maximum enhancement'."""

    def test_the_old_clamp_really_did_turn_nan_into_max(self):
        """Documents the bug this issue is about — not a test of our code."""
        assert max(0.0, min(1.0, float("nan"))) == 1.0
        assert max(0.0, min(1.0, float("inf"))) == 1.0
        assert max(0.0, min(1.0, float("-inf"))) == 0.0

    @pytest.mark.parametrize("value", REJECTED)
    def test_set_intensity_request_rejects(self, value):
        with pytest.raises(ValidationError):
            SetIntensityRequest(intensity=value)

    @pytest.mark.parametrize("value", ACCEPTED)
    def test_set_intensity_request_accepts_in_range(self, value):
        assert SetIntensityRequest(intensity=value).intensity == value

    def test_no_value_is_silently_altered(self):
        """A 200 must never carry a number the caller did not send."""
        for value in ACCEPTED:
            assert SetIntensityRequest(intensity=value).intensity == value


class TestBothRestSurfacesAgree:
    """#4600 acceptance: identical accept/reject for identical input."""

    @pytest.mark.parametrize("value", REJECTED)
    def test_both_reject(self, value):
        with pytest.raises(ValidationError):
            SetIntensityRequest(intensity=value)
        with pytest.raises(ValidationError):
            SettingsUpdateRequest(enhancement_intensity=value)

    @pytest.mark.parametrize("value", ACCEPTED)
    def test_both_accept(self, value):
        assert SetIntensityRequest(intensity=value).intensity == value
        assert SettingsUpdateRequest(enhancement_intensity=value).enhancement_intensity == value

    def test_settings_still_allows_omitting_the_field(self):
        """The settings model is a partial update; None must stay valid."""
        assert SettingsUpdateRequest().enhancement_intensity is None
        assert SettingsUpdateRequest(enhancement_intensity=None).enhancement_intensity is None


class TestSharedPredicateForTheWsPath:
    """The WS path keeps its fallback, but on the same bounds."""

    @pytest.mark.parametrize("value", REJECTED)
    def test_rejects_everything_the_models_reject(self, value):
        assert is_valid_intensity(value) is False

    @pytest.mark.parametrize("value", ACCEPTED)
    def test_accepts_everything_the_models_accept(self, value):
        assert is_valid_intensity(value) is True

    @pytest.mark.parametrize("value", [None, "0.5", [], {}, object()])
    def test_rejects_non_numbers(self, value):
        assert is_valid_intensity(value) is False

    def test_rejects_bool_which_is_an_int_subclass(self):
        """`True` would otherwise pass as 1.0 and read as maximum intensity."""
        assert is_valid_intensity(True) is False
        assert is_valid_intensity(False) is False

    def test_bounds_match_the_model_constraint(self):
        assert (INTENSITY_MIN, INTENSITY_MAX) == (0.0, 1.0)
        assert is_valid_intensity(INTENSITY_MIN) is True
        assert is_valid_intensity(INTENSITY_MAX) is True


class TestNothingNonFiniteCanReachRuntimeSettings:
    """#4600 acceptance criterion 2, expressed directly."""

    @pytest.mark.parametrize("value", REJECTED)
    def test_ws_path_falls_back_rather_than_storing_a_bad_value(self, value):
        # Mirrors the expression in handle_play_enhanced.
        intensity = float(value) if is_valid_intensity(value) else None
        assert intensity is None

        stored = 0.7  # what settings.get("intensity", 1.0) would return
        effective = intensity if intensity is not None else stored
        assert math.isfinite(effective)
        assert INTENSITY_MIN <= effective <= INTENSITY_MAX

    def test_ws_path_uses_a_valid_payload_value(self):
        intensity = float(0.3) if is_valid_intensity(0.3) else None
        assert intensity == 0.3


def _published_bounds(model, field: str) -> tuple[float | None, float | None]:
    """The bounds this field advertises in its JSON schema (i.e. in OpenAPI).

    Asserted on the published schema rather than on `model_fields[...].metadata`:
    for an optional field the constraint lives inside the `anyOf` member, so the
    top-level metadata list is empty even though validation is enforced. The
    JSON schema is also what API consumers and the docs actually see.
    """
    schema = model.model_json_schema()["properties"][field]
    candidates = schema.get("anyOf", [schema])
    for candidate in candidates:
        if candidate.get("type") == "number":
            return candidate.get("minimum"), candidate.get("maximum")
    return None, None


class TestSingleDefinition:
    """CONSISTENCY — the constraint must not be re-declared per surface."""

    def test_both_surfaces_publish_identical_bounds(self):
        """Same contract in OpenAPI, not just the same runtime behaviour."""
        assert _published_bounds(SetIntensityRequest, "intensity") == (0.0, 1.0)
        assert _published_bounds(SettingsUpdateRequest, "enhancement_intensity") == (
            0.0,
            1.0,
        )

    def test_bounds_come_from_the_shared_annotation(self):
        from schemas import EnhancementIntensity

        shared = {
            (attr, float(getattr(meta, attr)))
            for field_info in EnhancementIntensity.__metadata__
            for meta in getattr(field_info, "metadata", [])
            for attr in ("ge", "le")
            if getattr(meta, attr, None) is not None
        }
        assert shared == {("ge", 0.0), ("le", 1.0)}

    def test_both_routers_reference_the_shared_type(self):
        import routers.enhancement as enh
        import routers.settings as settings_mod

        for module in (enh, settings_mod):
            src = Path(str(module.__file__)).read_text()
            assert "EnhancementIntensity" in src, (
                f"{module.__name__} must use the shared constraint, not a local copy"
            )

    def test_no_clamping_validator_remains(self):
        import routers.enhancement as enh

        # A leftover field_validator named clamp_* would silently re-introduce
        # the coercion even with the constraint in place.
        assert not any(
            "clamp" in name for name in SetIntensityRequest.__dict__
        ), "a clamping validator is back on SetIntensityRequest"
        source_lines = [
            line
            for line in Path(str(enh.__file__)).read_text().splitlines()
            if not line.strip().startswith("#")
        ]
        assert not any("max(0.0, min(1.0" in line for line in source_lines), (
            "the clamp expression is back in executable code"
        )
