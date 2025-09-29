# Processing API Integration Instructions

## Overview
The audio processing API has been created in `processing_api.py` and `processing_engine.py`. To integrate it into the existing backend, follow these steps:

## Step 1: Add imports to main.py

Add these imports after the existing auralis imports (around line 40):

```python
# Import processing components
try:
    from processing_engine import ProcessingEngine
    from processing_api import router as processing_router, set_processing_engine
    HAS_PROCESSING = True
except ImportError as e:
    print(f"⚠️  Processing components not available: {e}")
    HAS_PROCESSING = False
```

## Step 2: Add processing_engine to global state

Change line 64-66 from:

```python
# Global state
library_manager: Optional[LibraryManager] = None
audio_player: Optional[EnhancedAudioPlayer] = None
connected_websockets: List[WebSocket] = []
```

To:

```python
# Global state
library_manager: Optional[LibraryManager] = None
audio_player: Optional[EnhancedAudioPlayer] = None
processing_engine: Optional[ProcessingEngine] = None
connected_websockets: List[WebSocket] = []
```

## Step 3: Initialize processing engine in startup_event

Add this code at the end of the `startup_event()` function (after line 97):

```python
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
```

## Step 4: Include the processing router

Add this line after the app is created (around line 61, after the CORS middleware):

```python
# Include processing API routes
if HAS_PROCESSING:
    app.include_router(processing_router)
```

## Step 5: Add WebSocket support for processing progress

In the `websocket_endpoint` function (around line 125), add a new message type handler:

```python
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
```

## Available Endpoints

After integration, the following endpoints will be available:

### Processing

- `POST /api/processing/process` - Submit audio for processing
- `POST /api/processing/upload-and-process` - Upload and process in one request
- `GET /api/processing/job/{job_id}` - Get job status
- `GET /api/processing/job/{job_id}/download` - Download processed file
- `POST /api/processing/job/{job_id}/cancel` - Cancel a job
- `GET /api/processing/jobs` - List all jobs
- `GET /api/processing/queue/status` - Get queue status
- `GET /api/processing/presets` - Get available presets
- `DELETE /api/processing/jobs/cleanup` - Clean up old jobs

## Testing

After integration, test the API:

```bash
# Start the backend
cd auralis-web/backend
python main.py

# In another terminal, test the presets endpoint
curl http://localhost:8000/api/processing/presets

# Check queue status
curl http://localhost:8000/api/processing/queue/status
```

## WebSocket Messages

The processing system will send these WebSocket messages:

```json
{
  "type": "job_progress",
  "data": {
    "job_id": "uuid",
    "progress": 0-100,
    "message": "Processing audio..."
  }
}
```

Clients should subscribe to job progress:

```json
{
  "type": "subscribe_job_progress",
  "job_id": "uuid"
}
```