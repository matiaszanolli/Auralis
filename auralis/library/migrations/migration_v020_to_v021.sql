-- Migration v020 to v021
-- Drops queue_state and queue_history: the queue undo feature was retired. Date: 2026-10-19
--
-- #5526: the queue-history/undo backend (#3805) never gained a frontend
-- caller — no component ever called recordOperation or rendered an Undo
-- control, so the history table was never populated by real usage and undo
-- could only ever answer 404. Ship-or-delete was resolved as delete per the
-- #4861 precedent: the REST endpoints, the repository, the models and the
-- frontend hook are removed in the same change. queue_state (v7, "queue
-- persistence across restarts") was only ever the anchor row the history
-- entries hung off — nothing else reads it — so it goes too.
--
-- Dropping is safe: rows in these tables were only ever written by the
-- never-invoked record endpoint.
--
-- @ALLOW_DROP_TABLE — deliberate feature retirement, not an accident: the
-- whole point of this migration is that these two tables have no remaining
-- readers.

DROP TABLE IF EXISTS queue_history;
DROP INDEX IF EXISTS idx_queue_history_queue_state_id;
DROP INDEX IF EXISTS idx_queue_history_created_at;
DROP INDEX IF EXISTS idx_queue_history_operation;
DROP TABLE IF EXISTS queue_state;
