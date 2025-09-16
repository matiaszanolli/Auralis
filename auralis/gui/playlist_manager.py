#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced Playlist Manager
~~~~~~~~~~~~~~~~~~~~~~~~

Advanced playlist management with smart playlists, drag-and-drop organization,
and mastering profiles.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Dict, List, Optional, Callable, Any
import json
import threading
from datetime import datetime, timedelta


class SmartPlaylistBuilder(ctk.CTkToplevel):
    """Smart playlist builder with criteria editor"""

    def __init__(self, parent, callback=None):
        super().__init__(parent)
        self.callback = callback
        self.criteria = []

        self.title("Smart Playlist Builder")
        self.geometry("600x500")
        self.resizable(True, True)

        self.setup_ui()

    def setup_ui(self):
        """Setup smart playlist builder UI"""
        # Header
        header = ctk.CTkLabel(self, text="🧠 Smart Playlist Builder",
                            font=ctk.CTkFont(size=18, weight="bold"))
        header.pack(pady=10)

        # Playlist name
        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(name_frame, text="Playlist Name:").pack(side="left")
        self.name_entry = ctk.CTkEntry(name_frame, placeholder_text="My Smart Playlist", width=200)
        self.name_entry.pack(side="left", padx=(10, 0))

        # Criteria section
        criteria_label = ctk.CTkLabel(self, text="Criteria (All conditions must be met):",
                                    font=ctk.CTkFont(size=14, weight="bold"))
        criteria_label.pack(anchor="w", padx=20, pady=(20, 5))

        # Criteria list
        self.criteria_frame = ctk.CTkScrollableFrame(self, height=200)
        self.criteria_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Add criteria button
        add_btn = ctk.CTkButton(self, text="+ Add Criteria", command=self._add_criteria)
        add_btn.pack(pady=5)

        # Preview section
        preview_label = ctk.CTkLabel(self, text="Preview:",
                                   font=ctk.CTkFont(size=14, weight="bold"))
        preview_label.pack(anchor="w", padx=20, pady=(20, 5))

        self.preview_label = ctk.CTkLabel(self, text="No criteria set - will include all tracks",
                                        font=ctk.CTkFont(size=11), text_color="#888888")
        self.preview_label.pack(anchor="w", padx=20)

        # Buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=20)

        cancel_btn = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy)
        cancel_btn.pack(side="right", padx=(5, 0))

        create_btn = ctk.CTkButton(button_frame, text="Create Playlist", command=self._create_playlist)
        create_btn.pack(side="right")

        # Add initial criteria
        self._add_criteria()

    def _add_criteria(self):
        """Add a new criteria row"""
        criteria_row = ctk.CTkFrame(self.criteria_frame)
        criteria_row.pack(fill="x", pady=2)

        # Field selection
        field_var = ctk.StringVar(value="Artist")
        field_menu = ctk.CTkOptionMenu(
            criteria_row, variable=field_var, width=100,
            values=["Artist", "Album", "Genre", "Year", "Duration", "Play Count", "Quality", "Favorite"]
        )
        field_menu.pack(side="left", padx=5)

        # Operator selection
        operator_var = ctk.StringVar(value="contains")
        operator_menu = ctk.CTkOptionMenu(
            criteria_row, variable=operator_var, width=100,
            values=["contains", "is", "is not", "starts with", "ends with", ">", "<", ">=", "<="]
        )
        operator_menu.pack(side="left", padx=5)

        # Value entry
        value_entry = ctk.CTkEntry(criteria_row, placeholder_text="Value", width=150)
        value_entry.pack(side="left", padx=5)

        # Remove button
        remove_btn = ctk.CTkButton(criteria_row, text="✕", width=30, command=lambda: self._remove_criteria(criteria_row))
        remove_btn.pack(side="right", padx=5)

        # Store criteria data
        criteria_data = {
            'frame': criteria_row,
            'field': field_var,
            'operator': operator_var,
            'value': value_entry
        }
        self.criteria.append(criteria_data)

        self._update_preview()

    def _remove_criteria(self, criteria_frame):
        """Remove a criteria row"""
        # Find and remove from criteria list
        self.criteria = [c for c in self.criteria if c['frame'] != criteria_frame]
        criteria_frame.destroy()
        self._update_preview()

    def _update_preview(self):
        """Update the preview text"""
        if not self.criteria:
            self.preview_label.configure(text="No criteria set - will include all tracks")
            return

        preview_parts = []
        for criteria in self.criteria:
            field = criteria['field'].get()
            operator = criteria['operator'].get()
            value = criteria['value'].get()

            if value:
                preview_parts.append(f"{field} {operator} '{value}'")

        if preview_parts:
            preview_text = " AND ".join(preview_parts)
            self.preview_label.configure(text=preview_text)
        else:
            self.preview_label.configure(text="Enter values to see preview")

    def _create_playlist(self):
        """Create the smart playlist"""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a playlist name")
            return

        # Build criteria JSON
        criteria_data = []
        for criteria in self.criteria:
            value = criteria['value'].get().strip()
            if value:
                criteria_data.append({
                    'field': criteria['field'].get(),
                    'operator': criteria['operator'].get(),
                    'value': value
                })

        playlist_data = {
            'name': name,
            'is_smart': True,
            'criteria': criteria_data
        }

        if self.callback:
            self.callback(playlist_data)

        self.destroy()


