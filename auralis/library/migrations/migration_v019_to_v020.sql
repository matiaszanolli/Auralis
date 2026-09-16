-- Migration v019 to v020
-- Adds processing_jobs, the durable record of mastering/export jobs. Date: 2026-09-16
--
-- #5278: ProcessingEngine kept jobs only in an in-memory dict, so a backend
-- restart or crash erased every queued and running job, and its status
-- endpoint answered a plain 404 as if the job had never existed. The backend
-- now writes each job here at every lifecycle transition, and on startup marks
-- jobs that were still queued or running as interrupted.
--
-- Mirrors auralis/library/models/processing_job.py (ProcessingJobRecord),
-- which is what a fresh database is built from.

CREATE TABLE IF NOT EXISTS processing_jobs (
    job_id        VARCHAR NOT NULL PRIMARY KEY,
    input_path    TEXT NOT NULL,
    output_path   TEXT NOT NULL,
    mode          VARCHAR NOT NULL,
    status        VARCHAR NOT NULL,
    progress      FLOAT NOT NULL,
    error_message TEXT,
    settings      TEXT NOT NULL,
    result_data   TEXT,
    created_at    DATETIME NOT NULL,
    started_at    DATETIME,
    completed_at  DATETIME
);
