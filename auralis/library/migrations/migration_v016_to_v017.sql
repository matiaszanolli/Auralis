-- Migration v016 to v017
-- Adds reference_weight to track_fingerprints for listening-behavior-weighted
-- mastering reference selection. Date: 2026-08-03
--
-- Layer 1 of #3480: the reference cloud previously treated every seeded
-- reference equally (a binary is_reference flag). reference_weight lets
-- auralis/learning/reference_seeder.py record how strongly a track should
-- pull the soft k-NN mastering target toward itself, based on the base
-- quality score plus play_count / favorite status. Defaults to 0.0 so
-- existing rows are inert until the next reference-cloud rebuild.

ALTER TABLE track_fingerprints ADD COLUMN reference_weight REAL NOT NULL DEFAULT 0.0;
