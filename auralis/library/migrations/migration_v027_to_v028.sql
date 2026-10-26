-- Migration v027 to v028
-- Drop the five never-populated tracks audio-property columns. Date: 2026-10-26
--
-- #5755: bit_depth, bitrate, peak_level, rms_level and lufs_level were declared
-- on tracks but the scanner never computes them (AudioFileInfo carries none of
-- them), so every row holds NULL; they reached the API as always-null fields
-- and StatsRepository averaged lufs_level into an always-null average_lufs.
-- Nothing in the frontend reads them. The ORM attributes, to_dict keys,
-- add()/update_by_filepath()/update() plumbing, TrackResponse fields, the stats
-- aggregate and the frontend Track types are removed in the same change.
-- (sample_rate, channels, format, filesize and dr_rating, which the scanner or
-- analysis do fill, stay.)

ALTER TABLE tracks DROP COLUMN bit_depth;
ALTER TABLE tracks DROP COLUMN bitrate;
ALTER TABLE tracks DROP COLUMN peak_level;
ALTER TABLE tracks DROP COLUMN rms_level;
ALTER TABLE tracks DROP COLUMN lufs_level;
