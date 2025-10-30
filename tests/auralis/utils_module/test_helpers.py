# -*- coding: utf-8 -*-

"""
Tests for Helper Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the general utility functions

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import tempfile
import os

from auralis.utils.helpers import (
    get_temp_folder,
    format_duration,
    format_filesize
)


# ===== get_temp_folder() Tests =====

def test_get_temp_folder_basic():
    """Test getting temp folder"""
    results = []
    temp_folder = get_temp_folder(results)

    assert temp_folder is not None
    assert isinstance(temp_folder, str)
    assert os.path.exists(temp_folder)
    assert os.path.isdir(temp_folder)


def test_get_temp_folder_returns_system_temp():
    """Test that temp folder is system temp directory"""
    results = []
    temp_folder = get_temp_folder(results)

    # Should return system temp directory
    assert temp_folder == tempfile.gettempdir()


def test_get_temp_folder_with_results():
    """Test temp folder with various results"""
    for results in [[], [1, 2, 3], ["a", "b"], None]:
        temp_folder = get_temp_folder(results)
        assert os.path.exists(temp_folder)


# ===== format_duration() Tests =====

def test_format_duration_seconds_only():
    """Test formatting duration in seconds"""
    assert format_duration(0) == "0s"
    assert format_duration(1) == "1s"
    assert format_duration(30) == "30s"
    assert format_duration(59) == "59s"


def test_format_duration_minutes_and_seconds():
    """Test formatting duration with minutes"""
    assert format_duration(60) == "1m 0s"
    assert format_duration(90) == "1m 30s"
    assert format_duration(125) == "2m 5s"
    assert format_duration(3599) == "59m 59s"


def test_format_duration_hours_minutes_seconds():
    """Test formatting duration with hours"""
    assert format_duration(3600) == "1h 0m 0s"
    assert format_duration(3661) == "1h 1m 1s"
    assert format_duration(7265) == "2h 1m 5s"
    assert format_duration(86400) == "24h 0m 0s"


def test_format_duration_negative():
    """Test formatting negative duration"""
    assert format_duration(-1) == "0s"
    assert format_duration(-100) == "0s"


def test_format_duration_float():
    """Test formatting float duration"""
    assert format_duration(1.5) == "1s"  # Truncates to int
    assert format_duration(60.9) == "1m 0s"
    assert format_duration(90.5) == "1m 30s"


def test_format_duration_large_values():
    """Test formatting very large durations"""
    assert format_duration(100000) == "27h 46m 40s"
    assert format_duration(1000000) == "277h 46m 40s"


def test_format_duration_zero():
    """Test formatting zero duration"""
    assert format_duration(0) == "0s"
    assert format_duration(0.0) == "0s"


# ===== format_filesize() Tests =====

def test_format_filesize_bytes():
    """Test formatting file size in bytes"""
    assert format_filesize(0) == "0.0 B"
    assert format_filesize(1) == "1.0 B"
    assert format_filesize(100) == "100.0 B"
    assert format_filesize(1023) == "1023.0 B"


def test_format_filesize_kilobytes():
    """Test formatting file size in KB"""
    assert format_filesize(1024) == "1.0 KB"
    assert format_filesize(2048) == "2.0 KB"
    assert format_filesize(10240) == "10.0 KB"
    assert format_filesize(1024 * 500) == "500.0 KB"


def test_format_filesize_megabytes():
    """Test formatting file size in MB"""
    assert format_filesize(1024 * 1024) == "1.0 MB"
    assert format_filesize(1024 * 1024 * 5) == "5.0 MB"
    assert format_filesize(1024 * 1024 * 100) == "100.0 MB"


def test_format_filesize_gigabytes():
    """Test formatting file size in GB"""
    assert format_filesize(1024 * 1024 * 1024) == "1.0 GB"
    assert format_filesize(1024 * 1024 * 1024 * 2) == "2.0 GB"
    assert format_filesize(1024 * 1024 * 1024 * 10) == "10.0 GB"


def test_format_filesize_terabytes():
    """Test formatting file size in TB"""
    assert format_filesize(1024 * 1024 * 1024 * 1024) == "1.0 TB"
    assert format_filesize(1024 * 1024 * 1024 * 1024 * 5) == "5.0 TB"


def test_format_filesize_petabytes():
    """Test formatting file size in PB"""
    pb = 1024 * 1024 * 1024 * 1024 * 1024
    assert format_filesize(pb) == "1.0 PB"
    assert format_filesize(pb * 10) == "10.0 PB"


def test_format_filesize_negative():
    """Test formatting negative file size"""
    assert format_filesize(-1) == "0 B"
    assert format_filesize(-1000) == "0 B"


def test_format_filesize_realistic_audio():
    """Test formatting realistic audio file sizes"""
    # 3-minute MP3 at 320kbps
    mp3_size = 3 * 60 * 320 * 1024 // 8
    result = format_filesize(mp3_size)
    assert "MB" in result

    # 10-minute FLAC
    flac_size = 10 * 60 * 44100 * 2 * 2  # 10min, 44.1kHz, stereo, 16-bit
    result = format_filesize(flac_size)
    assert "MB" in result


def test_format_filesize_decimal_precision():
    """Test decimal precision in formatting"""
    # 1.5 KB
    assert format_filesize(1536) == "1.5 KB"
    # 2.3 MB
    assert format_filesize(int(2.3 * 1024 * 1024)) == "2.3 MB"


# ===== Integration Tests =====

def test_combined_formatting():
    """Test combining duration and filesize formatting"""
    # Example: 5-minute audio file of 50 MB
    duration = 5 * 60
    filesize = 50 * 1024 * 1024

    duration_str = format_duration(duration)
    filesize_str = format_filesize(filesize)

    assert duration_str == "5m 0s"
    assert filesize_str == "50.0 MB"


def test_format_duration_edge_cases():
    """Test edge cases for duration formatting"""
    # Exactly 1 hour
    assert format_duration(3600) == "1h 0m 0s"

    # Just under 1 hour
    assert format_duration(3599) == "59m 59s"

    # Just over 1 hour
    assert format_duration(3601) == "1h 0m 1s"


def test_format_filesize_edge_cases():
    """Test edge cases for filesize formatting"""
    # Exactly 1 KB
    assert format_filesize(1024) == "1.0 KB"

    # Just under 1 KB
    assert format_filesize(1023) == "1023.0 B"

    # Just over 1 KB
    assert format_filesize(1025) == "1.0 KB"


# ===== Performance Tests =====

def test_format_duration_performance():
    """Test duration formatting performance"""
    import time

    start = time.perf_counter()
    for i in range(1000):
        format_duration(i * 60)
    elapsed = time.perf_counter() - start

    # Should be very fast (< 10ms for 1000 calls)
    assert elapsed < 0.01


def test_format_filesize_performance():
    """Test filesize formatting performance"""
    import time

    start = time.perf_counter()
    for i in range(1000):
        format_filesize(i * 1024 * 1024)
    elapsed = time.perf_counter() - start

    # Should be very fast (< 10ms for 1000 calls)
    assert elapsed < 0.01
