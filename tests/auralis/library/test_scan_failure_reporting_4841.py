"""
Scan failures reach the caller with a path and a reason (#4841)

`BatchProcessor` caught per-file exceptions, logged them, and returned a bare
`'failed'` with nothing attached. Only `files_failed: <int>` crossed the API
boundary, so the UI could say "3 files failed" and never which three or why —
leaving the user to read backend logs a desktop end user generally cannot see.
And the more common of the two failure sites logged at `debug`, a level most
default configs drop, so even that fallback was usually empty.

`ScanResult` now carries a bounded list of (filepath, reason), the per-file log
is a `warning`, and both the REST response and the `scan_complete` broadcast
include it.

The list is capped: a folder of corrupt files must not turn a scan result into
an unbounded WebSocket payload. `files_failed` stays exact regardless, so the
count and the named subset can legitimately disagree — the UI is written to
expect that.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import inspect
from unittest.mock import MagicMock

import pytest

from auralis.library.scan_models import MAX_RECORDED_FAILURES, ScanFailure, ScanResult
from auralis.library.scanner.batch_processor import BatchProcessor


class TestScanResultRecordsFailures:
    def test_record_failure_counts_and_retains(self):
        result = ScanResult()

        result.record_failure('/music/broken.mp3', 'Could not read audio information')

        assert result.files_failed == 1
        assert result.failures == [
            ScanFailure('/music/broken.mp3', 'Could not read audio information')
        ]

    def test_count_stays_exact_past_the_cap(self):
        """The cap bounds the payload, not the tally."""
        result = ScanResult()

        for i in range(MAX_RECORDED_FAILURES + 25):
            result.record_failure(f'/music/{i}.mp3', 'boom')

        assert result.files_failed == MAX_RECORDED_FAILURES + 25
        assert len(result.failures) == MAX_RECORDED_FAILURES

    def test_serialises_for_the_wire(self):
        assert ScanFailure('/a.mp3', 'why').to_dict() == {
            'filepath': '/a.mp3', 'reason': 'why'
        }


def _processor(*, extract_returns=None, extract_raises=None, add_returns=None):
    library_manager = MagicMock()
    library_manager.tracks.get_by_path.return_value = None
    library_manager.tracks.add.return_value = add_returns

    audio_analyzer = MagicMock()
    if extract_raises is not None:
        audio_analyzer.extract_audio_info.side_effect = extract_raises
    else:
        audio_analyzer.extract_audio_info.return_value = extract_returns

    metadata_extractor = MagicMock()
    return BatchProcessor(library_manager, audio_analyzer, metadata_extractor)


class TestProcessSingleFileReportsWhy:
    def test_unreadable_file_reports_a_reason(self):
        processor = _processor(extract_returns=None)

        status, track, reason = processor.process_single_file(
            '/music/corrupt.mp3', skip_existing=True, check_modifications=False
        )

        assert status == 'failed'
        assert track is None
        assert reason and 'unreadable' in reason.lower()

    def test_raised_exception_reports_its_message(self):
        processor = _processor(extract_raises=OSError('Permission denied'))

        status, _track, reason = processor.process_single_file(
            '/music/locked.mp3', skip_existing=True, check_modifications=False
        )

        assert status == 'failed'
        assert reason == 'Permission denied'

    def test_a_bare_exception_still_yields_a_usable_reason(self):
        """`str(e)` is empty for some exceptions; the class name beats ''."""
        processor = _processor(extract_raises=RuntimeError())

        _status, _track, reason = processor.process_single_file(
            '/music/x.mp3', skip_existing=True, check_modifications=False
        )

        assert reason == 'RuntimeError'

    def test_database_insert_failure_is_distinguished(self):
        processor = _processor(extract_returns=MagicMock(), add_returns=None)

        status, _track, reason = processor.process_single_file(
            '/music/ok.mp3', skip_existing=True, check_modifications=False
        )

        assert status == 'failed'
        assert reason == 'Database insert failed'

    def test_success_carries_no_reason(self):
        track = MagicMock()
        processor = _processor(extract_returns=MagicMock(), add_returns=track)

        status, returned, reason = processor.process_single_file(
            '/music/ok.mp3', skip_existing=True, check_modifications=False
        )

        assert status == 'added'
        assert returned is track
        assert reason is None


class TestBatchAccumulatesFailures:
    def test_batch_records_each_failed_path(self):
        processor = _processor(extract_returns=None)

        result = processor.process_file_batch(
            ['/music/a.mp3', '/music/b.mp3'], skip_existing=True, check_modifications=False
        )

        assert result.files_failed == 2
        assert [f.filepath for f in result.failures] == ['/music/a.mp3', '/music/b.mp3']
        assert all(f.reason for f in result.failures), "every failure needs a reason"

    def test_successes_are_not_recorded_as_failures(self):
        processor = _processor(extract_returns=MagicMock(), add_returns=MagicMock())

        result = processor.process_file_batch(
            ['/music/a.mp3'], skip_existing=True, check_modifications=False
        )

        assert result.files_failed == 0
        assert result.failures == []


class TestLogLevel:
    def test_per_file_failure_logs_at_warning_not_debug(self):
        """The acceptance criterion, checked at the source.

        This was the more common of the two failure sites and logged at `debug`
        — invisible in default configs, so the user's only fallback was empty
        too. A behavioural assertion would need the project's logging shim
        wired up; the level is what the criterion is actually about.
        """
        source = inspect.getsource(BatchProcessor.process_single_file)

        assert 'debug(' not in source, (
            "the per-file failure still logs at debug; default logging configs "
            "drop it, so the failure is invisible to the user (#4841)"
        )
        assert 'warning(' in source

    def test_batch_module_no_longer_imports_debug(self):
        import auralis.library.scanner.batch_processor as bp

        source = inspect.getsource(bp)
        import_line = next(
            line for line in source.splitlines() if 'utils.logging import' in line
        )
        assert 'debug' not in import_line, f"stale debug import: {import_line}"


class TestScannerCarriesFailuresUp:
    """A scan aggregates batches; the failures must survive that."""

    def test_scanner_accumulates_failures_across_batches(self):
        from auralis.library.scanner.scanner import LibraryScanner

        library_manager = MagicMock()
        library_manager.try_acquire_scan_slot.return_value = (True, 1)
        # #4509: a bare MagicMock's auto-attribute return value is truthy,
        # which would otherwise make the per-directory dedup guard reject
        # every scan.
        library_manager.try_reserve_scan_paths.return_value = []
        scanner = LibraryScanner(library_manager)

        files = [f'/music/{i}.mp3' for i in range(6)]
        scanner.file_discovery = MagicMock()
        scanner.file_discovery.discover_audio_files.side_effect = (
            lambda directory, recursive=True: iter(files)
        )

        def _batch(batch, *_a, **_kw):
            batch_result = ScanResult()
            for path in batch:
                batch_result.files_processed += 1
                batch_result.record_failure(path, 'boom')
            return batch_result

        scanner.batch_processor = MagicMock()
        scanner.batch_processor.process_file_batch.side_effect = _batch

        result = scanner.scan_directories(['/music'], batch_size=2)

        assert result.files_failed == 6
        assert [f.filepath for f in result.failures] == files, (
            "failures from later batches were dropped"
        )

    def test_scanner_respects_the_cap_when_aggregating(self, monkeypatch):
        import auralis.library.scanner.scanner as scanner_module
        from auralis.library.scanner.scanner import LibraryScanner

        monkeypatch.setattr(scanner_module, 'MAX_RECORDED_FAILURES', 3)

        library_manager = MagicMock()
        library_manager.try_acquire_scan_slot.return_value = (True, 1)
        # #4509: a bare MagicMock's auto-attribute return value is truthy,
        # which would otherwise make the per-directory dedup guard reject
        # every scan.
        library_manager.try_reserve_scan_paths.return_value = []
        scanner = LibraryScanner(library_manager)

        files = [f'/music/{i}.mp3' for i in range(8)]
        scanner.file_discovery = MagicMock()
        scanner.file_discovery.discover_audio_files.side_effect = (
            lambda directory, recursive=True: iter(files)
        )

        def _batch(batch, *_a, **_kw):
            batch_result = ScanResult()
            for path in batch:
                batch_result.files_processed += 1
                batch_result.record_failure(path, 'boom')
            return batch_result

        scanner.batch_processor = MagicMock()
        scanner.batch_processor.process_file_batch.side_effect = _batch

        result = scanner.scan_directories(['/music'], batch_size=2)

        assert result.files_failed == 8, "the count must stay exact"
        assert len(result.failures) == 3, "the retained list must respect the cap"


class TestWireShape:
    """Both emitters must carry the field, or the UI sees it on one path only."""

    @pytest.mark.parametrize("module_path", [
        "auralis-web/backend/routers/library_scan.py",
        "auralis-web/backend/services/library_auto_scanner.py",
    ])
    def test_scan_complete_broadcast_includes_failures(self, module_path):
        from pathlib import Path

        source = Path(module_path).read_text()

        assert '"failures"' in source, (
            f"{module_path} broadcasts scan_complete without the failures list, "
            "so that path still reports only a count (#4841)"
        )

    def test_rest_response_model_declares_failures(self):
        from pathlib import Path

        source = Path("auralis-web/backend/schemas.py").read_text()

        # response_model FILTERS undeclared keys, so an omission here would
        # silently strip the field from the REST reply.
        assert 'failures: list[dict[str, str]]' in source
