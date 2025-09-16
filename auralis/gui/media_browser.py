#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced Media Browser
~~~~~~~~~~~~~~~~~~~~~

Professional media library browsing interface with hierarchical organization,
advanced search, playlist management, and metadata visualization.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
import threading
import time
from datetime import datetime, timedelta

try:
    import tkinterdnd2 as tkdnd
    HAS_DND = True
except ImportError:
    HAS_DND = False


class ViewMode:
    """View mode constants"""
    ARTISTS = "artists"
    ALBUMS = "albums"
    TRACKS = "tracks"
    GENRES = "genres"
    PLAYLISTS = "playlists"


class SortOrder:
    """Sort order constants"""
    TITLE_ASC = "title_asc"
    TITLE_DESC = "title_desc"
    ARTIST_ASC = "artist_asc"
    ARTIST_DESC = "artist_desc"
    ALBUM_ASC = "album_asc"
    ALBUM_DESC = "album_desc"
    YEAR_ASC = "year_asc"
    YEAR_DESC = "year_desc"
    DURATION_ASC = "duration_asc"
    DURATION_DESC = "duration_desc"
    PLAYS_ASC = "plays_asc"
    PLAYS_DESC = "plays_desc"
    QUALITY_ASC = "quality_asc"
    QUALITY_DESC = "quality_desc"