class PlaylistTrackList(ctk.CTkScrollableFrame):
    """Track list for playlist with drag-and-drop reordering"""

    def __init__(self, master, callback_manager=None, **kwargs):
        super().__init__(master, **kwargs)
        self.callback_manager = callback_manager
        self.tracks = []
        self.drag_data = None

        self.setup_ui()

    def setup_ui(self):
        """Setup track list UI"""
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="#2B2B2B", height=30)
        header_frame.pack(fill="x", padx=5, pady=(5, 0))
        header_frame.pack_propagate(False)

        # Column headers
        headers = [
            ("#", 30),
            ("Title", 200),
            ("Artist", 150),
            ("Duration", 80),
            ("", 30),  # Remove button
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
            text="🎵 No tracks in playlist\n\nDrag tracks here or use 'Add Tracks' button",
            font=ctk.CTkFont(size=12), text_color="#666666"
        )
        self.empty_label.pack(expand=True, pady=30)

    def update_tracks(self, tracks):
        """Update the track list"""
        self.tracks = tracks

        # Clear existing tracks
        for widget in self.tracks_container.winfo_children():
            widget.destroy()

        if not tracks:
            self.empty_label = ctk.CTkLabel(
                self.tracks_container,
                text="🎵 No tracks in playlist\n\nDrag tracks here or use 'Add Tracks' button",
                font=ctk.CTkFont(size=12), text_color="#666666"
            )
            self.empty_label.pack(expand=True, pady=30)
            return

        # Create track rows
        for i, track in enumerate(tracks):
            track_row = self._create_track_row(track, i)
            track_row.pack(fill="x", pady=1)

    def _create_track_row(self, track, index):
        """Create a track row widget"""
        row_color = "#1F1F1F" if index % 2 == 0 else "#242424"
        row = ctk.CTkFrame(self.tracks_container, fg_color=row_color, height=35)
        row.pack_propagate(False)

        # Track number
        num_label = ctk.CTkLabel(
            row, text=str(index + 1),
            font=ctk.CTkFont(size=10),
            width=30, anchor="center"
        )
        num_label.place(x=5, y=8)

        # Title
        title_label = ctk.CTkLabel(
            row, text=track.get('title', 'Unknown'),
            font=ctk.CTkFont(size=11),
            width=200, anchor="w"
        )
        title_label.place(x=40, y=8)

        # Artist
        artists = track.get('artists', [])
        artist_text = ', '.join(artists) if artists else 'Unknown Artist'
        artist_label = ctk.CTkLabel(
            row, text=artist_text,
            font=ctk.CTkFont(size=10),
            text_color="#CCCCCC",
            width=150, anchor="w"
        )
        artist_label.place(x=250, y=8)

        # Duration
        duration = track.get('duration', 0)
        duration_text = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "--:--"
        duration_label = ctk.CTkLabel(
            row, text=duration_text,
            font=ctk.CTkFont(size=10),
            text_color="#CCCCCC",
            width=80, anchor="w"
        )
        duration_label.place(x=410, y=8)

        # Remove button
        remove_btn = ctk.CTkButton(
            row, text="✕", width=25, height=20,
            command=lambda: self._remove_track(track, index)
        )
        remove_btn.place(x=500, y=7)

        # Drag and drop functionality
        row.bind("<Button-1>", lambda e: self._start_drag(e, track, index))
        row.bind("<B1-Motion>", self._on_drag)
        row.bind("<ButtonRelease-1>", self._end_drag)

        return row

    def _start_drag(self, event, track, index):
        """Start drag operation"""
        self.drag_data = {
            'track': track,
            'index': index,
            'start_y': event.y_root
        }

    def _on_drag(self, event):
        """Handle drag motion"""
        if self.drag_data:
            # Visual feedback could be added here
            pass

    def _end_drag(self, event):
        """End drag operation and reorder if needed"""
        if not self.drag_data:
            return

        # Calculate new position based on mouse position
        y_offset = event.y_root - self.drag_data['start_y']
        row_height = 36  # Approximate row height
        position_change = round(y_offset / row_height)

        old_index = self.drag_data['index']
        new_index = max(0, min(len(self.tracks) - 1, old_index + position_change))

        if new_index != old_index:
            # Reorder tracks
            track = self.tracks.pop(old_index)
            self.tracks.insert(new_index, track)

            # Update display
            self.update_tracks(self.tracks)

            # Notify callback
            if self.callback_manager:
                self.callback_manager('tracks_reordered', self.tracks)

        self.drag_data = None

    def _remove_track(self, track, index):
        """Remove track from playlist"""
        if self.callback_manager:
            self.callback_manager('track_removed', {'track': track, 'index': index})


