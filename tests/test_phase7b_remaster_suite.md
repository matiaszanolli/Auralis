# Phase 7B: Remaster Comparison Test Suite

**Purpose**: Identify and test available original vs professionally remastered pairs in the music library.

This document tracks potential remaster pairs that can be tested with the sampling strategy to understand how professional mastering work impacts fingerprinting accuracy.

---

## Available Remaster Pairs Found

### 1. ✅ YES - "Close To The Edge" (HIGH PRIORITY - TESTING NOW)

**Description**: 20+ minute progressive rock epic, professional Steven Wilson 24-96 remaster

- **Original**: `/mnt/Musica/Musica/YES/Albums/1972 - Close To The Edge/01 - Close To The Edge.flac`
  - Source: Original 1972 pressing
  - Format: 16-bit 44.1kHz
  - Character: Natural, limited mastering

- **Steven Wilson Remaster (2018)**: `/mnt/Musica/Musica/YES/2018. Yes - The Steven Wilson Remixes [24-96]/Disc 3 - Close To The Edge (1972)/01. Close To The Edge.flac`
  - Source: 2018 Steven Wilson Remix
  - Format: 24-bit 96kHz
  - Character: Heavy professional remastering, clarity enhancement
  - Engineer: Steven Wilson (renowned for high-quality rock remasters)

**Test Status**: IN PROGRESS
**Expected Insights**:
- Can sampling detect professional mastering enhancement?
- How much does remastering change the harmonic fingerprint?
- Would matching be affected if comparing original vs remaster?

---

## Identified Remaster Directories

The following directories contain remastered/vinyl rip versions that could be tested:

```
/mnt/Musica/Musica/Meshuggah (1989-2013)/c) Vinyl & Remastered versions/
  - 1995 - Destroy Erase Improve (Reloaded 2008)
  - 1998 - Chaosphere (Reloaded 2008)
  - 1998 - Contradictions Collapse & None (Reloaded 2008)
  - 2002 - Nothing (2006 Remastered & Remixed)
  - 2008 - obZen (Vinyl)
  - 2012 - Koloss (Vinyl)

/mnt/Musica/Musica/Meshuggah/
  - ObZen (2023) (15th Anniversary Remastered Edition) [FLAC 24-44]
  - The Violent Sleep Of Reason 2016 (Black Vinyl) (96khz 24bit)
  - Immutable (2022) [24 Bit Hi-Res] FLAC [PMEDIA]

/mnt/Musica/Musica/YES/
  - Multiple Steven Wilson remix versions available
```

---

## Test Methodology

For each remaster pair, the test:

1. **Analyzes original version** with sampling strategy
   - Full-track analysis (baseline)
   - Sampling analysis (20s interval, 5s chunks)
   - Extracts harmonic features

2. **Analyzes remaster version** with same methodology
   - Full-track analysis
   - Sampling analysis with identical parameters
   - Extracts harmonic features

3. **Compares results**:
   - Feature-by-feature differences (harmonic ratio, pitch stability, chroma energy)
   - Correlation between original and remaster fingerprints
   - Impact of professional mastering on fingerprint signatures
   - Whether sampling detects the same differences as full-track

4. **Reports insights**:
   - Cross-correlation between versions (how different are they?)
   - Feature distance metrics
   - Interpretation of what changed in mastering

---

## Expected Findings

### Hypothesis 1: Professional Remastering Improves Clarity
If true, we'd expect:
- Higher pitch stability in remaster
- Increased harmonic ratio (cleaner harmonic content)
- Higher chroma energy concentration
- Sampling should detect these changes similarly to full-track

### Hypothesis 2: Remasters Have Different Dynamic Range
If true:
- Changes to dynamic analyzer outputs
- Temporal features may differ significantly
- Might affect overall fingerprint correlation

### Hypothesis 3: Sampling is Robust Across Masterings
If true:
- Original and remaster would still show 85%+ correlation in key harmonic features
- Sampling strategy remains reliable despite mastering variations
- Would validate sampling for production use regardless of mastering approach

---

## Why This Matters for Production

Understanding how sampling responds to professional remasters is crucial because:

1. **Fingerprint Matching**: Would a song's fingerprint match across different masterings?
   - If correlation < 85% between versions, matching would fail
   - If correlation ≥ 85%, matching would work across masterings

2. **Library Consistency**: Your music library may contain multiple masterings of same songs
   - Need to know if fingerprints from different masterings are compatible

3. **Professional Audio**: Most of your library contains commercially mastered audio
   - Understanding how sampling handles pro mastering validates production use

4. **Quality Indicators**: Could sampling be used to detect mastering quality?
   - High-quality remasters might show specific fingerprint patterns
   - Could inform decisions about which version to keep

---

## Future Remaster Pairs to Test

Once YES - Close To The Edge completes, potential next tests:

1. **Meshuggah - Nothing**
   - Original 2002 vs 2006 Remastered & Remixed
   - Tests: How much does remixing (not just remastering) affect fingerprint?

2. **Meshuggah - ObZen**
   - Original vs 15th Anniversary Remastered (2023)
   - Tests: Do fingerprints drift over time/versions?

3. **The Rolling Stones - Voodoo Lounge**
   - Available in 24-96 hi-res format
   - Tests: Impact of hi-res mastering on sampling accuracy

---

## Commands to Run

### Run YES Close To The Edge comparison:
```bash
python tests/test_phase7b_remaster_comparison.py
```

### Add more pairs to test suite:
1. Locate original and remaster paths
2. Add paths to `test_phase7b_remaster_comparison.py`
3. Re-run to compare all pairs

---

## Expected Test Duration

- **YES Close To The Edge**: ~5-10 minutes per version (20+ minute track)
  - Original version: ~5-10 min analysis
  - Remaster version: ~5-10 min analysis
  - Total: ~15-20 minutes for comparison
  - Reason: Track is very long, full-track analysis is thorough

- **Shorter tracks** (3-5 minutes): ~1-2 minutes total per pair

---

## Documentation

All remaster comparison results will be documented in:
- `test_phase7b_remaster_comparison.py` - Live test implementation
- `PHASE_7B_FINAL_REPORT.md` - Summary of findings
- Future Phase 7C documentation if needed for adaptive strategies

---

**Status**: TEST SUITE READY
**Current Test**: YES - Close To The Edge (in progress)
**Expected Completion**: Within 20 minutes
**Next Steps**: Review results and identify patterns for Phase 7C adaptive strategies
