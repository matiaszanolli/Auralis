#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auralis Enhanced GUI
~~~~~~~~~~~~~~~~~~~

Professional music management interface with hierarchical browsing,
advanced search, and sophisticated playlist management.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add auralis to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

try:
    import auralis
    from auralis import EnhancedAudioPlayer, PlayerConfig
    from auralis.library import LibraryManager
    HAS_AURALIS = True
    print("✅ Auralis library loaded successfully")
except ImportError as e:
    print(f"⚠️  Auralis not available: {e}")
    HAS_AURALIS = False

# Import new GUI components
try:
    from auralis.gui.media_browser import EnhancedMediaBrowser
    from auralis.gui.playlist_manager import PlaylistManagerWindow
    from auralis.gui.advanced_search import AdvancedSearchWindow, QuickSearchBar
    HAS_ENHANCED_GUI = True
    print("✅ Enhanced GUI components loaded")
except ImportError as e:
    print(f"⚠️  Enhanced GUI components not available: {e}")
    HAS_ENHANCED_GUI = False


class NowPlayingPanel(ctk.CTkFrame):
    """Compact now playing panel with track info and controls"""

    def __init__(self, master, player_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.player_callback = player_callback
        self.current_track = None

        self.setup_ui()

    def setup_ui(self):
        """Setup now playing panel UI"""
        # Track artwork area
        self.artwork_frame = ctk.CTkFrame(self, width=60, height=60, fg_color="#333333")
        self.artwork_frame.pack(side="left", padx=10, pady=10)
        self.artwork_frame.pack_propagate(False)

        self.artwork_label = ctk.CTkLabel(
            self.artwork_frame, text="🎵",
            font=ctk.CTkFont(size=24)
        )
        self.artwork_label.pack(expand=True)

        # Track info
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)

        self.title_label = ctk.CTkLabel(
            info_frame, text="No track playing",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        self.title_label.pack(fill="x")

        self.artist_label = ctk.CTkLabel(
            info_frame, text="Select a track to play",
            font=ctk.CTkFont(size=11),
            text_color="#888888", anchor="w"
        )
        self.artist_label.pack(fill="x")

        # Progress bar
        self.progress_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", pady=(5, 0))

        self.time_label = ctk.CTkLabel(self.progress_frame, text="0:00", font=ctk.CTkFont(size=9))
        self.time_label.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=4)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=5)
        self.progress_bar.set(0)

        self.duration_label = ctk.CTkLabel(self.progress_frame, text="0:00", font=ctk.CTkFont(size=9))
        self.duration_label.pack(side="right")

        # Control buttons
        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.pack(side="right", padx=10, pady=10)

        self.prev_btn = ctk.CTkButton(controls_frame, text="⏮️", width=40, height=40)
        self.prev_btn.pack(side="left", padx=2)

        self.play_btn = ctk.CTkButton(
            controls_frame, text="▶️", width=50, height=40,
            command=self._toggle_playback
        )
        self.play_btn.pack(side="left", padx=2)

        self.next_btn = ctk.CTkButton(controls_frame, text="⏭️", width=40, height=40)
        self.next_btn.pack(side="left", padx=2)

        # Volume control
        volume_frame = ctk.CTkFrame(self, fg_color="transparent")
        volume_frame.pack(side="right", padx=10, pady=10)

        ctk.CTkLabel(volume_frame, text="🔊", font=ctk.CTkFont(size=12)).pack(side="left")
        self.volume_slider = ctk.CTkSlider(volume_frame, from_=0, to=100, width=100)
        self.volume_slider.pack(side="left", padx=5)
        self.volume_slider.set(80)

    def update_track(self, track_data):
        """Update the now playing display"""
        self.current_track = track_data

        if track_data:
            self.title_label.configure(text=track_data.get('title', 'Unknown'))

            artists = track_data.get('artists', [])
            artist_text = ', '.join(artists) if artists else 'Unknown Artist'
            album = track_data.get('album', '')
            if album:
                artist_text += f" • {album}"

            self.artist_label.configure(text=artist_text)

            # Update duration
            duration = track_data.get('duration', 0)
            duration_text = f"{int(duration // 60)}:{int(duration % 60):02d}"
            self.duration_label.configure(text=duration_text)

            # Reset progress
            self.progress_bar.set(0)
            self.time_label.configure(text="0:00")

        else:
            self.title_label.configure(text="No track playing")
            self.artist_label.configure(text="Select a track to play")
            self.duration_label.configure(text="0:00")
            self.time_label.configure(text="0:00")
            self.progress_bar.set(0)

    def _toggle_playback(self):
        """Toggle play/pause"""
        if self.player_callback:
            self.player_callback('toggle_playback')


