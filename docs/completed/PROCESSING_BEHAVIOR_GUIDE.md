# Audio Processing Behavior Guide

**Quick Reference**: How Auralis processes different material types

---

## The 4 Processing Behaviors

### 1. Heavy Compression 🔨
**When**: Extreme dynamics (DR > 0.9, crest > 17 dB)
**Why**: Material is too dynamic for competitive loudness
**Action**: Compress heavily (-3 to -4 dB crest), increase RMS significantly
**Example**: Slayer "South of Heaven" (crest 18.98 → 15.74 dB)

### 2. Light Compression 🔧
**When**: Very loud + moderate dynamics (Level > 0.85, 0.45 <= DR < 0.6)
**Why**: Already loud but could be tighter
**Action**: Light compression (-1 to -2 dB crest), moderate RMS increase
**Example**: Testament "The Preacher" (crest 12.55 → 11.35 dB)

### 3. Preserve Dynamics 🎭
**When**: Classic/naturally dynamic recordings (Level < 0.5, DR > 0.9)
**Why**: Excellent dynamics, just needs level boost
**Action**: Gain only, no compression or expansion
**Example**: Seru Giran "Peperina" (crest 21.18 → 21.23 dB)

### 4. Expand Dynamics (De-mastering) 📈
**When**: Over-compressed modern masters (Level > 0.7, DR < 0.8)
**Why**: Restore dynamics lost in loudness war
**Action**: Expand peaks, reduce RMS, increase crest factor
**Examples**:
- Heavy: Pantera (crest 11.30 → 17.09 dB)
- Light: Soda Stereo (crest 15.14 → 17.76 dB)

---

## Decision Tree

```
Is Level > 0.8?
├─ YES: Is DR < 0.45?
│   ├─ YES: HEAVY EXPANSION (Pantera, Motörhead)
│   └─ NO: Is DR < 0.6?
│       ├─ YES: LIGHT COMPRESSION (Testament)
│       └─ NO: LIGHT EXPANSION or PRESERVE
└─ NO: Is Level > 0.7?
    ├─ YES: Is DR >= 0.6?
    │   ├─ YES: LIGHT EXPANSION (Soda Stereo)
    │   └─ NO: Other rules...
    └─ NO: Is DR > 0.9?
        ├─ YES: PRESERVE DYNAMICS (Seru Giran, Slayer)
        └─ NO: Standard processing
```

---

## Parameter Reference

### Compression Parameters
- `compression_amount`: 0.0-1.0
  - 0.0 = No compression
  - 0.42 = Light compression (Testament)
  - 0.85 = Heavy compression (Slayer)

### Expansion Parameters
- `expansion_amount`: 0.0-1.0
  - 0.0 = No expansion
  - 0.4 = Light expansion (Soda Stereo)
  - 0.7 = Heavy expansion (Pantera, Motörhead)

### Target RMS
- `-11.0 dB`: Standard loud mastering
- `-12.5 dB`: Moderate loudness (Testament)
- `-14.0 dB`: Conservative loudness (Soda Stereo)
- `-15.0 dB`: Compressed dynamics (Slayer)
- `-17.0 dB`: Expansion headroom (Pantera, Motörhead)
- `-18.0 dB`: Preserve dynamics (Seru Giran)

---

## Spectrum Metrics

### Input Level (0.0-1.0)
Normalized RMS level relative to reference:
- < 0.5: Under-leveled
- 0.5-0.8: Moderate level
- 0.8-0.9: Loud
- > 0.9: Very loud

### Dynamic Range (0.0-1.0)
Normalized crest factor:
- < 0.35: Over-compressed (crest < 12 dB)
- 0.35-0.6: Moderate dynamics (crest 12-15 dB)
- 0.6-0.9: High dynamics (crest 15-19 dB)
- > 0.9: Extreme dynamics (crest > 19 dB)

---

## Real-World Examples

| Artist | Album | Track | Behavior | Trigger |
|--------|-------|-------|----------|---------|
| Slayer | South of Heaven | South of Heaven | Heavy Compression | DR 1.00, crest 18.98 dB |
| Testament | Live at the Fillmore | The Preacher | Light Compression | Level 0.88, DR 0.52 |
| Seru Giran | Peperina | Peperina | Preserve Dynamics | Level 0.42, DR 1.00 |
| Motörhead | Inferno | Terminal Show | Heavy Expansion | Level 0.97, DR 0.37 |
| Soda Stereo | Signos | Signos | Light Expansion | Level 0.76, DR 0.73 |
| Pantera | Far Beyond Driven | Strength Beyond Strength | Heavy Expansion | Level 0.98, DR 0.35 |

---

## Expected Results

### Heavy Compression (Slayer)
- Crest reduction: ~3 dB (18.98 → ~15.7 dB)
- RMS increase: ~5 dB
- Result: Competitive metal loudness while preserving some dynamics

