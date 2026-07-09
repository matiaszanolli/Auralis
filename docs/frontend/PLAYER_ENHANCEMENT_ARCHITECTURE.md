# Player & Enhancement Pane Architecture (Current)

**Status:** Current as of 2026-07-09
**Supersedes:** `ARCHITECTURE_V3.md`, `analysis/PLAYER_COMPONENT_CONSOLIDATION_PLAN.md`, `analysis/PLAYER_ANALYSIS_SUMMARY.md`, `components/player-bar/PLAYERBARV2_REFACTORING_COMPLETE.md`, `components/player-bar/PLAYERBARV2_REFACTORING_FIXES.md`

This is a short, code-verified description of the player and enhancement UI as it exists today, replacing the "V2"/"V3" planning docs that described components deleted in `67f82aa8` (#4089). No `-v2`/`-v3`-suffixed component, `player-bar-v2/` directory, or `usePlayer()`/`useLibrary()`/`useEnhancement()` hooks exist in the current tree.

## Top-level layout

`ComfortableApp.tsx` renders:

- `AppContainer` — `AppSidebar` (nav) + a main column of `AppTopBar` (search/title) + `AppMainContent` (`CozyLibraryView`, lazy-loaded)
- `Player` — a fixed bottom bar rendered as a sibling of `AppContainer`, wrapped in its own `ErrorBoundary` so a player crash doesn't take down the rest of the app

There is no separate "V2" player bar — `components/player/Player.tsx` is the only player component mounted in production.

## Player bar

`components/player/Player.tsx` orchestrates the bottom playback bar from smaller presentational pieces in the same directory:

- `TimeDisplay`, `BufferingIndicator`, `ProgressBar`, `PlaybackControls`, `VolumeControl`, `TrackDisplay`, `QueuePanel`

Playback state comes from Redux (`store/slices/playerSlice`, `store/slices/queueSlice`, `playerSelectors`); actual audio streaming goes through the `usePlayEnhanced` WebSocket hook (`@/hooks/enhancement/usePlayEnhanced`), not a REST call.

## Enhancement / album-character pane

The right-side pane is **not** `EnhancementPane` — it's `AlbumCharacterPane` (`components/library/AlbumCharacterPane/`), rendered by `CozyLibraryView.tsx` inside `ViewContainer`/`LibraryViewRouter` for every library view. It shows an aggregate fingerprint visualization, mood tags, and an energy field for the current album, with an `EnhancementToggle` (via `useEnhancementControl`) rather than the old per-track parameter sliders.

`components/enhancement-pane/EnhancementPane.tsx` and `components/enhancement/EnhancementPane.tsx` (plus `EnhancedPlaybackControls.tsx`, a wrapper around the latter) still exist in the tree but are **not imported by any production code path** — only by tests. Treat them as legacy/unused rather than "in progress"; do not add new features to them without first confirming they're actually reachable from the app.

## Library

`components/library/CozyLibraryView.tsx` is the current library view, routing to per-view components under `components/library/Views/` via `LibraryViewRouter`.

## If you're planning new player/enhancement work

Search the actual component tree (`components/player/`, `components/library/AlbumCharacterPane/`) and check what's imported from `ComfortableApp.tsx`/`CozyLibraryView.tsx` before trusting any older planning doc under `docs/frontend/` — several were written against a `-v2`/`-v3` redesign that was abandoned or reverted.
