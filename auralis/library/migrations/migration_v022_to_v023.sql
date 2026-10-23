-- Migration v022 to v023
-- Normalizes user_settings.default_preset to the one remaining preset. Date: 2026-10-22
--
-- #5824: the 2026-09-13 preset narrowing (gentle/warm/bright/punchy/live ->
-- adaptive only) shipped without a data migration. Rows written before it can
-- still hold a removed name (or NULL), so three read sites each degraded an
-- off-list value with a warning -- re-encountered and re-logged on every boot
-- and every GET /api/settings -- and the frontend typed the field `| null` to
-- carry the same doubt. After this, the column only ever holds 'adaptive'
-- (writes are already restricted to the Literal), so those branches go.
--
-- The column itself stays nullable at the SQLite level (SQLite cannot add a
-- NOT NULL constraint in place); the ORM default and the API contract treat it
-- as always set.
--
-- playlists.mastering_profile and genres.preferred_profile (vestigial, default
-- 'balanced') are left for the column-removal migration tracked in #5755.

UPDATE user_settings SET default_preset = 'adaptive'
 WHERE default_preset IS NULL OR default_preset != 'adaptive';
