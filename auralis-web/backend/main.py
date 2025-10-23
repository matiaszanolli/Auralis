#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auralis Web Backend
~~~~~~~~~~~~~~~~~~

Modern FastAPI backend for Auralis audio processing and library management.
Replaces the Tkinter GUI with a professional web interface.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn
import asyncio
import json
import sys
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

# Import state management
from player_state import PlayerState, TrackInfo, create_track_info
from state_manager import PlayerStateManager
from proactive_buffer import buffer_presets_for_track

# Add parent directory to path for Auralis imports
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from auralis.library import LibraryManager
    from auralis.library.scanner import LibraryScanner
    from auralis.library.repositories.settings_repository import SettingsRepository
    from auralis.player.enhanced_audio_player import EnhancedAudioPlayer, PlaybackState
    from auralis.player.config import PlayerConfig
    from auralis.core.config import Config
    HAS_AURALIS = True
except ImportError as e:
    print(f"⚠️  Auralis library not available: {e}")
    HAS_AURALIS = False

# Import processing components
try:
    from processing_engine import ProcessingEngine
    from processing_api import router as processing_router, set_processing_engine
    from chunked_processor import ChunkedAudioProcessor
    HAS_PROCESSING = True
except ImportError as e:
    print(f"⚠️  Processing components not available: {e}")
    HAS_PROCESSING = False
    ChunkedAudioProcessor = None

# Import routers
from routers.system import create_system_router
from routers.files import create_files_router
from routers.enhancement import create_enhancement_router
from routers.artwork import create_artwork_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Auralis Web API",
    description="Modern web backend for Auralis audio processing",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include processing API routes
if HAS_PROCESSING:
    app.include_router(processing_router)

# Global state
library_manager: Optional[LibraryManager] = None
settings_repository: Optional[SettingsRepository] = None
audio_player: Optional[EnhancedAudioPlayer] = None
processing_cache: dict = {}  # Cache for processed audio files
player_state_manager: Optional[PlayerStateManager] = None
if HAS_PROCESSING:
    processing_engine: Optional[ProcessingEngine] = None
else:
    processing_engine = None
connected_websockets: List[WebSocket] = []

# Initialize Auralis components
@app.on_event("startup")
async def startup_event():
    """Initialize Auralis components on startup"""
    global library_manager, settings_repository, audio_player, processing_engine

    if HAS_AURALIS:
        try:
            library_manager = LibraryManager()
            logger.info("✅ Auralis LibraryManager initialized")

            # Initialize settings repository
            settings_repository = SettingsRepository(library_manager.SessionLocal)
            logger.info("✅ Settings Repository initialized")

            # Initialize enhanced audio player with optimized config
            player_config = PlayerConfig(
                buffer_size=1024,
                sample_rate=44100,
                enable_level_matching=True,
                enable_frequency_matching=False,
                enable_stereo_width=False,
                enable_auto_mastering=False,
                enable_advanced_smoothing=True,
                max_db_change_per_second=2.0
            )
            audio_player = EnhancedAudioPlayer(player_config)
            logger.info("✅ Enhanced Audio Player initialized")

            # Initialize state manager (must be after manager is created)
            global player_state_manager
            player_state_manager = PlayerStateManager(manager)
            logger.info("✅ Player State Manager initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Auralis components: {e}")
    else:
        logger.warning("⚠️  Auralis not available - running in demo mode")

    # Initialize processing engine
    if HAS_PROCESSING:
        try:
            processing_engine = ProcessingEngine(max_concurrent_jobs=2)
            set_processing_engine(processing_engine)
            # Start the processing worker
            asyncio.create_task(processing_engine.start_worker())
            logger.info("✅ Processing Engine initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Processing Engine: {e}")
    else:
        logger.warning("⚠️  Processing engine not available")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")

manager = ConnectionManager()

# Create and include system router (health, version, WebSocket)
system_router = create_system_router(
    manager=manager,
    get_library_manager=lambda: library_manager,
    get_processing_engine=lambda: processing_engine,
    HAS_AURALIS=HAS_AURALIS
)
app.include_router(system_router)

# Create and include files router (scan, upload, formats)
files_router = create_files_router(
    get_library_manager=lambda: library_manager,
    connection_manager=manager
)
app.include_router(files_router)

# Create and include enhancement router (toggle, preset, intensity, status)
enhancement_router = create_enhancement_router(
    get_enhancement_settings=lambda: enhancement_settings,
    connection_manager=manager
)
app.include_router(enhancement_router)

# Create and include artwork router (get, extract, delete)
artwork_router = create_artwork_router(
    get_library_manager=lambda: library_manager,
    connection_manager=manager
)
app.include_router(artwork_router)

