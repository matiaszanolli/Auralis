# Phase 4: UI Components Plan

**Date**: December 1, 2025
**Status**: Planning Phase 4

## Overview

Six focused UI sub-components for the new Player Bar, each with a single responsibility:

1. **ProgressBar** - Interactive progress display with seek
2. **PlaybackControls** - Play/pause/next/previous buttons
3. **TimeDisplay** - Current time and duration
4. **VolumeControl** - Volume slider and mute
5. **BufferingIndicator** - Buffered content visualization
6. **TrackDisplay** - Current track info (title, artist, album art)

## Component Specifications

### 1. ProgressBar.tsx (~120 lines)
**Purpose**: Interactive timeline with seeking capability
**Props**:
- `currentTime`: number (current position in seconds)
- `duration`: number (track length in seconds)
- `bufferedPercentage`: number (0-100)
- `onSeek`: (position: number) => void (seek callback)
- `disabled`: boolean (disable interaction)

**Features**:
- Draggable progress indicator
- Buffered range visualization
- Hover tooltip with time
- Click to seek

### 2. PlaybackControls.tsx (~100 lines)
**Purpose**: Control buttons for playback
**Props**:
- `isPlaying`: boolean
- `onPlay`: () => void
- `onPause`: () => void
- `onNextTrack`: () => void
- `onPreviousTrack`: () => void
- `isLoading`: boolean (show loading state)

**Features**:
- Play/pause toggle
- Next/previous buttons
- Loading indicator
- Keyboard support (space to toggle)

### 3. TimeDisplay.tsx (~80 lines)
**Purpose**: Format and display time information
**Props**:
- `currentTime`: number
- `duration`: number
- `showRemaining`: boolean (show remaining time instead of duration)

**Features**:
- Formats time (mm:ss or h:mm:ss)
- Shows remaining time when requested
- Live content detection (shows "LIVE")
- Tooltip on hover

### 4. VolumeControl.tsx (~100 lines)
**Purpose**: Volume adjustment and mute
**Props**:
- `volume`: number (0-100)
- `isMuted`: boolean
- `onVolumeChange`: (volume: number) => void
- `onMuteToggle`: () => void

**Features**:
- Horizontal slider
- Volume icons (mute, low, high)
- Click to mute/unmute
- Keyboard support (arrow keys)

### 5. BufferingIndicator.tsx (~80 lines)
**Purpose**: Show buffering progress and status
**Props**:
- `bufferedPercentage`: number (0-100)
- `isBuffering`: boolean
- `isError`: boolean
- `errorMessage`: string (optional)

**Features**:
- Progress bar under main progress
- Buffering spinner animation
- Error display
- Tooltip with percentage

### 6. TrackDisplay.tsx (~100 lines)
**Purpose**: Show current track information
**Props**:
- `title`: string (track title)
- `artist`: string (artist name)
- `album`: string (album name)
- `albumArt`: string (image URL, optional)
- `isEnhanced`: boolean (mastering applied)

**Features**:
- Album art thumbnail
- Title, artist, album text
- Enhancement badge
- Truncate long text with ellipsis
- Click handler for more info

## Implementation Order

1. **TimeDisplay** - Simplest, uses usePlayerDisplay
2. **BufferingIndicator** - Visual-only, no interaction
3. **ProgressBar** - More complex, interactive seek
4. **PlaybackControls** - Uses usePlayerControls
5. **VolumeControl** - Interactive slider
6. **TrackDisplay** - Data display

## Testing Strategy

- 8-10 tests per component (~70 tests total)
- Test props rendering
- Test event callbacks
- Test edge cases (0 duration, live content, etc.)
- Test accessibility (keyboard, aria labels)
- Integration tests for interactivity

## Estimated Lines of Code

- Components: ~580 lines
- Tests: ~700 lines
- **Total Phase 4**: ~1,280 lines

## Key Dependencies

- `usePlayerStreaming` - timing data
- `usePlayerControls` - control operations
- `usePlayerDisplay` - formatting and display
- Design tokens - colors, spacing, typography
- React Testing Library - component testing

## Success Criteria

✅ All 6 components implemented
✅ 70+ comprehensive tests passing
✅ Full TypeScript type safety
✅ Keyboard accessible
✅ Mobile responsive
✅ Proper error handling
✅ Accessible color contrast

---

**Status**: Ready to implement Phase 4
