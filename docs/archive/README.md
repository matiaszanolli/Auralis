# Archived Documentation

This directory holds **point-in-time historical documentation**: phase reports, session
logs, completed audits, fix write-ups, design plans, analyses and superseded guides. It is
kept for provenance and archaeology, **not** as current developer reference.

> **Do not treat anything here as authoritative.** These documents describe the code as it
> was when they were written, and most of it has since changed. For current, maintained
> documentation start at [`../README.md`](../README.md).

## What's here

| Directory | Contents |
|-----------|----------|
| `phases/` | Multi-week development phase plans and completion reports |
| `sessions/` | Dated working-session logs (design spikes, fixes, overhauls) |
| `audits/` | Completed audit reports from before the dated reports in [`../audits/`](../audits/) |
| `fixes/` | Individual bug-fix and security-fix write-ups, and troubleshooting notes written against retired code paths |
| `refactoring/` | Refactoring plans and completion reports |
| `development-history/` | Design plans, performance analyses, API audits, pipeline traces and migration guides for code that has since been rebuilt or deleted (includes the 2025 multi-style remaster study under `multistyle-analysis/`) |
| `frontend-history/` | Frontend redesign plans, sprint reports, component audits and test-suite summaries |
| `guides/` | Feature-level design notes and integration guides, and the v1.0 beta user guide |
| `roadmaps/` | Superseded roadmaps, launch checklists, the v1.0.0-beta.1 GitHub release record and the legacy changelog |
| `testing/` | Retired testing practices and test specifications (e.g. mutmut mutation testing, whose tests and target module no longer exist) |

## Why archived

The living documentation is a small set of maintained architecture, subsystem and process
docs (see [`../README.md`](../README.md)). Anything that records a moment, such as a plan,
an analysis or a fix report, lives here so it stops drowning the living docs while staying
browsable in the repo and in git history.

Links between archived documents are not maintained. A link that resolved when a document
was written may point at a file that has since moved or been deleted.
