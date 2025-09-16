#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test Enhanced GUI Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test script for the new enhanced media management GUI.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

import customtkinter as ctk

def test_basic_components():
    """Test that basic GUI components can be imported and created"""
    print("🔧 Testing GUI component imports...")

    from auralis.gui.media_browser import EnhancedMediaBrowser, ViewMode, SortOrder
    print("✅ Media browser components imported successfully")
    assert EnhancedMediaBrowser is not None
    assert hasattr(ViewMode, 'ARTISTS')

    from auralis.gui.playlist_manager import PlaylistManagerWindow, SmartPlaylistBuilder
    print("✅ Playlist manager components imported successfully")
    assert PlaylistManagerWindow is not None

    from auralis.gui.advanced_search import AdvancedSearchWindow, QuickSearchBar
    print("✅ Advanced search components imported successfully")
    assert AdvancedSearchWindow is not None

def test_media_browser_widget():
    """Test creating media browser widget"""
    print("\n🎵 Testing media browser widget creation...")

    from auralis.gui.media_browser import EnhancedMediaBrowser

    # Create test window
    root = ctk.CTk()
    root.withdraw()  # Hide window

    # Create media browser
    browser = EnhancedMediaBrowser(root)
    print("✅ Media browser widget created successfully")
    assert browser is not None

    # Test view mode constants
    from auralis.gui.media_browser import ViewMode
    assert hasattr(ViewMode, 'ARTISTS')
    assert hasattr(ViewMode, 'ALBUMS')
    assert hasattr(ViewMode, 'TRACKS')
    print("✅ View mode constants available")

    root.destroy()

def test_search_components():
    """Test search components"""
    print("\n🔍 Testing search components...")

    from auralis.gui.advanced_search import QuickSearchBar

    # Create test window
    root = ctk.CTk()
    root.withdraw()

    # Create search bar
    search_bar = QuickSearchBar(root)
    print("✅ Quick search bar created successfully")
    assert search_bar is not None

    root.destroy()

def test_enhanced_gui():
    """Test the main enhanced GUI"""
    print("\n🖥️  Testing enhanced GUI application...")

    from auralis_gui import EnhancedAuralisGUI

    # Create application instance (but don't run mainloop)
    app = EnhancedAuralisGUI()
    app.withdraw()  # Hide window

    print("✅ Enhanced GUI application created successfully")
    assert app is not None

    # Check that key components exist
    assert hasattr(app, 'media_browser') or hasattr(app, 'stats_label')
    assert hasattr(app, 'track_title_label')
    print("✅ GUI components properly initialized")

    app.destroy()

def main():
    """Run all tests"""
    print("🧪 Testing Enhanced Media Manager Components")
    print("=" * 50)

    tests = [
        ("Component Imports", test_basic_components),
        ("Media Browser Widget", test_media_browser_widget),
        ("Search Components", test_search_components),
        ("Enhanced GUI Application", test_enhanced_gui),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")

    print("\n" + "=" * 50)
    print(f"🏁 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Enhanced media manager is ready.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)