class MediaBrowserHeader(ctk.CTkFrame):
    """Header with view controls, search, and navigation"""

    def __init__(self, master, callback_manager=None, **kwargs):
        super().__init__(master, **kwargs)
        self.callback_manager = callback_manager
        self.current_view = ViewMode.ARTISTS

        self.setup_ui()

    def setup_ui(self):
        """Setup header UI components"""
        # Left side - Navigation and view controls
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.pack(side="left", fill="y", padx=(10, 5))

        # View mode buttons
        view_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        view_frame.pack(side="top", fill="x", pady=(5, 10))

        ctk.CTkLabel(view_frame, text="📚 Library View:",
                    font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        # View mode selection
        self.view_buttons = {}
        view_modes = [
            (ViewMode.ARTISTS, "👤 Artists"),
            (ViewMode.ALBUMS, "💿 Albums"),
            (ViewMode.TRACKS, "🎵 Songs"),
            (ViewMode.GENRES, "🎭 Genres"),
            (ViewMode.PLAYLISTS, "📋 Playlists")
        ]

        for mode, label in view_modes:
            btn = ctk.CTkButton(
                view_frame, text=label, width=80, height=28,
                command=lambda m=mode: self._change_view(m)
            )
            btn.pack(side="left", padx=2)
            self.view_buttons[mode] = btn

        # Breadcrumb navigation
        self.breadcrumb_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        self.breadcrumb_frame.pack(side="top", fill="x")

        self.breadcrumb_label = ctk.CTkLabel(
            self.breadcrumb_frame, text="🏠 Library",
            font=ctk.CTkFont(size=12), text_color="#888888"
        )
        self.breadcrumb_label.pack(side="left")

        # Right side - Search and controls
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.pack(side="right", fill="y", padx=(5, 10))

        # Search section
        search_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        search_frame.pack(side="top", fill="x", pady=(5, 5))

        self.search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="🔍 Search library...",
            width=250, height=32
        )
        self.search_entry.pack(side="left", padx=(0, 5))
        self.search_entry.bind('<KeyRelease>', self._on_search)

        # Advanced search button
        self.advanced_search_btn = ctk.CTkButton(
            search_frame, text="⚙️", width=32, height=32,
            command=self._show_advanced_search
        )
        self.advanced_search_btn.pack(side="left")

        # Control buttons
        controls_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        controls_frame.pack(side="top", fill="x", pady=(5, 5))

        # Sort dropdown
        ctk.CTkLabel(controls_frame, text="Sort:").pack(side="left", padx=(0, 5))

        self.sort_var = ctk.StringVar(value="Title A-Z")
        self.sort_menu = ctk.CTkOptionMenu(
            controls_frame, variable=self.sort_var, width=120,
            values=["Title A-Z", "Title Z-A", "Artist A-Z", "Artist Z-A",
                   "Album A-Z", "Album Z-A", "Year ↑", "Year ↓",
                   "Duration ↑", "Duration ↓", "Plays ↑", "Plays ↓", "Quality ↑", "Quality ↓"],
            command=self._on_sort_change
        )
        self.sort_menu.pack(side="left", padx=(0, 10))

        # Action buttons
        self.scan_btn = ctk.CTkButton(
            controls_frame, text="📁 Scan", width=70, height=28,
            command=self._scan_folder
        )
        self.scan_btn.pack(side="left", padx=2)

        self.stats_btn = ctk.CTkButton(
            controls_frame, text="📊 Stats", width=70, height=28,
            command=self._show_stats
        )
        self.stats_btn.pack(side="left", padx=2)

        # Update view button appearance
        self._update_view_buttons()

    def _change_view(self, view_mode):
        """Change the current view mode"""
        self.current_view = view_mode
        self._update_view_buttons()
        self._update_breadcrumb()

        if self.callback_manager:
            self.callback_manager('view_changed', view_mode)

    def _update_view_buttons(self):
        """Update view button appearances"""
        for mode, btn in self.view_buttons.items():
            if mode == self.current_view:
                btn.configure(fg_color="#1F538D")
            else:
                btn.configure(fg_color="#565b5e")

    def _update_breadcrumb(self, path=None):
        """Update breadcrumb navigation"""
        if path:
            self.breadcrumb_label.configure(text=f"🏠 Library > {path}")
        else:
            view_names = {
                ViewMode.ARTISTS: "Artists",
                ViewMode.ALBUMS: "Albums",
                ViewMode.TRACKS: "Songs",
                ViewMode.GENRES: "Genres",
                ViewMode.PLAYLISTS: "Playlists"
            }
            view_name = view_names.get(self.current_view, "Library")
            self.breadcrumb_label.configure(text=f"🏠 Library > {view_name}")

    def _on_search(self, event=None):
        """Handle search input"""
        query = self.search_entry.get().strip()
        if self.callback_manager:
            self.callback_manager('search_changed', query)

    def _on_sort_change(self, selection):
        """Handle sort selection change"""
        sort_mapping = {
            "Title A-Z": SortOrder.TITLE_ASC,
            "Title Z-A": SortOrder.TITLE_DESC,
            "Artist A-Z": SortOrder.ARTIST_ASC,
            "Artist Z-A": SortOrder.ARTIST_DESC,
            "Album A-Z": SortOrder.ALBUM_ASC,
            "Album Z-A": SortOrder.ALBUM_DESC,
            "Year ↑": SortOrder.YEAR_ASC,
            "Year ↓": SortOrder.YEAR_DESC,
            "Duration ↑": SortOrder.DURATION_ASC,
            "Duration ↓": SortOrder.DURATION_DESC,
            "Plays ↑": SortOrder.PLAYS_ASC,
            "Plays ↓": SortOrder.PLAYS_DESC,
            "Quality ↑": SortOrder.QUALITY_ASC,
            "Quality ↓": SortOrder.QUALITY_DESC,
        }

        sort_order = sort_mapping.get(selection, SortOrder.TITLE_ASC)
        if self.callback_manager:
            self.callback_manager('sort_changed', sort_order)

    def _show_advanced_search(self):
        """Show advanced search dialog"""
        if self.callback_manager:
            self.callback_manager('show_advanced_search')

    def _scan_folder(self):
        """Scan folder for music"""
        if self.callback_manager:
            self.callback_manager('scan_folder')

    def _show_stats(self):
        """Show library statistics"""
        if self.callback_manager:
            self.callback_manager('show_stats')