class LibraryStatsPanel(ctk.CTkFrame):
    """Library statistics and quick info panel"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.stats_data = {}

        self.setup_ui()

    def setup_ui(self):
        """Setup stats panel UI"""
        # Title
        title = ctk.CTkLabel(self, text="📊 Library Stats",
                           font=ctk.CTkFont(size=14, weight="bold"))
        title.pack(pady=(10, 5))

        # Stats grid
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Create stat widgets
        self.stats_widgets = {}
        stats = [
            ("tracks", "🎵 Songs", "0"),
            ("albums", "💿 Albums", "0"),
            ("artists", "👤 Artists", "0"),
            ("duration", "⏱️ Total Time", "0h 0m"),
            ("size", "💾 Library Size", "0 GB"),
            ("quality", "⭐ Avg Quality", "N/A")
        ]

        for i, (key, label, default) in enumerate(stats):
            row = i // 2
            col = i % 2

            stat_frame = ctk.CTkFrame(self.stats_frame, height=60)
            stat_frame.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            stat_frame.grid_propagate(False)

            label_widget = ctk.CTkLabel(stat_frame, text=label, font=ctk.CTkFont(size=10))
            label_widget.pack(pady=(5, 0))

            value_widget = ctk.CTkLabel(stat_frame, text=default,
                                      font=ctk.CTkFont(size=12, weight="bold"))
            value_widget.pack()

            self.stats_widgets[key] = value_widget

        # Configure grid weights
        self.stats_frame.grid_columnconfigure((0, 1), weight=1)

    def update_stats(self, stats_data):
        """Update the statistics display"""
        self.stats_data = stats_data

        if not stats_data:
            return

        # Update each stat
        updates = {
            'tracks': str(stats_data.get('total_tracks', 0)),
            'albums': str(stats_data.get('total_albums', 0)),
            'artists': str(stats_data.get('total_artists', 0)),
            'duration': stats_data.get('total_duration_formatted', '0h 0m'),
            'size': f"{stats_data.get('total_filesize_gb', 0):.1f} GB",
            'quality': f"{stats_data.get('avg_mastering_quality', 0):.1%}" if stats_data.get('avg_mastering_quality') else "N/A"
        }

        for key, value in updates.items():
            if key in self.stats_widgets:
                self.stats_widgets[key].configure(text=value)


class EnhancedAuralisGUI(ctk.CTk):
    """Enhanced Auralis GUI with professional media management"""

    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Auralis - Professional Audio Mastering")
        self.geometry("1400x900")
        self.minsize(1200, 700)

        # Initialize components
        self.library_manager = None
        self.audio_player = None
        self.current_track = None

        self.setup_library()
        self.setup_ui()
        self.setup_callbacks()

    def setup_library(self):
        """Initialize library manager"""
        if HAS_AURALIS:
            try:
                self.library_manager = LibraryManager()
                print("✅ Library manager initialized")
            except Exception as e:
                print(f"⚠️  Failed to initialize library manager: {e}")
                self.library_manager = None

    def setup_ui(self):
        """Setup the enhanced GUI layout"""
        # Main container
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Top panel - Quick search and controls
        top_panel = ctk.CTkFrame(main_container, height=50)
        top_panel.pack(fill="x", pady=(0, 5))
        top_panel.pack_propagate(False)

        if HAS_ENHANCED_GUI:
            self.quick_search = QuickSearchBar(top_panel, callback_manager=self._handle_search_callback)
            self.quick_search.pack(fill="both", expand=True, padx=10, pady=5)
        else:
            # Fallback simple search
            search_entry = ctk.CTkEntry(top_panel, placeholder_text="🔍 Search library...", width=300)
            search_entry.pack(side="left", padx=10, pady=10)

        # Main content area
        content_container = ctk.CTkFrame(main_container, fg_color="transparent")
        content_container.pack(fill="both", expand=True)

        # Left sidebar - Library stats and quick actions
        left_sidebar = ctk.CTkFrame(content_container, width=250)
        left_sidebar.pack(side="left", fill="y", padx=(0, 5))
        left_sidebar.pack_propagate(False)

        # Library stats panel
        self.stats_panel = LibraryStatsPanel(left_sidebar)
        self.stats_panel.pack(fill="x", padx=5, pady=5)

        # Quick actions
        actions_frame = ctk.CTkFrame(left_sidebar)
        actions_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(actions_frame, text="⚡ Quick Actions",
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 5))

        actions = [
            ("📁 Scan Music Folder", self._scan_folder),
            ("📋 Manage Playlists", self._open_playlist_manager),
            ("🔍 Advanced Search", self._open_advanced_search),
            ("📊 Library Statistics", self._show_detailed_stats),
            ("⚙️ Preferences", self._open_preferences)
        ]

        for text, command in actions:
            btn = ctk.CTkButton(actions_frame, text=text, height=35, command=command)
            btn.pack(fill="x", padx=10, pady=2)

        # Main media browser
        media_frame = ctk.CTkFrame(content_container)
        media_frame.pack(side="left", fill="both", expand=True)

        if HAS_ENHANCED_GUI:
            self.media_browser = EnhancedMediaBrowser(
                media_frame, library_manager=self.library_manager,
                player_callback=self._play_track
            )
            self.media_browser.pack(fill="both", expand=True, padx=5, pady=5)
        else:
            # Fallback basic browser
            fallback_label = ctk.CTkLabel(
                media_frame,
                text="Enhanced Media Browser\nNot Available\n\nPlease install enhanced GUI components",
                font=ctk.CTkFont(size=16),
                text_color="#888888"
            )
            fallback_label.pack(expand=True)

        # Bottom panel - Now playing
        bottom_panel = ctk.CTkFrame(main_container, height=100)
        bottom_panel.pack(fill="x", pady=(5, 0))
        bottom_panel.pack_propagate(False)

        self.now_playing = NowPlayingPanel(bottom_panel, player_callback=self._handle_player_callback)
        self.now_playing.pack(fill="both", expand=True, padx=5, pady=5)

        # Update library stats
        self._update_library_stats()

    def setup_callbacks(self):
        """Setup callback handlers"""
        pass  # Callbacks are handled in individual methods

    def _handle_search_callback(self, event_type, data=None):
        """Handle search-related callbacks"""
        if event_type == 'quick_search':
            self._perform_quick_search(data)
        elif event_type == 'search_execute':
            self._execute_search(data)
        elif event_type == 'filter_applied':
            self._apply_quick_filter(data)
        elif event_type == 'show_advanced_search':
            self._open_advanced_search()

    def _handle_player_callback(self, event_type, data=None):
        """Handle player control callbacks"""
        if event_type == 'toggle_playback':
            self._toggle_playback()
        # Add more player controls as needed

    def _perform_quick_search(self, query):
        """Perform quick search"""
        print(f"Quick search: {query}")
        # TODO: Implement quick search filtering

    def _execute_search(self, query):
        """Execute search query"""
        print(f"Execute search: {query}")
        # TODO: Implement full search execution

    def _apply_quick_filter(self, filter_type):
        """Apply quick filter"""
        print(f"Apply filter: {filter_type}")
        # TODO: Implement filtering logic

    def _play_track(self, track_data):
        """Play the selected track"""
        self.current_track = track_data
        self.now_playing.update_track(track_data)

        print(f"Playing: {track_data.get('title', 'Unknown')} by {', '.join(track_data.get('artists', ['Unknown']))}")

        # TODO: Integrate with actual audio player
        if HAS_AURALIS and self.audio_player:
            try:
                file_path = track_data.get('filepath')
                if file_path and Path(file_path).exists():
                    # Play the track
                    pass
            except Exception as e:
                print(f"Error playing track: {e}")

    def _toggle_playback(self):
        """Toggle play/pause"""
        print("Toggle playback")
        # TODO: Implement playback toggle

    def _scan_folder(self):
        """Scan a folder for music files"""
        if not self.library_manager:
            messagebox.showerror("Error", "Library manager not available")
            return

        folder = filedialog.askdirectory(title="Select Music Folder")
        if folder:
            # Show progress dialog
            progress_window = self._create_scan_progress_window()

            def scan_thread():
                try:
                    count = self.library_manager.scan_single_directory(folder)
                    self.after(0, lambda: self._scan_complete(progress_window, count))
                except Exception as e:
                    self.after(0, lambda: self._scan_error(progress_window, str(e)))

            threading.Thread(target=scan_thread, daemon=True).start()

    def _create_scan_progress_window(self):
        """Create scan progress window"""
        progress_window = ctk.CTkToplevel(self)
        progress_window.title("Scanning Music Library")
        progress_window.geometry("400x150")
        progress_window.resizable(False, False)

        # Center the window
        progress_window.transient(self)
        progress_window.grab_set()

        ctk.CTkLabel(progress_window, text="Scanning music files...",
                    font=ctk.CTkFont(size=14)).pack(pady=20)

        progress_bar = ctk.CTkProgressBar(progress_window, width=300)
        progress_bar.pack(pady=10)
        progress_bar.set(0.5)  # Indeterminate progress

        status_label = ctk.CTkLabel(progress_window, text="Please wait...",
                                  font=ctk.CTkFont(size=11), text_color="#888888")
        status_label.pack(pady=5)

        return progress_window

    def _scan_complete(self, progress_window, count):
        """Handle scan completion"""
        progress_window.destroy()
        messagebox.showinfo("Scan Complete", f"Successfully processed {count} files")

        # Refresh displays
        self._update_library_stats()
        if hasattr(self, 'media_browser') and self.media_browser:
            self.media_browser._update_library_stats()

    def _scan_error(self, progress_window, error_msg):
        """Handle scan error"""
        progress_window.destroy()
        messagebox.showerror("Scan Error", f"Failed to scan folder: {error_msg}")

    def _open_playlist_manager(self):
        """Open the playlist manager window"""
        if HAS_ENHANCED_GUI:
            playlist_window = PlaylistManagerWindow(
                self, library_manager=self.library_manager,
                player_callback=self._play_track
            )
        else:
            messagebox.showinfo("Playlist Manager", "Enhanced playlist manager not available")

    def _open_advanced_search(self):
        """Open the advanced search window"""
        if HAS_ENHANCED_GUI:
            search_window = AdvancedSearchWindow(
                self, library_manager=self.library_manager,
                callback=self._handle_advanced_search
            )
        else:
            messagebox.showinfo("Advanced Search", "Advanced search not available")

    def _handle_advanced_search(self, search_params):
        """Handle advanced search results"""
        print(f"Advanced search: {search_params}")
        # TODO: Implement advanced search results display

    def _show_detailed_stats(self):
        """Show detailed library statistics"""
        if not self.library_manager:
            messagebox.showwarning("No Library", "Library manager not available")
            return

        try:
            stats = self.library_manager.get_library_stats()
            if stats:
                stats_data = stats.to_dict()

                # Create stats window
                stats_window = ctk.CTkToplevel(self)
                stats_window.title("Library Statistics")
                stats_window.geometry("500x400")

                # Display detailed stats
                stats_text = f"""
