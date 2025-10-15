# Backend Integration Plan: Connecting UI to Real Functionality

## Overview
This plan connects our beautiful UI to the powerful Auralis backend, enabling real audio processing, library management, and playback functionality.

## Current Backend Status ✅

The backend is **running and ready** at `http://localhost:8000` with:
- ✅ LibraryManager initialized (SQLite database)
- ✅ Enhanced Audio Player initialized
- ✅ Processing Engine initialized
- ✅ WebSocket support for real-time updates
- ✅ REST API endpoints available

## Available Backend APIs

### 1. Library API (`/api/library/*`)
```
GET  /api/library/stats              - Library statistics
GET  /api/library/tracks              - List tracks (with pagination)
GET  /api/library/albums              - List albums
GET  /api/library/artists             - List artists
GET  /api/library/playlists           - List playlists
POST /api/library/scan                - Scan folder for music files
GET  /api/library/search?q=query      - Search library
```

### 2. Player API (`/api/player/*`)
```
GET  /api/player/status               - Current playback status
POST /api/player/play                 - Start playback
POST /api/player/pause                - Pause playback
POST /api/player/next                 - Next track
POST /api/player/previous             - Previous track
POST /api/player/seek                 - Seek to position
POST /api/player/volume               - Set volume
POST /api/player/queue                - Set queue
```

### 3. Processing API (`/api/processing/*`)
```
POST /api/processing/upload           - Upload audio file
POST /api/processing/process          - Start processing job
GET  /api/processing/jobs             - List processing jobs
GET  /api/processing/jobs/{id}        - Get job status
GET  /api/processing/jobs/{id}/result - Download processed audio
DELETE /api/processing/jobs/{id}      - Cancel job
```

### 4. WebSocket (`/ws`)
```
ws://localhost:8000/ws                - Real-time updates
  - Library scan progress
  - Processing job updates
  - Player state changes
```

## Integration Plan

### Phase 1: Library Integration (Priority 1) 🎵

#### 1.1 Connect CozyLibraryView to Real Data
**File**: `src/components/CozyLibraryView.tsx`

**Current**: Mock data and local state
**Target**: Real library data from backend API

**Changes**:
```typescript
// Replace mock data fetch with real API
const fetchTracks = async () => {
  setLoading(true);
  try {
    const response = await fetch('http://localhost:8000/api/library/tracks?limit=100');
    const data = await response.json();
    setTracks(data.tracks || []);
    success(`Loaded ${data.tracks.length} tracks`);
  } catch (err) {
    error('Failed to load library');
  } finally {
    setLoading(false);
  }
};

// Real folder scan
const handleScanFolder = async () => {
  setScanning(true);
  try {
    const response = await fetch('http://localhost:8000/api/library/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: folderPath })
    });
    const data = await response.json();
    success(`Scanned ${data.tracks_added} tracks`);
    fetchTracks(); // Refresh library
  } catch (err) {
    error('Scan failed');
  } finally {
    setScanning(false);
  }
};
```

**Benefits**:
- Real music library from user's files
- Actual album art and metadata
- Real-time scan progress

#### 1.2 Add Library Statistics Display
**New Component**: `src/components/library/LibraryStats.tsx`

```typescript
interface LibraryStats {
  total_tracks: number;
  total_albums: number;
  total_artists: number;
  total_duration: number;
}

const LibraryStats: React.FC = () => {
  const [stats, setStats] = useState<LibraryStats | null>(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/library/stats')
      .then(res => res.json())
      .then(setStats);
  }, []);

  return (
    <Box sx={{ display: 'flex', gap: 3 }}>
      <Stat label="Tracks" value={stats?.total_tracks} />
      <Stat label="Albums" value={stats?.total_albums} />
      <Stat label="Artists" value={stats?.total_artists} />
    </Box>
  );
};
```

### Phase 2: Player Integration (Priority 1) 🎧

#### 2.1 Connect BottomPlayerBar to Real Player
**File**: `src/components/BottomPlayerBar.tsx`

**Current**: Local state only
**Target**: Real audio playback via backend

**Changes**:
```typescript
import { usePlayerAPI } from '../hooks/usePlayerAPI';

const BottomPlayerBar: React.FC = () => {
  const {
    currentTrack,
    isPlaying,
    currentTime,
    duration,
    volume,
    play,
    pause,
    next,
    previous,
    seek,
    setVolume
  } = usePlayerAPI();

  const handlePlayPause = () => {
    if (isPlaying) {
      pause();
      info('Paused');
    } else {
      play();
      info(`Playing: ${currentTrack?.title}`);
    }
  };

  // Real-time progress updates via WebSocket
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'player_update') {
        // Update player state
      }
    };
    return () => ws.close();
  }, []);

  // ... rest of component
};
```

#### 2.2 Create usePlayerAPI Hook
**New File**: `src/hooks/usePlayerAPI.ts`

