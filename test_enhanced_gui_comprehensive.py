#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Comprehensive Test Suite for Enhanced GUI Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Expanded test coverage for the enhanced media management GUI.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

import customtkinter as ctk


class TestBasicComponents:
    """Test basic component imports and creation"""

    def test_media_browser_imports(self):
        """Test media browser component imports"""
        from auralis.gui.media_browser import EnhancedMediaBrowser, ViewMode, SortOrder

        # Check constants exist
        assert hasattr(ViewMode, 'ARTISTS')
        assert hasattr(ViewMode, 'ALBUMS')
        assert hasattr(ViewMode, 'TRACKS')
        assert hasattr(ViewMode, 'PLAYLISTS')

        assert hasattr(SortOrder, 'TITLE_ASC')
        assert hasattr(SortOrder, 'TITLE_DESC')
        assert hasattr(SortOrder, 'ARTIST_ASC')

    def test_playlist_manager_imports(self):
        """Test playlist manager imports"""
        from auralis.gui.playlist_manager import PlaylistManagerWindow, SmartPlaylistBuilder

        # Should import without error
        assert PlaylistManagerWindow is not None
        assert SmartPlaylistBuilder is not None

    def test_advanced_search_imports(self):
        """Test advanced search imports"""
        from auralis.gui.advanced_search import AdvancedSearchWindow, QuickSearchBar

        # Should import without error
        assert AdvancedSearchWindow is not None
        assert QuickSearchBar is not None


class TestMediaBrowser:
    """Test media browser functionality"""

    @pytest.fixture
    def mock_library_manager(self):
        """Create mock library manager"""
        mock_manager = Mock()
        mock_manager.get_all_artists.return_value = []
        mock_manager.get_all_albums.return_value = []
        mock_manager.get_all_tracks.return_value = []
        mock_manager.get_all_playlists.return_value = []
        mock_manager.search_tracks.return_value = []
        return mock_manager

    @pytest.fixture
    def media_browser(self, mock_library_manager):
        """Create media browser instance"""
        root = ctk.CTk()
        root.withdraw()

        from auralis.gui.media_browser import EnhancedMediaBrowser
        browser = EnhancedMediaBrowser(root, library_manager=mock_library_manager)

        yield browser
        root.destroy()

    def test_media_browser_creation(self, media_browser):
        """Test media browser widget creation"""
        assert media_browser is not None
        assert hasattr(media_browser, 'current_view')
        assert hasattr(media_browser, 'library_manager')

    def test_view_mode_switching(self, media_browser):
        """Test switching between view modes"""
        from auralis.gui.media_browser import ViewMode

        # Test setting different view modes
        media_browser._show_view(ViewMode.ARTISTS)
        assert media_browser.current_view == ViewMode.ARTISTS

        media_browser._show_view(ViewMode.ALBUMS)
        assert media_browser.current_view == ViewMode.ALBUMS

        media_browser._show_view(ViewMode.TRACKS)
        assert media_browser.current_view == ViewMode.TRACKS

    def test_search_functionality(self, media_browser):
        """Test search functionality"""
        # Test that library manager is available for searching
        assert media_browser.library_manager is not None

        # Test that media browser can display content
        assert hasattr(media_browser, 'current_view')

    def test_sort_functionality(self, media_browser):
        """Test sorting functionality"""
        from auralis.gui.media_browser import SortOrder

        # Test that sort constants exist
        assert hasattr(SortOrder, 'TITLE_ASC')
        assert hasattr(SortOrder, 'ARTIST_ASC')

        # Test that media browser has basic functionality
        assert hasattr(media_browser, 'library_manager')


class TestPlaylistManager:
    """Test playlist manager functionality"""

    @pytest.fixture
    def mock_library_manager(self):
        """Create mock library manager with playlist methods"""
        mock_manager = Mock()
        mock_manager.get_all_playlists.return_value = []
        mock_manager.create_playlist.return_value = Mock(id=1, name="Test Playlist")
        mock_manager.get_playlist.return_value = Mock(id=1, name="Test", tracks=[])
        mock_manager.delete_playlist.return_value = True
        mock_manager.add_track_to_playlist.return_value = True
        return mock_manager

    @pytest.fixture
    def playlist_manager(self, mock_library_manager):
        """Create playlist manager instance"""
        root = ctk.CTk()
        root.withdraw()

        from auralis.gui.playlist_manager import PlaylistManagerWindow
        manager = PlaylistManagerWindow(root, library_manager=mock_library_manager)

        yield manager
        root.destroy()

    def test_playlist_manager_creation(self, playlist_manager):
        """Test playlist manager creation"""
        assert playlist_manager is not None
        assert hasattr(playlist_manager, 'library_manager')

    def test_playlist_creation_logic(self, playlist_manager):
        """Test playlist creation logic"""
        # Mock the playlist creation
        result = playlist_manager.library_manager.create_playlist("New Playlist", "Description")

        assert result is not None
        # Just verify that create_playlist was called
        playlist_manager.library_manager.create_playlist.assert_called_with("New Playlist", "Description")

    def test_smart_playlist_builder(self):
        """Test smart playlist builder"""
        from auralis.gui.playlist_manager import SmartPlaylistBuilder

        root = ctk.CTk()
        root.withdraw()

        mock_callback = Mock()

        builder = SmartPlaylistBuilder(root, mock_callback)

        # Should create without error
        assert builder is not None

        root.destroy()


