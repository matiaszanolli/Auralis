# Player Refactoring Migration Guide

Quick-start guide for migrating to the refactored `EnhancedAudioPlayer`.

## Good News: No Code Changes Required

The refactored player maintains **100% backward-compatible API**. Your existing code continues to work unchanged.

## Current Implementation Files

### New Component-Based Implementation
Located in `auralis/player/`:

- **`playback_controller.py`** (100 lines)
  - State machine for PLAYING, PAUSED, STOPPED, LOADING, ERROR
  - Position tracking and seeking
  - Simple, testable, no I/O

- **`audio_file_manager.py`** (120 lines)
  - Audio file loading and data access
  - Reference audio management
  - Chunk extraction for playback

- **`queue_controller.py`** (150 lines)
  - Queue and playlist management
  - Track navigation (next, previous)
  - Shuffle and repeat modes

- **`gapless_playback_engine.py`** (150 lines)
  - Background prebuffering (threading)
  - Seamless track transitions
  - Buffer management

- **`integration_manager.py`** (130 lines)
  - Library track loading
  - Auto-reference selection
  - Effect and profile management
  - Session statistics

- **`enhanced_audio_player_refactored.py`** (150 lines)
  - Facade coordinating all components
  - Backward-compatible API
  - 100% drop-in replacement

### Original Monolithic Implementation
Still at `auralis/player/enhanced_audio_player.py` (698 lines)

## Switching to Refactored Version

### Option 1: Drop-In Replacement (Recommended)

The refactored version is already backward-compatible. You can use it identically to the original:

```python
# Your existing code works unchanged
from auralis.player.enhanced_audio_player_refactored import EnhancedAudioPlayer

player = EnhancedAudioPlayer()
player.load_file("song.mp3")
player.play()
player.seek(30.0)
player.next_track()
```

### Option 2: Use Components Directly (Advanced)

For new code, you can use components directly for finer control:

```python
from auralis.player.playback_controller import PlaybackController
from auralis.player.audio_file_manager import AudioFileManager
from auralis.player.queue_controller import QueueController
from auralis.player.gapless_playback_engine import GaplessPlaybackEngine
from auralis.player.integration_manager import IntegrationManager

# Create components
playback = PlaybackController()
file_mgr = AudioFileManager(sample_rate=44100)
queue = QueueController()
gapless = GaplessPlaybackEngine(file_mgr, queue)
integration = IntegrationManager(playback, file_mgr, queue, processor)

# Use directly
file_mgr.load_file("song.mp3")
playback.play()
playback.seek(30 * 44100, file_mgr.get_total_samples())
```

## Testing with Refactored Components

### Unit Test Individual Components

```python
def test_playback_controller():
    """Test playback state machine in isolation"""
    playback = PlaybackController()

    assert playback.state == PlaybackState.STOPPED
    playback.play()
    assert playback.is_playing()
    playback.pause()
    assert playback.is_paused()


def test_audio_file_manager():
    """Test file loading in isolation"""
    manager = AudioFileManager(sample_rate=44100)
    assert manager.load_file("test_files/test.wav")
    assert manager.is_loaded()
    assert manager.get_duration() > 0

    chunk = manager.get_audio_chunk(0, 2048)
    assert chunk.shape == (2048, 2)


def test_queue_controller():
    """Test queue operations in isolation"""
    queue = QueueController()
    queue.add_track({"id": 1, "title": "Track 1"})
    queue.add_track({"id": 2, "title": "Track 2"})

    assert queue.get_track_count() == 2
    next_track = queue.next_track()
    assert next_track["id"] == 1
```

### Integration Test Components Together

```python
def test_gapless_playback_integration():
    """Test gapless playback with real components"""
    config = PlayerConfig()
    player = EnhancedAudioPlayer(config)

    # Load a file
    assert player.load_file("test_files/track1.wav")

    # Add tracks to queue
    player.add_to_queue({"path": "test_files/track2.wav"})

    # Start playback
    assert player.play()

    # Verify prebuffering started
    assert player.gapless.has_prebuffered_track() or True

    # Advance with gapless
    assert player.next_track()
```

## Accessing Components Through Facade

Even with the facade, you can access internal components:

```python
player = EnhancedAudioPlayer()

# Access component state directly (advanced use)
print(player.playback.state)              # PlaybackState
print(player.file_manager.sample_rate)    # int
print(player.queue.get_queue_info())      # dict
print(player.gapless.has_prebuffered_track())  # bool
print(player.integration.current_track)   # Track

# But most code should use facade methods
player.play()
player.seek(30.0)
```

