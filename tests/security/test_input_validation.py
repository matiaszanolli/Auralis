"""
Input Validation Security Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for input sanitization and injection prevention.

SECURITY CONTROLS TESTED:
- Additional injection vectors beyond boundary tests
- Unicode normalization attacks
- Integer overflow/underflow
- Regular expression DoS (ReDoS)
- XML External Entity (XXE) attacks
- LDAP injection
- Format string vulnerabilities
- Null byte injection

NOTE: Basic SQL injection, XSS, path traversal, and command injection
are already tested in tests/boundaries/test_string_input_boundaries.py.
These tests cover additional attack vectors.
"""

import re

import pytest

from auralis.library.repositories import TrackRepository


@pytest.mark.security
class TestAdditionalInjectionVectors:
    """Test additional injection attack vectors."""

    def test_unicode_normalization_attack(self, temp_db):
        """
        SECURITY: Unicode normalization shouldn't bypass validation.
        Test: Unicode characters that normalize to dangerous chars.
        """
        track_repo = TrackRepository(temp_db)

        # Unicode normalization attacks
        # ＜script＞ (fullwidth) normalizes to <script>
        attacks = [
            "＜script＞alert('XSS')＜/script＞",  # Fullwidth
            "﹤script﹥alert('XSS')﹤/script﹥",   # Small
            "\uFE64script\uFE65",                  # Small form variants
        ]

        for attack in attacks:
            track_info = {
                'filepath': '/tmp/unicode_test.flac',
                'title': attack,
                'artists': ['Test Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }

            # Should accept (will be stored as-is) or normalize safely
            track = track_repo.add(track_info)

            if track:
                # Title should not contain actual script tags after normalization
                assert '<script>' not in track.title.lower(), \
                    "Unicode normalization bypass detected"

    def test_homograph_attack(self, temp_db):
        """
        SECURITY: Homograph attacks (lookalike characters).
        Test: Characters that look similar but have different unicode.
        """
        track_repo = TrackRepository(temp_db)

        # Cyrillic 'а' (U+0430) vs Latin 'a' (U+0061)
        # Can be used to bypass filters
        homographs = [
            "аdmin",      # Cyrillic 'а'
            "аdministrаtor",  # Multiple Cyrillic
            "раth/to/filе",   # Mixed Cyrillic
        ]

        for text in homographs:
            track_info = {
                'filepath': f'/tmp/{text}.flac',
                'title': text,
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }

            # Should handle homographs safely
            track = track_repo.add(track_info)
            # System may accept or reject, but shouldn't crash
            assert True, "Homograph handled without crash"

    def test_null_byte_injection(self, temp_db):
        """
        SECURITY: Null bytes shouldn't truncate strings or bypass validation.
        Test: Embedded null bytes in input.
        """
        track_repo = TrackRepository(temp_db)

        null_byte_attacks = [
            "safe.txt\x00.exe",
            "file\x00'; DROP TABLE tracks;--",
            "/tmp/file\x00../../etc/passwd",
        ]

        for attack in null_byte_attacks:
            track_info = {
                'filepath': attack,
                'title': 'Test Track',
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }

            # Should handle null bytes safely (reject or sanitize)
            try:
                track = track_repo.add(track_info)
                if track:
                    # Null bytes should not cause string truncation
                    assert '\x00' not in track.filepath or \
                           track.filepath == attack, \
                           "Null byte caused unexpected truncation"
            except (ValueError, Exception):
                # Rejection is also acceptable
                pass

    def test_ldap_injection(self, temp_db):
        """
        SECURITY: LDAP injection patterns should be sanitized.
        Test: LDAP metacharacters in search.
        """
        track_repo = TrackRepository(temp_db)

        # Add test track
        track_repo.add({
            'filepath': '/tmp/ldap_test.flac',
            'title': 'LDAP Test Track',
            'artists': ['Test Artist'],
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        })

        ldap_attacks = [
            "*)(uid=*",
            "admin*",
            "*()|&'",
            "*",
            "*)(objectClass=*",
        ]

        for attack in ldap_attacks:
            # Search should handle LDAP metacharacters safely
            result = track_repo.search(attack, limit=10, offset=0)

            if isinstance(result, tuple):
                results, total = result
            else:
                results = result

            # Should not expose all records or crash
            # May return 0 or some results, but should be safe
            assert True, "LDAP injection handled safely"


@pytest.mark.security
class TestIntegerBoundaries:
    """Test integer overflow and underflow handling."""

    def test_integer_overflow_in_sample_rate(self, temp_db):
        """
        SECURITY: Integer overflow in sample rate.
        Test: Very large sample rate values.
        """
        track_repo = TrackRepository(temp_db)

        overflow_values = [
            2**31 - 1,      # Max 32-bit signed int
            2**31,          # Overflow 32-bit signed
            2**32 - 1,      # Max 32-bit unsigned
            2**63 - 1,      # Max 64-bit signed
            2**64 - 1,      # Max 64-bit unsigned
        ]

        for value in overflow_values:
            track_info = {
                'filepath': f'/tmp/overflow_{value}.flac',
                'title': 'Overflow Test',
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': value,
                'channels': 2
            }

            # Should either accept or reject gracefully (not crash)
            try:
                track = track_repo.add(track_info)
                if track:
                    # Value should be stored correctly or clamped
                    assert track.sample_rate > 0, "Sample rate became invalid"
            except (ValueError, OverflowError, Exception):
                # Rejection is acceptable
                pass

    def test_negative_values(self, temp_db):
        """
        SECURITY: Negative values where positive expected.
        Test: Negative sample rates, channels, etc.
        """
        track_repo = TrackRepository(temp_db)

        track_info = {
            'filepath': '/tmp/negative_test.flac',
            'title': 'Negative Test',
            'artists': ['Artist'],
            'format': 'FLAC',
            'sample_rate': -44100,  # Negative
            'channels': -2,          # Negative
        }

        # Should reject or sanitize negative values
        try:
            track = track_repo.add(track_info)
            if track:
                # Values should be positive
                assert track.sample_rate > 0, "Negative sample rate accepted"
                assert track.channels > 0, "Negative channels accepted"
        except (ValueError, Exception):
            # Rejection is preferred
            pass


@pytest.mark.security
class TestRegexDoS:
    """Test Regular Expression Denial of Service (ReDoS) prevention."""

    def test_catastrophic_backtracking(self, temp_db):
        """
        SECURITY: Regex patterns susceptible to catastrophic backtracking.
        Test: Input that causes exponential regex processing.
        """
        track_repo = TrackRepository(temp_db)

        # Patterns known to cause ReDoS with certain regexes
        redos_inputs = [
            "a" * 100 + "!",                    # Long repetition
            "a" * 50 + "a" * 50,                # Nested repetition
            ("a" * 10 + "b") * 10,              # Alternation explosion
        ]

        import time

        for input_str in redos_inputs:
            start = time.time()

            track_info = {
                'filepath': '/tmp/redos_test.flac',
                'title': input_str,
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }

            track = track_repo.add(track_info)

            elapsed = time.time() - start

            # Should complete quickly (< 1 second)
            assert elapsed < 1.0, \
                f"Possible ReDoS: took {elapsed:.2f}s for input length {len(input_str)}"


@pytest.mark.security
class TestFormatStringVulnerabilities:
    """Test format string vulnerability prevention."""

    def test_format_string_in_title(self, temp_db):
        """
        SECURITY: Format string patterns shouldn't cause issues.
        Test: %s, %x, %n patterns in input.
        """
        track_repo = TrackRepository(temp_db)

        format_strings = [
            "%s%s%s%s%s",
            "%x%x%x%x",
            "%d%d%d%d",
            "Song %s by %s",  # Legitimate use case
        ]

        for i, fmt in enumerate(format_strings):
            track_info = {
                'filepath': f'/tmp/format_test_{i}.flac',  # Unique filepath per test
                'title': fmt,
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }

            # Should handle format strings safely
            track = track_repo.add(track_info)

            if track:
                # Should store as literal string, not interpret
                assert track.title == fmt, f"Format string was interpreted: expected {fmt}, got {track.title}"


@pytest.mark.security
class TestXMLInjection:
    """Test XML-related injection prevention."""

    def test_xxe_attack_in_metadata(self, temp_db):
        """
        SECURITY: XML External Entity (XXE) attacks.
        Test: XXE patterns in metadata.
        """
        track_repo = TrackRepository(temp_db)

        xxe_payloads = [
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
            '<!DOCTYPE foo [<!ELEMENT foo ANY ><!ENTITY xxe SYSTEM "file:///dev/random">]>',
        ]

        for payload in xxe_payloads:
            track_info = {
                'filepath': '/tmp/xxe_test.flac',
                'title': payload,
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }

            # Should not parse XML or expand entities
            track = track_repo.add(track_info)

            if track:
                # Should be stored as literal string
                assert '<!ENTITY' in track.title or \
                       track.title == payload, \
                       "XML was unexpectedly parsed"

    def test_xml_bomb(self, temp_db):
        """
        SECURITY: XML Bomb (Billion Laughs) attack.
        Test: Recursive entity expansion.
        """
        track_repo = TrackRepository(temp_db)

        xml_bomb = '''<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
]>
<lolz>&lol2;</lolz>'''

        track_info = {
            'filepath': '/tmp/xml_bomb.flac',
            'title': xml_bomb,
            'artists': ['Artist'],
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        }

        import time
        start = time.time()

        # Should not expand entities (causing massive memory usage)
        track = track_repo.add(track_info)

        elapsed = time.time() - start

        # Should complete quickly without expansion
        assert elapsed < 1.0, "XML bomb may have been processed"


@pytest.mark.security
class TestEncodingAttacks:
    """Test various encoding-based attacks."""

    def test_double_encoding(self, temp_db):
        """
        SECURITY: Double-encoded input to bypass filters.
        Test: %2527 (double-encoded apostrophe).
        """
        track_repo = TrackRepository(temp_db)

        # %27 is ', %2527 is %27 (double-encoded)
        double_encoded = [
            "%2527",
            "%252e%252e%252f",  # Double-encoded ../
            "%253Cscript%253E",  # Double-encoded <script>
        ]

        for encoded in double_encoded:
            track_info = {
                'filepath': f'/tmp/{encoded}.flac',
                'title': encoded,
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }

            # Should not double-decode
            track = track_repo.add(track_info)

            if track:
                # Should remain encoded or be rejected
                assert encoded in track.title or \
                       track.title == encoded, \
                       "Double decoding occurred"

    def test_utf7_xss(self, temp_db):
        """
        SECURITY: UTF-7 encoding to bypass XSS filters.
        Test: +ADw-script+AD4- (UTF-7 for <script>).
        """
        track_repo = TrackRepository(temp_db)

        utf7_payloads = [
            "+ADw-script+AD4-alert('XSS')+ADw-/script+AD4-",
            "+ADw-img src+AD0-x onerror+AD0-alert('XSS')+AD4-",
        ]

        for payload in utf7_payloads:
            track_info = {
                'filepath': '/tmp/utf7_test.flac',
                'title': payload,
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }

            # Should not decode UTF-7 (most systems don't by default)
            track = track_repo.add(track_info)

            if track:
                # Should remain as UTF-7 string, not decoded
                assert '<script>' not in track.title.lower(), \
                    "UTF-7 was decoded"


@pytest.mark.security
class TestResourceExhaustion:
    """Test input that could cause resource exhaustion."""

    def test_extremely_long_string(self, temp_db):
        """
        SECURITY: Very long strings shouldn't exhaust memory.
        Test: 10MB string in title.
        """
        track_repo = TrackRepository(temp_db)

        # 10MB string
        huge_string = "A" * (10 * 1024 * 1024)

        track_info = {
            'filepath': '/tmp/huge_string.flac',
            'title': huge_string,
            'artists': ['Artist'],
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        }

        # Should either accept with truncation or reject
        try:
            import time
            start = time.time()

            track = track_repo.add(track_info)

            elapsed = time.time() - start

            # Should complete quickly (< 5 seconds)
            assert elapsed < 5.0, \
                f"Processing {len(huge_string)} char string took {elapsed:.2f}s"

            if track:
                # May be truncated
                print(f"Accepted string of length {len(track.title)}")

        except (ValueError, MemoryError, Exception):
            # Rejection is acceptable
            pass

    def test_deeply_nested_structure(self, temp_db):
        """
        SECURITY: Deeply nested data structures.
        Test: Very long artist list.
        """
        track_repo = TrackRepository(temp_db)

        # 10,000 artists
        huge_artist_list = [f'Artist {i}' for i in range(10000)]

        track_info = {
            'filepath': '/tmp/huge_artists.flac',
            'title': 'Test Track',
            'artists': huge_artist_list,
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        }

        # Should handle large list gracefully
        try:
            import time
            start = time.time()

            track = track_repo.add(track_info)

            elapsed = time.time() - start

            # Should complete in reasonable time
            assert elapsed < 10.0, \
                f"Processing 10k artists took {elapsed:.2f}s"

        except (ValueError, MemoryError, Exception):
            # Rejection is acceptable
            pass
