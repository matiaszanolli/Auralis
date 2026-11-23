"""A long %-format template with args is logged whole, not lost (#6544).

The sanitizing record factory capped ``record.msg`` at 500 characters even when
it was a template, so a long one lost its trailing ``%s`` while the args stayed:
``getMessage()`` raised "not all arguments converted", the handler printed
``--- Logging error ---`` and the record was dropped. A template with args is
now escaped but never truncated; a pre-formatted message keeps its cap.
"""

import logging

import auralis.utils.logging  # noqa: F401  (installs the sanitizing record factory)


class _Collect(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())  # raises if the template was cut


def _logger():
    log = logging.getLogger("test.log_template_6544")
    log.propagate = False
    log.handlers = [handler := _Collect()]
    log.setLevel(logging.WARNING)
    return log, handler


def test_a_long_template_with_args_is_logged_in_full():
    log, handler = _logger()

    log.warning("a" * 600 + " %s", "tail")

    assert handler.messages == ["a" * 600 + " tail"]


def test_control_characters_are_still_escaped_in_template_and_args():
    log, handler = _logger()

    log.warning("line\nforged %s", "arg\r\nforged")

    assert handler.messages == ["line\\x0aforged arg\\x0d\\x0aforged"]


def test_a_preformatted_message_keeps_its_cap():
    log, handler = _logger()

    log.warning("b" * 600)

    assert handler.messages == ["b" * 500 + "…"]
