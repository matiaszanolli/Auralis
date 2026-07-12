# Archived Documentation

This directory holds **point-in-time historical documentation** — phase reports,
session logs, completed audits, fix write-ups, and refactoring completion reports.
It is kept for provenance and archaeology, **not** as current developer reference.

> ⚠️ **Do not treat anything here as authoritative.** These documents describe the
> state of the code at the time they were written and are frequently superseded.
> For current, maintained documentation start at [`../README.md`](../README.md).

## What's here

| Directory | Contents |
|-----------|----------|
| `phases/` | Multi-week development phase plans and completion reports |
| `sessions/` | Dated working-session logs (design spikes, fixes, overhauls) |
| `audits/` | Completed audit reports (backend, frontend, engine, security, …) |
| `fixes/` | Individual bug-fix write-ups |
| `refactoring/` | Refactoring plans and completion reports |
| `development-history/` | `PHASE*`/completion reports that used to live in `docs/development/` |

## Why archived

As of 2026-07-11 the evergreen developer documentation was rebuilt around a small,
maintained set of architecture and subsystem deep-dives (see [`../README.md`](../README.md)).
The ~300 historical files were relocated here so they stop drowning the living docs
while remaining browsable in-repo and in git history.
