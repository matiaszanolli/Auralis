# 🎵 Auralis Web - Modern Cross-Platform Audio Interface

A beautiful, responsive web-based interface for Auralis audio processing and library management. This replaces the old Tkinter GUI with a modern, professional, cross-platform solution.

## ✨ Features

- **🌐 Cross-Platform**: Works on Windows, Mac, Linux, iOS, Android, and any web browser
- **🎨 Modern UI**: Beautiful Material Design interface with dark theme
- **📱 Responsive**: Optimized for desktop, tablet, and mobile devices
- **⚡ Real-time**: WebSocket connections for live updates and notifications
- **🔍 Advanced Search**: Powerful search and filtering capabilities
- **📊 Audio Visualization**: Professional audio meters and waveform displays
- **🎵 Library Management**: Intuitive file browser with grid and list views
- **🚀 Progressive Web App**: Can be installed like a native app

## 🏗️ Architecture

```
┌─────────────────────┐    HTTP/WebSocket    ┌──────────────────┐
│   React Frontend    │ ←──────────────────→ │   FastAPI Backend│
│   - TypeScript      │                      │   - Python 3.8+  │
│   - Material-UI     │                      │   - Auralis Core  │
│   - Audio Components│                      │   - Library DB    │
└─────────────────────┘                      └──────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** (for backend)
- **Node.js 16+** (for frontend)
- **Existing Auralis installation**

### 1. Backend Setup

```bash
# Navigate to backend directory
cd auralis-web/backend

# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI server
python main.py
```

The backend will be available at: `http://localhost:8000`

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd auralis-web/frontend

# Install Node.js dependencies
npm install

# Start the React development server
npm start
```

The frontend will be available at: `http://localhost:3000`

### 3. Access the Application

Open your browser and navigate to: **http://localhost:3000**

## 📖 Usage Guide

### 🔍 Library Management

1. **Scan Directories**: Click the "📁 Scan Library" button or the floating action button
2. **Search Tracks**: Use the search bar to find tracks, artists, or albums
3. **Browse Library**: Navigate through your music collection with the modern interface
4. **Real-time Updates**: Watch as scans complete and new tracks appear automatically

### 🎵 Audio Playback

- **Play/Pause**: Click the play button on any track or use the main player controls
- **Volume Control**: Adjust volume with the slider in the audio player
- **Progress**: Seek through tracks using the progress bar

### 📱 Mobile Experience

The interface is fully responsive and works great on mobile devices:
- **Touch-friendly**: Large touch targets and intuitive gestures
- **Responsive Layout**: Adapts to different screen sizes
- **Mobile Navigation**: Collapsible sidebar for mobile viewing

## 🔧 Development

### Backend Development

```bash
# Start with auto-reload for development
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend Development

```bash
# Start with hot reloading
cd frontend
npm start
```

### API Documentation

When the backend is running, visit:
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

## 🌐 Production Deployment

### Build Frontend

```bash
cd frontend
npm run build
```

### Start Production Server

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

The built frontend will be served from the backend at `http://localhost:8000`

## 📚 API Endpoints

### Library Management
- `GET /api/library/stats` - Get library statistics
- `GET /api/library/tracks` - List tracks with search support
- `POST /api/library/scan` - Scan directory for audio files

### Audio Processing
- `POST /api/files/upload` - Upload audio files
- `GET /api/audio/formats` - Get supported formats

### Real-time Updates
- `WebSocket /ws` - Real-time notifications and updates

## 🎨 Customization

### Themes

The interface uses Material-UI with a professional dark theme optimized for audio work. You can customize colors, typography, and components in:

- `frontend/src/index.tsx` - Main theme configuration
- `frontend/src/index.css` - Custom CSS styles

### Components

All React components are located in `frontend/src/components/`:
- `LibraryView.tsx` - Main library browser
- `AudioPlayer.tsx` - Bottom audio player
- `StatusBar.tsx` - Status and connection info

## 🔌 Integration

### Existing Auralis Integration

The web interface integrates seamlessly with existing Auralis components:

```python
# Backend automatically imports existing Auralis modules
from auralis.library import LibraryManager
from auralis.library.scanner import LibraryScanner
```

### WebSocket Events

Real-time events for UI updates:
- `scan_complete` - Directory scan finished
- `scan_error` - Scan failed
- `track_added` - New track added to library

## 🚀 Future Enhancements

- **Audio Visualization**: Real-time spectrum analyzers and waveform displays
- **Advanced Audio Processing**: Web-based mastering controls
- **Playlist Management**: Drag-and-drop playlist creation
- **Cloud Sync**: Sync libraries across devices
- **Mobile App**: Native mobile app using the same backend

## 🐛 Troubleshooting

### Backend Issues
- **Import Errors**: Ensure Auralis is properly installed
- **Port Conflicts**: Change port in `main.py` if 8000 is in use
- **Database Issues**: Check SQLite database permissions

### Frontend Issues
- **Build Errors**: Delete `node_modules` and run `npm install`
- **Connection Issues**: Verify backend is running on port 8000
- **Proxy Errors**: Check proxy configuration in `package.json`

## 📄 License

GPLv3 - See LICENSE file for details

---

## 🎉 Welcome to the Future of Auralis!

This modern web interface represents a significant upgrade from the previous Tkinter implementation, providing:

- **Better User Experience**: Intuitive, responsive design
- **Cross-Platform Support**: Works everywhere
- **Professional Appearance**: Suitable for professional audio work
- **Extensibility**: Easy to add new features and components
- **Modern Technology Stack**: Built with current web standards

Enjoy your enhanced Auralis experience! 🎵