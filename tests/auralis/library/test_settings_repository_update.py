"""Regression tests for settings repository updates."""

from auralis.library.repositories.settings_repository import SettingsRepository


def test_update_settings_preserves_caller_payload(
    settings_repository: SettingsRepository,
) -> None:
    """Custom serialization must not consume fields from the caller (#5259)."""
    payload = {
        'scan_folders': ['/music'],
        'file_types': ['flac', 'mp3'],
        'theme': 'light',
    }
    expected = {
        'scan_folders': ['/music'],
        'file_types': ['flac', 'mp3'],
        'theme': 'light',
    }

    settings_repository.update_settings(payload)

    assert payload == expected