```typescript
export const usePlayerAPI = () => {
  const [playerState, setPlayerState] = useState<PlayerState>({
    currentTrack: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    volume: 80
  });

  const play = async () => {
    const response = await fetch('http://localhost:8000/api/player/play', {
      method: 'POST'
    });
    const data = await response.json();
    setPlayerState(prev => ({ ...prev, isPlaying: true }));
  };

  const pause = async () => {
    await fetch('http://localhost:8000/api/player/pause', { method: 'POST' });
    setPlayerState(prev => ({ ...prev, isPlaying: false }));
  };

  const next = async () => {
    await fetch('http://localhost:8000/api/player/next', { method: 'POST' });
  };

  const previous = async () => {
    await fetch('http://localhost:8000/api/player/previous', { method: 'POST' });
  };

  const seek = async (position: number) => {
    await fetch('http://localhost:8000/api/player/seek', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ position })
    });
  };

  const setVolume = async (volume: number) => {
    await fetch('http://localhost:8000/api/player/volume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ volume })
    });
    setPlayerState(prev => ({ ...prev, volume }));
  };

  // WebSocket for real-time updates
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'player_update') {
        setPlayerState(prev => ({
          ...prev,
          ...data.state
        }));
      }
    };

    return () => ws.close();
  }, []);

  return {
    ...playerState,
    play,
    pause,
    next,
    previous,
    seek,
    setVolume
  };
};
```

### Phase 3: Processing Integration (Priority 2) 🎛️

#### 3.1 Connect PresetPane to Processing Engine
**File**: `src/components/PresetPane.tsx`

**Current**: Only UI state
**Target**: Real mastering presets and settings

**Changes**:
```typescript
const PresetPane: React.FC<PresetPaneProps> = ({
  onPresetChange,
  onMasteringToggle
}) => {
  const [selectedPreset, setSelectedPreset] = useState('adaptive');
  const [intensity, setIntensity] = useState(50);

  const handlePresetChange = (preset: string) => {
    setSelectedPreset(preset);

    // Send to backend or parent component
    onPresetChange?.({
      preset,
      intensity,
      enabled: masteringEnabled
    });

    info(`Preset changed to ${preset}`);
  };

  const handleIntensityChange = (value: number) => {
    setIntensity(value);

    // Update backend settings
    onPresetChange?.({
      preset: selectedPreset,
      intensity: value,
      enabled: masteringEnabled
    });
  };

  // ... rest of component
};
```

#### 3.2 Create Processing Interface
**New Component**: `src/components/ProcessingInterface.tsx`

```typescript
const ProcessingInterface: React.FC = () => {
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [uploading, setUploading] = useState(false);
  const { success, error, info } = useToast();

  // File upload handler
  const handleFileUpload = async (file: File) => {
    setUploading(true);

    try {
      // Upload file
      const formData = new FormData();
      formData.append('file', file);

      const uploadRes = await fetch('http://localhost:8000/api/processing/upload', {
        method: 'POST',
        body: formData
      });
      const uploadData = await uploadRes.json();

      // Start processing
      const processRes = await fetch('http://localhost:8000/api/processing/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_file: uploadData.file_id,
          preset: selectedPreset,
          intensity: intensity / 100
        })
      });
      const processData = await processRes.json();

      success(`Processing started for ${file.name}`);

      // Add to jobs list
      setJobs(prev => [...prev, processData]);

    } catch (err) {
      error(`Failed to process ${file.name}`);
    } finally {
      setUploading(false);
    }
  };

  // WebSocket for job updates
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'processing_update') {
        setJobs(prev => prev.map(job =>
          job.id === data.job_id
            ? { ...job, status: data.status, progress: data.progress }
            : job
        ));

        if (data.status === 'completed') {
          success(`Processing completed: ${data.filename}`);
        }
      }
    };

    return () => ws.close();
  }, []);

  return (
    <Box>
      {/* Drag & Drop Upload */}
      <DropZone onDrop={handleFileUpload} uploading={uploading} />

      {/* Processing Jobs List */}
      <JobsList jobs={jobs} />
    </Box>
  );
};
```

#### 3.3 Create Drag & Drop Upload Component
**New Component**: `src/components/processing/DropZone.tsx`

```typescript
const DropZone: React.FC<DropZoneProps> = ({ onDrop, uploading }) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    const audioFiles = files.filter(f =>
      f.type.startsWith('audio/') ||
      f.name.match(/\.(wav|mp3|flac|ogg|m4a)$/i)
    );

    audioFiles.forEach(onDrop);
  };

  return (
    <Box
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      sx={{
        border: `2px dashed ${isDragging ? '#667eea' : 'rgba(102, 126, 234, 0.3)'}`,
        borderRadius: '12px',
        p: 6,
        textAlign: 'center',
        background: isDragging ? 'rgba(102, 126, 234, 0.1)' : 'transparent',
        transition: 'all 0.3s ease',
        cursor: 'pointer'
      }}
    >
      {uploading ? (
        <LoadingSpinner size={64} />
      ) : (
        <>
          <CloudUpload sx={{ fontSize: 64, color: '#667eea', mb: 2 }} />
          <Typography variant="h6" className="gradient-text">
            Drop audio files here
          </Typography>
          <Typography variant="body2" sx={{ color: colors.text.secondary, mt: 1 }}>
            Supports WAV, MP3, FLAC, OGG, M4A
          </Typography>
        </>
      )}
    </Box>
  );
};
```

