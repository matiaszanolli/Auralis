#!/usr/bin/env python3
"""
Auto-Mastering Script

Uses SimpleMasteringPipeline for fingerprint-driven adaptive mastering.

Usage:
    python auto_master.py input.flac
    python auto_master.py input.flac -o remastered.wav
    python auto_master.py input.flac --intensity 0.8
"""

import argparse
from pathlib import Path

from auralis.core.simple_mastering import create_simple_mastering_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Auto-mastering with fingerprint-driven adaptive processing"
    )
    parser.add_argument('input', help='Input audio file')
    parser.add_argument('-o', '--output', help='Output WAV file')
    parser.add_argument('-i', '--intensity', type=float, default=1.0,
                        help='Processing intensity 0.0-1.0')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress progress output')
    parser.add_argument('-t', '--time-metrics', action='store_true',
                        help='Show detailed timing for each step (dev only)')

    args = parser.parse_args()

    # Default output path
    input_path = Path(args.input)
    output_path = args.output or str(input_path.parent / f"{input_path.stem}_mastered.wav")

    try:
        pipeline = create_simple_mastering_pipeline()
        result = pipeline.master_file(
            input_path=args.input,
            output_path=output_path,
            intensity=args.intensity,
            verbose=not args.quiet,
            time_metrics=args.time_metrics
        )

        if not args.quiet:
            print(f"\n✨ Success! Play with: ffplay '{result['output']}'")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
