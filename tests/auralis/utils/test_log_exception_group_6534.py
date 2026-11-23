"""A logged exception group shows its sub-exceptions, sanitized (#6534).

SanitizingFormatter rebuilt tracebacks from the cause/context chain only. An
exception group keeps its leaves in ``.exceptions``, so a TaskGroup failure was
logged as ``ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)``
with no trace of the error inside it.
"""

import asyncio

from auralis.utils.logging import SanitizingFormatter


def _format(exc: BaseException) -> str:
    return SanitizingFormatter().formatException((type(exc), exc, exc.__traceback__))


def _caught(make):
    try:
        make()
    except BaseException as exc:  # noqa: BLE001 - the test formats whatever was raised
        return exc
    raise AssertionError("nothing was raised")


def test_a_task_group_failure_logs_the_sub_exception_escaped():
    async def boom():
        raise ValueError("bad tag\nforged line")

    async def main():
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())

    text = _format(_caught(lambda: asyncio.run(main())))

    assert "ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)" in text
    assert "    | ValueError: bad tag\\x0aforged line" in text
    assert "in boom" in text
    assert "\nforged line" not in text


def test_nested_groups_and_chained_members_are_all_rendered():
    def raise_nested():
        try:
            raise KeyError("cause")
        except KeyError as cause:
            inner = RuntimeError("member")
            inner.__cause__ = cause
        raise ExceptionGroup("outer", [ValueError("first"), ExceptionGroup("inner", [inner])])

    text = _format(_caught(raise_nested))

    for line in ("ExceptionGroup: outer (2 sub-exceptions)", "ValueError: first",
                 "ExceptionGroup: inner (1 sub-exception)", "RuntimeError: member", "KeyError: 'cause'"):
        assert line in text, line


def test_a_plain_chained_exception_renders_as_before():
    def raise_chain():
        try:
            raise KeyError("first")
        except KeyError as first:
            raise ValueError("second") from first

    text = _format(_caught(raise_chain))

    assert "The above exception was the direct cause of the following exception:" in text
    assert "+----" not in text
