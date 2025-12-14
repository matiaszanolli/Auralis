# Phase C.2 Implementation Plan

**Status:** Planning Phase
**Duration:** Week 7 (Estimated)
**Phase:** C.2 - Advanced UI Components & State Integration

---

## 🎯 Phase C.2 Objectives

Build advanced UI components that combine the Phase C.1 API client layer with Redux state management and WebSocket real-time updates.

### Core Goals
1. **Cache Management Dashboard** - Visual management and clearing of cache
2. **Player Controls** - Playback controls integrated with WebSocket
3. **Queue Manager** - Visual queue management with drag-and-drop
4. **Real-Time Indicators** - Status, health, and connection indicators
5. **State Integration** - Connect all components to Redux store
6. **Test Coverage** - 40+ tests for new components

---

## 📦 Components to Create

### 1. CacheManagementPanel (280+ lines)

**Purpose:** Advanced cache management UI

**Features:**
- Visual cache overview with tier breakdown
- Cache clear buttons with confirmation
- Per-track cache clearing
- Cache statistics with trend charts
- Memory usage breakdown
- Auto-refresh configuration

**Props:**
```typescript
interface CacheManagementPanelProps {
  onCacheClearRequest?: () => void;
  refreshInterval?: number;
  showAdvanced?: boolean;
}
```

**UI Elements:**
- Overall cache size visualization
- Tier 1/2 breakdown with progress bars
- Clear cache button with confirmation modal
- Clear specific track option
- Auto-cleanup toggle
- Performance charts (hit rate over time)
- Memory usage gauge

**Integration:**
- Uses `useCacheStats()` and `useCacheHealth()` hooks
- Uses `useStandardizedAPI()` for cache clearing
- Shows loading/error states
- Real-time updates via WebSocket

### 2. PlayerControls (320+ lines)

**Purpose:** Integrated playback control component

**Features:**
- Play/pause/seek controls
- Next/previous track navigation
- Volume control with mute
- Preset selector
- Current track info display
- Time display and seeking

**Props:**
```typescript
interface PlayerControlsProps {
  disabled?: boolean;
  compact?: boolean;
  showPresetSelector?: boolean;
}
```

**UI Elements:**
- Large play/pause button
- Skip controls (next/previous)
- Seek bar with time markers
- Current time / duration display
- Volume slider with percentage
- Mute button
- Preset selector dropdown (6 presets)
- Current track info panel
- Loading indicator during playback changes

**Integration:**
- Uses `usePlayerCommands()` WebSocket hook
- Redux connection for playback state
- Real-time sync with backend player state
- Error handling for failed commands
- Disabled state during network issues

### 3. QueueManager (380+ lines)

**Purpose:** Visual queue management with reordering

**Features:**
- Queue list display with reordering
- Add tracks to queue
- Remove tracks from queue
- Clear queue
- Queue statistics
- Current track highlighting
- Drag-and-drop reordering

**Props:**
```typescript
interface QueueManagerProps {
  compact?: boolean;
  maxHeight?: string;
  showAddTrack?: boolean;
}
```

**UI Elements:**
- Queue list with track thumbnails
- Current track highlight with indicator
- Drag handles for reordering
- Remove button per track
- Add track search/browser
- Clear queue button with confirmation
- Queue length and current position
- Estimated playtime remaining
- Virtual scrolling for large queues

**Integration:**
- Uses `useQueueCommands()` WebSocket hook
- Redux for queue state
- MSE for audio buffering
- Drag-and-drop library integration
- Real-time sync with backend queue

### 4. ConnectionStatusIndicator (180+ lines)

**Purpose:** Real-time connection status display

**Features:**
- WebSocket connection status
- API connection status
- Reconnection attempts display
- Connection history
- Latency measurement

**Props:**
```typescript
interface ConnectionStatusIndicatorProps {
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
  compact?: boolean;
}
```

**UI Elements:**
- Status dot (connected/disconnected/reconnecting)
- Status text
- Reconnect button
- Latency display (ms)
- Connection type indicator
- Retry count display
- Last update timestamp

**Integration:**
- Uses `useWebSocketProtocol()` hook
- Uses API connection status
- Auto-hide when connected
- Pulsing animation during reconnection

### 5. CacheHealthWidget (200+ lines)

**Purpose:** Compact cache health indicator

**Features:**
- Health status at a glance
- Quick alerts
- Quick actions
- Trend indicator

**Props:**
```typescript
interface CacheHealthWidgetProps {
  size?: 'small' | 'medium' | 'large';
  interactive?: boolean;
}
```

**UI Elements:**
- Status indicator (green/yellow/red)
- Health percentage
- Alert count badge
- Trend arrow (up/down/stable)
- Click to expand to full monitor
- Recommended action tooltip

**Integration:**
- Uses `useCacheHealth()` hook
- Redux for expanded state
- Modal or side-panel expansion
- Real-time status updates

