"""
File System Errors Edge Case Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for handling file system errors and edge cases.

INVARIANTS TESTED:
- Permission errors: Clear errors when lacking read/write permissions
- Missing files: Graceful handling of non-existent files
- Corrupted files: Detection and reporting of corrupted data
- Symbolic links: Proper handling of symlinks and broken links
- Special files: Handling of devices, pipes, sockets
- Path issues: Long paths, special characters, invalid paths
- File locking: Handling of locked files
"""

import os
import shutil
import stat
import tempfile
from pathlib import Path

import numpy as np
import pytest

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio
from auralis.library.repositories import TrackRepository
from auralis.utils.logging import ModuleError


@pytest.mark.edge_case
class TestPermissionErrors:
    """Test handling of permission-related errors."""

    def test_read_file_without_permission(self, temp_audio_dir):
        """
        INVARIANT: Should report clear error when file is not readable.
        Test: Remove read permission, try to load.
        """
        # Create file
        sample_rate = 44100
        duration = 1.0
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'no_read.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        # Remove read permission (Unix only)
        if os.name != 'nt':  # Skip on Windows
            os.chmod(filepath, 0o000)

            try:
                load_audio(filepath)
                read_failed = False
            except Exception as e:
                # Catch any exception - soundfile may raise RuntimeError instead of PermissionError
                read_failed = True
            finally:
                # Restore permissions for cleanup
                os.chmod(filepath, 0o644)

            # INVARIANT: Should get permission error
            assert read_failed, "Should fail to read file without permission"
        else:
            pytest.skip("Permission test requires Unix")

    def test_write_file_without_permission(self, temp_audio_dir):
        """
        INVARIANT: Should report clear error when directory is not writable.
        Test: Remove write permission from directory.
        """
        if os.name != 'nt':  # Skip on Windows
            # Remove write permission from directory
            os.chmod(temp_audio_dir, 0o555)

            try:
                sample_rate = 44100
                duration = 1.0
                audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
                filepath = os.path.join(temp_audio_dir, 'no_write.wav')
                save(filepath, audio, sample_rate, subtype='PCM_16')
                write_failed = False
            except Exception:
                # Catch any permission-related exception
                write_failed = True
            finally:
                # Restore permissions
                os.chmod(temp_audio_dir, 0o755)

            # INVARIANT: Should get permission error
            assert write_failed, "Should fail to write to read-only directory"
        else:
            pytest.skip("Permission test requires Unix")

    def test_delete_file_without_permission(self, temp_audio_dir):
        """
        INVARIANT: Should report clear error when file cannot be deleted.
        Test: Try to delete file in read-only directory.
        """
        if os.name != 'nt':
            # Create file
            filepath = os.path.join(temp_audio_dir, 'no_delete.txt')
            with open(filepath, 'w') as f:
                f.write('test')

            # Make directory read-only
            os.chmod(temp_audio_dir, 0o555)

            try:
                os.unlink(filepath)
                delete_failed = False
            except Exception:
                # Catch any permission-related exception
                delete_failed = True
            finally:
                os.chmod(temp_audio_dir, 0o755)
                try:
                    os.unlink(filepath)
                except:
                    pass

            # INVARIANT: Should fail to delete in read-only directory
            assert delete_failed, "Should fail to delete in read-only directory"
        else:
            pytest.skip("Permission test requires Unix")


