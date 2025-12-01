"""
Test Queue Export/Import Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for M3U and XSPF playlist format export/import.

Tests verify:
- M3U export and import (standard and extended)
- XSPF export and import with XML structure
- Format auto-detection
- File I/O operations
- Error handling and validation
- Large queue support
"""

import pytest
import tempfile
from pathlib import Path
from auralis.utils.queue import QueueExporter, M3UHandler, XSPFHandler


# Sample track data
SAMPLE_TRACKS = [
    {
        'filepath': '/music/artist1/album1/song1.mp3',
        'title': 'Song One',
        'artists': ['Artist One'],
        'album': 'Album One',
        'duration': 180
    },
    {
        'filepath': '/music/artist2/album2/song2.mp3',
        'title': 'Song Two',
        'artists': ['Artist Two', 'Feature Artist'],
        'album': 'Album Two',
        'duration': 240
    },
    {
        'filepath': '/music/artist3/song3.mp3',
        'title': 'Song Three',
        'artists': ['Artist Three'],
        'duration': 200
    }
]


class TestM3UExport:
    """Test M3U export functionality"""

    def test_export_simple_m3u(self):
        """Should export basic M3U without metadata"""
        content = M3UHandler.export(SAMPLE_TRACKS, extended=False)

        assert '/music/artist1/album1/song1.mp3' in content
        assert '/music/artist2/album2/song2.mp3' in content
        assert '/music/artist3/song3.mp3' in content
        # Simple M3U shouldn't have EXTINF
        assert '#EXTINF:' not in content

    def test_export_extended_m3u(self):
        """Should export Extended M3U with metadata"""
        content = M3UHandler.export(SAMPLE_TRACKS, extended=True)

        assert '#EXTM3U' in content
        assert '#EXT-X-ENCODING:UTF-8' in content
        assert '#EXTINF:180,Artist One - Song One' in content
        assert '#EXTINF:240,Artist Two, Feature Artist - Song Two' in content
        assert '/music/artist1/album1/song1.mp3' in content

    def test_export_empty_queue(self):
        """Should handle empty queue"""
        content = M3UHandler.export([], extended=True)

        assert '#EXTM3U' in content
        # No tracks, just header


class TestM3UImport:
    """Test M3U import functionality"""

    def test_import_simple_m3u(self):
        """Should import simple M3U format"""
        m3u_content = """#EXTM3U
#EXTINF:180,Song One
/music/song1.mp3
/music/song2.mp3
/music/song3.mp3
"""
        paths, errors = M3UHandler.import_from_string(m3u_content)

        assert len(paths) == 3
        assert '/music/song1.mp3' in paths
        assert '/music/song2.mp3' in paths
        assert '/music/song3.mp3' in paths
        assert len(errors) == 0

    def test_import_m3u_with_relative_paths(self):
        """Should handle relative paths with base_path"""
        m3u_content = """song1.mp3
song2.mp3
subdirectory/song3.mp3
"""
        paths, errors = M3UHandler.import_from_string(m3u_content, base_path='/music')

        assert len(paths) == 3
        assert '/music/song1.mp3' in paths
        assert '/music/song2.mp3' in paths
        assert '/music/subdirectory/song3.mp3' in paths

    def test_import_empty_m3u(self):
        """Should handle empty M3U file"""
        paths, errors = M3UHandler.import_from_string('#EXTM3U\n')

        assert len(paths) == 0
        assert len(errors) > 0

    def test_import_m3u_from_file(self):
        """Should import M3U from file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m3u', delete=False) as f:
            f.write('#EXTM3U\n')
            f.write('song1.mp3\n')
            f.write('song2.mp3\n')
            f.flush()
            temp_path = f.name

        try:
            paths, errors = M3UHandler.import_from_file(temp_path)

            assert len(paths) == 2
            assert len(errors) == 0
        finally:
            Path(temp_path).unlink()


class TestXSPFExport:
    """Test XSPF export functionality"""

    def test_export_xspf(self):
        """Should export valid XSPF format"""
        content = XSPFHandler.export(SAMPLE_TRACKS)

        assert '<?xml version="1.0" encoding="UTF-8"?>' in content
        assert 'version="1"' in content
        assert 'xmlns="http://xspf.org/ns/0/"' in content
        assert '<location>file:///music/artist1/album1/song1.mp3</location>' in content
        assert '<title>Song One</title>' in content
        assert '<creator>Artist One</creator>' in content
        assert '<album>Album One</album>' in content

    def test_export_xspf_with_title(self):
        """Should set playlist title in XSPF"""
        content = XSPFHandler.export(SAMPLE_TRACKS, title='My Playlist')

        assert '<title>My Playlist</title>' in content

    def test_export_xspf_duration_conversion(self):
        """Should convert duration to milliseconds in XSPF"""
        content = XSPFHandler.export(SAMPLE_TRACKS)

        # 180 seconds = 180000 milliseconds
        assert '<duration>180000</duration>' in content
        # 240 seconds = 240000 milliseconds
        assert '<duration>240000</duration>' in content


class TestXSPFImport:
    """Test XSPF import functionality"""

    def test_import_xspf(self):
        """Should import valid XSPF format"""
        xspf_content = """<?xml version="1.0" encoding="UTF-8"?>
