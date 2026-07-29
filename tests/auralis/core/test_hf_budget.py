"""Tests for the corpus-calibrated shared HF response."""

import pytest

from auralis.core.stages.hf_budget import (
    HF_NEED_CENTER,
    hf_lift_factor,
)


def test_hf_response_peaks_smoothly_at_moderately_low_spectral_balance():
    assert hf_lift_factor(HF_NEED_CENTER) == pytest.approx(1.0)
    assert hf_lift_factor(0.0) < 1.0
    assert hf_lift_factor(0.9) < 0.1


def test_hf_response_restrains_bright_testament_measurement():
    assert hf_lift_factor(0.88) == pytest.approx(0.106, abs=0.002)


def test_hf_response_has_no_activation_boundary():
    left = hf_lift_factor(0.499)
    center = hf_lift_factor(0.500)
    right = hf_lift_factor(0.501)

    assert left > center > right
    assert max(left - center, center - right) < 0.01