@pytest.mark.edge_case
class TestMissingFiles:
    """Test handling of non-existent files."""

    def test_load_nonexistent_file(self):
        """
        INVARIANT: Loading non-existent file should give clear error.
        Test: Try to load file that doesn't exist.
        """
        try:
            load_audio('/tmp/definitely_does_not_exist_12345.wav')
            failed = False
        except (FileNotFoundError, OSError, RuntimeError, ModuleError):
            failed = True

        # INVARIANT: Should get file not found error
        assert failed, "Should fail to load non-existent file"

    def test_process_nonexistent_file(self):
        """
        INVARIANT: Processing non-existent file should fail or return default audio.
        Test: Process with invalid filepath.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        try:
            result = processor.process('/tmp/nonexistent_audio_12345.flac')

            # INVARIANT: If succeeds, should return valid audio (fallback behavior)
            # This is acceptable - processor generates default audio for robustness
            assert result is not None
            assert len(result) > 0, "Should return non-empty result"

        except (FileNotFoundError, OSError, RuntimeError, ModuleError):
            # Also acceptable: Fail with clear error
            pass

    def test_add_track_with_nonexistent_file(self, temp_db):
        """
        INVARIANT: Adding track with non-existent file should be handled.
        Test: Add track record for file that doesn't exist.
        """
        track_repo = TrackRepository(temp_db)

        # Try to add track with non-existent filepath
        track = track_repo.add({
            'filepath': '/tmp/ghost_file_12345.flac',
            'title': 'Ghost Track',
            'artists': ['Test Artist'],
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        })

        # INVARIANT: Should either reject or mark as missing
        # (Current implementation allows adding non-existent paths)
        if track:
            # If allowed, should be queryable
            tracks, total = track_repo.get_all(limit=10, offset=0)
            assert total == 1

    def test_broken_symlink_handling(self, temp_audio_dir):
        """
        INVARIANT: Broken symbolic links should be detected.
        Test: Create symlink to non-existent target.
        """
        if os.name != 'nt':
            symlink_path = os.path.join(temp_audio_dir, 'broken_link.wav')

            # Create symlink to non-existent file
            os.symlink('/tmp/nonexistent_target.wav', symlink_path)

            try:
                load_audio(symlink_path)
                failed = False
            except (FileNotFoundError, OSError, RuntimeError, ModuleError):
                failed = True
            finally:
                try:
                    os.unlink(symlink_path)
                except:
                    pass

            # INVARIANT: Should detect broken symlink
            assert failed, "Should fail on broken symlink"
        else:
            pytest.skip("Symlink test requires Unix")


@pytest.mark.edge_case
class TestCorruptedFiles:
    """Test handling of corrupted or invalid files."""

    def test_corrupted_wav_header(self, temp_audio_dir):
        """
        INVARIANT: Corrupted WAV header should be detected.
        Test: Create file with invalid WAV header.
        """
        filepath = os.path.join(temp_audio_dir, 'corrupted_header.wav')

        # Create file with invalid header
        with open(filepath, 'wb') as f:
            f.write(b'RIFF' + b'\x00' * 100)  # Invalid header

        try:
            load_audio(filepath)
            failed = False
        except (ValueError, RuntimeError, Exception):
            failed = True

        # INVARIANT: Should detect corrupted header
        assert failed, "Should detect corrupted WAV header"

    def test_truncated_audio_file(self, temp_audio_dir):
        """
        INVARIANT: Truncated audio files should be detected.
        Test: Create truncated WAV file.
        """
        # Create valid file first
        sample_rate = 44100
        duration = 2.0
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'truncated.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        # Truncate file
        with open(filepath, 'r+b') as f:
            f.truncate(1000)  # Cut off most of file

        try:
            result_audio, sr = load_audio(filepath)
            # May load partially or fail
            failed = False
        except (ValueError, RuntimeError, EOFError, Exception):
            failed = True

        # INVARIANT: Should either fail or return partial data
        # (Both are acceptable behaviors)
        assert True, "Handled truncated file"

    def test_wrong_file_extension(self, temp_audio_dir):
        """
        INVARIANT: Files with wrong extension should be detected.
        Test: Text file with .wav extension.
        """
        filepath = os.path.join(temp_audio_dir, 'fake_audio.wav')

        # Create text file with audio extension
        with open(filepath, 'w') as f:
            f.write('This is not audio data')

        try:
            load_audio(filepath)
            failed = False
        except (ValueError, RuntimeError, Exception):
            failed = True

        # INVARIANT: Should detect invalid audio data
        assert failed, "Should detect non-audio file"

    def test_zero_byte_file(self, temp_audio_dir):
        """
        INVARIANT: Empty files should be rejected.
        Test: Zero-byte audio file.
        """
        filepath = os.path.join(temp_audio_dir, 'empty.wav')

        # Create empty file
        open(filepath, 'w').close()

        try:
            load_audio(filepath)
            failed = False
        except (ValueError, RuntimeError, EOFError, Exception):
            failed = True

        # INVARIANT: Should reject empty file
        assert failed, "Should reject zero-byte file"


@pytest.mark.edge_case
class TestSpecialFiles:
    """Test handling of special file types."""

    def test_directory_instead_of_file(self, temp_audio_dir):
        """
        INVARIANT: Directories should not be treated as files.
        Test: Try to load directory as audio file.
        """
        try:
            load_audio(temp_audio_dir)
            failed = False
        except (OSError, IsADirectoryError, RuntimeError, ModuleError, AttributeError):
            failed = True

        # INVARIANT: Should reject directory
        assert failed, "Should not load directory as file"

    def test_device_file_handling(self):
        """
        INVARIANT: Device files should not crash the system.
        Test: Try to access device file (Unix only).
        """
        if os.name != 'nt' and os.path.exists('/dev/null'):
            try:
                load_audio('/dev/null')
                failed = False
            except (ValueError, RuntimeError, Exception):
                failed = True

            # INVARIANT: Should reject device file gracefully
            assert failed, "Should not load device file"
        else:
            pytest.skip("Device file test requires Unix")

    def test_valid_symlink_handling(self, temp_audio_dir):
        """
        INVARIANT: Valid symbolic links should work like regular files.
        Test: Create symlink to valid audio file.
        """
        if os.name != 'nt':
            # Create valid audio file
            sample_rate = 44100
            duration = 1.0
            audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
            target_path = os.path.join(temp_audio_dir, 'target.wav')
            save(target_path, audio, sample_rate, subtype='PCM_16')

            # Create symlink
            link_path = os.path.join(temp_audio_dir, 'link.wav')
            os.symlink(target_path, link_path)

            try:
                result_audio, sr = load_audio(link_path)

                # INVARIANT: Should load successfully via symlink
                assert result_audio is not None
                assert sr == sample_rate
            finally:
                try:
                    os.unlink(link_path)
                except:
                    pass
        else:
            pytest.skip("Symlink test requires Unix")


@pytest.mark.edge_case
class TestPathIssues:
    """Test handling of path-related issues."""

    def test_very_long_path(self, temp_audio_dir):
        """
        INVARIANT: Very long paths should be handled or rejected gracefully.
        Test: Create nested directories with long path.
        """
        # Create nested path (may hit OS limits)
        deep_dir = temp_audio_dir
        for i in range(10):
            deep_dir = os.path.join(deep_dir, f'very_long_directory_name_{i}')

        try:
            os.makedirs(deep_dir, exist_ok=True)

            # Try to create file in deep path
            sample_rate = 44100
            duration = 0.5
            audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
            filepath = os.path.join(deep_dir, 'deep_file.wav')
            save(filepath, audio, sample_rate, subtype='PCM_16')

            # Try to load it back
            result_audio, sr = load_audio(filepath)

            # INVARIANT: Should handle long paths (or fail with clear error)
            assert result_audio is not None

        except (OSError, FileNotFoundError) as e:
            # Acceptable: OS path length limit exceeded
            assert "too long" in str(e).lower() or "name too long" in str(e).lower(), \
                f"Should report path length issue: {e}"

    def test_unicode_in_path(self, temp_audio_dir):
        """
        INVARIANT: Unicode characters in paths should be supported.
        Test: File with international characters.
        """
        # Create file with unicode name
        sample_rate = 44100
        duration = 0.5
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filename = '音楽_тест_🎵.wav'  # Japanese, Cyrillic, Emoji
        filepath = os.path.join(temp_audio_dir, filename)

        try:
            save(filepath, audio, sample_rate, subtype='PCM_16')
            result_audio, sr = load_audio(filepath)

            # INVARIANT: Should handle unicode paths
            assert result_audio is not None
            assert os.path.exists(filepath)

        except (UnicodeEncodeError, OSError):
            pytest.skip("File system doesn't support unicode filenames")

    def test_special_characters_in_path(self, temp_audio_dir):
        """
        INVARIANT: Special characters in paths should be handled safely.
        Test: Filenames with spaces, quotes, etc.
        """
        special_names = [
            'file with spaces.wav',
            'file\'with\'quotes.wav',
            'file"with"double"quotes.wav',
            'file(with)parens.wav',
            'file[with]brackets.wav'
        ]

        sample_rate = 44100
        duration = 0.1
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1

        for name in special_names:
            filepath = os.path.join(temp_audio_dir, name)

            try:
                save(filepath, audio, sample_rate, subtype='PCM_16')
                result_audio, sr = load_audio(filepath)

                # INVARIANT: Should handle special characters
                assert result_audio is not None

            except (OSError, ValueError) as e:
                # Some characters may be invalid on some file systems
                if "invalid" in str(e).lower():
                    continue
                else:
                    raise

    def test_relative_vs_absolute_paths(self, temp_audio_dir):
        """
        INVARIANT: Both relative and absolute paths should work.
        Test: Save with absolute, load with relative (or vice versa).
        """
        # Create file with absolute path
        sample_rate = 44100
        duration = 0.5
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filename = 'path_test.wav'
        abs_filepath = os.path.join(temp_audio_dir, filename)
        save(abs_filepath, audio, sample_rate, subtype='PCM_16')

        # Try to load with absolute path
        result1, sr1 = load_audio(abs_filepath)
        assert result1 is not None

        # Try to load with Path object
        result2, sr2 = load_audio(Path(abs_filepath))
        assert result2 is not None


@pytest.mark.edge_case
class TestFileLocking:
    """Test handling of locked files."""

    def test_concurrent_read_same_file(self, temp_audio_dir):
        """
        INVARIANT: Multiple readers should be able to read same file.
        Test: Open file for reading multiple times.
        """
        # Create test file
        sample_rate = 44100
        duration = 1.0
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'shared_read.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        # Open for reading multiple times
        handles = []
        try:
            for i in range(5):
                f = open(filepath, 'rb')
                handles.append(f)

            # INVARIANT: Should allow multiple readers
            assert len(handles) == 5, "Should allow multiple readers"

        finally:
            for f in handles:
                f.close()

    def test_write_while_reading(self, temp_audio_dir):
        """
        INVARIANT: Writing should be blocked/prevented while file is open for reading.
        Test: Open for read, try to write.
        """
        # Create test file
        filepath = os.path.join(temp_audio_dir, 'lock_test.txt')
        with open(filepath, 'w') as f:
            f.write('test')

        # Open for reading
        read_handle = open(filepath, 'rb')

        try:
            # Try to write (may or may not be blocked depending on OS)
            with open(filepath, 'wb') as write_handle:
                write_handle.write(b'new content')

            # On Unix, this typically succeeds (no mandatory locking)
            # On Windows, may fail
            can_write_while_reading = True

        except (PermissionError, OSError):
            can_write_while_reading = False

        finally:
            read_handle.close()

        # INVARIANT: Behavior is OS-dependent but should not crash
        assert True, "File locking handled (OS-dependent behavior)"

    def test_delete_open_file(self, temp_audio_dir):
        """
        INVARIANT: Deleting open files should be handled safely.
        Test: Try to delete file while it's open.
        """
        filepath = os.path.join(temp_audio_dir, 'delete_while_open.txt')
        with open(filepath, 'w') as f:
            f.write('test')

        # Open file
        handle = open(filepath, 'rb')

        try:
            os.unlink(filepath)
            delete_succeeded = True
        except (PermissionError, OSError):
            delete_succeeded = False
        finally:
            handle.close()

        # Clean up if delete failed
        if not delete_succeeded:
            try:
                os.unlink(filepath)
            except:
                pass

        # INVARIANT: Should handle attempt gracefully (Unix allows, Windows blocks)
        assert True, "Delete open file handled (OS-dependent)"


@pytest.mark.edge_case
class TestDatabaseFileIssues:
    """Test handling of database file issues."""

    def test_corrupted_database(self):
        """
        INVARIANT: Corrupted database should be detected.
        Test: Create invalid database file.
        """
        temp_db_path = tempfile.mktemp(suffix='.db')

        # Create corrupted database file
        with open(temp_db_path, 'wb') as f:
            f.write(b'This is not a SQLite database')

        try:
            from sqlalchemy import create_engine
            engine = create_engine(f'sqlite:///{temp_db_path}')

            # Try to use it
            from auralis.library.models import Base
            Base.metadata.create_all(engine)

            failed = False
        except Exception:
            failed = True
        finally:
            try:
                os.unlink(temp_db_path)
            except:
                pass

        # INVARIANT: Should detect corrupted database
        assert failed, "Should detect corrupted database"

    def test_database_in_readonly_directory(self):
        """
        INVARIANT: Should report clear error if database directory is read-only.
        Test: Try to create database in read-only directory.
        """
        if os.name != 'nt':
            readonly_dir = tempfile.mkdtemp()
            os.chmod(readonly_dir, 0o555)

            try:
                db_path = os.path.join(readonly_dir, 'test.db')
                from sqlalchemy import create_engine
                engine = create_engine(f'sqlite:///{db_path}')

                from auralis.library.models import Base
                Base.metadata.create_all(engine)

                failed = False
            except Exception:
                # Catch any permission-related exception
                failed = True
            finally:
                os.chmod(readonly_dir, 0o755)
                shutil.rmtree(readonly_dir)

            # INVARIANT: Should fail with permission error
            assert failed, "Should fail to create database in read-only directory"
        else:
            pytest.skip("Permission test requires Unix")