### Phase 4: Real-time Updates (Priority 2) 🔄

#### 4.1 Create WebSocket Hook
**New File**: `src/hooks/useWebSocketUpdates.ts`

```typescript
export const useWebSocketUpdates = () => {
  const { info, success, error } = useToast();
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');

    ws.onopen = () => {
      setConnected(true);
      console.log('WebSocket connected');
    };

    ws.onclose = () => {
      setConnected(false);
      console.log('WebSocket disconnected');
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      error('Lost connection to server');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'library_scan_progress':
          info(`Scanning: ${data.files_scanned} files...`);
          break;

        case 'library_scan_complete':
          success(`Scan complete: ${data.tracks_added} tracks added`);
          break;

        case 'processing_update':
          if (data.status === 'completed') {
            success(`Processing completed: ${data.filename}`);
          } else if (data.status === 'failed') {
            error(`Processing failed: ${data.error}`);
          }
          break;

        case 'player_update':
          // Player state updates handled by usePlayerAPI
          break;

        default:
          console.log('Unknown WebSocket message:', data);
      }
    };

    return () => ws.close();
  }, []);

  return { connected };
};
```

## Implementation Priority

### Phase 1: Core Functionality (Day 1)
1. ✅ Library API integration (CozyLibraryView)
2. ✅ Real folder scanning
3. ✅ Real track listing
4. ✅ Library statistics

**Time**: 2-3 hours
**Result**: Real music library working!

### Phase 2: Player Functionality (Day 1-2)
1. ✅ Player API integration (BottomPlayerBar)
2. ✅ Real audio playback
3. ✅ Queue management
4. ✅ WebSocket real-time updates

**Time**: 2-3 hours
**Result**: Real audio playback working!

### Phase 3: Processing Functionality (Day 2)
1. ✅ Processing API integration
2. ✅ File upload system
3. ✅ Drag & drop interface
4. ✅ Job management
5. ✅ Preset application

**Time**: 2-3 hours
**Result**: Real audio mastering working!

### Phase 4: Polish & Testing (Day 2-3)
1. ✅ Error handling
2. ✅ Loading states
3. ✅ Progress indicators
4. ✅ End-to-end testing

**Time**: 1-2 hours
**Result**: Production-ready application!

## File Structure After Integration

```
src/
├── hooks/
│   ├── usePlayerAPI.ts ← NEW (Player integration)
│   ├── useWebSocketUpdates.ts ← NEW (Real-time updates)
│   ├── useScrollAnimation.ts ✓
│   └── useWebSocket.ts ✓
├── components/
│   ├── processing/
│   │   ├── DropZone.tsx ← NEW (File upload)
│   │   ├── JobsList.tsx ← NEW (Processing jobs)
│   │   └── ProcessingInterface.tsx ← NEW (Main interface)
│   ├── library/
│   │   ├── LibraryStats.tsx ← NEW (Statistics)
│   │   ├── AlbumCard.tsx ✓
│   │   └── CozyLibraryView.tsx ← ENHANCED (Real data)
│   ├── player/
│   │   ├── TrackQueue.tsx ✓
│   │   └── BottomPlayerBar.tsx ← ENHANCED (Real playback)
│   └── PresetPane.tsx ← ENHANCED (Real presets)
└── services/
    ├── api.ts ← NEW (API client)
    └── websocket.ts ← NEW (WebSocket client)
```

## Expected Outcomes

After integration:
- ✅ **Real music library** from user's files
- ✅ **Real audio playback** with queue management
- ✅ **Real audio mastering** with 5 presets
- ✅ **Real-time updates** via WebSocket
- ✅ **File upload** with drag & drop
- ✅ **Processing jobs** with progress tracking
- ✅ **Download results** as mastered audio

## Testing Checklist

### Library Integration
- [ ] Load tracks from backend API
- [ ] Display real album art
- [ ] Scan folders for music
- [ ] Show library statistics
- [ ] Search functionality works

### Player Integration
- [ ] Play/pause works
- [ ] Next/previous track works
- [ ] Seek/scrubbing works
- [ ] Volume control works
- [ ] Queue updates in real-time

### Processing Integration
- [ ] Upload audio files
- [ ] Select preset and intensity
- [ ] Start processing job
- [ ] Monitor progress
- [ ] Download processed audio
- [ ] Error handling works

### Real-time Updates
- [ ] WebSocket connects successfully
- [ ] Library scan progress updates
- [ ] Processing job updates
- [ ] Player state syncs
- [ ] Reconnection on disconnect

## Success Criteria

- ✅ Can scan and load real music library
- ✅ Can play audio files from library
- ✅ Can upload and process audio files
- ✅ Can apply all 5 mastering presets
- ✅ Can download mastered audio
- ✅ Real-time updates work smoothly
- ✅ All UI components connected
- ✅ No console errors
- ✅ Professional user experience

---

**Ready to start Backend Integration!** 🚀

Let's begin with Phase 1: Library Integration!