class ArtistGridView(ctk.CTkScrollableFrame):
    """Grid view for artists with artwork and metadata"""

    def __init__(self, master, callback_manager=None, **kwargs):
        super().__init__(master, label_text="Artists", **kwargs)
        self.callback_manager = callback_manager
        self.artists_data = []
        self.current_sort = SortOrder.ARTIST_ASC

        self.setup_ui()

    def setup_ui(self):
        """Setup artist grid UI"""
        # Configure grid
        self.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="column")

        # Instructions label (shown when empty)
        self.empty_label = ctk.CTkLabel(
            self, text="🎤 No artists found\n\nAdd music to your library to see artists here",
            font=ctk.CTkFont(size=14), text_color="#666666"
        )
        self.empty_label.grid(row=0, column=0, columnspan=5, pady=50)

    def update_artists(self, artists_data, sort_order=None):
        """Update the artists display"""
        self.artists_data = artists_data
        if sort_order:
            self.current_sort = sort_order

        # Clear existing content
        for widget in self.winfo_children():
            widget.destroy()

        if not artists_data:
            self.empty_label = ctk.CTkLabel(
                self, text="🎤 No artists found\n\nAdd music to your library to see artists here",
                font=ctk.CTkFont(size=14), text_color="#666666"
            )
            self.empty_label.grid(row=0, column=0, columnspan=5, pady=50)
            return

        # Sort artists
        sorted_artists = self._sort_artists(artists_data)

        # Create artist cards
        for i, artist in enumerate(sorted_artists):
            row = i // 5
            col = i % 5

            artist_card = self._create_artist_card(artist)
            artist_card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

    def _sort_artists(self, artists):
        """Sort artists based on current sort order"""
        reverse = "desc" in self.current_sort.lower()

        if "name" in self.current_sort or "artist" in self.current_sort:
            return sorted(artists, key=lambda x: x.get('name', '').lower(), reverse=reverse)
        elif "plays" in self.current_sort:
            return sorted(artists, key=lambda x: x.get('total_plays', 0), reverse=reverse)
        elif "albums" in self.current_sort:
            return sorted(artists, key=lambda x: x.get('album_count', 0), reverse=reverse)
        else:
            return artists

    def _create_artist_card(self, artist):
        """Create an artist card widget"""
        card = ctk.CTkFrame(self, width=180, height=220)
        card.grid_propagate(False)

        # Artist image placeholder
        img_frame = ctk.CTkFrame(card, width=160, height=160, fg_color="#333333")
        img_frame.pack(pady=(10, 5))
        img_frame.pack_propagate(False)

        # Artist initial or icon
        initial = artist.get('name', 'Unknown')[0].upper() if artist.get('name') else '?'
        img_label = ctk.CTkLabel(
            img_frame, text=initial,
            font=ctk.CTkFont(size=48, weight="bold"),
            text_color="#888888"
        )
        img_label.pack(expand=True)

        # Artist name
        name_label = ctk.CTkLabel(
            card, text=artist.get('name', 'Unknown Artist'),
            font=ctk.CTkFont(size=12, weight="bold"),
            wraplength=160
        )
        name_label.pack(pady=2)

        # Stats
        album_count = artist.get('album_count', 0)
        track_count = artist.get('track_count', 0)
        stats_text = f"{album_count} albums • {track_count} songs"

        stats_label = ctk.CTkLabel(
            card, text=stats_text,
            font=ctk.CTkFont(size=10),
            text_color="#888888"
        )
        stats_label.pack()

        # Click handler
        def on_click(event, artist_data=artist):
            if self.callback_manager:
                self.callback_manager('artist_selected', artist_data)

        # Make entire card clickable
        card.bind("<Button-1>", on_click)
        img_frame.bind("<Button-1>", on_click)
        img_label.bind("<Button-1>", on_click)
        name_label.bind("<Button-1>", on_click)
        stats_label.bind("<Button-1>", on_click)

        return card