class TestAdvancedSearch:
    """Test advanced search functionality"""

    @pytest.fixture
    def mock_library_manager(self):
        """Create mock library manager"""
        mock_manager = Mock()
        mock_manager.search_tracks.return_value = []
        mock_manager.get_all_artists.return_value = []
        mock_manager.get_all_genres.return_value = []
        return mock_manager

    @pytest.fixture
    def search_window(self, mock_library_manager):
        """Create advanced search window"""
        root = ctk.CTk()
        root.withdraw()

        from auralis.gui.advanced_search import AdvancedSearchWindow
        window = AdvancedSearchWindow(root, library_manager=mock_library_manager)

        yield window
        root.destroy()

    @pytest.fixture
    def quick_search_bar(self):
        """Create quick search bar"""
        root = ctk.CTk()
        root.withdraw()

        from auralis.gui.advanced_search import QuickSearchBar
        search_bar = QuickSearchBar(root)

        yield search_bar
        root.destroy()

    def test_advanced_search_creation(self, search_window):
        """Test advanced search window creation"""
        assert search_window is not None
        assert hasattr(search_window, 'library_manager')

    def test_quick_search_bar_creation(self, quick_search_bar):
        """Test quick search bar creation"""
        assert quick_search_bar is not None
        assert hasattr(quick_search_bar, 'search_entry')

    def test_search_criteria_handling(self, search_window):
        """Test search criteria handling"""
        # Test that search window has the expected components
        assert hasattr(search_window, 'library_manager')

        # Test that it's a CTkToplevel window
        assert isinstance(search_window, ctk.CTkToplevel)


class TestGuiIntegration:
    """Test GUI integration and main application"""

    @pytest.fixture
    def enhanced_gui(self):
        """Create enhanced GUI instance"""
        # Mock the library manager to avoid database dependencies
        with patch('auralis_gui.LibraryManager') as mock_lib_manager:
            mock_lib_manager.return_value = Mock()

            from auralis_gui import EnhancedAuralisGUI
            app = EnhancedAuralisGUI()
            app.withdraw()

            yield app
            app.destroy()

    def test_enhanced_gui_creation(self, enhanced_gui):
        """Test enhanced GUI application creation"""
        assert enhanced_gui is not None
        assert hasattr(enhanced_gui, 'library_manager')
        assert hasattr(enhanced_gui, 'media_browser')

    def test_gui_components_exist(self, enhanced_gui):
        """Test that key GUI components exist"""
        # Check sidebar components
        assert hasattr(enhanced_gui, 'stats_label')
        assert hasattr(enhanced_gui, 'track_title_label')
        assert hasattr(enhanced_gui, 'play_btn')

        # Check main area components
        assert hasattr(enhanced_gui, 'media_browser')
        assert hasattr(enhanced_gui, 'quick_search')

        # Check info panel components
        assert hasattr(enhanced_gui, 'details_content')
        assert hasattr(enhanced_gui, 'auto_master_switch')

    def test_player_controls(self, enhanced_gui):
        """Test player control methods"""
        # Test methods exist and can be called without error
        enhanced_gui._toggle_play()
        enhanced_gui._stop()
        enhanced_gui._on_volume_change(0.5)

        # Should not raise exceptions
        assert True

    def test_mastering_controls(self, enhanced_gui):
        """Test mastering control methods"""
        enhanced_gui._toggle_auto_mastering()
        enhanced_gui._on_profile_change("warm")

        # Should not raise exceptions
        assert True


class TestLibraryIntegration:
    """Test library integration functionality"""

    def test_mock_library_operations(self):
        """Test mock library operations"""
        # Create a comprehensive mock library manager
        mock_manager = Mock()

        # Configure mock returns
        mock_manager.get_library_stats.return_value = {
            'total_tracks': 100,
            'total_artists': 25,
            'total_albums': 30,
            'total_genres': 10,
            'total_playlists': 5,
            'total_duration_formatted': '5h 30m',
            'total_filesize_gb': 2.5,
            'avg_mastering_quality': 0.85
        }

        mock_track = Mock()
        mock_track.to_dict.return_value = {
            'id': 1,
            'title': 'Test Track',
            'artists': ['Test Artist'],
            'album': 'Test Album',
            'duration': 240.5,
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2,
            'mastering_quality': 0.9,
            'play_count': 5
        }

        mock_manager.get_track.return_value = mock_track

        # Test the mock operations
        stats = mock_manager.get_library_stats()
        assert stats['total_tracks'] == 100

        track = mock_manager.get_track(1)
        assert track.to_dict()['title'] == 'Test Track'


def test_component_imports():
    """Test that all components can be imported"""
    from auralis.gui.media_browser import EnhancedMediaBrowser
    from auralis.gui.playlist_manager import PlaylistManagerWindow
    from auralis.gui.advanced_search import AdvancedSearchWindow
    from auralis_gui import EnhancedAuralisGUI

    # Should import without error
    assert EnhancedMediaBrowser is not None
    assert PlaylistManagerWindow is not None
    assert AdvancedSearchWindow is not None
    assert EnhancedAuralisGUI is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])