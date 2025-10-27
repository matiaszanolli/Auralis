# Auralis Research Documentation

This directory contains academic research materials related to the Auralis real-time adaptive audio mastering system.

## Directory Structure

```
research/
├── README.md                          # This file
├── paper/                             # Technical papers and publications
│   └── auralis_realtime_adaptive_mastering.md  # Main technical paper (AES/ACM/IEEE-style)
├── figures/                           # Diagrams, plots, and visual materials
└── data/                              # Benchmark data, test results, measurements
```

## Papers

### Auralis: A Real-Time Adaptive Audio Mastering System with Progressive Streaming and Multi-Tier Buffering

**File**: [paper/auralis_realtime_adaptive_mastering.md](paper/auralis_realtime_adaptive_mastering.md)

**Status**: Draft v1.0 (October 27, 2025)

**Abstract**: We present Auralis, a novel real-time adaptive audio mastering system that combines progressive streaming with intelligent multi-tier buffering to enable instant audio enhancement preset switching during playback. The system achieves <100ms preset switching latency (20-50x improvement over traditional systems), processes audio at 36.6x real-time speed, and reduces storage requirements by 86% through WebM/Opus encoding.

**Key Contributions**:
1. Unified streaming architecture eliminating dual playback conflicts
2. Chunked multidimensional segmentation for real-time mastering
3. CPU-inspired multi-tier buffer system with branch prediction
4. WebM/Opus progressive encoding (86% size reduction)
5. Production-validated implementation with comprehensive testing

**Sections**:
1. Introduction (motivation, challenges, contributions)
2. Background and Related Work (PCM, Matchering, MSE)
3. Methodology (chunked segmentation, content analysis, adaptive targets)
4. Implementation (backend, frontend, caching, processing)
5. Results and Performance (latency, encoding, caching metrics)
6. Discussion (limitations, edge cases, perceptual considerations)
7. Future Work (ML adaptation, perceptual testing, cross-platform)
8. Conclusion
9. Appendices (architecture diagrams, sequence diagrams, benchmarks)

**Target Venues**:
- Audio Engineering Society (AES) Convention/Journal
- ACM Multimedia Conference
- IEEE ICASSP (International Conference on Acoustics, Speech, and Signal Processing)
- ISMIR (International Society for Music Information Retrieval)

## How to Use This Research

### For Academic Purposes

If you're citing Auralis in academic work:

```bibtex
@article{auralis2025realtime,
  title={Auralis: A Real-Time Adaptive Audio Mastering System with Progressive Streaming and Multi-Tier Buffering},
  author={Auralis Team},
  journal={[To be submitted]},
  year={2025},
  note={Draft version available at https://github.com/matiaszanolli/Auralis}
}
```

### For Implementation Reference

The paper provides detailed technical specifications for:
- Chunked audio processing algorithms
- Multi-tier caching strategies
- MSE integration patterns
- Real-time DSP optimizations
- Content-aware parameter adaptation

Refer to specific sections for implementation details.

### For Benchmarking

Appendix D contains comprehensive performance benchmarks:
- WebM encoding (bitrate vs. quality trade-offs)
- HybridProcessor (component-level timing)
- Cache performance (hit rates, latency distributions)
- Branch prediction (learning curves, accuracy metrics)

Use these as baselines for comparison with other systems.

## Research Questions (Future Work)

### Open Problems

1. **Perceptual Quality**: How do users perceive chunked processing vs. full-file mastering? What is the JND (Just Noticeable Difference) for chunk boundary artifacts?

2. **Preset Personalization**: Can machine learning automatically discover user-specific preset preferences? What features predict preference alignment?

3. **Cross-Genre Generalization**: Do current preset profiles generalize across musical genres? How can we automatically adapt parameters to genre-specific characteristics?

4. **Latency-Quality Trade-off**: What is the optimal chunk size for balancing first-chunk latency and processing quality?

5. **Cache Efficiency**: Can we improve branch prediction accuracy beyond 68%? What additional signals (time-of-day, genre, listening context) improve prediction?

### Proposed Studies

1. **MUSHRA Listening Test**: Compare chunked vs. full-file processing across 5 presets and 10 diverse tracks. Hypothesis: No statistically significant difference (p > 0.05).

2. **Preset Switching Latency Study**: User study on perceived "instantness". What latency threshold (<50ms? <100ms?) is perceived as instant vs. noticeable?

3. **Long-Term User Preference Learning**: Longitudinal study tracking preset usage patterns over weeks/months. Can we predict future preferences based on listening history?

4. **Cross-Platform Performance**: Benchmark Auralis on mobile devices (Android/iOS), low-power systems (Raspberry Pi), and web browsers. Identify performance bottlenecks.

## Datasets and Benchmarks

### Test Audio Files

Standard test tracks used for benchmarking:
- **Iron Maiden - "Fear of the Dark"** (232.7s): Long-duration test, diverse dynamics
- **Rush - "Tom Sawyer"** (4:33): Classic rock, high dynamic range
- **Exodus - "Bonded by Blood"** (3:51): Thrash metal, aggressive compression test
- **Various genres**: Classical, jazz, electronic, spoken word

### Performance Metrics

Key metrics tracked:
- **Preset switching latency** (ms): Target <100ms
- **Real-time factor** (x): Audio duration / processing time
- **Cache hit rate** (%): Percentage of chunks served from cache
- **Memory footprint** (MB): Peak memory usage during playback
- **File size reduction** (%): WebM vs. WAV compression ratio

### Benchmark Scripts

(To be added)
- `benchmark_preset_switching.py`: Automated latency measurement
- `benchmark_processing_speed.py`: Real-time factor calculation
- `benchmark_cache_performance.py`: Cache hit rate simulation
- `benchmark_encoding_quality.py`: WebM quality metrics (MUSHRA-style)

## Contributing to Research

We welcome contributions to Auralis research:

1. **Perceptual Studies**: Help design and conduct listening tests
2. **Performance Analysis**: Profile and optimize critical paths
3. **ML/AI Integration**: Develop preference learning models
4. **Documentation**: Improve clarity and technical accuracy of papers

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## Contact

For research inquiries, collaboration proposals, or dataset requests:
- GitHub Issues: https://github.com/matiaszanolli/Auralis/issues
- Email: [To be determined]

## License

Research materials in this directory are licensed under:
- **Papers/Documentation**: CC BY 4.0 (Creative Commons Attribution)
- **Code/Implementation**: GPLv3 (see [LICENSE](../LICENSE))

---

**Last Updated**: October 27, 2025
**Version**: 1.0 (Initial draft)