class AlbumGridView(ctk.CTkScrollableFrame):
    """Grid view for albums with artwork and metadata"""

    def __init__(self, master, callback_manager=None, **kwargs):
        super().__init__(master, label_text="Albums", **kwargs)
        self.callback_manager = callback_manager
        self.albums_data = []

        self.setup_ui()

    def setup_ui(self):
        """Setup album grid UI"""
        # Configure grid
        self.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="column")

        # Instructions label (shown when empty)
        self.empty_label = ctk.CTkLabel(
            self, text="💿 No albums found\n\nAdd music to your library to see albums here",
            font=ctk.CTkFont(size=14), text_color="#666666"
        )
        self.empty_label.grid(row=0, column=0, columnspan=5, pady=50)

    def update_albums(self, albums_data, artist_filter=None):
        """Update the albums display"""
        self.albums_data = albums_data

        # Filter by artist if specified
        if artist_filter:
            albums_data = [a for a in albums_data if a.get('artist') == artist_filter]

        # Clear existing content
        for widget in self.winfo_children():
            widget.destroy()

        if not albums_data:
            self.empty_label = ctk.CTkLabel(
                self, text="💿 No albums found",
                font=ctk.CTkFont(size=14), text_color="#666666"
            )
            self.empty_label.grid(row=0, column=0, columnspan=5, pady=50)
            return

        # Create album cards
        for i, album in enumerate(albums_data):
            row = i // 5
            col = i % 5

            album_card = self._create_album_card(album)
            album_card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

    def _create_album_card(self, album):
        """Create an album card widget"""
        card = ctk.CTkFrame(self, width=180, height=240)
        card.grid_propagate(False)

        # Album artwork placeholder
        art_frame = ctk.CTkFrame(card, width=160, height=160, fg_color="#333333")
        art_frame.pack(pady=(10, 5))
        art_frame.pack_propagate(False)

        # Album icon
        art_label = ctk.CTkLabel(
            art_frame, text="💿",
            font=ctk.CTkFont(size=48),
        )
        art_label.pack(expand=True)

        # Album title
        title_label = ctk.CTkLabel(
            card, text=album.get('title', 'Unknown Album'),
            font=ctk.CTkFont(size=12, weight="bold"),
            wraplength=160
        )
        title_label.pack(pady=2)

        # Artist name
        artist_label = ctk.CTkLabel(
            card, text=album.get('artist', 'Unknown Artist'),
            font=ctk.CTkFont(size=10),
            text_color="#888888",
            wraplength=160
        )
        artist_label.pack()

        # Year and track count
        year = album.get('year', '')
        track_count = album.get('track_count', 0)
        info_text = f"{year} • {track_count} tracks" if year else f"{track_count} tracks"

        info_label = ctk.CTkLabel(
            card, text=info_text,
            font=ctk.CTkFont(size=9),
            text_color="#666666"
        )
        info_label.pack()

        # Click handler
        def on_click(event, album_data=album):
            if self.callback_manager:
                self.callback_manager('album_selected', album_data)

        # Make entire card clickable
        for widget in [card, art_frame, art_label, title_label, artist_label, info_label]:
            widget.bind("<Button-1>", on_click)

        return card


