"""Compatibility version exports and independent data-format versions.

The product version is authored in :mod:`auralis.version`.  The two product
constants below are retained for older importers and are updated by
``sync_version.py``.  Database schema and fingerprint algorithm versions are
independent and must only change with their respective formats.
"""

__version__ = "1.5.1"
__version_info__ = (1, 5, 1, "", 0)
__db_schema_version__ = 18  # tracks.filepath_key for case-insensitive path matching on Windows/macOS (#4842)

# Fingerprint algorithm version — increment this whenever the 25D extraction
# algorithm changes in a way that produces different values for the same audio.
# All existing fingerprints with a lower version will be automatically
# re-fingerprinted by background workers.
# v2 (#4136): 7-band frequency analysis now applies a Hann window before the FFT
#             (was rectangular), matching the windowed STFT spectral features and
#             removing leakage bias on transient-rich audio.
# v3 (#13 Stage 3): fingerprinting routed through the in-process Rust engine,
#             producing different values than the prior Python path.
# v4 (#4595): the batch library-scan path no longer truncates to the first 90 s
#             from the start. Both the batch and on-demand paths now share one
#             windowing implementation (body window at 50 % of duration + two
#             30 s probes at 25 %/75 %, median lufs/crest_db). Rows written by
#             the old batch path are NOT comparable to rows written by the
#             unified path — similarity distances across a mixed-vintage library
#             would be subtly wrong — so this bump exists to force recomputation.
# v5: dynamic-range variation now measures per-frame crest-factor variation
#             instead of peak/minimum-sample ratios, and maps it continuously
#             without a hard saturation threshold.
# v6 (#4533): rhythm_stability and silence_ratio now come from the librosa-parity
#             implementation ported out of the deleted fingerprint-server crate
#             (originally #4113). rhythm_stability was an energy-envelope onset
#             CV — a loudness metric, not a rhythmic one — and is now the
#             inter-beat-interval CV from a tempogram + Ellis-2007 beat tracker.
#             silence_ratio counted individual samples below an ABSOLUTE -40 dB
#             and is now the fraction of RMS frames more than 40 dB below the
#             loudest frame. Two of 25 dimensions therefore change value, so
#             v5 rows are not comparable to v6 rows and must be recomputed.
# v7 (#3690): chroma_energy now measures constant-Q chroma concentration
#             (sum of squared, per-frame-normalized chroma bins) instead of
#             a normalized RMS/loudness proxy. It previously duplicated the
#             `lufs` dimension; it is now decorrelated from loudness. v6 rows
#             are not comparable to v7 rows and must be recomputed.
# v8 (#5110): FFmpeg-routed formats (.mp3/.m4a/.aac/.ogg/.wma/.opus) now decode
#             only the analysed window instead of the whole file. The old path
#             decoded everything, resampled the whole buffer, and cropped last;
#             a bounded decode necessarily crops before resampling, matching
#             what the libsndfile and pre-loaded branches already did. Measured
#             on a real MP3 that shifts values up to ~1.1% (crest_db by
#             ~0.13 dB, others under 0.7%). A 1 s decode pre-roll removes the
#             codec-warm-up component; the residual is the resampling window
#             itself and is inherent to any bounded decode.
#             Lossless formats are bit-identical — only FFmpeg-routed rows
#             change — but the version is global, so this bump recomputes
#             everything. v7 rows are not comparable to v8 rows for
#             FFmpeg-routed sources and must be recomputed.
FINGERPRINT_ALGORITHM_VERSION = 8

# Version history
# 1.0.0 - Initial release with adaptive mastering, web UI, and desktop app
# Schema v2 - Added lyrics column to tracks table
# Schema v3 - Added database indexes for improved query performance (created_at, title, play_count, favorite)
# Schema v4 - Added track_fingerprints table for 25D audio fingerprint storage (2025-10-28)
# Schema v5 - Added similarity_graph table for K-nearest neighbors storage (2025-10-28)
# Schema v6 - Added fingerprint status tracking columns to tracks table (2025-11-24)
# Schema v7 - Added queue_state table for queue persistence across application restarts (2025-12-01)
# Schema v8 - Added queue_history table for undo/redo queue operations (2025-12-01)
# Schema v9 - Added queue_template table for saved queue configurations (2025-12-01)
# Schema v10 - Added artist artwork columns (artwork_url, artwork_source, artwork_fetched_at) (2025-12-27)
# Schema v11 - Added artist normalized_name for duplicate detection and merging (2025-12-29)
# Schema v12 - Added fingerprint_hash for integrity verification (2026-02-22)
# Schema v13 - Added bitrate column to tracks table (2026-02-22)
# Schema v14 - Added indexes on favorite, play_count, created_at, similarity_graph (2026-03-05)
# Schema v15 - Added is_reference flag on track_fingerprints for mastering reference cloud (2026-05-24)
# Schema v16 - track_playlist: UNIQUE(track_id, playlist_id) + position column to eliminate concurrent add_track races (2026-05-27)
