# EnhancedAudioPlayer Architecture Diagram

## Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│         EnhancedAudioPlayer (Facade)                            │
│         ~150 lines - Coordinates all components                 │
│         100% backward compatible API                            │
└─────────────────┬───────────────────────────────────────────────┘
                  │
        ┌─────────┼─────────┬─────────────┬──────────────┐
        │         │         │             │              │
        ▼         ▼         ▼             ▼              ▼
    ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────────┐
    │Playback│ │ Audio  │ │Queue   │ │Gapless   │ │Integration │
    │Control │ │ File   │ │Control │ │Playback  │ │ Manager    │
    │ler     │ │Manager │ │ler     │ │ Engine   │ │            │
    └────────┘ └────────┘ └────────┘ └──────────┘ └────────────┘
    ~100 lines ~120 lines ~150 lines ~150 lines   ~130 lines
```

## Data Flow: Loading and Playing a Track

```
Application
    │
    ├─► player.load_file("song.mp3")
    │       │
    │       ├─► playback.set_loading()
    │       ├─► file_manager.load_file()
    │       │       └─► load audio from disk
    │       ├─► playback.stop()
    │       └─► gapless.start_prebuffering()
    │               └─► prebuffer next track in background
    │
    ├─► player.play()
    │       └─► playback.play()
    │           └─► state = PLAYING
    │
    └─► player.get_audio_chunk(2048)
            ├─► file_manager.get_audio_chunk()
            │   └─► extract samples from loaded audio
            ├─► playback.position += chunk_size
            ├─► processor.process_chunk()
            │   └─► apply DSP effects
            └─► return processed audio
```

## Data Flow: Gapless Playback (Next Track)

```
player.next_track()
    │
    ├─► queue.next_track()
    │   └─► advance queue index
    │
    └─► gapless.advance_with_prebuffer()
            │
            ├─► Check: is next track prebuffered?
            │
            ├─► YES (Gapless <10ms)
            │   ├─► file_manager.audio_data = prebuffered
            │   ├─► Clear prebuffer
            │   └─► Instant transition!
            │
            └─► NO (Normal ~100ms)
                ├─► file_manager.load_file(next_path)
                └─► Normal loading delay
```

## Component Interactions

### PlaybackController ↔ AudioFileManager
```
PlaybackController          AudioFileManager
    │                           │
    ├─ position ─────────────────► used to extract chunk
    │                           │
    └─ seek(position) ──────────► validates against total_samples
```

### AudioFileManager ↔ GaplessPlaybackEngine
```
AudioFileManager            GaplessPlaybackEngine
    │                           │
    ├─ load_file() ◄───────────── _prebuffer_worker()
    │                           │
    └─ audio_data ──────────────► used for playback
```

### QueueController ↔ GaplessPlaybackEngine
```
QueueController             GaplessPlaybackEngine
    │                           │
    ├─ next_track() ◄───────────── advance_with_prebuffer()
    │                           │
    ├─ peek_next() ─────────────► used to prebuffer ahead
    │                           │
    └─ current track ───────────► metadata for transition
```

### IntegrationManager ↔ All Components
```
IntegrationManager (Coordinator)
    │
    ├─► Receives state changes from PlaybackController
    ├─► Queries AudioFileManager for position/duration
    ├─► Uses QueueController for track info
    ├─► Monitors GaplessPlaybackEngine prebuffer
    │
    └─► Enriches info and notifies external callbacks
```

## Thread Model

```
Main Thread (Application)
    │
    ├─► player.load_file()  (blocking I/O)
    ├─► player.play()       (quick state change)
    ├─► player.get_audio_chunk()  (audio processing)
    │
    └─► gapless.start_prebuffering()
            │
            └─ Spawns ──────────────────┐
                                        │
                                   Background Thread
                                        │
                                        ├─ GaplessPlaybackEngine._prebuffer_worker()
                                        ├─► file_manager.load_file() (blocking I/O)
                                        ├─► update_lock.acquire()
                                        ├─► Store prebuffered audio
                                        └─► update_lock.release()
```

## State Machine (PlaybackController)

```
                 ┌──────────────┐
                 │   STOPPED    │
                 └──────────────┘
                  │          ▲
              play│          │stop
                  │          │
                  ▼          │
         ┌──────────────┐    │
    ┌────┤  PLAYING    ├────┘
    │    └──────────────┘
    │       │         ▲
    │ pause │         │play
    │       ▼         │
    │    ┌──────────────┐
    └───►│   PAUSED     │
         └──────────────┘

    LOADING ─────────────┐
         (during load)    │
                          ├──────► STOPPED / ERROR
                          │
                   (on success)

    ERROR
      (on failure)
