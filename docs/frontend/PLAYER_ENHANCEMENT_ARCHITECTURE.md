# Player and Enhancement Pane Architecture

How the bottom player bar and the right-hand enhancement pane are built. The app shell, the
playback session and the audio pipeline are owned by
[subsystems/frontend.md](../subsystems/frontend.md); this page covers the two UI surfaces.

## Where they mount

`ComfortableApp` renders `AppContainer` (sidebar, top bar, main content) and, as a sibling, the
`Player` bar in its own `ErrorBoundary`. The pane is not mounted by the shell: `CozyLibraryView`
(Songs, Favourites) and `LibraryViewRouter` (Albums) hand `AlbumCharacterPane` to `ViewContainer`
as its `rightPane`. Artist views and detail pages have no pane.

## Player bar

`src/components/player/Player.tsx` composes presentational pieces from the same directory and owns
only the queue-panel open state:

- **Top edge:** `BufferingIndicator` and `ProgressBar` (drag and keyboard seeking via
  `useProgressBarDrag`, `useKeyboardSeek`; disabled while seeking, on error, or while a transport
  command is pending).
- **Left:** `TrackDisplay` (artwork, title, artist and album) and `TimeDisplay`.
- **Centre:** `PlaybackControls` (previous, play/pause, next).
- **Right:** `VolumeControl` (slider and mute) and the "Toggle queue" button, which shows or hides
  `QueuePanel` (queue list, shuffle, repeat off/all/one, clear, drag and keyboard reorder, remove).

State comes from Redux (`playerSelectors`, `selectEnhancedStreaming`) and from the playback session
(`usePlaybackControls`, `usePlaybackProgress` in `src/contexts/PlaybackSessionContext.tsx`). The
bar sends no REST playback calls itself; transport commands run through the session, which starts
streams over the WebSocket. The bar has no enhancement control. `QueuePanel` has its own error
boundary inside `Player`, so a queue crash leaves the transport usable.

## Enhancement pane

`src/components/library/AlbumCharacterPane/AlbumCharacterPane.tsx` is a fixed-width (360 px) pane
with two parts:

1. **`AutoMasteringToggle`**, always at the top, in every pane state. It renders
   `EnhancementToggle` (`src/components/shared/EnhancementToggle/`, switch variant) labelled
   "Auto-Mastering", described as "Enhancing playback" or "Original audio". It reads
   `useEnhancementControl()` and calls `setEnabled`; a failed request shows a toast and the switch
   is disabled while the request is in flight.
2. **A character view** of the audio fingerprint: waveform, glowing arc, mood tags, an energy
   field and rotating descriptions. It shows the playing track's fingerprint, else the hovered
   album's aggregate, and placeholder panes while nothing is playing, the analysis is pending or
   loading, or no fingerprint exists. Motion fades out over a short decay when playback stops.

There are no preset or per-parameter controls in the pane. `adaptive` is the only valid
enhancement preset.

### Enhancement state

`src/hooks/enhancement/useEnhancementControl.ts` holds `enabled`, `preset` and `intensity` in local
state, seeded from `GET /api/player/enhancement/status` and kept current by the
`enhancement_settings_changed` WebSocket broadcast (`useEnhancementStatusSync`). Changes post to
`/api/player/enhancement/toggle`, `/preset` and `/intensity` (`useEnhancementCommands`) with
optimistic updates and rollback. Because the backend binds these values when a stream starts, a
change while audio is playing re-issues the active stream (`reissueActiveStreamAs`) from the
current position: as `play_normal` when enhancement turns off, as `play_enhanced` otherwise.

`PlaybackSessionProvider` reads the same hook, so the next track starts with the current setting.
Settings → Enhancement edits the stored defaults (default preset, "Auto-enhance playback",
"Enhancement Intensity") through `settingsService`; see
[../getting-started/USER_GUIDE.md](../getting-started/USER_GUIDE.md) for the user-facing behaviour.