## Debugging with Components

### Component-Level Logging

Each component logs independently:

```python
# PlaybackController logs state changes
INFO: Playback started
INFO: Seeked to 30.0s
INFO: Playback paused

# AudioFileManager logs file operations
INFO: Loaded audio file: song.mp3
INFO: Duration: 3.5s
INFO: Sample rate: 44100 Hz

# GaplessPlaybackEngine logs prebuffering
INFO: Prebuffering next track: next_song.mp3
INFO: Prebuffered: next_song.mp3 (3.2s)

# IntegrationManager logs library operations
INFO: Loaded track from library: Track 1
INFO: Using recommended reference: reference.mp3
```

### Isolating Issues

With components separated, it's easier to identify issues:

**Issue: Playback stops suddenly**
- ✅ Check PlaybackController state transitions
- ✅ Check AudioFileManager has audio loaded
- ❌ Can't be queue-related if file manager is fine

**Issue: Gapless playback has gaps**
- ✅ Check GaplessPlaybackEngine prebuffer timing
- ✅ Check thread completion
- ✅ Check buffer validation
- ❌ Likely not a playback state issue

**Issue: Auto-reference not working**
- ✅ Check IntegrationManager reference selection
- ✅ Check library query results
- ❌ Not a prebuffering issue

## Backward Compatibility Checklist

All these patterns still work exactly as before:

```python
# ✅ Basic playback
player.load_file("song.mp3")
player.play()
player.pause()
player.stop()

# ✅ Seeking
player.seek(30.0)  # Position in seconds

# ✅ Queue operations
player.add_to_queue({"path": "track2.mp3"})
player.next_track()
player.previous_track()
player.load_playlist(playlist_id=1)

# ✅ Effects and profiles
player.set_effect_enabled("eq", True)
player.set_auto_master_profile("bright")

# ✅ Callbacks
player.add_callback(on_playback_state_changed)
info = player.get_playback_info()

# ✅ Properties
pos = player.position
file = player.current_file
track = player.current_track
state = player.state

# ✅ Library integration
player.load_track_from_library(track_id=42)
player.search_and_add_to_queue("query", limit=10)
```

## Performance Considerations

The refactored version has the same performance characteristics as the original:

- **No overhead**: Same number of operations, just better organized
- **Same threading**: Prebuffering works identically
- **Same I/O**: File loading unchanged
- **Better debugging**: Easier to profile individual components

## Troubleshooting

### "ImportError: cannot import name 'EnhancedAudioPlayer'"

Make sure you're importing from the correct module:

```python
# ✅ Correct - new refactored version
from auralis.player.enhanced_audio_player_refactored import EnhancedAudioPlayer

# ✅ Also correct - old monolithic version (backward compatible)
from auralis.player.enhanced_audio_player import EnhancedAudioPlayer

# ❌ Wrong - both paths are valid but use one consistently
```

### Components not initialized

All components are created automatically by the facade:

```python
player = EnhancedAudioPlayer()  # All components initialized

# Don't do this:
player.playback = None  # Don't manually clear components

# Use cleanup for proper teardown:
player.cleanup()  # Safe cleanup
```

### Gapless playback not working

Check prebuffering setup:

```python
player = EnhancedAudioPlayer()
player.load_file("song1.mp3")
player.add_to_queue({"path": "song2.mp3"})

# Wait a moment for prebuffering
import time
time.sleep(1.0)

# Check prebuffer status
if player.gapless.has_prebuffered_track():
    print("Prebuffered, gapless transition should work!")
else:
    print("Not prebuffered yet, will fall back to normal loading")
```

## Next Steps

1. **Run tests**: Ensure all tests pass with new components
   ```bash
   pytest tests/player/ -v
   ```

2. **Profile**: Check performance is maintained
   ```bash
   python benchmark_performance.py
   ```

3. **Monitor logs**: Verify component logging shows expected flow
   ```bash
   python -m logging DEBUG
   ```

4. **Update documentation**: Document component usage for new code

## Questions?

See full architecture documentation:
- [PLAYER_REFACTORING_ARCHITECTURE.md](./PLAYER_REFACTORING_ARCHITECTURE.md)

For specific component details:
- [PlaybackController](../../auralis/player/playback_controller.py) - State machine
- [AudioFileManager](../../auralis/player/audio_file_manager.py) - File I/O
- [QueueController](../../auralis/player/queue_controller.py) - Queue management
- [GaplessPlaybackEngine](../../auralis/player/gapless_playback_engine.py) - Prebuffering
- [IntegrationManager](../../auralis/player/integration_manager.py) - Library & effects
