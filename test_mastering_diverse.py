#!/usr/bin/env python3
"""
Diverse mastering test — good vs bad source material.

Tests the pipeline across source material quality extremes:
  - Good:  well-mastered hi-DR references (SW HCE, Gilmour Pompeii, Polyphia, deadmau5)
  - Mixed: period-typical or format-limited (Metallica Load, Nightwish mp3, Soda Stereo m4a)
  - Bad:   notorious loudness-war victims (Death Magnetic, St. Anger)

Measures before/after: LUFS, True Peak, LRA, crest factor, clip ratio.
Goal: confirm net benefit across all quality tiers.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))

from auralis.core.simple_mastering import SimpleMasteringPipeline  # noqa: E402

# ---------------------------------------------------------------------------
# Track list: (label, input_path, quality_tier)
# ---------------------------------------------------------------------------
TRACKS = [
    # ── Good: well-mastered, high-DR reference material ──────────────────────
    # Steven Wilson — Hand Cannot Erase (Limited Edition CD1, stereo MP3, 44.1 kHz)
    # These are the correct stereo masters; the HCE [2015] folder has 5.1 surround FLACs.
    (
        "SW HCE / Hand Cannot Erase",
        "/mnt/Musica/Musica/Steven Wilson/2015 - Hand. Cannot. Erase (Limited Edition)/CD1/03 - Hand Cannot Erase.mp3",
        "good",
    ),
    (
        "SW HCE / 3 Years Older",
        "/mnt/Musica/Musica/Steven Wilson/2015 - Hand. Cannot. Erase (Limited Edition)/CD1/02 - 3 Years Older.mp3",
        "good",
    ),
    (
        "SW HCE / Routine",
        "/mnt/Musica/Musica/Steven Wilson/2015 - Hand. Cannot. Erase (Limited Edition)/CD1/05 - Routine.mp3",
        "good",
    ),
    (
        "SW HCE / Home Invasion",
        "/mnt/Musica/Musica/Steven Wilson/2015 - Hand. Cannot. Erase (Limited Edition)/CD1/06 - Home Invasion.mp3",
        "good",
    ),
    # Porcupine Tree — Closure/Continuation (2022): exceptional modern production
    (
        "Porcupine Tree / Harridan",
        "/mnt/Musica/Musica/Porcupine Tree/Porcupine Tree - 2022 - Closure - Continuation (FLAC)/01 - Harridan.flac",
        "good",
    ),
    (
        "Porcupine Tree / Dignity",
        "/mnt/Musica/Musica/Porcupine Tree/Porcupine Tree - 2022 - Closure - Continuation (FLAC)/04 - Dignity.flac",
        "good",
    ),
    (
        "Polyphia / Nasty",
        "/mnt/Musica/Musica/Polyphia/New Levels New Devils [2018]/01. Nasty (feat Jason Richardson).flac",
        "good",
    ),
    (
        "Polyphia / GOAT",
        "/mnt/Musica/Musica/Polyphia/New Levels New Devils [2018]/10. GOAT.flac",
        "good",
    ),
    (
        "deadmau5 / I Remember",
        "/mnt/Musica/Musica/deadmau5/Deadmau5 - 2008 - Random Album Title/07. I Remember.flac",
        "good",
    ),
    (
        "Gilmour / Wish You Were Here",
        "/mnt/Musica/Musica/David Gilmour/2017 - Live At Pompeii/08.-Wish You Were Here.flac",
        "good",
    ),
    (
        "Gilmour / Comfortably Numb",
        "/mnt/Musica/Musica/David Gilmour/2017 - Live At Pompeii/21.-Comfortably Numb.flac",
        "good",
    ),
    (
        "Gilmour / Shine On",
        "/mnt/Musica/Musica/David Gilmour/2017 - Live At Pompeii/13.-Shine On You Crazy Diamond (Pts. 1-5).flac",
        "good",
    ),
    # ── Mixed: period-typical or format-limited masters ───────────────────────
    (
        "Metallica / Load — Ain’t My Bitch",
        "/mnt/Musica/Musica/Metallica/Metallica - Load (1996) [FLAC] 88/01. Ain’t My Bitch.flac",
        "mixed",
    ),
    (
        "Metallica / Load — King Nothing",
        "/mnt/Musica/Musica/Metallica/Metallica - Load (1996) [FLAC] 88/05. King Nothing.flac",
        "mixed",
    ),
    (
        "Nightwish / Imaginaerum — Storytime",
        "/mnt/Musica/Musica/Nightwish/2011 - Imaginaerum/CD-1/02 - Storytime.mp3",
        "mixed",
    ),
    (
        "Nightwish / Imaginaerum — Ghost River",
        "/mnt/Musica/Musica/Nightwish/2011 - Imaginaerum/CD-1/03 - Ghost River.mp3",
        "mixed",
    ),
    (
        "Soda Stereo / Comfort — En La Ciudad",
        "/mnt/Musica/Musica/Soda Stereo/1996 - Comfort y Música para Volar (Lossless)/02 Soda Stereo - En La Ciudad de La Furia.m4a",
        "mixed",
    ),
    (
        "Soda Stereo / Comfort — Zoom",
        "/mnt/Musica/Musica/Soda Stereo/1996 - Comfort y Música para Volar (Lossless)/05 Soda Stereo - Zoom.m4a",
        "mixed",
    ),
    # ── Bad: loudness-war victims, notorious bad masters ──────────────────────
    # Greta Van Fleet — Starcatcher (2023, 96 kHz Hi-Res)
    # Good band, very hot mastering: -5.6 LUFS, 4.6 LU LRA, crest ~8 dB
    (
        "GVF / Starcatcher — Fate of the Faithful",
        "/mnt/Musica/Musica/Greta Van Fleet/Starcatcher [2023]/01 Fate Of The Faithful.flac",
        "bad",
    ),
    (
        "GVF / Starcatcher — Runway Blues",
        "/mnt/Musica/Musica/Greta Van Fleet/Starcatcher [2023]/05 Runway Blues.flac",
        "bad",
    ),
    # Annihilator discography: famously over-compressed modern metal
    (
        "Annihilator / All For You — All For You",
        "/mnt/Musica/Musica/Annihilator/All For You/(01) [Annihilator] All For You.flac",
        "bad",
    ),
    (
        "Annihilator / Metal — Army of One",
        "/mnt/Musica/Musica/Annihilator/Metal/03 Army of One.flac",
        "bad",
    ),
    (
        "Annihilator / Criteria BW — Bloodbath",
        "/mnt/Musica/Musica/Annihilator/1999 - Criteria For A Black Widow/(01) [Annihilator] Bloodbath.flac",
        "bad",
    ),
    (
        "Metallica / St. Anger — St. Anger",
        "/mnt/Musica/Musica/Metallica/UICY94669 - St. Anger/02 - St. Anger.flac",
        "bad",
    ),
    (
        "Metallica / St. Anger — Frantic",
        "/mnt/Musica/Musica/Metallica/UICY94669 - St. Anger/01 - Frantic.flac",
        "bad",
    ),
    (
        "Metallica / Death Magnetic — That Was Just Your Life",
        "/mnt/Musica/Musica/Metallica/METALLICA [2008] [5LP] Death Magnetic [VERTIGO 2517-73731-0]/01 - That Was Just Your Life.flac",
        "bad",
    ),
    (
        "Metallica / Death Magnetic — All Nightmare Long",
        "/mnt/Musica/Musica/Metallica/METALLICA [2008] [5LP] Death Magnetic [VERTIGO 2517-73731-0]/05 - All Nightmare Long.flac",
        "bad",
    ),
    # AC/DC Power Up (2020): heavily brickwalled modern release
    (
        "AC/DC / Power Up — Shot in the Dark",
        "/mnt/Musica/Musica/AC_DC/POWER UP/03 Shot in the Dark.flac",
        "bad",
    ),
    (
        "AC/DC / Power Up — Realize",
        "/mnt/Musica/Musica/AC_DC/POWER UP/01 Realize.flac",
        "bad",
    ),
    # Motörhead 2020 40th Anniversary Remaster — known over-compression
    (
        "Motörhead / Ace of Spades (2020) — Ace of Spades",
        "/mnt/Musica/Musica/Motörhead/Ace of Spades [2020]/01 Ace of Spades (40th Anniversary Master).flac",
        "bad",
    ),
    (
        "Motörhead / Ace of Spades (2020) — Fast and Loose",
        "/mnt/Musica/Musica/Motörhead/Ace of Spades [2020]/05 Fast and Loose (40th Anniversary Master).flac",
        "bad",
    ),
    # Motörhead 1977 (original): raw/lo-fi but not loudness-war — baseline reference
    (
        "Motörhead / 1977 — Motörhead",
        "/mnt/Musica/Musica/Motörhead/1977  Motorhead/(01) [Motorhead] Motorhead.flac",
        "mixed",
    ),
    # Dio — 80s Japanese pressings (audiophile quality, good dynamics)
    (
        "Dio / Holy Diver (1986 JP) — Holy Diver",
        "/mnt/Musica/Musica/Dio/Albums/1983 - Holy Diver [1986 Nippon Phonogram 32PD-128 Japan]/(2) [Dio] Holy Diver.flac",
        "good",
    ),
    (
        "Dio / Holy Diver (1986 JP) — Rainbow in the Dark",
        "/mnt/Musica/Musica/Dio/Albums/1983 - Holy Diver [1986 Nippon Phonogram 32PD-128 Japan]/(8) [Dio] Rainbow In The Dark.flac",
        "good",
    ),
]

OUTPUT_DIR = Path(__file__).parent / "output_diverse_test8"
RESULTS_FILE = OUTPUT_DIR / "results.json"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def measure_ffmpeg_lufs(path: str) -> dict:
    """Use ffmpeg ebur128 for accurate LUFS, LRA, and True Peak.

    ffmpeg emits per-frame 'I: X LUFS' lines throughout the file, starting at
    the gating floor (-70 LUFS) and converging to the integrated value. We need
    the FINAL summary value, not the first match. Strategy: parse the 'Summary:'
    block from the end of stderr, where the values are stable.
    """
    try:
        cmd = [
            "ffmpeg", "-nostdin", "-i", str(path),
            "-filter:a", "ebur128=peak=true",
            "-f", "null", "-"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        output = proc.stderr

        # Isolate the Summary block (everything after the last 'Summary:')
        summary_idx = output.rfind("Summary:")
        summary = output[summary_idx:] if summary_idx != -1 else output

        # Parse integrated loudness from summary
        m = re.search(r"\bI:\s*([-\d.]+)\s*LUFS", summary)
        lufs = float(m.group(1)) if m else None

        # Parse LRA from summary
        m = re.search(r"\bLRA:\s*([\d.]+)\s*LU", summary)
        lra = float(m.group(1)) if m else None

        # Parse True Peak from summary (single 'Peak:' line)
        peaks = re.findall(r"\bPeak:\s*([-\d.]+)\s*dBFS", summary)
        true_peak = max(float(p) for p in peaks) if peaks else None

        return {"lufs": lufs, "lra": lra, "true_peak": true_peak}
    except Exception as e:
        return {"lufs": None, "lra": None, "true_peak": None, "error": str(e)}


def measure_numpy(path: str) -> dict:
    """Crest factor and clip ratio from raw samples."""
    try:
        # Use ffmpeg to decode to wav for non-native formats
        import tempfile
        suffix = Path(path).suffix.lower()
        native = suffix in {".flac", ".wav", ".ogg"}

        if native:
            data, sr = sf.read(path, dtype="float32")
        else:
            with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
                subprocess.run(
                    ["ffmpeg", "-nostdin", "-y", "-i", path, tmp.name],
                    capture_output=True, timeout=120
                )
                data, sr = sf.read(tmp.name, dtype="float32")

        if data.ndim == 1:
            data = np.stack([data, data], axis=1)

        rms = float(np.sqrt(np.mean(data ** 2)))
        peak = float(np.max(np.abs(data)))
        rms_db = 20 * np.log10(max(rms, 1e-9))
        peak_db = 20 * np.log10(max(peak, 1e-9))
        crest_db = peak_db - rms_db
        clip_ratio = float(np.mean(np.abs(data) > 0.99))

        return {
            "crest_db": round(crest_db, 2),
            "peak_db": round(peak_db, 2),
            "rms_db": round(rms_db, 2),
            "clip_ratio": round(clip_ratio * 100, 4),  # pct
            "duration_s": round(len(data) / sr, 1),
        }
    except Exception as e:
        return {"crest_db": None, "clip_ratio": None, "error": str(e)}


def measure_all(path: str) -> dict:
    ff = measure_ffmpeg_lufs(path)
    np_ = measure_numpy(path)
    return {**ff, **np_}


# ---------------------------------------------------------------------------
# Delta formatting helpers
# ---------------------------------------------------------------------------

def delta(before, after, key, fmt=".1f", higher_better=True):
    b, a = before.get(key), after.get(key)
    if b is None or a is None:
        return "N/A"
    d = a - b
    sign = "+" if d >= 0 else ""
    verdict = ""
    if abs(d) > 0.3:
        good_change = (d > 0) == higher_better
        verdict = " ✓" if good_change else " ✗"
    return f"{b:{fmt}} → {a:{fmt}}  ({sign}{d:{fmt}}){verdict}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pipeline = SimpleMasteringPipeline()
    results = []

    tiers = {"good": [], "mixed": [], "bad": []}

    print(f"\n{'=' * 80}")
    print(f"  AURALIS MASTERING — DIVERSE TRACK TEST  ({len(TRACKS)} tracks)")
    print(f"{'=' * 80}\n")

    for idx, (label, input_path, tier) in enumerate(TRACKS, 1):
        inp = Path(input_path)
        if not inp.exists():
            print(f"[{idx:2}/{len(TRACKS)}] SKIP  {label}  (file not found)")
            results.append({"label": label, "tier": tier, "status": "missing", "path": input_path})
            continue

        out_stem = label.replace("/", "-").replace(" ", "_").replace("'", "").replace("—", "-")
        output_path = OUTPUT_DIR / f"{out_stem}_mastered.flac"

        print(f"[{idx:2}/{len(TRACKS)}] [{tier.upper():5}]  {label}")
        print(f"         Input:  {inp.name}")

        # Before metrics
        print("         Measuring source...", end="", flush=True)
        before = measure_all(str(inp))
        print(f"  LUFS={before.get('lufs', '?')}  Crest={before.get('crest_db', '?')}dB  "
              f"TP={before.get('true_peak', '?')}dBFS  Clip={before.get('clip_ratio', '?')}%")

        # Process
        t0 = time.perf_counter()
        try:
            result = pipeline.master_file(
                input_path=str(inp),
                output_path=str(output_path),
                intensity=1.0,
                verbose=False,
            )
            elapsed = time.perf_counter() - t0
            status = "ok"
        except Exception as e:
            elapsed = time.perf_counter() - t0
            status = "error"
            error_msg = str(e)
            print(f"         ✗ ERROR ({elapsed:.1f}s): {error_msg}")
            results.append({
                "label": label, "tier": tier, "status": "error",
                "elapsed": round(elapsed, 1), "error": error_msg,
                "before": before,
            })
            tiers[tier].append({"label": label, "status": "error"})
            print()
            continue

        # After metrics
        after = measure_all(str(output_path))
        stages = [s.get("stage", "?") for s in result.get("processing", {}).get("stages", [])]
        fp = result.get("fingerprint", {})
        mat_type = result.get("processing", {}).get("material_type", "?")

        print(f"         ✓ {elapsed:.1f}s  |  material={mat_type or '?'}  |  stages={stages}")
        print(f"         LUFS:   {delta(before, after, 'lufs', '.1f', higher_better=False)}")
        print(f"         Crest:  {delta(before, after, 'crest_db', '.1f', higher_better=True)}")
        print(f"         T.Peak: {delta(before, after, 'true_peak', '.1f', higher_better=False)}")
        print(f"         Clip%:  {delta(before, after, 'clip_ratio', '.3f', higher_better=False)}")
        if before.get("lra") is not None:
            print(f"         LRA:    {delta(before, after, 'lra', '.1f', higher_better=True)}")
        print()

        entry = {
            "label": label, "tier": tier, "status": "ok",
            "elapsed": round(elapsed, 1),
            "before": before, "after": after,
            "stages": stages,
            "fingerprint": {k: v for k, v in fp.items() if not k.startswith("_")},
            "material_type": mat_type,
        }
        results.append(entry)
        tiers[tier].append(entry)

    # ---------------------------------------------------------------------------
    # Summary table
    # ---------------------------------------------------------------------------
    print(f"\n{'=' * 80}")
    print("  SUMMARY")
    print(f"{'=' * 80}")
    header = f"  {'Label':<42}  {'Tier':5}  {'Status':6}  {'LUFS in':>8}  {'LUFS out':>8}  {'ΔCrest':>7}  {'ΔClip%':>8}"
    print(header)
    print(f"  {'-' * 78}")

    for r in results:
        status = r.get("status", "?")
        tier = r.get("tier", "?")
        label = r.get("label", "?")[:42]
        if status == "ok":
            b, a = r["before"], r["after"]
            lufs_in = f"{b.get('lufs', float('nan')):.1f}" if b.get("lufs") is not None else " N/A"
            lufs_out = f"{a.get('lufs', float('nan')):.1f}" if a.get("lufs") is not None else " N/A"
            dc = (a.get("crest_db") or 0) - (b.get("crest_db") or 0)
            dcl = (a.get("clip_ratio") or 0) - (b.get("clip_ratio") or 0)
            dc_s = f"{dc:+.1f}"
            dcl_s = f"{dcl:+.3f}"
        elif status == "missing":
            lufs_in = lufs_out = dc_s = dcl_s = "N/A"
        else:
            lufs_in = lufs_out = dc_s = dcl_s = "ERR"
        print(f"  {label:<42}  {tier:5}  {status:6}  {lufs_in:>8}  {lufs_out:>8}  {dc_s:>7}  {dcl_s:>8}")

    # Tier-level summary
    print(f"\n{'=' * 80}")
    print("  NET-BENEFIT CHECK  (✓ = improved, ✗ = degraded, – = no change)")
    print(f"{'=' * 80}")
    for tier_name, entries in tiers.items():
        ok = [e for e in entries if e.get("status") == "ok"]
        if not ok:
            continue
        crest_deltas = [(e["after"].get("crest_db") or 0) - (e["before"].get("crest_db") or 0) for e in ok]
        clip_deltas = [(e["after"].get("clip_ratio") or 0) - (e["before"].get("clip_ratio") or 0) for e in ok]
        avg_dc = sum(crest_deltas) / len(crest_deltas) if crest_deltas else 0
        avg_dcl = sum(clip_deltas) / len(clip_deltas) if clip_deltas else 0
        crest_ok = sum(1 for d in crest_deltas if d >= -0.5)
        clip_ok = sum(1 for d in clip_deltas if d <= 0.01)
        print(f"\n  [{tier_name.upper():5}]  {len(ok)} tracks")
        print(f"    Crest Δ avg {avg_dc:+.1f} dB  ({crest_ok}/{len(ok)} tracks improved or neutral)")
        print(f"    Clip% Δ avg {avg_dcl:+.3f}%  ({clip_ok}/{len(ok)} tracks improved or neutral)")

    # Save JSON
    RESULTS_FILE.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n  Results saved → {RESULTS_FILE}")
    print(f"  Outputs      → {OUTPUT_DIR}/\n")


if __name__ == "__main__":
    main()
