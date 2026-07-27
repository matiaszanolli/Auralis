#!/usr/bin/env python3
"""
Auto-Mastering Script

Uses SimpleMasteringPipeline for fingerprint-driven adaptive mastering.

Usage (single file):
    python auto_master.py input.flac
    python auto_master.py input.flac -o remastered.wav
    python auto_master.py input.flac --intensity 0.8

Usage (folder - recursively remaster all audio files):
    python auto_master.py /path/to/music/folder
    # Creates output/ folder with remasted files in same structure
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any, cast

from auralis.core.simple_mastering import (
    SimpleMasteringPipeline,
    create_simple_mastering_pipeline,
)

# Supported audio formats
AUDIO_EXTENSIONS = {'.flac', '.wav', '.mp3', '.ogg', '.m4a', '.aac'}
QUALITY_ACCEPTED_VERDICTS = frozenset({'improved', 'bypass'})
QUALITY_VERDICTS = ('improved', 'bypass', 'rejected', 'unavailable')
QUALITY_GATE_FAILURE_EXIT = 2


def get_quality_evaluation(result: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized quality evaluation from a mastering result."""
    evaluation = result.get('evaluation')
    if not isinstance(evaluation, dict):
        return {
            'verdict': 'unavailable',
            'reason': 'mastering result did not include a quality evaluation',
        }
    verdict = evaluation.get('verdict')
    if verdict not in QUALITY_VERDICTS:
        return {
            **evaluation,
            'verdict': 'unavailable',
            'reason': f"unknown quality verdict: {verdict!r}",
        }
    return evaluation


def quality_gate_passed(result: dict[str, Any]) -> bool:
    """Whether a mastering result is objectively accepted."""
    return get_quality_evaluation(result)['verdict'] in QUALITY_ACCEPTED_VERDICTS


def format_quality_outcome(result: dict[str, Any]) -> str:
    """Build a concise, user-facing quality-gate outcome."""
    evaluation = get_quality_evaluation(result)
    verdict = evaluation['verdict']
    if verdict == 'improved':
        dimensions = evaluation.get('improved_dimensions') or ()
        detail = ', '.join(dimensions) if dimensions else 'measured quality'
        return f"accepted — improved {detail}"
    if verdict == 'bypass':
        return "accepted — no material adjustment was needed"
    if verdict == 'rejected':
        regressed = evaluation.get('regressed_dimensions') or ()
        artifacts = evaluation.get('artifact_violations') or ()
        if regressed:
            return f"rejected — regressed {', '.join(regressed)}"
        if artifacts:
            return f"rejected — artifact gate: {', '.join(artifacts)}"
        return "rejected — no diagnosed dimension improved enough"
    return f"unavailable — {evaluation.get('reason', 'unknown evaluation error')}"


def master_single_file(
    pipeline: SimpleMasteringPipeline,
    input_path: str | Path,
    output_path: str | Path,
    intensity: float,
    quiet: bool,
    time_metrics: bool,
) -> dict[str, Any]:
    """Master a single audio file."""
    result = pipeline.master_file(
        input_path=str(input_path),
        output_path=str(output_path),
        intensity=intensity,
        verbose=not quiet,
        time_metrics=time_metrics
    )
    return cast(dict[str, Any], result)