### 6. PlaybackProgressBar (200+ lines)

**Purpose:** Advanced progress bar with seeking

**Features:**
- Visual progress display
- Seeking with drag
- Time markers and labels
- Buffered regions display
- Preview on hover

**Props:**
```typescript
interface PlaybackProgressBarProps {
  disabled?: boolean;
  showTimeLabels?: boolean;
  showMarkers?: boolean;
}
```

**UI Elements:**
- Main progress bar
- Current playhead
- Buffered region visualization
- Time labels (current/total)
- Marker points for key moments
- Hover preview with time
- Seek animation
- Loading state during seeking

**Integration:**
- Uses `usePlayerCommands()` for seeking
- Redux for current time and duration
- Real-time duration updates
- Smooth seeking without jarring

---

## 🔌 Integration Strategy

### Redux Store Integration

**Player State:**
```typescript
{
  playback: {
    isPlaying: boolean;
    currentTrack: Track | null;
    currentTime: number;
    duration: number;
    volume: number;
    isMuted: boolean;
    preset: PresetName;
    isLoading: boolean;
  },
  queue: {
    tracks: Track[];
    currentIndex: number;
    hasMore: boolean;
    isLoading: boolean;
  },
  cache: {
    stats: CacheStats | null;
    health: CacheHealth | null;
    lastUpdate: number;
  },
  connection: {
    wsConnected: boolean;
    apiConnected: boolean;
    latency: number;
    reconnectAttempts: number;
  }
}
```

### WebSocket Integration Points

Each component will subscribe to relevant WebSocket message types:

- **PlayerControls**: `PLAY`, `PAUSE`, `SEEK`, `STOP`
- **QueueManager**: `QUEUE_ADD`, `QUEUE_REMOVE`, `QUEUE_REORDER`
- **CacheManagementPanel**: `CACHE_STATS`, `CACHE_STATUS`
- **ConnectionStatusIndicator**: Connection events
- **PlaybackProgressBar**: `STATUS_UPDATE` messages

### API Integration Points

Components will use the following API endpoints:

- `/api/cache/clear` - Clear cache
- `/api/cache/clear-track/{id}` - Clear track from cache
- `/api/player/play` - Play track
- `/api/player/pause` - Pause playback
- `/api/player/seek` - Seek to position
- `/api/queue/add` - Add to queue
- `/api/queue/remove` - Remove from queue
- `/api/queue/reorder` - Reorder queue

---

## 🧪 Test Plan

### Component Tests (40+ tests)

**CacheManagementPanel (8 tests)**
- Rendering with cache stats
- Clear cache confirmation
- Per-track clearing
- Loading/error states
- Auto-refresh functionality

**PlayerControls (12 tests)**
- Play/pause button behavior
- Seek functionality
- Volume control
- Next/previous navigation
- Preset selection
- Disabled state
- Loading states

**QueueManager (12 tests)**
- Queue list rendering
- Add track functionality
- Remove track functionality
- Reorder via drag-drop
- Clear queue confirmation
- Current track highlighting
- Virtual scrolling with large queue

**ConnectionStatusIndicator (5 tests)**
- Connected state display
- Disconnected state display
- Reconnecting animation
- Latency display
- Reconnect button

**CacheHealthWidget (3 tests)**
- Health status display
- Alert badge rendering
- Expansion functionality

### Integration Tests (10+ tests)

- Player controls updating Redux
- Queue changes syncing with backend
- Cache clearing triggering updates
- WebSocket events updating components
- Connection status affecting component state

---

## 📋 Implementation Checklist

- [ ] Create CacheManagementPanel component
- [ ] Create PlayerControls component
- [ ] Create QueueManager component
- [ ] Create ConnectionStatusIndicator component
- [ ] Create CacheHealthWidget component
- [ ] Create PlaybackProgressBar component
- [ ] Create Redux slices for new state
- [ ] Integrate WebSocket subscriptions
- [ ] Create component tests (40+ tests)
- [ ] Create integration tests (10+ tests)
- [ ] Verify all tests passing
- [ ] Create Phase C.2 documentation

---

## 🎯 Completion Criteria

✅ **All components implemented** (6 components, 1,560+ lines)
✅ **Full Redux integration** (state slices, actions, selectors)
✅ **WebSocket subscriptions** (real-time updates for all events)
✅ **Test coverage** (50+ tests, 100% passing)
✅ **Design system compliance** (all components using tokens)
✅ **Documentation** (Phase C.2 completion summary)
✅ **No broken tests** (backend and frontend)
✅ **Git commit** (proper commit message with all changes)

---

## 🚀 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Component Count | 6 | Delivered |
| Production Code | 1,560+ lines | Measured |
| Test Coverage | 50+ tests | Execution |
| Test Success Rate | 100% | Pass/Fail |
| Design Compliance | 100% | Token usage |
| Documentation | Complete | Presence |

---

*Phase C.2 Plan - Ready for Implementation*
