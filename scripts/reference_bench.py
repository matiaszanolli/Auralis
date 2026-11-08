#!/usr/bin/env python3
"""Hold the adaptive mastering path to the user's reference records.

Renders each reference through the app's own chunked renderer (the path a stream
takes), profiles source and result with ``auralis.analysis.reference_profile`` and
reports the change. Two roles:

  good  an excellent master. The render must leave it essentially alone
        (``near_identity_violations``); any violation fails the run.
  flat  a brick-walled master. The render should move it toward the good ones;
        the change is reported, not gated, until the targets are tuned by ear.

The render runs under a throwaway HOME, so the real library, caches and
fingerprint store are never touched.

    python scripts/reference_bench.py --refs refs.json

refs.json:
    [{"name": "Crow", "path": "/music/crow.mp3", "role": "good"},
     {"name": "Scarlet", "path": "/music/scarlet.flac", "role": "flat"}]

Exit code 1 when a "good" reference is not left alone.
"""

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Must happen before anything imports auralis: caches and the library resolve
# under HOME at import time.
_HOME = tempfile.mkdtemp(prefix="auralis-bench-home-")
os.environ["HOME"] = _HOME
sys.path[:0] = [str(REPO), str(REPO / "auralis-web" / "backend")]


def render(path: str, track_id: int) -> Path:
    """Render ``path`` through the chunked adaptive path; return the full-file WAV."""
    from core.chunked_processor import ChunkedAudioProcessor
    from core.file_signature import FileSignatureService
    from core.mastering_target_service import get_mastering_target_service

    # The stream path loads the stored fingerprint; extract it the same way a
    # first play does, without writing a sidecar.
    get_mastering_target_service().load_fingerprint(
        track_id, path, extract_if_missing=True, save_extracted=False,
        file_signature=FileSignatureService.generate(path),
    )
    processor = ChunkedAudioProcessor(track_id=track_id, filepath=path, preset="adaptive", intensity=1.0)
    try:
        return Path(asyncio.run(processor.get_full_processed_audio_path()))
    finally:
        processor.close()


def _row(label: str, p) -> str:
    return (f"  {label:7s} LUFS {p.integrated_lufs:6.1f}  LRA {p.loudness_range_lu:4.1f}  "
            f"PLR {p.plr_db:5.1f}  crest {p.crest_median_db:5.1f}  spread {p.rms_spread_db:4.1f}  "
            f"corr {p.correlation:5.2f}  S/M {p.side_mid_db:5.1f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refs", required=True, type=Path, help="JSON list of {name, path, role}")
    parser.add_argument("--json-out", type=Path, help="also write the profiles and verdicts here")
    args = parser.parse_args()

    from auralis.analysis.reference_profile import near_identity_violations, profile_audio
    from auralis.io.unified_loader import load_audio

    refs = json.loads(args.refs.read_text())
    report, failed = [], False
    for index, ref in enumerate(refs):
        started = time.time()
        before_audio, before_sr = load_audio(ref["path"])
        rendered = render(ref["path"], 900_000 + index)
        after_audio, after_sr = load_audio(str(rendered))
        before, after = profile_audio(before_audio, before_sr), profile_audio(after_audio, after_sr)

        print(f"{ref['name']} [{ref['role']}]  ({time.time() - started:.0f}s)")
        print(_row("source", before))
        print(_row("result", after))
        entry = {"name": ref["name"], "role": ref["role"],
                 "source": before.as_dict(), "result": after.as_dict()}
        if ref["role"] == "good":
            violations = near_identity_violations(before, after)
            entry["violations"] = violations
            print("  OK: left alone" if not violations else "  FAIL: " + "; ".join(violations))
            failed |= bool(violations)
        else:
            print(f"  change: PLR {after.plr_db - before.plr_db:+.1f} dB, crest "
                  f"{after.crest_median_db - before.crest_median_db:+.1f} dB, corr "
                  f"{after.correlation - before.correlation:+.2f}")
        report.append(entry)

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        shutil.rmtree(_HOME, ignore_errors=True)
    sys.exit(code)
