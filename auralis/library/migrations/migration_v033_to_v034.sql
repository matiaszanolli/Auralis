-- Migration v033 to v034
-- Drop the four playback settings nothing consumed. Date: 2026-11-22
--
-- #6683: user_settings.crossfade_enabled, crossfade_duration, gapless_enabled
-- and replay_gain_enabled were stored, validated, returned and editable in the
-- Settings dialog, but no player, streaming or engine code read them: the
-- stream never crossfades (#4642), gapless prebuffering is unconditional, and
-- there is no ReplayGain stage. The ORM attributes, API fields and Settings
-- controls are removed in the same change. None of the columns is indexed.
--
-- Fresh installs never have the columns: the runner skips "no such column" on
-- DROP COLUMN.

ALTER TABLE user_settings DROP COLUMN crossfade_enabled;
ALTER TABLE user_settings DROP COLUMN crossfade_duration;
ALTER TABLE user_settings DROP COLUMN gapless_enabled;
ALTER TABLE user_settings DROP COLUMN replay_gain_enabled;
