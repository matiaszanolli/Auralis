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
from pathlib import Path

from auralis.core.simple_mastering import create_simple_mastering_pipeline

# Supported audio formats
AUDIO_EXTENSIONS = {'.flac', '.wav', '.mp3', '.ogg', '.m4a', '.aac'}


def master_single_file(pipeline, input_path, output_path, intensity, quiet, time_metrics):
    """Master a single audio file."""
    result = pipeline.master_file(
        input_path=str(input_path),
        output_path=str(output_path),
        intensity=intensity,
        verbose=not quiet,
        time_metrics=time_metrics
    )
    return result


def master_folder(pipeline, input_folder, output_folder, intensity, quiet, time_metrics):
    """Recursively master all audio files in a folder structure."""
    input_path = Path(input_folder)
    output_path = Path(output_folder)

    # Clean up existing output folder
    if output_path.exists():
        if not quiet:
            print(f"🧹 Cleaning up existing output folder...")
        shutil.rmtree(output_path)

    output_path.mkdir(parents=True, exist_ok=True)

    # Find all audio files
    audio_files = []
    for ext in AUDIO_EXTENSIONS:
        audio_files.extend(input_path.rglob(f'*{ext}'))
        audio_files.extend(input_path.rglob(f'*{ext.upper()}'))

    audio_files = sorted(set(audio_files))  # Remove duplicates and sort

    if not audio_files:
        print(f"⚠️  No audio files found in {input_folder}")
        return {"count": 0, "output": str(output_path)}

    if not quiet:
        print(f"📁 Found {len(audio_files)} audio files to process\n")

    success_count = 0
    failed_files = []

    for idx, input_file in enumerate(audio_files, 1):
        # Calculate relative path and create output directory structure
        relative_path = input_file.relative_to(input_path)
        output_file = output_path / relative_path.parent / f"{relative_path.stem}_mastered.wav"
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

        except Exception as e:
            failed_files.append((str(relative_path), str(e)))
            if not quiet:
                print(f"  ✗ Error: {e}")

    # Summary
    if not quiet:
        print(f"\n{'=' * 60}")
        print(f"✨ Completed: {success_count}/{len(audio_files)} files processed")
        if failed_files:
            print(f"\n⚠️  Failed files ({len(failed_files)}):")
            for file_path, error in failed_files:
                print(f"  - {file_path}: {error}")
        print(f"📂 Output folder: {output_path}")

    return {
        "count": success_count,
        "total": len(audio_files),
        "output": str(output_path),
        "failed": failed_files
    }


def main():
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
                print(f"\n✨ Success! Play with: ffplay '{result['output']}'")

        elif input_path.is_dir():
            # Folder mode
            output_folder = args.output or "output"
            result = master_folder(
                pipeline, input_path, output_folder, args.intensity, args.quiet, args.time_metrics
            )

            if result["count"] > 0:
                return 0
            else:
                return 1

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
