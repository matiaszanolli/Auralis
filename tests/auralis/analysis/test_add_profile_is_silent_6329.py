"""Building the profile database must not write to stdout (#6329)."""

from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine


def test_constructing_the_engine_prints_nothing(capsys):
    AdaptiveMasteringEngine()

    assert capsys.readouterr().out == ""