<playlist version="1" xmlns="http://xspf.org/ns/0/">
  <title>Test Playlist</title>
  <trackList>
    <track>
      <location>file:///music/song1.mp3</location>
      <title>Song 1</title>
    </track>
    <track>
      <location>file:///music/song2.mp3</location>
      <title>Song 2</title>
    </track>
  </trackList>
</playlist>
"""
        paths, errors = XSPFHandler.import_from_string(xspf_content)

        assert len(paths) == 2
        assert '/music/song1.mp3' in paths
        assert '/music/song2.mp3' in paths
        assert len(errors) == 0

    def test_import_xspf_from_file(self):
        """Should import XSPF from file"""
        xspf_content = """<?xml version="1.0" encoding="UTF-8"?>
<playlist version="1" xmlns="http://xspf.org/ns/0/">
  <trackList>
    <track>
      <location>song1.mp3</location>
    </track>
    <track>
      <location>song2.mp3</location>
    </track>
  </trackList>
</playlist>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xspf', delete=False) as f:
            f.write(xspf_content)
            f.flush()
            temp_path = f.name

        try:
            paths, errors = XSPFHandler.import_from_file(temp_path)

            assert len(paths) == 2
            assert len(errors) == 0
        finally:
            Path(temp_path).unlink()

    def test_import_invalid_xspf(self):
        """Should handle invalid XSPF"""
        invalid_xspf = '<?xml version="1.0"?><invalid>Not XSPF</invalid>'
        paths, errors = XSPFHandler.import_from_string(invalid_xspf)

        assert len(paths) == 0
        assert len(errors) > 0


class TestQueueExporterHighLevel:
    """Test high-level QueueExporter functionality"""

    def test_export_m3u_format(self):
        """Should export queue in M3U format"""
        content = QueueExporter.export(SAMPLE_TRACKS, format='m3u')

        assert '#EXTM3U' in content
        assert '/music/artist1/album1/song1.mp3' in content

    def test_export_xspf_format(self):
        """Should export queue in XSPF format"""
        content = QueueExporter.export(SAMPLE_TRACKS, format='xspf')

        assert '<?xml version="1.0"' in content
        assert '<playlist' in content

    def test_export_unsupported_format(self):
        """Should reject unsupported formats"""
        with pytest.raises(ValueError, match='Unsupported format'):
            QueueExporter.export(SAMPLE_TRACKS, format='invalid')

    def test_export_to_file(self):
        """Should export queue to file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = f'{tmpdir}/queue.m3u'
            success, msg = QueueExporter.export_to_file(SAMPLE_TRACKS, filepath)

            assert success is True
            assert Path(filepath).exists()
            with open(filepath) as f:
                content = f.read()
                assert '#EXTM3U' in content

    def test_export_to_file_auto_format(self):
        """Should auto-detect format from filename"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test M3U
            m3u_path = f'{tmpdir}/queue.m3u'
            success, _ = QueueExporter.export_to_file(SAMPLE_TRACKS, m3u_path)
            assert success is True

            # Test XSPF
            xspf_path = f'{tmpdir}/queue.xspf'
            success, _ = QueueExporter.export_to_file(SAMPLE_TRACKS, xspf_path)
            assert success is True

            with open(xspf_path) as f:
                assert '<?xml' in f.read()

    def test_import_from_string_auto_detect(self):
        """Should auto-detect format from content"""
        m3u_content = '#EXTM3U\n/music/song.mp3'
        paths, _ = QueueExporter.import_from_string(m3u_content)
        assert len(paths) > 0

        xspf_content = '<?xml version="1.0"?><playlist xmlns="http://xspf.org/ns/0/"><trackList></trackList></playlist>'
        paths, _ = QueueExporter.import_from_string(xspf_content)
        # Should handle XSPF without error

    def test_import_from_file_auto_detect(self):
        """Should auto-detect format from file extension"""
        m3u_content = '#EXTM3U\nsong1.mp3\nsong2.mp3'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m3u', delete=False) as f:
            f.write(m3u_content)
            f.flush()
            temp_path = f.name

        try:
            paths, errors = QueueExporter.import_from_file(temp_path)
            assert len(paths) == 2
            assert len(errors) == 0
        finally:
            Path(temp_path).unlink()

    def test_detect_format(self):
        """Should detect format from filename"""
        assert QueueExporter.detect_format('playlist.m3u') == 'm3u'
        assert QueueExporter.detect_format('playlist.m3u8') == 'm3u'
        assert QueueExporter.detect_format('playlist.xspf') == 'xspf'
        assert QueueExporter.detect_format('playlist.unknown') == 'unknown'