```

## Memory Layout During Playback

```
┌─ PlaybackController
│  ├─ state: PlaybackState.PLAYING
│  └─ position: 44100 (1 second at 44.1kHz)
│
├─ AudioFileManager
│  ├─ audio_data: ndarray(5292000, 2) [30s stereo @ 44.1kHz]
│  ├─ sample_rate: 44100
│  ├─ current_file: "song.mp3"
│  ├─ reference_data: ndarray(1029600, 2) [optional]
│  └─ reference_file: "reference.mp3" [optional]
│
├─ QueueController
│  ├─ queue.tracks: [Track1, Track2, Track3]
│  ├─ queue.current_index: 0
│  └─ library: LibraryManager instance
│
├─ GaplessPlaybackEngine
│  ├─ next_track_buffer: ndarray(4410000, 2) [prebuffered song 2]
│  ├─ next_track_info: {"id": 2, "title": "Song 2"}
│  ├─ prebuffer_thread: Thread (running)
│  └─ update_lock: Lock
│
└─ IntegrationManager
   ├─ current_track: Track{id:1, title:"Song 1"}
   ├─ tracks_played: 0
   ├─ session_start_time: 1731384000.5
   └─ library: LibraryManager instance
```

## Dependency Graph

```
PlaybackController (no external dependencies)
        │
        ├─ AudioFileManager (depends on io.loader)
        │
        ├─ QueueController (depends on LibraryManager)
        │
        ├─ GaplessPlaybackEngine (depends on AudioFileManager, QueueController)
        │
        └─ IntegrationManager (depends on all above + RealtimeProcessor)
                │
                └─ EnhancedAudioPlayer (Facade - depends on all)
```

## Testing Strategy by Component

```
PlaybackController
    │
    └─► Unit Tests (no mocks needed)
            ├─► State transitions
            ├─► Seek validation
            ├─► Callback invocation
            └─► 5 minutes to write, instant to run

AudioFileManager
    │
    └─► Unit Tests + Integration Tests
            ├─► File loading (needs test file)
            ├─► Chunk extraction
            ├─► Stereo conversion
            └─► 10 minutes to write, <1 second to run

QueueController
    │
    └─► Unit Tests (can mock LibraryManager)
            ├─► Track navigation
            ├─► Queue operations
            ├─► Shuffle/repeat
            └─► 15 minutes to write, instant to run

GaplessPlaybackEngine
    │
    └─► Integration Tests (with mocks)
            ├─► Thread lifecycle
            ├─► Buffer management
            ├─► Prebuffer validation
            └─► 20 minutes to write, 1-2 seconds to run

IntegrationManager
    │
    └─► Integration Tests (with real components)
            ├─► Library integration
            ├─► Callback coordination
            ├─► Statistics tracking
            └─► 25 minutes to write, 2-3 seconds to run

EnhancedAudioPlayer (Facade)
    │
    └─► End-to-End Tests
            ├─► Full playback workflow
            ├─► Queue to playback
            ├─► Gapless transitions
            └─► 30 minutes to write, 3-5 seconds to run
```

## Component Communication Pattern

```
┌─────────────────────────────────────────┐
│  PlaybackController                     │
│  (Observer Pattern - callbacks)         │
│                                         │
│  Notifies:                              │
│  - PlaybackState changes               │
│  - Position updates                    │
└─────────────────┬───────────────────────┘
                  │ state change event
                  │
                  ├──────────────────────────┐
                  │                          │
                  ▼                          ▼
         ┌─────────────────┐      ┌─────────────────────┐
         │ IntegrationMgr  │      │ External Callbacks  │
         │ (coordinates)   │      │ (Application code)  │
         │                 │      │                     │
         │ enriches event  │      │ Updates UI, etc.    │
         └────────┬────────┘      └─────────────────────┘
                  │
                  ├─ Queries AudioFileManager for context
                  ├─ Queries QueueController for queue state
                  └─ Monitors GaplessPlaybackEngine status
```

## API Flow Example

```python
# Application calls facade
player = EnhancedAudioPlayer()
player.load_file("song.mp3")

# Facade coordinates components
play.playback.set_loading()                    # Step 1
player.file_manager.load_file("song.mp3")     # Step 2
player.playback.stop()                        # Step 3
player.gapless.start_prebuffering()           # Step 4
    # spawns background thread

# Background thread runs
player.gapless._prebuffer_worker()
    player.queue.peek_next_track()            # Get next from queue
    player.file_manager.load_file(next_path)  # Prebuffer it

# Application plays
player.play()
    player.playback.play()                    # State → PLAYING

# Playback loop
chunk = player.get_audio_chunk(2048)
    player.file_manager.get_audio_chunk(...)  # Get samples
    player.playback.position += 2048          # Update position
    processor.process_chunk(chunk)            # Apply effects
    return processed_chunk
```

## Summary

The refactored architecture:
- ✅ Separates concerns into 5 focused components
- ✅ Uses Facade pattern for backward compatibility
- ✅ Clear data flow and state transitions
- ✅ Thread-safe with explicit synchronization
- ✅ Observable pattern for integration
- ✅ Easy to test in isolation
- ✅ Easy to extend with new features

Each component is:
- **Simple**: 100-150 lines, single responsibility
- **Testable**: No circular dependencies, easy to mock
- **Maintainable**: Clear purpose, focused methods
- **Observable**: Sends callbacks on state changes
- **Flexible**: Can be used independently or together