Library Statistics

Content:
• {stats_data['total_tracks']} songs
• {stats_data['total_albums']} albums
• {stats_data['total_artists']} artists
• {stats_data['total_genres']} genres

Storage:
• Total duration: {stats_data['total_duration_formatted']}
• Library size: {stats_data['total_filesize_gb']:.1f} GB

Quality Metrics:
• Average DR rating: {stats_data['avg_dr_rating']:.1f} dB
• Average LUFS: {stats_data['avg_lufs']:.1f}
• Average mastering quality: {stats_data['avg_mastering_quality']:.1%}

Last Scan:
• Date: {stats_data['last_scan_date'] or 'Never'}
• Files processed: {stats_data['files_scanned']}
• New files found: {stats_data['new_files_found']}
                """

                text_widget = ctk.CTkTextbox(stats_window, width=460, height=350)
                text_widget.pack(padx=20, pady=20)
                text_widget.insert("1.0", stats_text)
                text_widget.configure(state="disabled")

            else:
                messagebox.showinfo("Statistics", "No library statistics available")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to retrieve statistics: {e}")

    def _open_preferences(self):
        """Open preferences/settings window"""
        messagebox.showinfo("Preferences", "Preferences window coming soon!")

    def _update_library_stats(self):
        """Update library statistics display"""
        if not self.library_manager:
            return

        try:
            stats = self.library_manager.get_library_stats()
            if stats:
                # Handle both dict and object types
                if hasattr(stats, 'to_dict'):
                    stats_data = stats.to_dict()
                else:
                    stats_data = stats
                self.stats_panel.update_stats(stats_data)

        except Exception as e:
            print(f"Error updating library stats: {e}")


def main():
    """Main entry point"""
    print("🎵 Starting Auralis Enhanced GUI...")

    try:
        app = EnhancedAuralisGUI()
        app.mainloop()
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()