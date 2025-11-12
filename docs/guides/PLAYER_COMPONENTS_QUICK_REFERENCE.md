# Player Components Quick Reference

## Component at a Glance

### PlaybackController
```python
from auralis.player.playback_controller import PlaybackController, PlaybackState

controller = PlaybackController()
controller.play()           # Start playback
controller.pause()          # Pause playback
controller.stop()           # Stop and reset
controller.seek(44100, 441000)  # Seek to position
controller.is_playing()     # Check state
controller.add_callback(callback)  # Register listener
```

**State enum**:
- `PlaybackState.STOPPED`
- `PlaybackState.PLAYING`
- `PlaybackState.PAUSED`
- `PlaybackState.LOADING`
- `PlaybackState.ERROR`

---

### AudioFileManager
```python
from auralis.player.audio_file_manager import AudioFileManager

manager = AudioFileManager(sample_rate=44100)
manager.load_file("song.mp3")                    # Load audio
manager.load_reference("reference.mp3")          # Load reference
chunk = manager.get_audio_chunk(0, 2048)         # Get samples
duration = manager.get_duration()                # Duration in seconds
samples = manager.get_total_samples()            # Total sample count
is_loaded = manager.is_loaded()                  # Check loaded
manager.clear_audio()                            # Clear memory
```

**Audio format**: Always stereo (N, 2) float32
**Chunk extraction**: Handles mono-to-stereo conversion, padding

---

### QueueController
```python
from auralis.player.queue_controller import QueueController

queue = QueueController()
queue.add_track({"id": 1, "title": "Song"})      # Add track
next_track = queue.next_track()                  # Next + advance
prev_track = queue.previous_track()              # Previous
peek = queue.peek_next_track()                   # Peek without advancing
queue.load_playlist(playlist_id=1)               # Load playlist
queue.search_and_add("query", limit=10)          # Search library
queue.set_shuffle(True)                          # Enable shuffle
queue.set_repeat(True)                           # Enable repeat
info = queue.get_queue_info()                    # Get queue state
queue.clear_queue()                              # Clear queue
```

**Queue info fields**:
- `tracks`: List of track dicts
- `current_index`: Current position
- `current_track`: Current track dict
- `track_count`: Number of tracks
- `has_next`, `has_previous`: Boolean flags
- `shuffle_enabled`, `repeat_enabled`: Mode flags

---

### GaplessPlaybackEngine
```python
from auralis.player.gapless_playback_engine import GaplessPlaybackEngine

gapless = GaplessPlaybackEngine(file_manager, queue_controller)
gapless.start_prebuffering()                     # Start bg thread
has_prebuf = gapless.has_prebuffered_track()     # Check ready
audio, sr = gapless.get_prebuffered_track()      # Get buffer
success = gapless.advance_with_prebuffer(True)   # Advance + use buffer
gapless.invalidate_prebuffer()                   # Clear buffer
gapless.add_prebuffer_callback(callback)         # On prebuffer done
gapless.cleanup()                                # Stop threads
```

**Thread safety**: `update_lock` protects shared state
**Prebuffering**: Reduces gap from ~100ms to <10ms

---

### IntegrationManager
```python
from auralis.player.integration_manager import IntegrationManager

mgr = IntegrationManager(playback, file_manager, queue, processor)
mgr.load_track_from_library(track_id=42)         # Load library track
mgr.set_effect_enabled("eq", True)               # Control effects
mgr.set_auto_master_profile("bright")            # Set profile
mgr.add_callback(callback)                       # Register callback
info = mgr.get_playback_info()                   # Get full state
mgr.record_track_completion()                    # Update stats
mgr.cleanup()                                    # Cleanup
```

**Playback info fields**:
```python
{
    'playback': {...},      # State, position, duration
    'queue': {...},         # Queue info
    'library': {...},       # Current track, auto-ref status
    'processing': {...},    # DSP info
    'session': {...}        # Statistics
}
```

---

### EnhancedAudioPlayer (Facade)
```python
from auralis.player.enhanced_audio_player_refactored import EnhancedAudioPlayer

player = EnhancedAudioPlayer(config, library_manager)

# All original methods work
player.load_file("song.mp3")
player.load_reference("ref.mp3")
player.load_track_from_library(42)
player.play()
player.pause()
player.stop()
player.seek(30.0)  # Seconds
player.next_track()
player.previous_track()
player.add_to_queue(track_dict)
player.add_track_to_queue(track_id)
player.search_and_add_to_queue("query")
player.load_playlist(playlist_id)
player.clear_queue()
player.set_effect_enabled("eq", True)
player.set_auto_master_profile("bright")
player.set_shuffle(True)
player.set_repeat(True)
player.add_callback(callback)
player.get_playback_info()
player.get_queue_info()
chunk = player.get_audio_chunk(2048)
player.cleanup()

# Component access (advanced)
player.playback            # PlaybackController
player.file_manager        # AudioFileManager
player.queue               # QueueController
player.gapless             # GaplessPlaybackEngine
player.integration         # IntegrationManager
player.processor           # RealtimeProcessor
```

---

## Component Dependencies

```
PlaybackController → (none)
   ↓
AudioFileManager → io.loader
   ↓
QueueController → io.loader, library.manager
   ↓
GaplessPlaybackEngine → AudioFileManager, QueueController
   ↓
IntegrationManager → all above + RealtimeProcessor
   ↓
EnhancedAudioPlayer → all components
```

---

## Testing Patterns

### Unit Test PlaybackController
```python
from auralis.player.playback_controller import PlaybackController

def test_play_state():
    playback = PlaybackController()
    assert playback.is_stopped()
    playback.play()
    assert playback.is_playing()
```

