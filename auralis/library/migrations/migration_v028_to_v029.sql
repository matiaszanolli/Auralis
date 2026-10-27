-- Migration v028 to v029
-- Adds track_fingerprints.fingerprint_blob (the quantized 25-byte vector). Date: 2026-10-26
--
-- #5718: the ORM column was added (2025-12-11) with no migration. create_all()
-- never alters an existing table, so a library whose track_fingerprints was
-- created by the v003->v004 migration before that date has no such column, yet
-- every select(TrackFingerprint) and both raw upserts name it: every
-- fingerprint read failed with "no such column" and the callers recomputed, so
-- fingerprints never stuck.
--
-- Databases that already have the column (fresh installs, hand-patched ones)
-- are unaffected: the runner skips "duplicate column". Existing rows get NULL,
-- which is what the column means for a fingerprint stored before quantization.

ALTER TABLE track_fingerprints ADD COLUMN fingerprint_blob BLOB;
