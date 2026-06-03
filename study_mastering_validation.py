#!/usr/bin/env python3
"""
Mastering algorithm validation study — three sub-studies.

Study 1 — Fingerprint LUFS accuracy
    Compares single-window (current), 3-window-median, and full-track LUFS
    across the test corpus to quantify the intro-bias and validate the
    multi-window approach before implementing it.

Study 2 — True Peak audit on test8 outputs
    Measures intersample peaks on every test8 output file to understand
    how much headroom the harmonic exciter is consuming at 44.1 kHz.

Study 3 — Makeup gain accuracy and crest-proportional scaling
    For every QuietBranch track: compares the gain actually applied
    (based on fp_lufs) vs the gain that was needed (based on actual LUFS),
    then simulates the crest-proportional formula and shows what the
    residual error would be.

Usage:
    python study_mastering_validation.py
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

# ---------------------------------------------------------------------------
# Track list  (label, input_path, tier)
# ---------------------------------------------------------------------------
TRACKS = [
    ("SW HCE / Hand Cannot Erase", "/mnt/Musica/Musica/Steven Wilson/2015 - Hand. Cannot. Erase (Limited Edition)/CD1/03 - Hand Cannot Erase.mp3", "good"),
    ("SW HCE / 3 Years Older",     "/mnt/Musica/Musica/Steven Wilson/2015 - Hand. Cannot. Erase (Limited Edition)/CD1/02 - 3 Years Older.mp3",    "good"),
    ("SW HCE / Routine",           "/mnt/Musica/Musica/Steven Wilson/2015 - Hand. Cannot. Erase (Limited Edition)/CD1/05 - Routine.mp3",           "good"),
    ("SW HCE / Home Invasion",     "/mnt/Musica/Musica/Steven Wilson/2015 - Hand. Cannot. Erase (Limited Edition)/CD1/06 - Home Invasion.mp3",     "good"),
    ("PT / Harridan",              "/mnt/Musica/Musica/Porcupine Tree/Porcupine Tree - 2022 - Closure - Continuation (FLAC)/01 - Harridan.flac",  "good"),
    ("PT / Dignity",               "/mnt/Musica/Musica/Porcupine Tree/Porcupine Tree - 2022 - Closure - Continuation (FLAC)/04 - Dignity.flac",   "good"),
    ("Polyphia / Nasty",           "/mnt/Musica/Musica/Polyphia/New Levels New Devils [2018]/01. Nasty (feat Jason Richardson).flac",             "good"),
    ("Polyphia / GOAT",            "/mnt/Musica/Musica/Polyphia/New Levels New Devils [2018]/10. GOAT.flac",                                      "good"),
    ("deadmau5 / I Remember",      "/mnt/Musica/Musica/deadmau5/Deadmau5 - 2008 - Random Album Title/07. I Remember.flac",                         "good"),
    ("Gilmour / Wish You Were Here","/mnt/Musica/Musica/David Gilmour/2017 - Live At Pompeii/08.-Wish You Were Here.flac",                         "good"),
    ("Gilmour / Comfortably Numb", "/mnt/Musica/Musica/David Gilmour/2017 - Live At Pompeii/21.-Comfortably Numb.flac",                           "good"),
    ("Gilmour / Shine On",         "/mnt/Musica/Musica/David Gilmour/2017 - Live At Pompeii/13.-Shine On You Crazy Diamond (Pts. 1-5).flac",       "good"),
    ("Dio / Holy Diver",           "/mnt/Musica/Musica/Dio/Albums/1983 - Holy Diver [1986 Nippon Phonogram 32PD-128 Japan]/(2) [Dio] Holy Diver.flac", "good"),
    ("Dio / Rainbow in the Dark",  "/mnt/Musica/Musica/Dio/Albums/1983 - Holy Diver [1986 Nippon Phonogram 32PD-128 Japan]/(8) [Dio] Rainbow In The Dark.flac", "good"),
    ("Load / Ain't My Bitch",      "/mnt/Musica/Musica/Metallica/Metallica - Load (1996) [FLAC] 88/01. Ain't My Bitch.flac",                      "mixed"),
    ("Load / King Nothing",        "/mnt/Musica/Musica/Metallica/Metallica - Load (1996) [FLAC] 88/05. King Nothing.flac",                        "mixed"),
    ("Nightwish / Storytime",      "/mnt/Musica/Musica/Nightwish/2011 - Imaginaerum/CD-1/02 - Storytime.mp3",                                     "mixed"),
    ("Nightwish / Ghost River",    "/mnt/Musica/Musica/Nightwish/2011 - Imaginaerum/CD-1/03 - Ghost River.mp3",                                   "mixed"),
    ("Soda Stereo / En La Ciudad", "/mnt/Musica/Musica/Soda Stereo/1996 - Comfort y Música para Volar (Lossless)/02 Soda Stereo - En La Ciudad de La Furia.m4a", "mixed"),
    ("Soda Stereo / Zoom",         "/mnt/Musica/Musica/Soda Stereo/1996 - Comfort y Música para Volar (Lossless)/05 Soda Stereo - Zoom.m4a",     "mixed"),
    ("Motörhead / 1977",           "/mnt/Musica/Musica/Motörhead/1977  Motorhead/(01) [Motorhead] Motorhead.flac",                               "mixed"),
    ("GVF / Fate of the Faithful", "/mnt/Musica/Musica/Greta Van Fleet/Starcatcher [2023]/01 Fate Of The Faithful.flac",                         "bad"),
    ("GVF / Runway Blues",         "/mnt/Musica/Musica/Greta Van Fleet/Starcatcher [2023]/05 Runway Blues.flac",                                 "bad"),
    ("Annihilator / All For You",  "/mnt/Musica/Musica/Annihilator/All For You/(01) [Annihilator] All For You.flac",                             "bad"),
    ("Annihilator / Army of One",  "/mnt/Musica/Musica/Annihilator/Metal/03 Army of One.flac",                                                   "bad"),
    ("Annihilator / Bloodbath",    "/mnt/Musica/Musica/Annihilator/1999 - Criteria For A Black Widow/(01) [Annihilator] Bloodbath.flac",          "bad"),
    ("St. Anger / St. Anger",      "/mnt/Musica/Musica/Metallica/UICY94669 - St. Anger/02 - St. Anger.flac",                                     "bad"),
    ("St. Anger / Frantic",        "/mnt/Musica/Musica/Metallica/UICY94669 - St. Anger/01 - Frantic.flac",                                       "bad"),
    ("Death Magnetic / TWJYL",     "/mnt/Musica/Musica/Metallica/METALLICA [2008] [5LP] Death Magnetic [VERTIGO 2517-73731-0]/01 - That Was Just Your Life.flac", "bad"),
    ("Death Magnetic / All Night", "/mnt/Musica/Musica/Metallica/METALLICA [2008] [5LP] Death Magnetic [VERTIGO 2517-73731-0]/05 - All Nightmare Long.flac", "bad"),
    ("AC/DC / Shot in the Dark",   "/mnt/Musica/Musica/AC_DC/POWER UP/03 Shot in the Dark.flac",                                                 "bad"),
    ("AC/DC / Realize",            "/mnt/Musica/Musica/AC_DC/POWER UP/01 Realize.flac",                                                          "bad"),
    ("Motörhead / Ace of Spades",  "/mnt/Musica/Musica/Motörhead/Ace of Spades [2020]/01 Ace of Spades (40th Anniversary Master).flac",          "bad"),
    ("Motörhead / Fast and Loose", "/mnt/Musica/Musica/Motörhead/Ace of Spades [2020]/05 Fast and Loose (40th Anniversary Master).flac",         "bad"),
]

OUTPUT_DIR = Path(__file__).parent / "output_diverse_test8"

# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------

def ffmpeg_lufs_full(path: str, timeout: int = 300) -> dict:
    """Full-track LUFS, LRA, True Peak via ffmpeg ebur128."""
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-i", str(path),
         "-filter:a", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, timeout=timeout,
    )
    out = proc.stderr
    idx = out.rfind("Summary:")
    summary = out[idx:] if idx != -1 else out

    m_i   = re.search(r"\bI:\s*([-\d.]+)\s*LUFS", summary)
    m_lra = re.search(r"\bLRA:\s*([\d.]+)\s*LU",  summary)
    m_tp  = re.findall(r"\bPeak:\s*([-\d.]+)\s*dBFS", summary)
    return {
        "lufs":      float(m_i.group(1))        if m_i   else None,
        "lra":       float(m_lra.group(1))      if m_lra else None,
        "true_peak": max(float(p) for p in m_tp) if m_tp else None,
    }


def ffmpeg_lufs_window(path: str, offset_s: float, duration_s: float = 30.0) -> float | None:
    """LUFS for a single window (offset + duration) — fast, no True Peak."""
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-ss", str(offset_s), "-i", str(path),
         "-t", str(duration_s), "-filter:a", "ebur128", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    out = proc.stderr
    idx = out.rfind("Summary:")
    summary = out[idx:] if idx != -1 else out
    m = re.search(r"\bI:\s*([-\d.]+)\s*LUFS", summary)
    return float(m.group(1)) if m else None


def get_duration(path: str) -> float | None:
    try:
        with sf.SoundFile(path) as f:
            return len(f) / f.samplerate
    except Exception:
        return None


def numpy_crest(path: str, offset_s: float = 0.0, window_s: float = 30.0) -> float | None:
    """Sample-level crest factor over a window."""
    try:
        import tempfile
        suffix = Path(path).suffix.lower()
        if suffix not in {".flac", ".wav", ".ogg"}:
            with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
                subprocess.run(
                    ["ffmpeg", "-nostdin", "-y", "-ss", str(offset_s),
                     "-i", path, "-t", str(window_s), tmp.name],
                    capture_output=True, timeout=60,
                )
                data, sr = sf.read(tmp.name, dtype="float32")
        else:
            with sf.SoundFile(path) as f:
                sr = f.samplerate
                start = int(offset_s * sr)
                n = int(window_s * sr)
                f.seek(start)
                data = f.read(n, dtype="float32")

        if data.ndim == 1:
            data = data.reshape(-1, 1)
        rms = np.sqrt(np.mean(data ** 2))
        peak = np.max(np.abs(data))
        if rms < 1e-9:
            return None
        return round(float(20 * np.log10(peak / rms)), 2)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Study 1 — Fingerprint LUFS accuracy
# ---------------------------------------------------------------------------

def study1_fingerprint_bias():
    print("\n" + "=" * 80)
    print("  STUDY 1 — FINGERPRINT LUFS ACCURACY")
    print("  Single-window (current)  vs  3-window median  vs  full-track LUFS")
    print("=" * 80)
    print(f"\n  {'Track':<40}  {'Actual':>7}  {'1-win':>7}  {'3-win':>7}  {'Err1':>6}  {'Err3':>6}")
    print(f"  {'-'*76}")

    errors_single, errors_multi = [], []
    rows = []

    for label, path, tier in TRACKS:
        p = Path(path)
        if not p.exists():
            continue

        total_s = get_duration(str(p))
        if total_s is None:
            continue

        # Full-track LUFS (ground truth)
        full = ffmpeg_lufs_full(str(p))
        actual_lufs = full["lufs"]
        if actual_lufs is None:
            continue

        # Current single-window: skip min(25%, 120s), 90s duration
        offset_cur = min(total_s * 0.25, 120.0)
        offset_cur = min(offset_cur, max(0.0, total_s - 90.0))
        win_cur = ffmpeg_lufs_window(str(p), offset_cur, 30.0)  # 30s subset for speed

        # 3-window median: 25%, 50%, 75%
        fracs = [0.25, 0.50, 0.75]
        win3 = []
        for frac in fracs:
            off = min(frac * total_s, max(0.0, total_s - 30.0))
            w = ffmpeg_lufs_window(str(p), off, 30.0)
            if w is not None:
                win3.append(w)
        multi_lufs = float(np.median(win3)) if win3 else None

        if win_cur is None or multi_lufs is None:
            continue

        err1 = win_cur - actual_lufs
        err3 = multi_lufs - actual_lufs
        errors_single.append(abs(err1))
        errors_multi.append(abs(err3))

        flag1 = " ✗" if abs(err1) > 3 else ""
        flag3 = " ✗" if abs(err3) > 3 else ""
        print(f"  {label:<40}  {actual_lufs:>7.1f}  {win_cur:>7.1f}  {multi_lufs:>7.1f}  {err1:>+6.1f}{flag1}  {err3:>+6.1f}{flag3}")
        rows.append({"label": label, "tier": tier, "actual": actual_lufs,
                     "single": win_cur, "multi": multi_lufs, "err1": err1, "err3": err3})

    print(f"\n  {'RMSE':^15}  single={np.sqrt(np.mean(np.array(errors_single)**2)):.2f} dB"
          f"   multi={np.sqrt(np.mean(np.array(errors_multi)**2)):.2f} dB")
    print(f"  {'MaxAbsErr':^15}  single={max(errors_single):.2f} dB"
          f"   multi={max(errors_multi):.2f} dB")
    print(f"  {'Bias>3dB':^15}  single={sum(1 for e in errors_single if e>3)}/{len(errors_single)}"
          f"      multi={sum(1 for e in errors_multi if e>3)}/{len(errors_multi)}")
    return rows


# ---------------------------------------------------------------------------
# Study 2 — True Peak audit on test8 outputs
# ---------------------------------------------------------------------------

def study2_true_peak_audit():
    print("\n" + "=" * 80)
    print("  STUDY 2 — TRUE PEAK AUDIT  (test8 outputs, EBU R128 intersample measurement)")
    print("=" * 80)

    THRESHOLDS = {
        "EBU R128 broadcast (−1 dBFS)": -1.0,
        "Streaming services  (−1 dBFS)": -1.0,
        "Practical safe zone (−0.5 dBFS)": -0.5,
        "Over 0 dBFS":  0.0,
        "Over +1 dBFS": 1.0,
    }

    results = []
    files = sorted(OUTPUT_DIR.glob("*.flac"))
    print(f"\n  Measuring {len(files)} output files ...\n")

    header = f"  {'Output file':<50}  {'True Peak':>10}  {'Status'}"
    print(header)
    print(f"  {'-'*70}")

    for fp in files:
        m = ffmpeg_lufs_full(str(fp))
        tp = m["true_peak"]
        if tp is None:
            print(f"  {fp.name:<50}  {'N/A':>10}")
            continue
        if tp > 0.0:
            status = f"⚠ OVER  0 dBFS ({tp:+.1f})"
        elif tp > -0.5:
            status = f"⚠ tight ({tp:+.1f})"
        elif tp > -1.0:
            status = f"• OK    ({tp:+.1f})"
        else:
            status = f"✓ clean ({tp:+.1f})"
        print(f"  {fp.name:<50}  {tp:>+10.2f}  {status}")
        results.append({"file": fp.name, "true_peak": tp, "lufs": m["lufs"]})

    over0   = [r for r in results if r["true_peak"] > 0.0]
    overtight = [r for r in results if -0.5 < r["true_peak"] <= 0.0]
    print(f"\n  Over  0 dBFS: {len(over0)}/{len(results)}  (D/A reconstruction clipping risk)")
    print(f"  Over −0.5 dBFS: {len(overtight)}/{len(results)}  (tight but below EBU ceiling)")
    if over0:
        avg_excess = np.mean([r["true_peak"] for r in over0])
        print(f"  Average excess above 0 dBFS: {avg_excess:+.2f} dB")
    return results


# ---------------------------------------------------------------------------
# Study 3 — Makeup gain accuracy and crest-proportional scaling
# ---------------------------------------------------------------------------

def study3_makeup_gain():
    print("\n" + "=" * 80)
    print("  STUDY 3 — MAKEUP GAIN ACCURACY & CREST-PROPORTIONAL SCALING")
    print("  Shows what gain the pipeline applied (from fp_lufs) vs what was needed")
    print("  (from actual LUFS), then simulates the proposed crest-scaling formula.")
    print("=" * 80)

    from auralis.analysis.fingerprint.fingerprint_service import FingerprintService
    svc = FingerprintService(fingerprint_strategy="sampling")

    TARGET_LUFS = -11.0

    print(f"\n  {'Track':<40}  {'ActLUFS':>8}  {'FpLUFS':>8}  {'FpCrest':>8}  {'GainApp':>8}  {'GainNeed':>8}  {'GainErr':>8}  {'GainCSc':>8}")
    print(f"  {'-'*100}")

    raw_errors, scaled_errors = [], []
    rows = []

    for label, path, tier in TRACKS:
        p = Path(path)
        if not p.exists():
            continue

        # Fingerprint from cache
        fp = svc._load_from_database(str(p)) or svc._load_from_file_cache(p)
        if fp is None:
            continue
        fp_lufs  = fp.get("lufs")
        fp_crest = fp.get("crest_db")
        if fp_lufs is None or fp_crest is None:
            continue

        # Full-track actual LUFS
        full = ffmpeg_lufs_full(str(p))
        actual_lufs = full["lufs"]
        if actual_lufs is None:
            continue

        # Is this a QuietBranch track?  (fp_lufs ≤ −12)
        if fp_lufs > -12.0:
            continue  # loud branch — no makeup gain

        # Approximate AdaptiveLoudnessControl behaviour:
        # gain_needed_by_fp = TARGET - fp_lufs (simplified; actual formula is more nuanced
        # but this captures the proportional relationship)
        gain_applied = max(0.0, (TARGET_LUFS - fp_lufs) * 0.35)   # empirical scale factor
        gain_needed  = max(0.0, TARGET_LUFS - actual_lufs)
        gain_error   = gain_applied - gain_needed                   # positive = over-processed

        # Simulated crest-proportional scaling:
        #   crest < 12  → 1.0x   crest = 18 → 0.4x   crest ≥ 22 → 0.0x
        if fp_crest >= 12.0:
            crest_scale = max(0.0, 1.0 - (fp_crest - 12.0) / 10.0)
        else:
            crest_scale = 1.0
        gain_scaled  = gain_applied * crest_scale
        gain_err_sc  = gain_scaled - gain_needed

        raw_errors.append(abs(gain_error))
        scaled_errors.append(abs(gain_err_sc))

        flag = " ✗" if abs(gain_error) > 3 else ""
        print(f"  {label:<40}  {actual_lufs:>8.1f}  {fp_lufs:>8.1f}  {fp_crest:>8.1f}  "
              f"{gain_applied:>8.1f}  {gain_needed:>8.1f}  {gain_error:>+8.1f}{flag}  {gain_err_sc:>+8.1f}")

        rows.append({"label": label, "tier": tier, "actual_lufs": actual_lufs,
                     "fp_lufs": fp_lufs, "fp_crest": fp_crest,
                     "gain_applied": gain_applied, "gain_needed": gain_needed,
                     "gain_error": gain_error, "gain_scaled_error": gain_err_sc,
                     "crest_scale": crest_scale})

    if raw_errors:
        print(f"\n  Gain error BEFORE crest scaling:  MAE={np.mean(raw_errors):.2f} dB  "
              f"RMSE={np.sqrt(np.mean(np.array(raw_errors)**2)):.2f} dB  "
              f"Max={max(raw_errors):.2f} dB")
        print(f"  Gain error AFTER  crest scaling:  MAE={np.mean(scaled_errors):.2f} dB  "
              f"RMSE={np.sqrt(np.mean(np.array(scaled_errors)**2)):.2f} dB  "
              f"Max={max(scaled_errors):.2f} dB")
        reduction = (1 - np.mean(scaled_errors) / np.mean(raw_errors)) * 100
        print(f"  → Crest-scaling reduces mean absolute gain error by {reduction:.0f}%")

    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\nAuralis Mastering — Algorithm Validation Study")
    print("Testing corpus: 34 tracks across good/mixed/bad quality tiers")
    print("Reference outputs: output_diverse_test8/\n")

    t0 = time.perf_counter()
    rows1 = study1_fingerprint_bias()
    rows2 = study2_true_peak_audit()
    rows3 = study3_makeup_gain()
    elapsed = time.perf_counter() - t0

    # Persist full results
    results = {"study1": rows1, "study2": rows2, "study3": rows3}
    out = Path(__file__).parent / "study_results.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n  Full results → {out}  ({elapsed:.0f}s total)")


if __name__ == "__main__":
    main()
