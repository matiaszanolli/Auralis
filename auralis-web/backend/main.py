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

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

# Add parent directory to path for Auralis imports
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from auralis.library import LibraryManager
    from auralis.library.scanner import LibraryScanner
    HAS_AURALIS = True
except ImportError as e:
    print(f"⚠️  Auralis library not available: {e}")
    HAS_AURALIS = False

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

# Global state
library_manager: Optional[LibraryManager] = None
connected_websockets: List[WebSocket] = []

# Initialize Auralis components
@app.on_event("startup")
async def startup_event():
    """Initialize Auralis components on startup"""
    global library_manager

    if HAS_AURALIS:
        try:
            library_manager = LibraryManager()
            logger.info("✅ Auralis LibraryManager initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize LibraryManager: {e}")
    else:
        logger.warning("⚠️  Auralis not available - running in demo mode")

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

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        manager.disconnect(websocket)

# API Routes

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "auralis_available": HAS_AURALIS,
        "library_manager": library_manager is not None
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

@app.get("/api/library/artists")
async def get_artists():
    """Get all artists"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        # This would need to be implemented in the library manager
        return {"artists": [], "message": "Artist listing not yet implemented"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get artists: {e}")

@app.post("/api/library/scan")
async def scan_directory(directory: str):
    """Scan directory for audio files"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

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

@app.post("/api/files/upload")
async def upload_files(files: List[UploadFile] = File(...)):
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

@app.get("/api/audio/formats")
async def get_supported_formats():
    """Get supported audio formats"""
    return {
        "input_formats": [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"],
        "output_formats": [".wav", ".flac", ".mp3"],
        "sample_rates": [44100, 48000, 88200, 96000, 192000],
        "bit_depths": [16, 24, 32]
    }

# Serve React frontend (when built)
frontend_path = Path(__file__).parent.parent / "frontend" / "build"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return HTMLResponse("""
        <html>
            <head><title>Auralis Web</title></head>
            <body>
                <h1>🎵 Auralis Web Backend</h1>
                <p>FastAPI backend is running!</p>
                <p>Frontend not built yet. Build the React app to see the full interface.</p>
                <p><a href="/api/docs">View API Documentation</a></p>
            </body>
        </html>
        """)

if __name__ == "__main__":
    print("🚀 Starting Auralis Web Backend...")
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )