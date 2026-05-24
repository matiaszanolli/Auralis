-- Migration v014 to v015
-- Adds is_reference flag to track_fingerprints for the mastering reference cloud.
-- Date: 2026-05-24
--
-- Each fingerprint can be marked as a "reference" — a well-mastered track whose
-- spectral shape is used as a target by the soft k-NN mastering pipeline. The
-- seeder (auralis/learning/reference_seeder.py) selects eligible tracks
-- programmatically (LUFS / crest / band-distribution heuristics).
--
-- Index supports the cloud lookup (`WHERE is_reference = 1`) used by
-- FingerprintRepository.get_reference_cloud() in the mastering hot path.

ALTER TABLE track_fingerprints ADD COLUMN is_reference INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS ix_fingerprints_is_reference
    ON track_fingerprints (is_reference)
    WHERE is_reference = 1;