class TrackListView(ctk.CTkScrollableFrame):
    """List view for tracks with detailed metadata"""

    def __init__(self, master, callback_manager=None, **kwargs):
        super().__init__(master, label_text="Songs", **kwargs)
        self.callback_manager = callback_manager
        self.tracks_data = []

        self.setup_ui()

    def setup_ui(self):
        """Setup track list UI"""
        # Header row
        header_frame = ctk.CTkFrame(self, fg_color="#2B2B2B", height=30)
        header_frame.pack(fill="x", padx=5, pady=(5, 0))
        header_frame.pack_propagate(False)

        # Column headers
        headers = [
            ("", 30),          # Play button
            ("Title", 200),
            ("Artist", 150),
            ("Album", 150),
            ("Duration", 80),
            ("Plays", 60),
            ("Quality", 80),
            ("❤️", 30),        # Favorite
        ]

        x_pos = 10
        for header, width in headers:
            label = ctk.CTkLabel(
                header_frame, text=header,
                font=ctk.CTkFont(size=10, weight="bold"),
                width=width, anchor="w"
            )
            label.place(x=x_pos, y=5)
            x_pos += width + 10

        # Tracks container
        self.tracks_container = ctk.CTkFrame(self, fg_color="transparent")
        self.tracks_container.pack(fill="both", expand=True, padx=5)

        # Empty state
        self.empty_label = ctk.CTkLabel(
            self.tracks_container,
            text="🎵 No songs found\n\nAdd music to your library to see songs here",
            font=ctk.CTkFont(size=14), text_color="#666666"
        )
        self.empty_label.pack(expand=True, pady=50)

    def update_tracks(self, tracks_data, album_filter=None, artist_filter=None):
        """Update the tracks display"""
        self.tracks_data = tracks_data

        # Apply filters
        filtered_tracks = tracks_data
        if album_filter:
            filtered_tracks = [t for t in filtered_tracks if t.get('album') == album_filter]
        if artist_filter:
            filtered_tracks = [t for t in filtered_tracks if artist_filter in t.get('artists', [])]

        # Clear existing tracks
        for widget in self.tracks_container.winfo_children():
            widget.destroy()

        if not filtered_tracks:
            self.empty_label = ctk.CTkLabel(
                self.tracks_container,
                text="🎵 No songs found",
                font=ctk.CTkFont(size=14), text_color="#666666"
            )
            self.empty_label.pack(expand=True, pady=50)
            return

        # Create track rows
        for i, track in enumerate(filtered_tracks):
            track_row = self._create_track_row(track, i)
            track_row.pack(fill="x", pady=1)

    def _create_track_row(self, track, index):
        """Create a track row widget"""
        row_color = "#1F1F1F" if index % 2 == 0 else "#242424"
        row = ctk.CTkFrame(self.tracks_container, fg_color=row_color, height=40)
        row.pack_propagate(False)

        # Play button
        play_btn = ctk.CTkButton(
            row, text="▶️", width=25, height=25,
            command=lambda: self._play_track(track)
        )
        play_btn.place(x=5, y=7)

        # Track info
        x_pos = 40

        # Title
        title_label = ctk.CTkLabel(
            row, text=track.get('title', 'Unknown'),
            font=ctk.CTkFont(size=11),
            width=200, anchor="w"
        )
        title_label.place(x=x_pos, y=10)
        x_pos += 210

        # Artist
        artists = track.get('artists', [])
        artist_text = ', '.join(artists) if artists else 'Unknown Artist'
        artist_label = ctk.CTkLabel(
            row, text=artist_text,
            font=ctk.CTkFont(size=10),
            text_color="#CCCCCC",
            width=150, anchor="w"
        )
        artist_label.place(x=x_pos, y=10)
        x_pos += 160

        # Album
        album_label = ctk.CTkLabel(
            row, text=track.get('album', 'Unknown Album'),
            font=ctk.CTkFont(size=10),
            text_color="#CCCCCC",
            width=150, anchor="w"
        )
        album_label.place(x=x_pos, y=10)
        x_pos += 160

        # Duration
        duration = track.get('duration', 0)
        duration_text = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "--:--"
        duration_label = ctk.CTkLabel(
            row, text=duration_text,
            font=ctk.CTkFont(size=10),
            text_color="#CCCCCC",
            width=80, anchor="w"
        )
        duration_label.place(x=x_pos, y=10)
        x_pos += 90

        # Play count
        plays_label = ctk.CTkLabel(
            row, text=str(track.get('play_count', 0)),
            font=ctk.CTkFont(size=10),
            text_color="#CCCCCC",
            width=60, anchor="w"
        )
        plays_label.place(x=x_pos, y=10)
        x_pos += 70

        # Quality score
        quality = track.get('mastering_quality', 0)
        quality_text = f"{quality:.1%}" if quality else "N/A"
        quality_color = "#00FF00" if quality > 0.8 else "#FFFF00" if quality > 0.6 else "#FF6666"
        quality_label = ctk.CTkLabel(
            row, text=quality_text,
            font=ctk.CTkFont(size=10),
            text_color=quality_color,
            width=80, anchor="w"
        )
        quality_label.place(x=x_pos, y=10)
        x_pos += 90

        # Favorite button
        fav_emoji = "❤️" if track.get('favorite') else "🤍"
        fav_btn = ctk.CTkButton(
            row, text=fav_emoji, width=25, height=25,
            command=lambda: self._toggle_favorite(track)
        )
        fav_btn.place(x=x_pos, y=7)

        # Double-click to play
        row.bind("<Double-Button-1>", lambda e: self._play_track(track))

        return row

    def _play_track(self, track):
        """Play the selected track"""
        if self.callback_manager:
            self.callback_manager('track_play', track)

    def _toggle_favorite(self, track):
        """Toggle track favorite status"""
        if self.callback_manager:
            self.callback_manager('track_favorite', track)