### Light Compression (Testament)
- Crest reduction: ~1-2 dB (12.55 → ~11.35 dB)
- RMS increase: ~1-2 dB
- Result: Tighter, more consistent presentation

### Preserve Dynamics (Seru Giran)
- Crest: Unchanged (~21 dB)
- RMS: Slight increase for competitive level
- Result: Natural dynamics preserved with level boost

### Light Expansion (Soda Stereo)
- Crest increase: ~2-3 dB (15.14 → ~17.76 dB)
- RMS reduction: ~3 dB
- Result: Enhanced dynamics, more open sound

### Heavy Expansion (Pantera, Motörhead)
- Crest increase: ~3-6 dB (11.3-11.6 → 15-17 dB)
- RMS reduction: ~3-6 dB
- Result: Restored dynamics, reduced listening fatigue

---

## Content Rules in Code

### Heavy Expansion
```python
if position.input_level > 0.8 and position.dynamic_range < 0.45:
    params.expansion_amount = 0.7
    params.output_target_rms = -17.0
```

### Light Compression
```python
elif position.input_level > 0.85 and position.dynamic_range >= 0.45 and position.dynamic_range < 0.6:
    params.compression_amount = 0.42
    params.output_target_rms = -12.5
```

### Light Expansion
```python
elif position.input_level > 0.7 and position.input_level <= 0.85 and position.dynamic_range >= 0.6 and position.dynamic_range < 0.8:
    params.expansion_amount = 0.4
    params.output_target_rms = -14.0
```

### Heavy Compression
```python
if position.dynamic_range > 0.9:
    params.compression_amount = 0.85
    params.output_target_rms = -15.0
```

### Preserve Dynamics
```python
elif position.input_level < 0.5 and position.dynamic_range > 0.9:
    params.compression_amount = 0.0
    params.output_target_rms = -18.0
```

---

## Testing Your Material

To see which behavior your track triggers:

1. **Run processing** and check console output for:
   ```
   [Content Rule] LOUD+COMPRESSED → EXPAND dynamics for restoration
   ```

2. **Look for these messages**:
   - `EXTREME dynamics` → Heavy compression
   - `VERY LOUD+MODERATE DYNAMICS` → Light compression
   - `NATURALLY dynamic classic recording` → Preserve dynamics
   - `MODERATELY LOUD+HIGH DYNAMICS` → Light expansion
   - `LOUD+COMPRESSED` → Heavy expansion

3. **Check spectrum metrics**:
   ```
   [Spectrum Position] Level:X.XX Dynamics:Y.YY
   ```

---

## Common Questions

**Q: Why is my loud metal track getting expansion instead of compression?**
A: If Level > 0.8 and DR < 0.45, it's detected as over-compressed (loudness war casualty). The system is restoring dynamics, not adding more compression.

**Q: Why is my classical recording not getting louder?**
A: If Level < 0.5 and DR > 0.9, it's naturally dynamic. The system preserves these excellent dynamics and only adds minimal gain.

**Q: Can I force a specific behavior?**
A: Not currently. The system automatically selects the appropriate behavior based on material analysis. This is by design - trust the analysis!

**Q: What if my track doesn't match any rule?**
A: The system falls back to standard spectrum-based interpolation from preset anchors. This handles most "normal" material well.

---

## Technical Details

See these files for implementation:
- [auralis/core/analysis/spectrum_mapper.py](auralis/core/analysis/spectrum_mapper.py) - Content rules (lines 300-450)
- [auralis/core/hybrid_processor.py](auralis/core/hybrid_processor.py) - DIY compressor/expander (lines 380-462)
- [DYNAMICS_EXPANSION_COMPLETE.md](DYNAMICS_EXPANSION_COMPLETE.md) - Full implementation details
- [CRITICAL_DISCOVERY_DEMASTERING.md](CRITICAL_DISCOVERY_DEMASTERING.md) - Original research findings

---

## Performance

**Current accuracy** (as of October 24, 2025):
- Light compression (Testament): 0.03 dB crest error ✅ EXCELLENT
- Light expansion (Motörhead): 0.08 dB crest error ✅ EXCELLENT
- Light expansion (Soda Stereo): 0.60 dB crest error ✅ EXCELLENT
- Preserve dynamics (Seru Giran): 0.05 dB crest error ✅ GOOD
- Heavy compression (Slayer): 0.83 dB crest error ⚠️ ACCEPTABLE
- Heavy expansion (Pantera): 2.42 dB crest error ⚠️ ACCEPTABLE

**Average**: 0.67 dB crest error, 1.30 dB RMS error across all behaviors

---

**Last Updated**: October 24, 2025
**Status**: Production-ready, optional refinement for extreme cases