class TestValidation:
    """Test format validation"""

    def test_validate_m3u(self):
        """Should validate M3U format"""
        valid_m3u = '#EXTM3U\n/music/song.mp3'
        is_valid, errors = M3UHandler.validate(valid_m3u)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_m3u(self):
        """Should reject empty M3U"""
        invalid_m3u = '#EXTM3U'
        is_valid, errors = M3UHandler.validate(invalid_m3u)

        assert is_valid is False
        assert len(errors) > 0

    def test_validate_xspf(self):
        """Should validate XSPF format"""
        valid_xspf = """<?xml version="1.0"?>
<playlist xmlns="http://xspf.org/ns/0/">
  <trackList>
    <track>
      <location>song.mp3</location>
    </track>
  </trackList>
</playlist>
"""
        is_valid, errors = XSPFHandler.validate(valid_xspf)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_xspf(self):
        """Should reject invalid XSPF"""
        invalid_xspf = 'not xml'
        is_valid, errors = XSPFHandler.validate(invalid_xspf)

        assert is_valid is False
        assert len(errors) > 0


class TestLargeQueues:
    """Test with large track lists"""

    def test_export_large_queue_m3u(self):
        """Should handle large queue export in M3U"""
        large_tracks = [
            {
                'filepath': f'/music/song{i}.mp3',
                'title': f'Song {i}',
                'duration': 180 + i
            }
            for i in range(500)
        ]

        content = M3UHandler.export(large_tracks)

        # Check that all tracks are present
        for i in range(500):
            assert f'/music/song{i}.mp3' in content

    def test_export_large_queue_xspf(self):
        """Should handle large queue export in XSPF"""
        large_tracks = [
            {
                'filepath': f'/music/song{i}.mp3',
                'title': f'Song {i}',
                'duration': 180
            }
            for i in range(200)
        ]

        content = XSPFHandler.export(large_tracks)

        # Verify structure and track count
        assert '<?xml' in content
        assert '/music/song0.mp3' in content
        assert '/music/song199.mp3' in content

    def test_import_large_queue(self):
        """Should handle large queue import"""
        lines = ['#EXTM3U']
        for i in range(300):
            lines.append(f'/music/song{i}.mp3')

        content = '\n'.join(lines)
        paths, errors = M3UHandler.import_from_string(content)

        assert len(paths) == 300
        assert len(errors) == 0


class TestRoundTrip:
    """Test round-trip export/import"""

    def test_m3u_roundtrip(self):
        """Should preserve data in M3U roundtrip"""
        # Export to M3U
        exported = M3UHandler.export(SAMPLE_TRACKS)

        # Import from M3U
        paths, errors = M3UHandler.import_from_string(exported)

        # Verify paths preserved
        assert len(paths) == 3
        assert all(Path(p).name.endswith('.mp3') for p in paths)

    def test_xspf_roundtrip(self):
        """Should preserve data in XSPF roundtrip"""
        # Export to XSPF
        exported = XSPFHandler.export(SAMPLE_TRACKS)

        # Import from XSPF
        paths, errors = XSPFHandler.import_from_string(exported)

        # Verify paths preserved
        assert len(paths) == 3
        assert '/music/artist1/album1/song1.mp3' in paths
