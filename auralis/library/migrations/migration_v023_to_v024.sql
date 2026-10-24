-- Migration v023 to v024
-- Drops playlists.mastering_profile and genres.preferred_profile. Date: 2026-10-24
--
-- #6261: both columns are vestigial remains of the removed-preset vocabulary
-- (gentle/warm/bright/punchy/live -> adaptive only, 2026-09-13). Both default
-- to 'balanced' — a name that was never a valid preset even before the
-- narrowing — are written by nobody (GenreRepository.create's parameter was
-- passed only by a test) and are read by nobody. Playlist.mastering_profile
-- was serialized onto the wire with no frontend reader.
--
-- Dropping is safe: neither column has held a value any code path consumed
-- since the preset narrowing; the wire field and the repository parameter are
-- removed in the same change.

ALTER TABLE playlists DROP COLUMN mastering_profile;
ALTER TABLE genres DROP COLUMN preferred_profile;
