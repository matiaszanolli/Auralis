# -*- coding: utf-8 -*-

"""
Tests for Logging System
~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the logging and debug utilities

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest

from auralis.utils.logging import (
    Code,
    ModuleError,
    set_log_handler,
    set_log_level,
    get_log_level,
    debug,
    info,
    warning,
    error,
    debug_line
)


# ===== Code Class Tests =====

def test_code_class_attributes():
    """Test Code class has expected attributes"""
    assert hasattr(Code, 'INFO_LOADING')
    assert hasattr(Code, 'INFO_EXPORTING')
    assert hasattr(Code, 'INFO_COMPLETED')
    assert hasattr(Code, 'ERROR_VALIDATION')
    assert hasattr(Code, 'ERROR_LOADING')
    assert hasattr(Code, 'ERROR_INVALID_AUDIO')


def test_code_values():
    """Test Code class values"""
    assert isinstance(Code.INFO_LOADING, str)
    assert isinstance(Code.ERROR_VALIDATION, str)
    assert len(Code.INFO_LOADING) > 0
    assert len(Code.ERROR_VALIDATION) > 0


# ===== ModuleError Tests =====

def test_module_error_basic():
    """Test ModuleError creation"""
    error = ModuleError(Code.ERROR_VALIDATION)

    assert isinstance(error, Exception)
    assert error.code == Code.ERROR_VALIDATION


def test_module_error_message():
    """Test ModuleError message format"""
    error = ModuleError(Code.ERROR_LOADING)

    error_str = str(error)
    assert "Module error" in error_str
    assert Code.ERROR_LOADING in error_str


def test_module_error_raise():
    """Test raising ModuleError"""
    with pytest.raises(ModuleError) as exc_info:
        raise ModuleError(Code.ERROR_INVALID_AUDIO)

    assert exc_info.value.code == Code.ERROR_INVALID_AUDIO


def test_module_error_custom_code():
    """Test ModuleError with custom code"""
    custom_code = "CUSTOM_ERROR_CODE"
    error = ModuleError(custom_code)

    assert error.code == custom_code


# ===== Log Handler Tests =====

def test_set_log_handler():
    """Test setting log handler"""
    messages = []

    def test_handler(message):
        messages.append(message)

    set_log_handler(test_handler)

    # Test that handler is set by logging something
    debug("test message")

    # Should have captured the message
    assert len(messages) > 0
    assert "test message" in messages[0]


def test_log_handler_none():
    """Test setting log handler to None"""
    set_log_handler(None)

    # Should not raise exception when logging
    debug("test")
    info("test")
    warning("test")
    error("test")


def test_log_handler_receives_all_levels():
    """Test log handler receives all log levels"""
    messages = []

    def test_handler(message):
        messages.append(message)

    set_log_handler(test_handler)

    debug("debug msg")
    info("info msg")
    warning("warning msg")
    error("error msg")

    assert len(messages) == 4
    assert any("DEBUG" in msg for msg in messages)
    assert any("INFO" in msg for msg in messages)
    assert any("WARNING" in msg for msg in messages)
    assert any("ERROR" in msg for msg in messages)


# ===== Log Level Tests =====

def test_set_log_level_valid():
    """Test setting valid log levels"""
    for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
        set_log_level(level)
        assert get_log_level() == level


def test_set_log_level_case_insensitive():
    """Test setting log level is case insensitive"""
    set_log_level("debug")
    assert get_log_level() == "DEBUG"

    set_log_level("Info")
    assert get_log_level() == "INFO"

    set_log_level("warning")
    assert get_log_level() == "WARNING"


def test_set_log_level_invalid():
    """Test setting invalid log level"""
    original_level = get_log_level()

    # Invalid level should not change current level
    set_log_level("INVALID_LEVEL")
    assert get_log_level() == original_level


def test_get_log_level_default():
    """Test default log level"""
    # Reset to default by setting INFO
    set_log_level("INFO")
    assert get_log_level() in ["DEBUG", "INFO", "WARNING", "ERROR"]


# ===== Logging Function Tests =====

def test_debug_function():
    """Test debug logging function"""
    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    debug("This is a debug message")

    assert len(messages) == 1
    assert "DEBUG" in messages[0]
    assert "This is a debug message" in messages[0]


def test_info_function():
    """Test info logging function"""
    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    info("This is an info message")

    assert len(messages) == 1
    assert "INFO" in messages[0]
    assert "This is an info message" in messages[0]


def test_warning_function():
    """Test warning logging function"""
    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    warning("This is a warning message")

    assert len(messages) == 1
    assert "WARNING" in messages[0]
    assert "This is a warning message" in messages[0]


def test_error_function():
    """Test error logging function"""
    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    error("This is an error message")

    assert len(messages) == 1
    assert "ERROR" in messages[0]
    assert "This is an error message" in messages[0]


def test_debug_line_function():
    """Test debug line separator"""
    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    debug_line()

    assert len(messages) == 1
    assert "-" in messages[0]
    assert len(messages[0]) > 10  # Should be a line of dashes


def test_logging_without_handler():
    """Test logging without handler set"""
    set_log_handler(None)

    # Should not raise exceptions
    debug("test")
    info("test")
    warning("test")
    error("test")
    debug_line()


# ===== Integration Tests =====

def test_full_logging_workflow():
    """Test complete logging workflow"""
    messages = []

    def capture_handler(message):
        messages.append(message)

    # Set handler
    set_log_handler(capture_handler)

    # Set level
    set_log_level("DEBUG")

    # Log various messages
    debug("Starting process")
    info(Code.INFO_LOADING)
    debug_line()
    warning("Low memory")
    debug_line()
    error(Code.ERROR_VALIDATION)

    # Verify all messages captured
    assert len(messages) == 6
    assert any("Starting process" in msg for msg in messages)
    assert any(Code.INFO_LOADING in msg for msg in messages)
    assert any("Low memory" in msg for msg in messages)
    assert any(Code.ERROR_VALIDATION in msg for msg in messages)


def test_exception_handling_with_logging():
    """Test exception handling with logging"""
    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    try:
        error("About to raise exception")
        raise ModuleError(Code.ERROR_INVALID_AUDIO)
    except ModuleError as e:
        error(f"Caught error: {e.code}")

    assert len(messages) == 2
    assert any("About to raise" in msg for msg in messages)
    assert any(Code.ERROR_INVALID_AUDIO in msg for msg in messages)


# ===== Edge Cases =====

def test_empty_log_messages():
    """Test logging empty messages"""
    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    debug("")
    info("")
    warning("")
    error("")

    # Should log empty messages
    assert len(messages) == 4


def test_very_long_log_message():
    """Test logging very long messages"""
    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    long_message = "x" * 10000
    debug(long_message)

    assert len(messages) == 1
    assert len(messages[0]) > 10000


def test_special_characters_in_logs():
    """Test logging messages with special characters"""
    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    special_msg = "Test: \n\t\\\"special\" chars"
    info(special_msg)

    assert len(messages) == 1
    assert special_msg in messages[0]


def test_unicode_in_logs():
    """Test logging Unicode messages"""
    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    unicode_msg = "Audio: 🎵 🎶 Processing..."
    info(unicode_msg)

    assert len(messages) == 1
    assert unicode_msg in messages[0]


# ===== Performance Tests =====

def test_logging_performance_with_handler():
    """Test logging performance with handler"""
    import time

    messages = []
    set_log_handler(lambda msg: messages.append(msg))

    start = time.perf_counter()
    for i in range(1000):
        debug(f"Message {i}")
    elapsed = time.perf_counter() - start

    # Should be reasonably fast (< 100ms for 1000 messages)
    assert elapsed < 0.1
    assert len(messages) == 1000


def test_logging_performance_without_handler():
    """Test logging performance without handler"""
    import time

    set_log_handler(None)

    start = time.perf_counter()
    for i in range(1000):
        debug(f"Message {i}")
    elapsed = time.perf_counter() - start

    # Should be very fast when no handler (< 10ms)
    assert elapsed < 0.01