def master_folder(
    pipeline: SimpleMasteringPipeline,
    input_folder: str | Path,
    output_folder: str | Path,
    intensity: float,
    quiet: bool,
    time_metrics: bool,
) -> dict[str, Any]:
    """Recursively master all audio files in a folder structure."""
    input_path = Path(input_folder)
    output_path = Path(output_folder)

    # Clean up existing output folder
    if output_path.exists():
        if not quiet:
            print("🧹 Cleaning up existing output folder...")
        shutil.rmtree(output_path)

    output_path.mkdir(parents=True, exist_ok=True)

    # Find all audio files
    audio_files: list[Path] = []
    for ext in AUDIO_EXTENSIONS:
        audio_files.extend(input_path.rglob(f'*{ext}'))
        audio_files.extend(input_path.rglob(f'*{ext.upper()}'))

    audio_files = sorted(set(audio_files))  # Remove duplicates and sort

    if not audio_files:
        print(f"⚠️  No audio files found in {input_folder}")
        return {
            "count": 0,
            "total": 0,
            "accepted": 0,
            "output": str(output_path),
            "failed": [],
            "quality": dict.fromkeys(QUALITY_VERDICTS, 0),
            "quality_failures": [],
        }

    if not quiet:
        print(f"📁 Found {len(audio_files)} audio files to process\n")

    success_count = 0
    failed_files: list[tuple[str, str]] = []
    quality_counts: dict[str, int] = dict.fromkeys(QUALITY_VERDICTS, 0)
    quality_failures: list[dict[str, str]] = []

    for idx, input_file in enumerate(audio_files, 1):
        # Calculate relative path and create output directory structure
        relative_path = input_file.relative_to(input_path)
        output_file = output_path / relative_path.parent / f"{relative_path.stem}_mastered.flac"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            if not quiet:
                print(f"[{idx}/{len(audio_files)}] Processing: {relative_path}")

            result = master_single_file(
                pipeline, input_file, output_file, intensity, quiet=True, time_metrics=False
            )
            success_count += 1
            evaluation = get_quality_evaluation(result)
            verdict = evaluation['verdict']
            quality_counts[verdict] += 1
            if verdict not in QUALITY_ACCEPTED_VERDICTS:
                quality_failures.append({
                    'file': str(relative_path),
                    'verdict': verdict,
                    'reason': format_quality_outcome(result),
                })

            if not quiet:
                marker = '✓' if verdict in QUALITY_ACCEPTED_VERDICTS else '!'
                print(f"  {marker} {output_file.name}: {format_quality_outcome(result)}")

        except Exception as e:  # noqa: BLE001
            # A batch must continue after one file fails, then report all
            # failures in its aggregate result.
            failed_files.append((str(relative_path), str(e)))
            if not quiet:
                print(f"  ✗ Error: {e}")

    # Summary
    if not quiet:
        print(f"\n{'=' * 60}")
        print(f"✨ Completed: {success_count}/{len(audio_files)} files processed")
        print(
            "🔎 Quality gate: "
            f"{quality_counts['improved']} improved, "
            f"{quality_counts['bypass']} bypass, "
            f"{quality_counts['rejected']} rejected, "
            f"{quality_counts['unavailable']} unavailable"
        )
        if failed_files:
            print(f"\n⚠️  Failed files ({len(failed_files)}):")
            for file_path, error in failed_files:
                print(f"  - {file_path}: {error}")
        if quality_failures:
            print(f"\n⚠️  Quality failures ({len(quality_failures)}):")
            for failure in quality_failures:
                print(f"  - {failure['file']}: {failure['reason']}")
        print(f"📂 Output folder: {output_path}")

    return {
        "count": success_count,
        "total": len(audio_files),
        "accepted": sum(
            quality_counts[verdict] for verdict in QUALITY_ACCEPTED_VERDICTS
        ),
        "output": str(output_path),
        "failed": failed_files,
        "quality": quality_counts,
        "quality_failures": quality_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-mastering with fingerprint-driven adaptive processing"
    )
    parser.add_argument('input', help='Input audio file or folder')
    parser.add_argument('-o', '--output', help='Output WAV file (file mode) or output folder (folder mode)')
    parser.add_argument('-i', '--intensity', type=float, default=1.0,
                        help='Processing intensity 0.0-1.0')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress progress output')
    parser.add_argument('-t', '--time-metrics', action='store_true',
                        help='Show detailed timing for each step (dev only)')

    args = parser.parse_args()

    input_path = Path(args.input)

    # Check if input is a file or folder
    if not input_path.exists():
        print(f"❌ Error: {args.input} does not exist")
        return 1

    try:
        pipeline = create_simple_mastering_pipeline()

        if input_path.is_file():
            # Single file mode
            output_path = args.output or str(input_path.parent / f"{input_path.stem}_mastered.wav")
            result = master_single_file(
                pipeline, input_path, output_path, args.intensity, args.quiet, args.time_metrics
            )

            if not args.quiet:
                print(f"\n🔎 Quality gate: {format_quality_outcome(result)}")
                if quality_gate_passed(result):
                    print(f"✨ Success! Play with: ffplay '{result['output']}'")
                else:
                    print(
                        f"⚠️  Candidate kept for inspection: {result['output']}"
                    )
            if not quality_gate_passed(result):
                return QUALITY_GATE_FAILURE_EXIT

        elif input_path.is_dir():
            # Folder mode
            output_folder = args.output or "output"
            result = master_folder(
                pipeline, input_path, output_folder, args.intensity, args.quiet, args.time_metrics
            )

            if result["count"] == 0:
                return 1
            if result["quality_failures"]:
                return QUALITY_GATE_FAILURE_EXIT
            return 0

        return 0

    except Exception as e:  # noqa: BLE001
        # CLI boundary: convert unexpected processing failures into a stable
        # non-zero exit status while preserving the traceback for diagnosis.
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