class PlaylistManagerWindow(ctk.CTkToplevel):
    """Enhanced playlist manager window"""

    def __init__(self, parent, library_manager=None, player_callback=None):
        super().__init__(parent)
        self.library_manager = library_manager
        self.player_callback = player_callback
        self.current_playlist = None

        self.title("Playlist Manager")
        self.geometry("900x600")
        self.resizable(True, True)

        self.setup_ui()
        self.load_playlists()

    def setup_ui(self):
        """Setup playlist manager UI"""
        # Main container
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Left panel - Playlist list
        left_panel = ctk.CTkFrame(main_container, width=250)
        left_panel.pack(side="left", fill="y", padx=(0, 5))
        left_panel.pack_propagate(False)

        # Playlist list header
        list_header = ctk.CTkFrame(left_panel, fg_color="transparent")
        list_header.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(list_header, text="📋 Playlists",
                    font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")

        # Playlist controls
        controls_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        controls_frame.pack(fill="x", padx=10, pady=(0, 10))

        new_btn = ctk.CTkButton(controls_frame, text="+ New", width=70, command=self._create_playlist)
        new_btn.pack(side="left", padx=(0, 5))

        smart_btn = ctk.CTkButton(controls_frame, text="🧠 Smart", width=70, command=self._create_smart_playlist)
        smart_btn.pack(side="left")

        # Playlist list
        self.playlist_frame = ctk.CTkScrollableFrame(left_panel)
        self.playlist_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Right panel - Playlist details
        right_panel = ctk.CTkFrame(main_container)
        right_panel.pack(side="right", fill="both", expand=True)

        # Playlist info header
        self.info_frame = ctk.CTkFrame(right_panel, height=100)
        self.info_frame.pack(fill="x", padx=10, pady=10)
        self.info_frame.pack_propagate(False)

        # Playlist name and stats
        self.playlist_title = ctk.CTkLabel(
            self.info_frame, text="Select a playlist",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.playlist_title.pack(anchor="w", padx=15, pady=(15, 5))

        self.playlist_stats = ctk.CTkLabel(
            self.info_frame, text="",
            font=ctk.CTkFont(size=12), text_color="#888888"
        )
        self.playlist_stats.pack(anchor="w", padx=15)

        # Playlist controls
        controls_right = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        controls_right.pack(side="right", padx=15, pady=15)

        self.play_all_btn = ctk.CTkButton(controls_right, text="▶️ Play All", command=self._play_all)
        self.play_all_btn.pack(side="top", pady=2)

        self.shuffle_btn = ctk.CTkButton(controls_right, text="🔀 Shuffle", command=self._shuffle_play)
        self.shuffle_btn.pack(side="top", pady=2)

        # Track management
        track_controls = ctk.CTkFrame(right_panel, fg_color="transparent")
        track_controls.pack(fill="x", padx=10, pady=(0, 5))

        add_tracks_btn = ctk.CTkButton(track_controls, text="+ Add Tracks", command=self._add_tracks)
        add_tracks_btn.pack(side="left", padx=5)

        remove_duplicates_btn = ctk.CTkButton(track_controls, text="Remove Duplicates", command=self._remove_duplicates)
        remove_duplicates_btn.pack(side="left", padx=5)

        clear_btn = ctk.CTkButton(track_controls, text="Clear All", command=self._clear_playlist)
        clear_btn.pack(side="right", padx=5)

        # Track list
        self.track_list = PlaylistTrackList(right_panel, callback_manager=self._handle_track_callback)
        self.track_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def load_playlists(self):
        """Load playlists from database"""
        if not self.library_manager:
            return

        # Clear existing playlist widgets
        for widget in self.playlist_frame.winfo_children():
            widget.destroy()

        try:
            playlists = self.library_manager.get_all_playlists()

            if not playlists:
                empty_label = ctk.CTkLabel(
                    self.playlist_frame,
                    text="No playlists yet\n\nCreate your first playlist!",
                    font=ctk.CTkFont(size=12), text_color="#666666"
                )
                empty_label.pack(expand=True, pady=30)
                return

            for playlist in playlists:
                self._create_playlist_item(playlist)

        except Exception as e:
            print(f"Error loading playlists: {e}")

    def _create_playlist_item(self, playlist):
        """Create a playlist item widget"""
        playlist_data = playlist.to_dict()

        item_frame = ctk.CTkFrame(self.playlist_frame, height=60)
        item_frame.pack(fill="x", pady=2)
        item_frame.pack_propagate(False)

        # Playlist info
        info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        info_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Name and type
        name_text = playlist_data['name']
        if playlist_data['is_smart']:
            name_text += " 🧠"

        name_label = ctk.CTkLabel(
            info_frame, text=name_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        name_label.pack(fill="x")

        # Stats
        track_count = playlist_data['track_count']
        duration = playlist_data['total_duration']
        duration_text = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "0:00"

        stats_text = f"{track_count} tracks • {duration_text}"
        stats_label = ctk.CTkLabel(
            info_frame, text=stats_text,
            font=ctk.CTkFont(size=10),
            text_color="#888888", anchor="w"
        )
        stats_label.pack(fill="x")

        # Click handler
        def on_select(event=None):
            self._select_playlist(playlist_data)

        # Make clickable
        item_frame.bind("<Button-1>", on_select)
        info_frame.bind("<Button-1>", on_select)
        name_label.bind("<Button-1>", on_select)
        stats_label.bind("<Button-1>", on_select)

        # Context menu
        def show_context_menu(event):
            context_menu = tk.Menu(self, tearoff=0)
            context_menu.add_command(label="Rename", command=lambda: self._rename_playlist(playlist_data))
            context_menu.add_command(label="Duplicate", command=lambda: self._duplicate_playlist(playlist_data))
            context_menu.add_separator()
            context_menu.add_command(label="Delete", command=lambda: self._delete_playlist(playlist_data))

            context_menu.tk_popup(event.x_root, event.y_root)

        item_frame.bind("<Button-3>", show_context_menu)

    def _select_playlist(self, playlist_data):
        """Select and display playlist"""
        self.current_playlist = playlist_data

        # Update info display
        self.playlist_title.configure(text=playlist_data['name'])

        track_count = playlist_data['track_count']
        duration = playlist_data['total_duration']
        duration_text = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "0:00"

        stats_text = f"{track_count} tracks • {duration_text}"
        if playlist_data['is_smart']:
            stats_text += " • Smart Playlist"

        self.playlist_stats.configure(text=stats_text)

        # Load tracks
        self._load_playlist_tracks()

    def _load_playlist_tracks(self):
        """Load tracks for current playlist"""
        if not self.current_playlist or not self.library_manager:
            return

        try:
            playlist_id = self.current_playlist['id']
            tracks = self.library_manager.get_playlist_tracks(playlist_id)
            tracks_data = [track.to_dict() for track in tracks]

            self.track_list.update_tracks(tracks_data)

        except Exception as e:
            print(f"Error loading playlist tracks: {e}")

    def _create_playlist(self):
        """Create a new regular playlist"""
        name = simpledialog.askstring("New Playlist", "Enter playlist name:")
        if name:
            try:
                playlist = self.library_manager.create_playlist(name)
                self.load_playlists()
                self._select_playlist(playlist.to_dict())
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create playlist: {e}")

    def _create_smart_playlist(self):
        """Create a new smart playlist"""
        builder = SmartPlaylistBuilder(self, callback=self._on_smart_playlist_created)

    def _on_smart_playlist_created(self, playlist_data):
        """Handle smart playlist creation"""
        try:
            criteria_json = json.dumps(playlist_data['criteria'])
            playlist = self.library_manager.create_smart_playlist(
                playlist_data['name'], criteria_json
            )
            self.load_playlists()
            self._select_playlist(playlist.to_dict())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create smart playlist: {e}")

    def _rename_playlist(self, playlist_data):
        """Rename playlist"""
        new_name = simpledialog.askstring("Rename Playlist", "Enter new name:", initialvalue=playlist_data['name'])
        if new_name and new_name != playlist_data['name']:
            try:
                self.library_manager.rename_playlist(playlist_data['id'], new_name)
                self.load_playlists()
                # Update current selection if it's the renamed playlist
                if self.current_playlist and self.current_playlist['id'] == playlist_data['id']:
                    self.current_playlist['name'] = new_name
                    self.playlist_title.configure(text=new_name)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename playlist: {e}")

    def _duplicate_playlist(self, playlist_data):
        """Duplicate playlist"""
        new_name = f"{playlist_data['name']} Copy"
        try:
            new_playlist = self.library_manager.duplicate_playlist(playlist_data['id'], new_name)
            self.load_playlists()
            self._select_playlist(new_playlist.to_dict())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to duplicate playlist: {e}")

    def _delete_playlist(self, playlist_data):
        """Delete playlist"""
        if messagebox.askyesno("Delete Playlist", f"Are you sure you want to delete '{playlist_data['name']}'?"):
            try:
                self.library_manager.delete_playlist(playlist_data['id'])
                self.load_playlists()
                # Clear selection if deleted playlist was selected
                if self.current_playlist and self.current_playlist['id'] == playlist_data['id']:
                    self.current_playlist = None
                    self.playlist_title.configure(text="Select a playlist")
                    self.playlist_stats.configure(text="")
                    self.track_list.update_tracks([])
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete playlist: {e}")

    def _add_tracks(self):
        """Add tracks to current playlist"""
        if not self.current_playlist:
            messagebox.showwarning("No Playlist", "Please select a playlist first")
            return

        # TODO: Implement track selection dialog
        messagebox.showinfo("Add Tracks", "Track selection dialog coming soon!")

    def _remove_duplicates(self):
        """Remove duplicate tracks from playlist"""
        if not self.current_playlist:
            return

        try:
            removed_count = self.library_manager.remove_playlist_duplicates(self.current_playlist['id'])
            self._load_playlist_tracks()
            messagebox.showinfo("Duplicates Removed", f"Removed {removed_count} duplicate tracks")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove duplicates: {e}")

    def _clear_playlist(self):
        """Clear all tracks from playlist"""
        if not self.current_playlist:
            return

        if messagebox.askyesno("Clear Playlist", "Remove all tracks from this playlist?"):
            try:
                self.library_manager.clear_playlist(self.current_playlist['id'])
                self._load_playlist_tracks()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear playlist: {e}")

    def _play_all(self):
        """Play all tracks in playlist"""
        if not self.current_playlist or not self.player_callback:
            return

        try:
            tracks = self.library_manager.get_playlist_tracks(self.current_playlist['id'])
            if tracks:
                # Play first track and queue the rest
                first_track = tracks[0].to_dict()
                self.player_callback(first_track)
                # TODO: Queue remaining tracks
        except Exception as e:
            print(f"Error playing playlist: {e}")

    def _shuffle_play(self):
        """Shuffle and play playlist"""
        if not self.current_playlist or not self.player_callback:
            return

        try:
            tracks = self.library_manager.get_playlist_tracks(self.current_playlist['id'])
            if tracks:
                import random
                shuffled_tracks = tracks.copy()
                random.shuffle(shuffled_tracks)

                # Play first shuffled track
                first_track = shuffled_tracks[0].to_dict()
                self.player_callback(first_track)
                # TODO: Queue remaining shuffled tracks
        except Exception as e:
            print(f"Error shuffling playlist: {e}")

    def _handle_track_callback(self, event_type, data=None):
        """Handle track list callbacks"""
        if event_type == 'track_removed':
            track_id = data['track']['id']
            try:
                self.library_manager.remove_track_from_playlist(self.current_playlist['id'], track_id)
                self._load_playlist_tracks()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to remove track: {e}")

        elif event_type == 'tracks_reordered':
            # TODO: Implement track reordering in database
            pass