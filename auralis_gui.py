#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auralis GUI - Enhanced Music Management Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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


class EnhancedAuralisGUI(ctk.CTk):
    """Enhanced Auralis GUI with professional media management"""

    def __init__(self):
        super().__init__()

        # Configure window
        self.title("🎵 Auralis - Professional Music Management & Mastering")
        self.geometry("1600x1000")
        self.minsize(1400, 900)

        # Initialize components
        self.player = None
        self.library_manager = None
        self.update_running = False
        self.media_browser = None
        self.playlist_manager = None
        self.advanced_search = None

        # Create interface
        self.setup_ui()

        # Initialize audio system
        self.initialize_audio_system()

        # Start update loop
        self.start_update_loop()

    def setup_ui(self):
        """Setup the enhanced user interface"""
        # Main container
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Create three-panel layout
        self.create_sidebar(main_container)
        self.create_main_area(main_container)
        self.create_info_panel(main_container)

        # Status bar
        self.status_bar = ctk.CTkLabel(
            self,
            text="🎵 Enhanced Auralis ready - Professional music management at your fingertips",
            font=ctk.CTkFont(size=11),
            fg_color="#1a1a1a",
            corner_radius=0,
            height=25
        )
        self.status_bar.pack(side="bottom", fill="x")

    def create_sidebar(self, parent):
        """Create left sidebar with navigation and controls"""
        sidebar = ctk.CTkFrame(parent, width=300)
        sidebar.pack(side="left", fill="y", padx=(0, 5))
        sidebar.pack_propagate(False)

        # Quick actions header
        header = ctk.CTkFrame(sidebar)
        header.pack(fill="x", padx=5, pady=5)

        title = ctk.CTkLabel(
            header,
            text="🎵 Quick Actions",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.pack(pady=10)

        # Quick action buttons
        actions_frame = ctk.CTkFrame(sidebar)
        actions_frame.pack(fill="x", padx=5, pady=(0, 5))

        scan_btn = ctk.CTkButton(
            actions_frame,
            text="📁 Scan Library",
            command=self._quick_scan_library,
            height=35
        )
        scan_btn.pack(fill="x", padx=10, pady=5)

        search_btn = ctk.CTkButton(
            actions_frame,
            text="🔍 Advanced Search",
            command=self._show_advanced_search,
            height=35
        )
        search_btn.pack(fill="x", padx=10, pady=5)

        playlist_btn = ctk.CTkButton(
            actions_frame,
            text="📋 Manage Playlists",
            command=self._show_playlist_manager,
            height=35
        )
        playlist_btn.pack(fill="x", padx=10, pady=5)

        # Library stats
        self.stats_frame = ctk.CTkFrame(sidebar)
        self.stats_frame.pack(fill="x", padx=5, pady=(0, 5))

        stats_title = ctk.CTkLabel(
            self.stats_frame,
            text="📊 Library Stats",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        stats_title.pack(pady=(10, 5))

        self.stats_label = ctk.CTkLabel(
            self.stats_frame,
            text="Loading statistics...",
            font=ctk.CTkFont(size=11),
            justify="left"
        )
        self.stats_label.pack(padx=10, pady=(0, 10))

        # Now playing section
        self.now_playing_frame = ctk.CTkFrame(sidebar)
        self.now_playing_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        now_playing_title = ctk.CTkLabel(
            self.now_playing_frame,
            text="🎧 Now Playing",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        now_playing_title.pack(pady=(10, 5))

        # Track info
        self.track_title_label = ctk.CTkLabel(
            self.now_playing_frame,
            text="No track loaded",
            font=ctk.CTkFont(size=12, weight="bold"),
            wraplength=250
        )
        self.track_title_label.pack(padx=10, pady=2)

        self.track_artist_label = ctk.CTkLabel(
            self.now_playing_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#888888",
            wraplength=250
        )
        self.track_artist_label.pack(padx=10, pady=2)

        # Simple playback controls
        controls_frame = ctk.CTkFrame(self.now_playing_frame, fg_color="transparent")
        controls_frame.pack(pady=10)

        self.play_btn = ctk.CTkButton(
            controls_frame,
            text="▶️",
            width=50,
            height=40,
            command=self._toggle_play,
            font=ctk.CTkFont(size=16)
        )
        self.play_btn.pack(side="left", padx=2)

        stop_btn = ctk.CTkButton(
            controls_frame,
            text="⏹️",
            width=40,
            height=40,
            command=self._stop,
            font=ctk.CTkFont(size=14)
        )
        stop_btn.pack(side="left", padx=2)

        # Volume control
        volume_frame = ctk.CTkFrame(self.now_playing_frame, fg_color="transparent")
        volume_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(volume_frame, text="🔊", font=ctk.CTkFont(size=12)).pack(side="left")

        self.volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0,
            to=1,
            command=self._on_volume_change,
            width=150
        )
        self.volume_slider.set(0.8)
        self.volume_slider.pack(side="left", fill="x", expand=True, padx=(5, 10))

        self.volume_label = ctk.CTkLabel(volume_frame, text="80%", width=40)
        self.volume_label.pack(side="right")

    def create_main_area(self, parent):
        """Create main content area with media browser"""
        main_area = ctk.CTkFrame(parent)
        main_area.pack(side="left", fill="both", expand=True, padx=(0, 5))

        # Media browser header
        browser_header = ctk.CTkFrame(main_area)
        browser_header.pack(fill="x", padx=5, pady=5)

        browser_title = ctk.CTkLabel(
            browser_header,
            text="🗂️ Media Library",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        browser_title.pack(side="left", padx=10, pady=10)

        # Quick search
        self.quick_search = QuickSearchBar(
            browser_header,
            search_callback=self._on_quick_search
        ) if HAS_ENHANCED_GUI else None

        if self.quick_search:
            self.quick_search.pack(side="right", padx=10, pady=10)

        # Media browser frame
        media_frame = ctk.CTkFrame(main_area)
        media_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # Enhanced media browser or fallback
        if HAS_ENHANCED_GUI:
            self.media_browser = EnhancedMediaBrowser(
                media_frame,
                library_manager=self.library_manager,
                player_callback=self._play_track
            )
            self.media_browser.pack(fill="both", expand=True, padx=5, pady=5)
        else:
            # Fallback simple browser
            fallback_label = ctk.CTkLabel(
                media_frame,
                text="Enhanced media browser not available\nFalling back to basic mode",
                font=ctk.CTkFont(size=14),
                text_color="#888888"
            )
            fallback_label.pack(expand=True)

    def create_info_panel(self, parent):
        """Create right info panel with track details and controls"""
        info_panel = ctk.CTkFrame(parent, width=250)
        info_panel.pack(side="right", fill="y")
        info_panel.pack_propagate(False)

        # Track details
        details_header = ctk.CTkLabel(
            info_panel,
            text="🎵 Track Details",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        details_header.pack(pady=(10, 5))

        self.details_frame = ctk.CTkScrollableFrame(info_panel, height=300)
        self.details_frame.pack(fill="x", padx=5, pady=(0, 10))

        self.details_content = ctk.CTkLabel(
            self.details_frame,
            text="Select a track to view details",
            font=ctk.CTkFont(size=11),
            justify="left",
            anchor="nw"
        )
        self.details_content.pack(fill="x", padx=10, pady=10)

        # Mastering controls
        mastering_header = ctk.CTkLabel(
            info_panel,
            text="🎛️ Mastering",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        mastering_header.pack(pady=(10, 5))

        mastering_frame = ctk.CTkFrame(info_panel)
        mastering_frame.pack(fill="x", padx=5, pady=(0, 10))

        # Auto mastering toggle
        self.auto_master_switch = ctk.CTkSwitch(
            mastering_frame,
            text="Auto Mastering",
            command=self._toggle_auto_mastering
        )
        self.auto_master_switch.pack(padx=10, pady=10)

        # Profile selector
        profile_frame = ctk.CTkFrame(mastering_frame, fg_color="transparent")
        profile_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(profile_frame, text="Profile:", font=ctk.CTkFont(size=11)).pack(anchor="w")

        self.profile_var = ctk.StringVar(value="balanced")
        self.profile_menu = ctk.CTkOptionMenu(
            profile_frame,
            variable=self.profile_var,
            values=["balanced", "warm", "bright", "punchy", "vintage"],
            command=self._on_profile_change
        )
        self.profile_menu.pack(fill="x", pady=(2, 0))

        # Audio metrics
        metrics_header = ctk.CTkLabel(
            info_panel,
            text="📊 Audio Metrics",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        metrics_header.pack(pady=(10, 5))

        self.metrics_frame = ctk.CTkFrame(info_panel)
        self.metrics_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        self.metrics_content = ctk.CTkLabel(
            self.metrics_frame,
            text="No audio loaded",
            font=ctk.CTkFont(size=11),
            justify="left"
        )
        self.metrics_content.pack(padx=10, pady=10)

    def initialize_audio_system(self):
        """Initialize the audio system"""
        if not HAS_AURALIS:
            self.status_bar.configure(
                text="❌ Auralis library not available - Enhanced features disabled"
            )
            return

        try:
            # Create library manager
            self.library_manager = LibraryManager()

            # Update media browser with library manager
            if self.media_browser:
                self.media_browser.set_library_manager(self.library_manager)

            # Create enhanced player
            config = PlayerConfig(
                sample_rate=44100,
                buffer_size=2048,
                enable_level_matching=True,
                enable_auto_mastering=True
            )

            self.player = EnhancedAudioPlayer(config, self.library_manager)

            self.status_bar.configure(
                text="✅ Enhanced Auralis system initialized - Ready for professional audio management"
            )

            # Load initial library stats
            self._update_library_stats()

        except Exception as e:
            self.status_bar.configure(
                text=f"❌ Failed to initialize audio system: {e}"
            )
            print(f"Audio system initialization error: {e}")

    def _update_library_stats(self):
        """Update library statistics display"""
        if not self.library_manager:
            return

        try:
            stats = self.library_manager.get_library_stats()

            # Handle both dict and object responses
            if hasattr(stats, 'to_dict'):
                stats_data = stats.to_dict()
            else:
                stats_data = stats

            stats_text = f"""Tracks: {stats_data.get('total_tracks', 0):,}
Artists: {stats_data.get('total_artists', 0):,}
Albums: {stats_data.get('total_albums', 0):,}
Genres: {stats_data.get('total_genres', 0):,}
Playlists: {stats_data.get('total_playlists', 0):,}

Duration: {stats_data.get('total_duration_formatted', 'Unknown')}
Size: {stats_data.get('total_filesize_gb', 0):.1f} GB

Avg Quality: {stats_data.get('avg_mastering_quality', 0):.1%}"""

            self.stats_label.configure(text=stats_text)

        except Exception as e:
            self.stats_label.configure(text=f"Stats unavailable: {e}")

    def _play_track(self, track_id: int):
        """Play a track from the library"""
        if not self.player:
            messagebox.showerror("Error", "Audio player not available")
            return

        try:
            success = self.player.load_track_from_library(track_id)
            if success:
                self.player.play()
                self.status_bar.configure(text=f"🎵 Playing track ID: {track_id}")

                # Update now playing info
                if self.library_manager:
                    track = self.library_manager.get_track(track_id)
                    if track:
                        self._update_now_playing(track)
            else:
                messagebox.showerror("Error", f"Failed to load track {track_id}")

        except Exception as e:
            messagebox.showerror("Error", f"Playback error: {e}")

    def _update_now_playing(self, track):
        """Update now playing display"""
        try:
            # Convert track to dict if needed
            if hasattr(track, 'to_dict'):
                track_data = track.to_dict()
            else:
                track_data = track

            title = track_data.get('title', 'Unknown Title')
            artists = track_data.get('artists', [])
            artist_text = ', '.join(artists) if artists else 'Unknown Artist'

            self.track_title_label.configure(text=title)
            self.track_artist_label.configure(text=artist_text)

            # Update track details
            details_text = f"""Title: {title}
Artist: {artist_text}
Album: {track_data.get('album', 'Unknown')}
Duration: {track_data.get('duration', 0):.1f}s
Format: {track_data.get('format', 'Unknown')}
Sample Rate: {track_data.get('sample_rate', 0)} Hz
Channels: {track_data.get('channels', 0)}

Quality Score: {track_data.get('mastering_quality', 0):.1%}
Play Count: {track_data.get('play_count', 0)}"""

            self.details_content.configure(text=details_text)

        except Exception as e:
            print(f"Error updating now playing: {e}")

    def _toggle_play(self):
        """Toggle play/pause"""
        if not self.player:
            return

        try:
            info = self.player.get_playback_info()
            if info.get('state') == 'playing':
                self.player.pause()
                self.play_btn.configure(text="▶️")
            else:
                self.player.play()
                self.play_btn.configure(text="⏸️")
        except Exception as e:
            print(f"Playback toggle error: {e}")

    def _stop(self):
        """Stop playback"""
        if self.player:
            try:
                self.player.stop()
                self.play_btn.configure(text="▶️")
                self.track_title_label.configure(text="No track loaded")
                self.track_artist_label.configure(text="")
                self.details_content.configure(text="Select a track to view details")
            except Exception as e:
                print(f"Stop error: {e}")

    def _on_volume_change(self, value):
        """Handle volume change"""
        volume_percent = int(float(value) * 100)
        self.volume_label.configure(text=f"{volume_percent}%")
        # Note: Volume control would be implemented in the audio player

    def _toggle_auto_mastering(self):
        """Toggle auto mastering"""
        if self.player:
            enabled = self.auto_master_switch.get()
            # Note: This would toggle auto mastering in the player
            status = "enabled" if enabled else "disabled"
            self.status_bar.configure(text=f"Auto mastering {status}")

    def _on_profile_change(self, value):
        """Handle mastering profile change"""
        if self.player:
            # Note: This would change the mastering profile
            self.status_bar.configure(text=f"Mastering profile: {value}")

    def _quick_scan_library(self):
        """Quick library scan"""
        folder = filedialog.askdirectory(title="Select Music Folder to Scan")
        if folder and self.library_manager:
            self.status_bar.configure(text=f"Scanning {folder}...")
            # Note: Implement background scanning
            messagebox.showinfo("Scan Started", f"Scanning {folder} in background...")

    def _show_advanced_search(self):
        """Show advanced search window"""
        if not HAS_ENHANCED_GUI:
            messagebox.showinfo("Not Available", "Enhanced search components not loaded")
            return

        if not self.advanced_search:
            self.advanced_search = AdvancedSearchWindow(
                self,
                library_manager=self.library_manager,
                result_callback=self._on_search_result
            )
        self.advanced_search.show()

    def _show_playlist_manager(self):
        """Show playlist manager window"""
        if not HAS_ENHANCED_GUI:
            messagebox.showinfo("Not Available", "Enhanced playlist components not loaded")
            return

        if not self.playlist_manager:
            self.playlist_manager = PlaylistManagerWindow(
                self,
                library_manager=self.library_manager,
                player_callback=self._play_track
            )
        self.playlist_manager.show()

    def _on_quick_search(self, query):
        """Handle quick search"""
        if self.media_browser and hasattr(self.media_browser, 'search'):
            self.media_browser.search(query)

    def _on_search_result(self, results):
        """Handle search results"""
        if self.media_browser and hasattr(self.media_browser, 'show_search_results'):
            self.media_browser.show_search_results(results)

    def start_update_loop(self):
        """Start the GUI update loop"""
        self.update_running = True
        self.update_gui()

    def update_gui(self):
        """Update GUI with current player state"""
        if self.update_running:
            try:
                # Update library stats periodically (every 30 seconds)
                import time
                if not hasattr(self, '_last_stats_update'):
                    self._last_stats_update = 0

                if time.time() - self._last_stats_update > 30:
                    self._update_library_stats()
                    self._last_stats_update = time.time()

                # Update player state
                if self.player:
                    info = self.player.get_playback_info()
                    state = info.get('state', 'stopped')

                    if state == 'playing':
                        self.play_btn.configure(text="⏸️")
                    else:
                        self.play_btn.configure(text="▶️")

            except Exception as e:
                print(f"GUI update error: {e}")

        # Schedule next update
        if self.update_running:
            self.after(1000, self.update_gui)  # 1 second intervals

    def on_closing(self):
        """Handle window closing"""
        self.update_running = False
        if self.player:
            try:
                self.player.cleanup()
            except:
                pass
        self.destroy()


def main():
    """Main application entry point"""
    print("🎵 Starting Enhanced Auralis GUI...")

    app = EnhancedAuralisGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()