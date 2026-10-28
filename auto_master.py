#!/usr/bin/env python3
"""
Auto-Mastering Script

Standalone OFFLINE CLI. This is the sole entry point into
``SimpleMasteringPipeline`` and the 13-stage ``auralis/core/stages/`` package —
roughly 3,400 LOC that nothing in the Electron app reaches (#4873). The app's
own audio goes ``HybridProcessor.process()`` -> ``ContinuousMode`` instead.
Keeping this tool is what keeps that subsystem alive; retiring it would make
~3,400 LOC deletable.

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
from typing import Any

from auralis.core.mastering_config import validate_intensity
from auralis.core.simple_mastering import SimpleMasteringPipeline

# Supported audio formats
AUDIO_EXTENSIONS = {'.flac', '.wav', '.mp3', '.ogg', '.m4a', '.aac'}


def _intensity_arg(text: str) -> float:
    """argparse type for --intensity: a finite number in [0.0, 1.0] (#6137)."""
    try:
        return validate_intensity(float(text))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _unsafe_output_reason(input_path: Path, output_path: Path) -> str | None:
    """Refusal reason when the output overlaps the input tree (#5696).

    ``-o`` equal to, inside, or containing the input folder all end in data
    loss: the old unconditional ``shutil.rmtree(output_path)`` deleted the
    sources (or their ancestors) before the input was even scanned. Paths
    are resolved so symlinked/relative spellings of the same tree cannot
    sneak past the comparison.
    """
    input_resolved = input_path.resolve()
    output_resolved = output_path.resolve()
    if output_resolved == input_resolved:
        return (
            f"output folder is the input folder ({input_resolved}); refusing "
            f"to master a folder into itself (#5696)"
        )
    if output_resolved in input_resolved.parents:
        return (
            f"output folder ({output_resolved}) contains the input folder "
            f"({input_resolved}); refusing — the input tree would be wiped "
            f"(#5696)"
        )
    if input_resolved in output_resolved.parents:
        return (
            f"output folder ({output_resolved}) is inside the input folder "
            f"({input_resolved}); refusing — a re-run would master the "
            f"mastered files (#5696)"
        )
    return None


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
    # master_file is annotated dict[str, Any]; the old cast() here was
    # redundant (flagged by mypy while touching this file for #5696).
    return result


def master_folder(
    pipeline: SimpleMasteringPipeline,
    input_folder: str | Path,
    output_folder: str | Path,
    intensity: float,
    quiet: bool,
    time_metrics: bool,
    clean: bool = False,
) -> dict[str, Any]:
    """Recursively master all audio files in a folder structure.

    ``clean`` (the CLI's ``--clean``) is the only way an existing output
    folder gets wiped (#5696); the default writes into it, overwriting
    staged ``*_mastered.flac`` files and leaving unrelated files alone.
    """
    input_path = Path(input_folder)
    output_path = Path(output_folder)

    # Refuse overlapping output before touching anything (#5696): the old
    # unconditional rmtree below deleted the input tree when -o was the
    # input, a parent of it, or an existing user folder hit by the default
    # relative "output".
    refusal = _unsafe_output_reason(input_path, output_path)
    if refusal is not None:
        print(f"❌ Error: {refusal}")
        return {
            "count": 0,
            "total": 0,
            "output": str(output_path),
            "failed": [],
        }

    # Wipe the existing output folder only when explicitly asked (#5696).
    if output_path.exists() and clean:
        if not quiet:
            print("🧹 Cleaning up existing output folder (--clean)...")
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
            "output": str(output_path),
            "failed": [],
        }

    if not quiet:
        print(f"📁 Found {len(audio_files)} audio files to process\n")

    success_count = 0
    failed_files: list[tuple[str, str]] = []
    claimed_outputs: dict[Path, Path] = {}  # output file -> the input that owns it

    for idx, input_file in enumerate(audio_files, 1):
        # Calculate relative path and create output directory structure
        relative_path = input_file.relative_to(input_path)
        output_file = output_path / relative_path.parent / f"{relative_path.stem}_mastered.flac"

        # Outputs are named from the stem, so `Track.mp3` and `Track.wav` (or
        # `.flac`/`.FLAC`) map to one file; the later render would silently
        # replace the earlier master (#6135). Refuse it up front and say why.
        owner = claimed_outputs.setdefault(output_file, relative_path)
        if owner != relative_path:
            failed_files.append((str(relative_path), f"output name collides with {owner}; not rendered"))
            if not quiet:
                print(f"[{idx}/{len(audio_files)}] ✗ {relative_path}: output name collides with {owner}")
            continue
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            if not quiet:
                print(f"[{idx}/{len(audio_files)}] Processing: {relative_path}")

            master_single_file(
                pipeline, input_file, output_file, intensity, quiet=True, time_metrics=False
            )
            success_count += 1

            if not quiet:
                print(f"  ✓ {output_file.name}")

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
        print(f"📂 Output folder: {output_path}")
    if failed_files:
        # stderr and regardless of -q: a script running quietly still needs to
        # see which files did not get mastered (#6136).
        print(f"\n⚠️  Failed files ({len(failed_files)}):", file=sys.stderr)
        for file_path, error in failed_files:
            print(f"  - {file_path}: {error}", file=sys.stderr)

    return {
        "count": success_count,
        "total": len(audio_files),
        "output": str(output_path),
        "failed": failed_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-mastering with fingerprint-driven adaptive processing"
    )
    parser.add_argument('input', help='Input audio file or folder')
    parser.add_argument('-o', '--output', help='Output WAV file (file mode) or output folder (folder mode)')
    parser.add_argument('-i', '--intensity', type=_intensity_arg, default=1.0,
                        help='Processing intensity 0.0-1.0')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress progress output')
    parser.add_argument('-t', '--time-metrics', action='store_true',
                        help='Show detailed timing for each step (dev only)')
    parser.add_argument('--clean', action='store_true',
                        help='Folder mode: wipe the output folder before '
                             'mastering (never allowed to overlap the input)')

    args = parser.parse_args()

    input_path = Path(args.input)

    # Check if input is a file or folder
    if not input_path.exists():
        print(f"❌ Error: {args.input} does not exist")
        return 1

    try:
        pipeline = SimpleMasteringPipeline()

        if input_path.is_file():
            # Single file mode
            output_path = Path(args.output or str(input_path.parent / f"{input_path.stem}_mastered.wav"))
            # Same refusal as folder mode for the exact-overlap case (#5696):
            # -o pointing at the input replaced the original in place via the
            # staged os.replace with no warning.
            if output_path.resolve() == input_path.resolve():
                print(
                    f"❌ Error: output file is the input file "
                    f"({input_path.resolve()}); refusing to overwrite the "
                    f"source (#5696)"
                )
                return 1
            result = master_single_file(
                pipeline, input_path, output_path, args.intensity, args.quiet, args.time_metrics
            )

            if not args.quiet:
                print(f"\n✨ Success! Play with: ffplay '{result['output']}'")

        elif input_path.is_dir():
            # Folder mode
            output_folder = args.output or "output"
            result = master_folder(
                pipeline, input_path, output_folder, args.intensity, args.quiet, args.time_metrics,
                clean=args.clean,
            )

            # Any failure is a failure: a partial batch must not look like success (#6136).
            if result["count"] == 0 or result["failed"]:
                return 1
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