# OLD WebSocket endpoint - KEEPING FOR NOW, WILL REMOVE AFTER TESTING
# TODO: Remove these old endpoints after verifying router works
@app.websocket("/ws_old")
async def websocket_endpoint_old(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif message.get("type") == "processing_settings_update":
                # Handle processing settings updates
                settings = message.get("data", {})
                logger.info(f"Processing settings updated: {settings}")

                # Broadcast to all connected clients
                await manager.broadcast({
                    "type": "processing_settings_applied",
                    "data": settings
                })

            elif message.get("type") == "ab_track_loaded":
                # Handle A/B comparison track loading
                track_data = message.get("data", {})
                logger.info(f"A/B track loaded: {track_data}")

                # Broadcast to all connected clients
                await manager.broadcast({
                    "type": "ab_track_ready",
                    "data": track_data
                })

            elif message.get("type") == "subscribe_job_progress":
                # Subscribe to job progress updates
                job_id = message.get("job_id")
                if job_id and processing_engine:
                    async def progress_callback(job_id, progress, message):
                        await websocket.send_text(json.dumps({
                            "type": "job_progress",
                            "data": {
                                "job_id": job_id,
                                "progress": progress,
                                "message": message
                            }
                        }))

                    processing_engine.register_progress_callback(job_id, progress_callback)

    except WebSocketDisconnect:
        manager.disconnect(websocket)

# API Routes
# OLD system endpoints - KEEPING FOR NOW, WILL REMOVE AFTER TESTING
# TODO: Remove these after verifying system router works

@app.get("/api/health_old")
async def health_check_old():
    """OLD Health check endpoint - use system router instead"""
    return {
        "status": "healthy",
        "auralis_available": HAS_AURALIS,
        "library_manager": library_manager is not None
    }

@app.get("/api/version_old")
async def get_version_old():
    """OLD Get version information - use system router instead"""
    try:
        from version import get_version_info
        return get_version_info()
    except ImportError:
        # Fallback if version module not available
        return {
            "api_version": "1.0.0",
            "api_version_info": {"major": 1, "minor": 0, "patch": 0},
            "db_schema_version": 1,
            "min_client_version": "1.0.0"
        }

@app.get("/api/library/stats")
async def get_library_stats():
    """Get library statistics"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        stats = library_manager.get_library_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")

@app.get("/api/library/tracks")
async def get_tracks(limit: int = 50, offset: int = 0, search: Optional[str] = None):
    """Get tracks from library"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        if search:
            tracks = library_manager.search_tracks(search, limit=limit)
        else:
            tracks = library_manager.get_recent_tracks(limit=limit)

        # Convert to dicts for JSON serialization
        tracks_data = []
        for track in tracks:
            if hasattr(track, 'to_dict'):
                tracks_data.append(track.to_dict())
            else:
                tracks_data.append({
                    'id': getattr(track, 'id', None),
                    'title': getattr(track, 'title', 'Unknown'),
                    'filepath': getattr(track, 'filepath', ''),
                    'duration': getattr(track, 'duration', 0),
                    'format': getattr(track, 'format', 'Unknown')
                })

        return {
            "tracks": tracks_data,
            "total": len(tracks_data),
            "offset": offset,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tracks: {e}")

@app.get("/api/library/tracks/favorites")
async def get_favorite_tracks(limit: int = 100):
    """Get all favorite tracks"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        tracks = library_manager.tracks.get_favorites(limit=limit)

        # Convert to dicts for JSON serialization
        tracks_data = []
        for track in tracks:
            if hasattr(track, 'to_dict'):
                tracks_data.append(track.to_dict())

        return {
            "tracks": tracks_data,
            "total": len(tracks_data)
        }
    except Exception as e:
        logger.error(f"Failed to get favorite tracks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get favorites: {e}")

@app.post("/api/library/tracks/{track_id}/favorite")
async def set_track_favorite(track_id: int):
    """Mark track as favorite"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        library_manager.tracks.set_favorite(track_id, True)
        logger.info(f"Track {track_id} marked as favorite")
        return {"message": "Track marked as favorite", "track_id": track_id, "favorite": True}
    except Exception as e:
        logger.error(f"Failed to set favorite: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set favorite: {e}")

@app.delete("/api/library/tracks/{track_id}/favorite")
async def remove_track_favorite(track_id: int):
    """Remove track from favorites"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        library_manager.tracks.set_favorite(track_id, False)
        logger.info(f"Track {track_id} removed from favorites")
        return {"message": "Track removed from favorites", "track_id": track_id, "favorite": False}
    except Exception as e:
        logger.error(f"Failed to remove favorite: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove favorite: {e}")

@app.get("/api/library/tracks/{track_id}/lyrics")
async def get_track_lyrics(track_id: int):
    """Get lyrics for a track"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        track = library_manager.tracks.get_by_id(track_id)
        if not track:
            raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

        # If lyrics exist in database, return them
        if track.lyrics:
            return {
                "track_id": track_id,
                "lyrics": track.lyrics,
                "format": "lrc" if "[" in track.lyrics and "]" in track.lyrics else "plain"
            }

        # If no lyrics in database, try to extract from file
        try:
            import mutagen
            audio_file = mutagen.File(track.filepath)

            lyrics_text = None

            # Try different lyrics tags
            if audio_file:
                # ID3 tags (MP3)
                if hasattr(audio_file, 'tags') and audio_file.tags:
                    # USLT frame (Unsynchronized lyrics)
                    if 'USLT::eng' in audio_file.tags:
                        lyrics_text = str(audio_file.tags['USLT::eng'])
                    elif 'USLT' in audio_file.tags:
                        lyrics_text = str(audio_file.tags['USLT'])
                    # Alternative text frame
                    elif 'LYRICS' in audio_file.tags:
                        lyrics_text = str(audio_file.tags['LYRICS'])

                # Vorbis comments (FLAC, OGG)
                elif hasattr(audio_file, 'get'):
                    lyrics_text = audio_file.get('LYRICS', [None])[0] or audio_file.get('UNSYNCEDLYRICS', [None])[0]

                # MP4/M4A tags
                elif hasattr(audio_file, '__getitem__'):
                    try:
                        lyrics_text = audio_file.get('\xa9lyr', [None])[0]
                    except:
                        pass

            if lyrics_text:
                # Save to database for future requests
                track.lyrics = lyrics_text
                library_manager.tracks.update(track)

                return {
                    "track_id": track_id,
                    "lyrics": lyrics_text,
                    "format": "lrc" if "[" in lyrics_text and "]" in lyrics_text else "plain"
                }

        except Exception as e:
            logger.error(f"Failed to extract lyrics from file: {e}")

        # No lyrics found
        return {
            "track_id": track_id,
            "lyrics": None,
            "format": None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get lyrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get lyrics: {e}")

@app.get("/api/library/artists")
async def get_artists():
    """Get all artists"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        artists = library_manager.artists.get_all()
        return {
            "artists": [artist.to_dict() for artist in artists],
            "total": len(artists)
        }
    except Exception as e:
        logger.error(f"Failed to get artists: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get artists: {e}")

@app.get("/api/library/artists/{artist_id}")
async def get_artist(artist_id: int):
    """Get artist details by ID with albums and tracks"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        artist = library_manager.artists.get_by_id(artist_id)
        if not artist:
            raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")

        return artist.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get artist {artist_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get artist: {e}")

@app.get("/api/library/albums")
async def get_albums():
    """Get all albums"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        albums = library_manager.albums.get_all()
        return {
            "albums": [album.to_dict() for album in albums],
            "total": len(albums)
        }
    except Exception as e:
        logger.error(f"Failed to get albums: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get albums: {e}")

@app.get("/api/library/albums/{album_id}")
async def get_album(album_id: int):
    """Get album details by ID with tracks"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        album = library_manager.albums.get_by_id(album_id)
        if not album:
            raise HTTPException(status_code=404, detail=f"Album {album_id} not found")

        return album.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get album {album_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get album: {e}")

# ============================================================================
# PLAYLIST MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/playlists")
async def get_playlists():
    """Get all playlists"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        playlists = library_manager.playlists.get_all()
        return {
            "playlists": [p.to_dict() for p in playlists],
            "total": len(playlists)
        }
    except Exception as e:
        logger.error(f"Failed to get playlists: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get playlists: {e}")

@app.get("/api/playlists/{playlist_id}")
async def get_playlist(playlist_id: int):
    """Get playlist by ID with all tracks"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        playlist = library_manager.playlists.get_by_id(playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        playlist_dict = playlist.to_dict()
        # Add full track details
        playlist_dict['tracks'] = [track.to_dict() for track in playlist.tracks]

        return playlist_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get playlist: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get playlist: {e}")

class CreatePlaylistRequest(BaseModel):
    name: str
    description: str = ""
    track_ids: List[int] = []

@app.post("/api/playlists")
async def create_playlist(request: CreatePlaylistRequest):
    """Create a new playlist"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        playlist = library_manager.playlists.create(
            name=request.name,
            description=request.description,
            track_ids=request.track_ids if request.track_ids else None
        )

        if not playlist:
            raise HTTPException(status_code=400, detail="Failed to create playlist")

        # Broadcast playlist created event
        await manager.broadcast({
            "type": "playlist_created",
            "data": {
                "playlist_id": playlist.id,
                "name": playlist.name
            }
        })

        return {
            "message": f"Playlist '{request.name}' created",
            "playlist": playlist.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create playlist: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create playlist: {e}")

class UpdatePlaylistRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

@app.put("/api/playlists/{playlist_id}")
async def update_playlist(playlist_id: int, request: UpdatePlaylistRequest):
    """Update playlist name or description"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        # Build update data dictionary
        update_data = {}
        if request.name is not None:
            update_data['name'] = request.name
        if request.description is not None:
            update_data['description'] = request.description

        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")

        success = library_manager.playlists.update(playlist_id, update_data)

        if not success:
            raise HTTPException(status_code=404, detail="Playlist not found or update failed")

        # Broadcast playlist updated event
        await manager.broadcast({
            "type": "playlist_updated",
            "data": {
                "playlist_id": playlist_id,
                "updates": update_data
            }
        })

        return {"message": "Playlist updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update playlist: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update playlist: {e}")

@app.delete("/api/playlists/{playlist_id}")
async def delete_playlist(playlist_id: int):
    """Delete a playlist"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        success = library_manager.playlists.delete(playlist_id)

        if not success:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Broadcast playlist deleted event
        await manager.broadcast({
            "type": "playlist_deleted",
            "data": {
                "playlist_id": playlist_id
            }
        })

        return {"message": "Playlist deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete playlist: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete playlist: {e}")

class AddTracksRequest(BaseModel):
    track_ids: List[int]

@app.post("/api/playlists/{playlist_id}/tracks")
async def add_tracks_to_playlist(playlist_id: int, request: AddTracksRequest):
    """Add tracks to playlist"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        added_count = 0
        for track_id in request.track_ids:
            if library_manager.playlists.add_track(playlist_id, track_id):
                added_count += 1

        if added_count == 0:
            raise HTTPException(status_code=400, detail="No tracks were added")

        # Broadcast playlist updated event
        await manager.broadcast({
            "type": "playlist_tracks_added",
            "data": {
                "playlist_id": playlist_id,
                "added_count": added_count
            }
        })

        return {
            "message": f"Added {added_count} track(s) to playlist",
            "added_count": added_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add tracks to playlist: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add tracks: {e}")

@app.delete("/api/playlists/{playlist_id}/tracks/{track_id}")
async def remove_track_from_playlist(playlist_id: int, track_id: int):
    """Remove a track from playlist"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        success = library_manager.playlists.remove_track(playlist_id, track_id)

        if not success:
            raise HTTPException(status_code=404, detail="Playlist or track not found")

        # Broadcast playlist updated event
        await manager.broadcast({
            "type": "playlist_track_removed",
            "data": {
                "playlist_id": playlist_id,
                "track_id": track_id
            }
        })

        return {"message": "Track removed from playlist"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove track from playlist: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove track: {e}")

@app.delete("/api/playlists/{playlist_id}/tracks")
async def clear_playlist(playlist_id: int):
    """Remove all tracks from playlist"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        success = library_manager.playlists.clear(playlist_id)

        if not success:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Broadcast playlist cleared event
        await manager.broadcast({
            "type": "playlist_cleared",
            "data": {
                "playlist_id": playlist_id
            }
        })

        return {"message": "Playlist cleared"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear playlist: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear playlist: {e}")

# ============================================================================
# END PLAYLIST ENDPOINTS
# ============================================================================

# ============================================================================
# ALBUM ARTWORK ENDPOINTS
# ============================================================================

@app.get("/api/albums/{album_id}/artwork_old")
async def get_album_artwork_old(album_id: int):
    """Get album artwork file"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        # Get album to find artwork path
        session = library_manager.get_session()
        try:
            from auralis.library.models import Album
            album = session.query(Album).filter(Album.id == album_id).first()

            if not album:
                raise HTTPException(status_code=404, detail="Album not found")

            if not album.artwork_path or not Path(album.artwork_path).exists():
                raise HTTPException(status_code=404, detail="Artwork not found")

            # Return artwork file
            from fastapi.responses import FileResponse
            return FileResponse(
                album.artwork_path,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "public, max-age=31536000",  # Cache for 1 year
                }
            )

        finally:
            session.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get artwork: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get artwork: {e}")


@app.post("/api/albums/{album_id}/artwork/extract_old")
async def extract_album_artwork_old(album_id: int):
    """Extract artwork from album tracks"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        artwork_path = library_manager.albums.extract_and_save_artwork(album_id)

        if not artwork_path:
            raise HTTPException(
                status_code=404,
                detail="No artwork found in album tracks"
            )

        # Broadcast artwork extracted event
        await manager.broadcast({
            "type": "artwork_extracted",
            "data": {
                "album_id": album_id,
                "artwork_path": artwork_path
            }
        })

        return {
            "message": "Artwork extracted successfully",
            "artwork_path": artwork_path,
            "album_id": album_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to extract artwork: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract artwork: {e}")


@app.delete("/api/albums/{album_id}/artwork_old")
async def delete_album_artwork_old(album_id: int):
    """Delete album artwork"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        success = library_manager.albums.delete_artwork(album_id)

        if not success:
            raise HTTPException(status_code=404, detail="Artwork not found")

        # Broadcast artwork deleted event
        await manager.broadcast({
            "type": "artwork_deleted",
            "data": {"album_id": album_id}
        })

        return {"message": "Artwork deleted successfully", "album_id": album_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete artwork: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete artwork: {e}")

# ============================================================================
# END ARTWORK ENDPOINTS
# ============================================================================

class ScanRequest(BaseModel):
    directory: str

@app.post("/api/library/scan_old")
async def scan_directory_old(request: ScanRequest):
    """Scan directory for audio files"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    directory = request.directory

    try:
        scanner = LibraryScanner(library_manager)

        # Start scan in background
        async def scan_worker():
            try:
                result = scanner.scan_single_directory(directory, recursive=True)

                # Broadcast scan completion to all connected clients
                await manager.broadcast({
                    "type": "scan_complete",
                    "data": {
                        "directory": directory,
                        "files_found": result.files_found,
                        "files_added": result.files_added,
                        "files_updated": result.files_updated,
                        "files_failed": result.files_failed,
                        "scan_time": result.scan_time
                    }
                })

            except Exception as e:
                await manager.broadcast({
                    "type": "scan_error",
                    "data": {"directory": directory, "error": str(e)}
                })

        # Start the scan
        asyncio.create_task(scan_worker())

        return {"message": f"Scan of {directory} started", "status": "scanning"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scan: {e}")

@app.post("/api/files/upload_old")
async def upload_files_old(files: List[UploadFile] = File(...)):
    """Upload audio files for processing"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    results = []
    for file in files:
        try:
            # Validate file type
            if not file.filename.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "message": "Unsupported file type"
                })
                continue

            # For now, just acknowledge the upload
            results.append({
                "filename": file.filename,
                "status": "success",
                "message": "File upload simulation - processing not yet implemented"
            })

        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "message": str(e)
            })

    return {"results": results}

@app.get("/api/audio/formats_old")
async def get_supported_formats_old():
    """Get supported audio formats"""
    return {
        "input_formats": [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"],
        "output_formats": [".wav", ".flac", ".mp3"],
        "sample_rates": [44100, 48000, 88200, 96000, 192000],
        "bit_depths": [16, 24, 32]
    }

# Enhanced Audio Player API Endpoints

@app.get("/api/player/status")
async def get_player_status():
    """Get current player status (single source of truth)"""
    if not player_state_manager:
        raise HTTPException(status_code=503, detail="Player not available")

    try:
        # Return current state from state manager
        state = player_state_manager.get_state()
        return state.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get player status: {e}")

@app.get("/api/player/stream/{track_id}")
async def stream_audio(
    track_id: int,
    enhanced: bool = False,
    preset: str = "adaptive",
    intensity: float = 1.0,
    background_tasks: BackgroundTasks = None
):
    """
    Stream audio file to frontend for playback via HTML5 Audio API

    Supports real-time audio enhancement with Auralis processing using
    chunked streaming for fast playback start.

    Args:
        track_id: Track ID from library
        enhanced: Enable Auralis processing (default: False)
        preset: Processing preset - adaptive, gentle, warm, bright, punchy (default: adaptive)
        intensity: Processing intensity 0.0-1.0 (default: 1.0)
        background_tasks: FastAPI background tasks for async chunk processing

    Performance:
        - Without enhancement: Streams original file immediately
        - With enhancement (chunked): Processes first 30s chunk (~1s), then streams
        - Background processes remaining chunks while user listens
    """
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library not available")

    try:
        # Get track from library
        track = library_manager.tracks.get_by_id(track_id)
        if not track:
            raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

        # Check if file exists
        if not os.path.exists(track.filepath):
            raise HTTPException(status_code=404, detail=f"Audio file not found: {track.filepath}")

        # If enhancement is requested, use chunked processing
        if enhanced:
            # Check if full processed file is cached
            cache_key = f"{track_id}_{preset}_{intensity}"
            cached_file = processing_cache.get(cache_key)

            if cached_file and os.path.exists(cached_file):
                logger.info(f"Serving cached enhanced audio for track {track_id}")
                file_to_serve = cached_file
            else:
                # Use chunked processing for fast start
                logger.info(f"Starting chunked processing for track {track_id} (preset: {preset}, intensity: {intensity})")

                try:
                    if ChunkedAudioProcessor is None:
                        raise ImportError("ChunkedAudioProcessor not available")

                    # Create chunked processor
                    processor = ChunkedAudioProcessor(
                        track_id=track_id,
                        filepath=track.filepath,
                        preset=preset,
                        intensity=intensity,
                        chunk_cache=processing_cache  # Share cache
                    )

                    # Check if we have a cached full file
                    full_path = processor.chunk_dir / f"track_{track_id}_{preset}_{intensity}_full.wav"

                    if full_path.exists():
                        # Fully processed file exists from previous playback
                        logger.info(f"Serving cached full processed file")
                        file_to_serve = str(full_path)
                    else:
                        # Process first chunk only (fast - ~1 second)
                        logger.info(f"Processing first chunk (0/{processor.total_chunks}) - this will be quick!")
                        first_chunk_path = processor.process_chunk(0)
                        logger.info(f"First chunk ready in ~1 second!")

                        # Start proactive buffering of first 3 chunks for ALL presets
                        # This enables instant preset switching with zero wait time
                        if background_tasks:
                            background_tasks.add_task(
                                buffer_presets_for_track,
                                track_id=track_id,
                                filepath=track.filepath,
                                intensity=intensity,
                                total_chunks=processor.total_chunks
                            )
                            logger.info(f"🚀 Proactive buffering started: 3 chunks × 5 presets")

                        # Start background processing of remaining chunks for current preset
                        if background_tasks:
                            background_tasks.add_task(processor.process_all_chunks_async)
                            logger.info(f"Background task started to process all {processor.total_chunks} chunks")

                        # For now, fall back to processing all chunks to create full file
                        # TODO: Implement true progressive streaming in future
                        logger.info(f"Creating full processed audio (all chunks)...")
                        file_to_serve = processor.get_full_processed_audio_path()

                        logger.info(f"Full audio ready at {file_to_serve}")

                    # Cache the full file
                    processing_cache[cache_key] = file_to_serve

                except Exception as process_error:
                    logger.error(f"Chunked processing failed: {process_error}")
                    # Fall back to original file
                    file_to_serve = track.filepath
        else:
            # No enhancement - serve original file
            file_to_serve = track.filepath

        # Determine MIME type based on file extension
        ext = os.path.splitext(file_to_serve)[1].lower()
        mime_types = {
            '.mp3': 'audio/mpeg',
            '.flac': 'audio/flac',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac'
        }
        media_type = mime_types.get(ext, 'audio/wav')

        # Return the audio file with proper headers for streaming
        return FileResponse(
            file_to_serve,
            media_type=media_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": f"inline; filename=\"{os.path.basename(file_to_serve)}\"",
                "X-Enhanced": "true" if enhanced else "false",
                "X-Preset": preset if enhanced else "none",
                "X-Chunked": "true" if (enhanced and ChunkedAudioProcessor) else "false"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream audio: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stream audio: {e}")

# ============================================================================
# ENHANCEMENT API ENDPOINTS
# ============================================================================

# Global enhancement state
enhancement_settings = {
    "enabled": False,
    "preset": "adaptive",
    "intensity": 1.0
}

@app.post("/api/player/enhancement/toggle_old")
async def toggle_enhancement_old(enabled: bool):
    """Enable or disable real-time audio enhancement"""
    try:
        enhancement_settings["enabled"] = enabled

        # Broadcast to all clients
        await manager.broadcast({
            "type": "enhancement_toggled",
            "data": {
                "enabled": enabled,
                "preset": enhancement_settings["preset"],
                "intensity": enhancement_settings["intensity"]
            }
        })

        logger.info(f"Enhancement {'enabled' if enabled else 'disabled'}")
        return {
            "message": f"Enhancement {'enabled' if enabled else 'disabled'}",
            "settings": enhancement_settings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle enhancement: {e}")

@app.post("/api/player/enhancement/preset_old")
async def set_enhancement_preset_old(preset: str):
    """Change the enhancement preset"""
    valid_presets = ["adaptive", "gentle", "warm", "bright", "punchy"]

    if preset.lower() not in valid_presets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid preset. Must be one of: {', '.join(valid_presets)}"
        )

    try:
        enhancement_settings["preset"] = preset.lower()

        # Broadcast to all clients
        await manager.broadcast({
            "type": "enhancement_preset_changed",
            "data": {
                "preset": preset.lower(),
                "enabled": enhancement_settings["enabled"],
                "intensity": enhancement_settings["intensity"]
            }
        })

        logger.info(f"Enhancement preset changed to: {preset}")
        return {
            "message": f"Preset changed to {preset}",
            "settings": enhancement_settings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to change preset: {e}")

@app.post("/api/player/enhancement/intensity_old")
async def set_enhancement_intensity_old(intensity: float):
    """Adjust the enhancement intensity (0.0 - 1.0)"""
    if not 0.0 <= intensity <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="Intensity must be between 0.0 and 1.0"
        )

    try:
        enhancement_settings["intensity"] = intensity

        # Broadcast to all clients
        await manager.broadcast({
            "type": "enhancement_intensity_changed",
            "data": {
                "intensity": intensity,
                "enabled": enhancement_settings["enabled"],
                "preset": enhancement_settings["preset"]
            }
        })

        logger.info(f"Enhancement intensity changed to: {intensity}")
        return {
            "message": f"Intensity set to {intensity}",
            "settings": enhancement_settings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set intensity: {e}")

@app.get("/api/player/enhancement/status_old")
async def get_enhancement_status_old():
    """Get current enhancement settings"""
    return enhancement_settings

# ============================================================================
# PLAYER CONTROL ENDPOINTS
# ============================================================================

@app.post("/api/player/load")
async def load_track(track_path: str):
    """Load a track into the player"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        # Add to queue and load
        audio_player.add_to_queue(track_path)
        success = audio_player.load_current_track() if hasattr(audio_player, 'load_current_track') else True

        if success:
            # Broadcast to all connected clients
            await manager.broadcast({
                "type": "track_loaded",
                "data": {"track_path": track_path}
            })
            return {"message": "Track loaded successfully", "track_path": track_path}
        else:
            raise HTTPException(status_code=400, detail="Failed to load track")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load track: {e}")

@app.post("/api/player/play")
async def play_audio():
    """Start playback (updates single source of truth)"""
    if not player_state_manager:
        raise HTTPException(status_code=503, detail="Player not available")
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        audio_player.play()

        # Update state (broadcasts automatically)
        await player_state_manager.set_playing(True)

        return {"message": "Playback started", "state": "playing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start playback: {e}")

@app.post("/api/player/pause")
async def pause_audio():
    """Pause playback (updates single source of truth)"""
    if not player_state_manager:
        raise HTTPException(status_code=503, detail="Player not available")
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        audio_player.pause()

        # Update state (broadcasts automatically)
        await player_state_manager.set_playing(False)

        return {"message": "Playback paused", "state": "paused"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause playback: {e}")

@app.post("/api/player/stop")
async def stop_audio():
    """Stop playback"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        audio_player.stop()

        # Broadcast to all connected clients
        await manager.broadcast({
            "type": "playback_stopped",
            "data": {"state": "stopped"}
        })

        return {"message": "Playback stopped", "state": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop playback: {e}")

@app.post("/api/player/seek")
async def seek_position(position: float):
    """Seek to position in seconds"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'seek_to_position'):
            audio_player.seek_to_position(position)

        # Broadcast to all connected clients
        await manager.broadcast({
            "type": "position_changed",
            "data": {"position": position}
        })

        return {"message": "Position updated", "position": position}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to seek: {e}")

@app.post("/api/player/volume")
async def set_volume(volume: float):
    """Set playback volume (0.0 to 1.0)"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        # Clamp volume to valid range
        volume = max(0.0, min(1.0, volume))

        if hasattr(audio_player, 'set_volume'):
            audio_player.set_volume(volume)

        # Broadcast to all connected clients
        await manager.broadcast({
            "type": "volume_changed",
            "data": {"volume": volume}
        })

        return {"message": "Volume updated", "volume": volume}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set volume: {e}")

@app.get("/api/player/queue")
async def get_queue():
    """Get current playback queue"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'queue_manager'):
            queue_info = audio_player.queue_manager.get_queue_info() if hasattr(audio_player.queue_manager, 'get_queue_info') else {
                "tracks": list(audio_player.queue_manager.queue),
                "current_index": audio_player.queue_manager.current_index,
                "total_tracks": len(audio_player.queue_manager.queue)
            }
            return queue_info
        else:
            return {"tracks": [], "current_index": 0, "total_tracks": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get queue: {e}")

class SetQueueRequest(BaseModel):
    tracks: List[int]  # Track IDs
    start_index: int = 0

@app.post("/api/player/queue")
async def set_queue(request: SetQueueRequest):
    """Set the playback queue (updates single source of truth)"""
    if not player_state_manager:
        raise HTTPException(status_code=503, detail="Player not available")
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        # Get tracks from library by IDs
        db_tracks = []
        for track_id in request.tracks:
            track = library_manager.tracks.get_by_id(track_id)
            if track:
                db_tracks.append(track)

        if not db_tracks:
            raise HTTPException(status_code=400, detail="No valid tracks found")

        # Convert to TrackInfo for state
        track_infos = [create_track_info(t) for t in db_tracks]
        track_infos = [t for t in track_infos if t is not None]

        # Update state manager (this broadcasts automatically)
        await player_state_manager.set_queue(track_infos, request.start_index)

        # Set queue in actual player
        if hasattr(audio_player, 'queue_manager'):
            audio_player.queue_manager.set_queue([t.filepath for t in db_tracks], request.start_index)

        # Load and start playing if requested
        if request.start_index >= 0 and request.start_index < len(db_tracks):
            current_track = db_tracks[request.start_index]

            # Update state with current track
            await player_state_manager.set_track(current_track, library_manager)

            # Load the track in player
            audio_player.load_file(current_track.filepath)

            # Start playback
            audio_player.play()

            # Update playing state
            await player_state_manager.set_playing(True)

        return {
            "message": "Queue set successfully",
            "track_count": len(track_infos),
            "start_index": request.start_index
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set queue: {e}")

@app.post("/api/player/queue/add")
async def add_to_queue(track_path: str):
    """Add track to playback queue"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        audio_player.add_to_queue(track_path)

        # Broadcast queue update
        await manager.broadcast({
            "type": "queue_updated",
            "data": {"action": "added", "track_path": track_path}
        })

        return {"message": "Track added to queue", "track_path": track_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add to queue: {e}")

@app.delete("/api/player/queue/{index}")
async def remove_from_queue(index: int):
    """Remove track from queue at specified index"""
    if not player_state_manager:
        raise HTTPException(status_code=503, detail="Player not available")
    if not audio_player or not hasattr(audio_player, 'queue_manager'):
        raise HTTPException(status_code=503, detail="Queue manager not available")

    try:
        queue_manager = audio_player.queue_manager

        # Validate index
        if index < 0 or index >= queue_manager.get_queue_size():
            raise HTTPException(status_code=400, detail=f"Invalid index: {index}")

        # Remove track from queue
        success = queue_manager.remove_track(index)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to remove track")

        # Get updated queue
        updated_queue = queue_manager.get_queue()

        # Broadcast queue update
        await manager.broadcast({
            "type": "queue_updated",
            "data": {
                "action": "removed",
                "index": index,
                "queue_size": len(updated_queue)
            }
        })

        return {
            "message": "Track removed from queue",
            "index": index,
            "queue_size": len(updated_queue)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove from queue: {e}")

class ReorderQueueRequest(BaseModel):
    new_order: List[int]  # New order of track indices

@app.put("/api/player/queue/reorder")
async def reorder_queue(request: ReorderQueueRequest):
    """Reorder the playback queue"""
    if not player_state_manager:
        raise HTTPException(status_code=503, detail="Player not available")
    if not audio_player or not hasattr(audio_player, 'queue_manager'):
        raise HTTPException(status_code=503, detail="Queue manager not available")

    try:
        queue_manager = audio_player.queue_manager

        # Validate new_order
        queue_size = queue_manager.get_queue_size()
        if len(request.new_order) != queue_size:
            raise HTTPException(
                status_code=400,
                detail=f"new_order length ({len(request.new_order)}) must match queue size ({queue_size})"
            )

        if set(request.new_order) != set(range(queue_size)):
            raise HTTPException(
                status_code=400,
                detail="new_order must contain all indices from 0 to queue_size-1 exactly once"
            )

        # Reorder queue
        success = queue_manager.reorder_tracks(request.new_order)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to reorder queue")

        # Get updated queue
        updated_queue = queue_manager.get_queue()

        # Broadcast queue update
        await manager.broadcast({
            "type": "queue_updated",
            "data": {
                "action": "reordered",
                "queue_size": len(updated_queue)
            }
        })

        return {
            "message": "Queue reordered successfully",
            "queue_size": len(updated_queue)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reorder queue: {e}")

@app.post("/api/player/queue/clear")
async def clear_queue():
    """Clear the entire playback queue"""
    if not player_state_manager:
        raise HTTPException(status_code=503, detail="Player not available")
    if not audio_player or not hasattr(audio_player, 'queue_manager'):
        raise HTTPException(status_code=503, detail="Queue manager not available")

    try:
        queue_manager = audio_player.queue_manager

        # Clear queue
        queue_manager.clear()

        # Stop playback
        if hasattr(audio_player, 'stop'):
            audio_player.stop()

        # Update player state
        await player_state_manager.set_playing(False)
        await player_state_manager.set_track(None, None)

        # Broadcast queue update
        await manager.broadcast({
            "type": "queue_updated",
            "data": {
                "action": "cleared",
                "queue_size": 0
            }
        })

        return {"message": "Queue cleared successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear queue: {e}")

@app.post("/api/player/queue/shuffle")
async def shuffle_queue():
    """Shuffle the playback queue (keeps current track in place)"""
    if not player_state_manager:
        raise HTTPException(status_code=503, detail="Player not available")
    if not audio_player or not hasattr(audio_player, 'queue_manager'):
        raise HTTPException(status_code=503, detail="Queue manager not available")

    try:
        queue_manager = audio_player.queue_manager

        # Shuffle queue
        queue_manager.shuffle()

        # Get updated queue
        updated_queue = queue_manager.get_queue()

        # Broadcast queue update
        await manager.broadcast({
            "type": "queue_updated",
            "data": {
                "action": "shuffled",
                "queue_size": len(updated_queue)
            }
        })

        return {
            "message": "Queue shuffled successfully",
            "queue_size": len(updated_queue)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to shuffle queue: {e}")

@app.post("/api/player/next")
async def next_track():
    """Skip to next track"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'next_track'):
            success = audio_player.next_track()
            if success:
                await manager.broadcast({
                    "type": "track_changed",
                    "data": {"action": "next"}
                })
                return {"message": "Skipped to next track"}
            else:
                return {"message": "No next track available"}
        else:
            return {"message": "Next track function not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to skip track: {e}")

@app.post("/api/player/previous")
async def previous_track():
    """Skip to previous track"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'previous_track'):
            success = audio_player.previous_track()
            if success:
                await manager.broadcast({
                    "type": "track_changed",
                    "data": {"action": "previous"}
                })
                return {"message": "Skipped to previous track"}
            else:
                return {"message": "No previous track available"}
        else:
            return {"message": "Previous track function not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to skip track: {e}")

# Audio Processing Control Endpoints

@app.post("/api/processing/enable_matching")
async def enable_level_matching(enabled: bool):
    """Enable/disable real-time level matching"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'config'):
            audio_player.config.enable_level_matching = enabled

        await manager.broadcast({
            "type": "processing_changed",
            "data": {"level_matching": enabled}
        })

        return {"message": f"Level matching {'enabled' if enabled else 'disabled'}", "enabled": enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle level matching: {e}")

@app.post("/api/processing/load_reference")
async def load_reference_track(reference_path: str):
    """Load reference track for level matching"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'load_reference'):
            success = audio_player.load_reference(reference_path)
            if success:
                await manager.broadcast({
                    "type": "reference_loaded",
                    "data": {"reference_path": reference_path}
                })
                return {"message": "Reference track loaded", "reference_path": reference_path}
            else:
                raise HTTPException(status_code=400, detail="Failed to load reference track")
        else:
            return {"message": "Reference loading not supported"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load reference: {e}")

@app.post("/api/processing/apply_preset")
async def apply_processing_preset(preset_name: str, settings: dict):
    """Apply a processing preset"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        logger.info(f"Applying preset '{preset_name}' with settings: {settings}")

        # Store the preset settings (in a real implementation, this would apply to the audio processing)
        # For now, we'll just broadcast the settings
        await manager.broadcast({
            "type": "preset_applied",
            "data": {
                "preset_name": preset_name,
                "settings": settings
            }
        })

        return {"message": f"Preset '{preset_name}' applied successfully", "settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply preset: {e}")

@app.get("/api/processing/analysis")
async def get_audio_analysis():
    """Get real-time audio analysis data"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        # Mock analysis data for now
        analysis = {
            "peak_level": 0.7 + (0.3 * __import__('random').random()),
            "rms_level": 0.4 + (0.2 * __import__('random').random()),
            "frequency_spectrum": [
                0.1 + (0.6 * __import__('random').random()) for _ in range(64)
            ],
            "dynamic_range": 12.5,
            "lufs": -16.2
        }

        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analysis: {e}")

@app.post("/api/comparison/load_tracks")
async def load_comparison_tracks(track_a: str, track_b: str):
    """Load tracks for A/B comparison"""
    try:
        # This would load both tracks into separate players
        # For now, we'll simulate the loading
        await manager.broadcast({
            "type": "comparison_tracks_loaded",
            "data": {
                "track_a": track_a,
                "track_b": track_b,
                "ready": True
            }
        })

        return {
            "message": "A/B comparison tracks loaded",
            "track_a": track_a,
            "track_b": track_b
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load comparison tracks: {e}")


# ========================================
# SETTINGS API ENDPOINTS
# ========================================

@app.get("/api/settings")
async def get_settings():
    """Get current user settings"""
    if not settings_repository:
        raise HTTPException(status_code=503, detail="Settings not available")

    try:
        settings = settings_repository.get_settings()
        return settings.to_dict()
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {e}")


class SettingsUpdate(BaseModel):
    """Pydantic model for settings updates"""
    # Library
    scan_folders: Optional[List[str]] = None
    file_types: Optional[List[str]] = None
    auto_scan: Optional[bool] = None
    scan_interval: Optional[int] = None

    # Playback
    crossfade_enabled: Optional[bool] = None
    crossfade_duration: Optional[float] = None
    gapless_enabled: Optional[bool] = None
    replay_gain_enabled: Optional[bool] = None
    volume: Optional[float] = None

    # Audio
    output_device: Optional[str] = None
    bit_depth: Optional[int] = None
    sample_rate: Optional[int] = None

    # Interface
    theme: Optional[str] = None
    language: Optional[str] = None
    show_visualizations: Optional[bool] = None
    mini_player_on_close: Optional[bool] = None

    # Enhancement
    default_preset: Optional[str] = None
    auto_enhance: Optional[bool] = None
    enhancement_intensity: Optional[float] = None

    # Advanced
    cache_size: Optional[int] = None
    max_concurrent_scans: Optional[int] = None
    enable_analytics: Optional[bool] = None
    debug_mode: Optional[bool] = None


@app.put("/api/settings")
async def update_settings(updates: SettingsUpdate):
    """Update user settings"""
    if not settings_repository:
        raise HTTPException(status_code=503, detail="Settings not available")

    try:
        # Convert to dictionary and remove None values
        updates_dict = {k: v for k, v in updates.dict().items() if v is not None}

        # Update settings
        settings = settings_repository.update_settings(updates_dict)

        # Broadcast settings changed event
        await manager.broadcast({
            "type": "settings_changed",
            "data": settings.to_dict()
        })

        return {
            "message": "Settings updated successfully",
            "settings": settings.to_dict()
        }
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {e}")


@app.post("/api/settings/reset")
async def reset_settings():
    """Reset all settings to defaults"""
    if not settings_repository:
        raise HTTPException(status_code=503, detail="Settings not available")

    try:
        settings = settings_repository.reset_to_defaults()

        # Broadcast settings reset event
        await manager.broadcast({
            "type": "settings_reset",
            "data": settings.to_dict()
        })

        return {
            "message": "Settings reset to defaults",
            "settings": settings.to_dict()
        }
    except Exception as e:
        logger.error(f"Failed to reset settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {e}")


class ScanFolderRequest(BaseModel):
    """Request to add a scan folder"""
    folder: str


@app.post("/api/settings/scan-folders")
async def add_scan_folder(request: ScanFolderRequest):
    """Add a new folder to scan list"""
    if not settings_repository:
        raise HTTPException(status_code=503, detail="Settings not available")

    try:
        settings = settings_repository.add_scan_folder(request.folder)

        await manager.broadcast({
            "type": "scan_folder_added",
            "data": {"folder": request.folder}
        })

        return {
            "message": f"Added scan folder: {request.folder}",
            "settings": settings.to_dict()
        }
    except Exception as e:
        logger.error(f"Failed to add scan folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add scan folder: {e}")


@app.delete("/api/settings/scan-folders")
async def remove_scan_folder(request: ScanFolderRequest):
    """Remove a folder from scan list"""
    if not settings_repository:
        raise HTTPException(status_code=503, detail="Settings not available")

    try:
        settings = settings_repository.remove_scan_folder(request.folder)

        await manager.broadcast({
            "type": "scan_folder_removed",
            "data": {"folder": request.folder}
        })

        return {
            "message": f"Removed scan folder: {request.folder}",
            "settings": settings.to_dict()
        }
    except Exception as e:
        logger.error(f"Failed to remove scan folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove scan folder: {e}")


# Serve React frontend (when built)
# Check if running from PyInstaller bundle
if hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle - frontend is bundled in _MEIPASS/frontend
    frontend_path = Path(sys._MEIPASS) / "frontend"
    logger.info(f"PyInstaller mode: _MEIPASS={sys._MEIPASS}")
else:
    # Development mode - look in regular location
    frontend_path = Path(__file__).parent.parent / "frontend" / "build"

logger.info(f"Looking for frontend at: {frontend_path}")
if frontend_path.exists():
    logger.info(f"✅ Serving frontend from: {frontend_path}")
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
else:
    logger.warning(f"⚠️  Frontend not found at {frontend_path}")
    @app.get("/")
    async def root():
        return HTMLResponse(f"""
        <html>
            <head><title>Auralis Web</title></head>
            <body>
                <h1>🎵 Auralis Web Backend</h1>
                <p>FastAPI backend is running!</p>
                <p>Frontend not found at: {frontend_path}</p>
                <p><a href="/api/docs">View API Documentation</a></p>
            </body>
        </html>
        """)

if __name__ == "__main__":
    print("🚀 Starting Auralis Web Backend...")
    print("Backend ready", flush=True)  # Signal to Electron that backend is ready

    # Detect if running in PyInstaller bundle (production mode)
    import sys
    is_bundled = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

    uvicorn.run(
        app,  # Pass app directly instead of "main:app" to avoid module duplication
        host="127.0.0.1",
        port=8765,
        log_level="info"
    )