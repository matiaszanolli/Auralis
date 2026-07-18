"""Regression tests for FFmpeg minimum-version warning (#4344).

check_ffmpeg() previously only probed presence (`ffmpeg -version` exit code),
inheriting whatever FFmpeg build the user has installed with no
version-recency signal. It now parses the version from `ffmpeg -version`
and logs a warning when it's below MINIMUM_FFMPEG_VERSION — presence is
still all that's required to proceed (a hard refusal on a heuristic version
parse risks breaking playback on a legitimately-patched but unusually
versioned build).

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from unittest.mock import MagicMock, patch

import pytest

from auralis.io.loaders import ffmpeg_loader


@pytest.fixture(autouse=True)
def _clear_cache():
    ffmpeg_loader.check_ffmpeg.cache_clear()
    yield
    ffmpeg_loader.check_ffmpeg.cache_clear()


def _mock_run(stdout: str) -> MagicMock:
    return MagicMock(returncode=0, stdout=stdout)


class TestParseFfmpegVersion:
    def test_parses_plain_version(self):
        assert ffmpeg_loader._parse_ffmpeg_version(
            "ffmpeg version 6.0 Copyright (c) 2000-2023 the FFmpeg developers\n"
        ) == (6, 0)

    def test_parses_distro_patched_version(self):
        assert ffmpeg_loader._parse_ffmpeg_version(
            "ffmpeg version 4.4.2-0ubuntu0.22.04.1 Copyright (c) 2000-2021 the FFmpeg developers\n"
        ) == (4, 4, 2)

    def test_parses_n_prefixed_git_version(self):
        assert ffmpeg_loader._parse_ffmpeg_version(
            "ffmpeg version n6.1 Copyright (c) 2000-2023 the FFmpeg developers\n"
        ) == (6, 1)

    def test_returns_none_for_unparseable_output(self):
        assert ffmpeg_loader._parse_ffmpeg_version("garbage, no version here") is None


class TestCheckFfmpegVersionWarning:
    def test_old_version_warns_but_still_returns_true(self):
        """Mock an old FFmpeg version — assert the loader warns but proceeds."""
        with (
            patch.object(ffmpeg_loader.subprocess, "run", return_value=_mock_run(
                "ffmpeg version 2.8.15 Copyright (c) 2000-2018 the FFmpeg developers\n"
            )),
            patch.object(ffmpeg_loader, "warning") as mock_warning,
        ):
            result = ffmpeg_loader.check_ffmpeg()

        assert result is True
        assert mock_warning.called
        warned_text = " ".join(str(c) for c in mock_warning.call_args_list)
        assert "2.8.15" in warned_text

    def test_recent_version_does_not_warn(self):
        """Mock a recent FFmpeg version — assert the loader proceeds without warning."""
        with (
            patch.object(ffmpeg_loader.subprocess, "run", return_value=_mock_run(
                "ffmpeg version 6.1.1 Copyright (c) 2000-2023 the FFmpeg developers\n"
            )),
            patch.object(ffmpeg_loader, "warning") as mock_warning,
        ):
            result = ffmpeg_loader.check_ffmpeg()

        assert result is True
        mock_warning.assert_not_called()

    def test_exactly_minimum_version_does_not_warn(self):
        min_str = ".".join(str(p) for p in ffmpeg_loader.MINIMUM_FFMPEG_VERSION)
        with (
            patch.object(ffmpeg_loader.subprocess, "run", return_value=_mock_run(
                f"ffmpeg version {min_str} Copyright (c) 2000-2018 the FFmpeg developers\n"
            )),
            patch.object(ffmpeg_loader, "warning") as mock_warning,
        ):
            result = ffmpeg_loader.check_ffmpeg()

        assert result is True
        mock_warning.assert_not_called()

    def test_unparseable_version_warns_but_still_returns_true(self):
        with (
            patch.object(ffmpeg_loader.subprocess, "run", return_value=_mock_run(
                "some unexpected output with no version string\n"
            )),
            patch.object(ffmpeg_loader, "warning") as mock_warning,
        ):
            result = ffmpeg_loader.check_ffmpeg()

        assert result is True
        assert mock_warning.called