### Unit Test AudioFileManager
```python
from auralis.player.audio_file_manager import AudioFileManager

def test_load_file():
    manager = AudioFileManager()
    assert manager.load_file("test.wav")
    assert manager.is_loaded()
    chunk = manager.get_audio_chunk(0, 2048)
    assert chunk.shape == (2048, 2)
```

### Unit Test QueueController (with mock)
```python
from auralis.player.queue_controller import QueueController
from unittest.mock import Mock

def test_add_track():
    queue = QueueController(Mock())  # Mock library
    queue.add_track({"id": 1, "title": "Song"})
    assert queue.get_track_count() == 1
```

### Integration Test GaplessPlaybackEngine
```python
from auralis.player.gapless_playback_engine import GaplessPlaybackEngine
import time

def test_prebuffering():
    gapless = GaplessPlaybackEngine(file_manager, queue)
    gapless.start_prebuffering()
    time.sleep(1)  # Wait for thread
    assert gapless.has_prebuffered_track()
```

### Integration Test Full Player
```python
from auralis.player.enhanced_audio_player_refactored import EnhancedAudioPlayer

def test_playback():
    player = EnhancedAudioPlayer()
    player.load_file("test.wav")
    player.play()
    chunk = player.get_audio_chunk(2048)
    assert chunk is not None
```

---

## Common Usage Patterns

### Basic Playback
```python
player = EnhancedAudioPlayer()
player.load_file("song.mp3")
player.play()

# In playback loop:
chunk = player.get_audio_chunk(2048)
# Send chunk to audio output
```

### Queue and Next Track
```python
player.add_to_queue({"path": "track1.mp3"})
player.add_to_queue({"path": "track2.mp3"})
player.load_file("track1.mp3")
player.play()

# When track ends or user skips:
player.next_track()  # Auto-uses prebuffering
```

### Library Integration
```python
# Load specific track
player.load_track_from_library(track_id=42)
player.play()

# Load playlist
player.load_playlist(playlist_id=1)
player.play()

# Search and add
player.search_and_add_to_queue("artist name")
```

### Real-time Effects
```python
# Enable/disable effects
player.set_effect_enabled("eq", True)
player.set_effect_enabled("compression", False)

# Set mastering profile
player.set_auto_master_profile("bright")
player.set_auto_master_profile("warm")
player.set_auto_master_profile("punchy")
```

### State Monitoring
```python
player.add_callback(on_state_change)

def on_state_change(info):
    print(f"State: {info['state']}")
    print(f"Position: {info['position_seconds']}s")
    print(f"Duration: {info['duration_seconds']}s")
```

---

## Error Handling

### File Loading
```python
if not player.load_file("song.mp3"):
    print(f"Error: {player.state}")  # PlaybackState.ERROR
    # Try another file
```

### Library Operations
```python
if not player.load_track_from_library(track_id):
    print("Track not found in library")
    # Fall back to file path
```

### Queue Operations
```python
if player.next_track():
    print("Advanced to next track")
else:
    print("No next track in queue")
```

---

## Memory Considerations

### Audio Data
- Loaded audio stored in AudioFileManager
- Prebuffered audio stored in GaplessPlaybackEngine
- Both are cleared on `cleanup()` or component destruction

### Queue
- Entire queue stored in memory
- For large playlists, consider pagination in future

### Callbacks
- Registered callbacks kept in list
- Removed automatically if callback raises exception

---

## Thread Safety

### Shared Data
- `GaplessPlaybackEngine` protects buffers with `update_lock`
- `PlaybackController` not thread-safe (single playback thread assumed)
- `AudioFileManager` not thread-safe (designed for single reader)

### Best Practice
```python
# Safe: Playback thread calls get_audio_chunk()
# Safe: Background prebuffer thread in GaplessPlaybackEngine
# Unsafe: Multiple threads accessing player simultaneously
# Always use player from single playback loop
```

---

## Debugging Tips

### Check Prebuffer Status
```python
if player.gapless.has_prebuffered_track():
    print("Next track prebuffered, gapless!")
else:
    print("Prebuffering in progress or not available")
```

### Get Detailed State
```python
info = player.get_playback_info()
print(f"State: {info['playback']['state']}")
print(f"Position: {info['playback']['position_seconds']}s")
print(f"Queue size: {info['queue']['track_count']}")
print(f"Tracks played: {info['session']['tracks_played']}")
```

### Monitor Components
```python
print(f"Playback: {player.playback.state}")
print(f"Loaded: {player.file_manager.is_loaded()}")
print(f"Queue size: {player.queue.get_track_count()}")
print(f"Prebuffered: {player.gapless.has_prebuffered_track()}")
```

---

## Performance Notes

- PlaybackController: O(1) for all operations
- AudioFileManager: O(n) for file loading (linear in file size)
- QueueController: O(1) for navigation, O(n) for searches
- GaplessPlaybackEngine: Threading overhead ~1-2ms
- IntegrationManager: Library queries may be cached

**Real-time factor**: 36.6x (process 1hr in ~98 seconds)

---

## Version & Compatibility

- **Version**: 1.0.0-beta.12.1
- **API**: 100% backward compatible
- **Original**: Original `enhanced_audio_player.py` still available
- **New**: `enhanced_audio_player_refactored.py` recommended for new code

---

## See Also

- [PLAYER_REFACTORING_ARCHITECTURE.md](./PLAYER_REFACTORING_ARCHITECTURE.md) - Full architecture
- [PLAYER_MIGRATION_QUICK_START.md](./PLAYER_MIGRATION_QUICK_START.md) - Migration guide
- [PLAYER_ARCHITECTURE_DIAGRAM.md](./PLAYER_ARCHITECTURE_DIAGRAM.md) - Visual diagrams