class EnhancedMediaBrowser(ctk.CTkFrame):
    """Enhanced media browser with hierarchical views and advanced features"""

    def __init__(self, master, library_manager=None, player_callback=None, **kwargs):
        super().__init__(master, **kwargs)

        self.library_manager = library_manager
        self.player_callback = player_callback
        self.current_view = ViewMode.ARTISTS
        self.current_artist = None
        self.current_album = None

        self.setup_ui()
        self.setup_callbacks()

    def setup_ui(self):
        """Setup the enhanced media browser UI"""
        # Header with controls
        self.header = MediaBrowserHeader(self, callback_manager=self._handle_header_callback)
        self.header.pack(fill="x", padx=5, pady=5)

        # Main content area
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # Create different view components
        self.artist_view = ArtistGridView(self.content_frame, callback_manager=self._handle_view_callback)
        self.album_view = AlbumGridView(self.content_frame, callback_manager=self._handle_view_callback)
        self.track_view = TrackListView(self.content_frame, callback_manager=self._handle_view_callback)

        # Status bar
        self.status_bar = ctk.CTkFrame(self, height=30, fg_color="#1F1F1F")
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_bar, text="Ready",
            font=ctk.CTkFont(size=10), text_color="#888888"
        )
        self.status_label.pack(side="left", padx=10, pady=5)

        # Library stats
        self.stats_label = ctk.CTkLabel(
            self.status_bar, text="No library loaded",
            font=ctk.CTkFont(size=10), text_color="#888888"
        )
        self.stats_label.pack(side="right", padx=10, pady=5)

        # Initially show artist view (after status bar is created)
        self._show_view(ViewMode.ARTISTS)

    def setup_callbacks(self):
        """Setup callback handlers"""
        pass  # Callbacks are handled in _handle_header_callback and _handle_view_callback

    def _handle_header_callback(self, event_type, data=None):
        """Handle callbacks from header component"""
        if event_type == 'view_changed':
            self._show_view(data)
        elif event_type == 'search_changed':
            self._handle_search(data)
        elif event_type == 'sort_changed':
            self._handle_sort(data)
        elif event_type == 'scan_folder':
            self._scan_folder()
        elif event_type == 'show_stats':
            self._show_stats()
        elif event_type == 'show_advanced_search':
            self._show_advanced_search()

    def _handle_view_callback(self, event_type, data=None):
        """Handle callbacks from view components"""
        if event_type == 'artist_selected':
            self._select_artist(data)
        elif event_type == 'album_selected':
            self._select_album(data)
        elif event_type == 'track_play':
            self._play_track(data)
        elif event_type == 'track_favorite':
            self._toggle_track_favorite(data)

    def _show_view(self, view_mode):
        """Show the specified view mode"""
        # Hide all views
        self.artist_view.pack_forget()
        self.album_view.pack_forget()
        self.track_view.pack_forget()

        # Show selected view
        self.current_view = view_mode

        if view_mode == ViewMode.ARTISTS:
            self.artist_view.pack(fill="both", expand=True)
            self._load_artists()
        elif view_mode == ViewMode.ALBUMS:
            self.album_view.pack(fill="both", expand=True)
            self._load_albums()
        elif view_mode == ViewMode.TRACKS:
            self.track_view.pack(fill="both", expand=True)
            self._load_tracks()
        elif view_mode == ViewMode.GENRES:
            # TODO: Implement genres view
            pass
        elif view_mode == ViewMode.PLAYLISTS:
            # TODO: Implement playlists view
            pass

    def _load_artists(self):
        """Load and display artists"""
        if not self.library_manager:
            return

        try:
            # Get tracks and extract unique artists
            with self.library_manager.get_session() as session:
                from auralis.library.models import Artist
                artists = session.query(Artist).all()
                artists_data = [artist.to_dict() for artist in artists]

            self.artist_view.update_artists(artists_data)
            self._update_status(f"Showing {len(artists_data)} artists")

        except Exception as e:
            print(f"Error loading artists: {e}")
            self._update_status("Error loading artists")

    def _load_albums(self, artist_filter=None):
        """Load and display albums"""
        if not self.library_manager:
            return

        try:
            # Get albums from library
            with self.library_manager.get_session() as session:
                from auralis.library.models import Album
                albums = session.query(Album).all()
                albums_data = [album.to_dict() for album in albums]

            self.album_view.update_albums(albums_data, artist_filter)

            count_text = f"Showing {len(albums_data)} albums"
            if artist_filter:
                count_text += f" by {artist_filter}"
            self._update_status(count_text)

        except Exception as e:
            print(f"Error loading albums: {e}")
            self._update_status("Error loading albums")

    def _load_tracks(self, album_filter=None, artist_filter=None):
        """Load and display tracks"""
        if not self.library_manager:
            return

        try:
            # Get tracks from library
            with self.library_manager.get_session() as session:
                from auralis.library.models import Track
                tracks = session.query(Track).all()
                tracks_data = [track.to_dict() for track in tracks]

            self.track_view.update_tracks(tracks_data, album_filter, artist_filter)

            count_text = f"Showing {len(tracks_data)} songs"
            if album_filter:
                count_text += f" from {album_filter}"
            elif artist_filter:
                count_text += f" by {artist_filter}"
            self._update_status(count_text)

        except Exception as e:
            print(f"Error loading tracks: {e}")
            self._update_status("Error loading tracks")

    def _select_artist(self, artist_data):
        """Handle artist selection"""
        self.current_artist = artist_data['name']

        # Switch to albums view filtered by artist
        self.header._change_view(ViewMode.ALBUMS)
        self._load_albums(artist_filter=self.current_artist)

        # Update breadcrumb
        self.header._update_breadcrumb(f"Artists > {self.current_artist}")

    def _select_album(self, album_data):
        """Handle album selection"""
        self.current_album = album_data['title']

        # Switch to tracks view filtered by album
        self.header._change_view(ViewMode.TRACKS)
        self._load_tracks(album_filter=self.current_album)

        # Update breadcrumb
        breadcrumb = f"Albums > {self.current_album}"
        if self.current_artist:
            breadcrumb = f"Artists > {self.current_artist} > {self.current_album}"
        self.header._update_breadcrumb(breadcrumb)

    def _play_track(self, track_data):
        """Play the selected track"""
        if self.player_callback:
            self.player_callback(track_data)
        self._update_status(f"Playing: {track_data.get('title', 'Unknown')}")

    def _toggle_track_favorite(self, track_data):
        """Toggle track favorite status"""
        if not self.library_manager:
            return

        try:
            track_id = track_data.get('id')
            if track_id:
                # Toggle favorite in database
                self.library_manager.toggle_track_favorite(track_id)

                # Refresh current view
                if self.current_view == ViewMode.TRACKS:
                    self._load_tracks(self.current_album, self.current_artist)

                fav_status = "Added to" if not track_data.get('favorite') else "Removed from"
                self._update_status(f"{fav_status} favorites: {track_data.get('title', 'Unknown')}")

        except Exception as e:
            print(f"Error toggling favorite: {e}")
            self._update_status("Error updating favorite")

    def _handle_search(self, query):
        """Handle search query"""
        # TODO: Implement search functionality
        self._update_status(f"Searching for: {query}" if query else "Search cleared")

    def _handle_sort(self, sort_order):
        """Handle sort order change"""
        # TODO: Implement sorting
        self._update_status(f"Sorting by: {sort_order}")

    def _scan_folder(self):
        """Scan folder for music files"""
        if not self.library_manager:
            messagebox.showerror("Error", "No library manager available")
            return

        folder = filedialog.askdirectory(title="Select Music Folder")
        if folder:
            self._update_status("Scanning folder...")

            # Run scan in background thread
            def scan_thread():
                try:
                    count = self.library_manager.scan_directory(folder)
                    self.after(0, lambda: self._scan_complete(count))
                except Exception as e:
                    self.after(0, lambda: self._scan_error(str(e)))

            threading.Thread(target=scan_thread, daemon=True).start()

    def _scan_complete(self, count):
        """Handle scan completion"""
        self._update_status(f"Scan complete: {count} files processed")

        # Refresh current view
        if self.current_view == ViewMode.ARTISTS:
            self._load_artists()
        elif self.current_view == ViewMode.ALBUMS:
            self._load_albums()
        elif self.current_view == ViewMode.TRACKS:
            self._load_tracks()

        # Update library stats
        self._update_library_stats()

    def _scan_error(self, error_msg):
        """Handle scan error"""
        self._update_status("Scan failed")
        messagebox.showerror("Scan Error", f"Failed to scan folder: {error_msg}")

    def _show_stats(self):
        """Show library statistics dialog"""
        # TODO: Implement stats dialog
        messagebox.showinfo("Library Stats", "Library statistics feature coming soon!")

    def _show_advanced_search(self):
        """Show advanced search dialog"""
        # TODO: Implement advanced search
        messagebox.showinfo("Advanced Search", "Advanced search feature coming soon!")

    def _update_status(self, message):
        """Update status bar message"""
        self.status_label.configure(text=message)

    def _update_library_stats(self):
        """Update library statistics display"""
        if not self.library_manager:
            self.stats_label.configure(text="No library loaded")
            return

        try:
            stats = self.library_manager.get_library_stats()
            if stats:
                # Handle both dict and object responses safely
                if hasattr(stats, 'to_dict') and callable(getattr(stats, 'to_dict')):
                    stats_data = stats.to_dict()
                elif isinstance(stats, dict):
                    stats_data = stats
                else:
                    # Convert object attributes to dict
                    stats_data = {
                        'total_tracks': getattr(stats, 'total_tracks', 0),
                        'total_albums': getattr(stats, 'total_albums', 0),
                        'total_artists': getattr(stats, 'total_artists', 0)
                    }

                tracks = stats_data.get('total_tracks', 0)
                albums = stats_data.get('total_albums', 0)
                artists = stats_data.get('total_artists', 0)

                stats_text = f"{tracks} songs • {albums} albums • {artists} artists"
                self.stats_label.configure(text=stats_text)
            else:
                self.stats_label.configure(text="Library empty")

        except Exception as e:
            # Only print debug info in debug mode
            if hasattr(self, '_debug') and self._debug:
                print(f"Library stats error: {e}")
            self.stats_label.configure(text="Stats unavailable")

    def set_library_manager(self, library_manager):
        """Set the library manager and refresh"""
        self.library_manager = library_manager
        self._update_library_stats()

        # Load initial view
        if self.current_view == ViewMode.ARTISTS:
            self._load_artists()
        elif self.current_view == ViewMode.ALBUMS:
            self._load_albums()
        elif self.current_view == ViewMode.TRACKS:
            self._load_tracks()