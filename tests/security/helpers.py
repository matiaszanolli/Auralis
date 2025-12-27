"""
Security Test Helpers
~~~~~~~~~~~~~~~~~~~~~

Utility functions for security testing.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List


def is_sql_injection(input_str: str) -> bool:
    """
    Check if input contains SQL injection patterns.

    This is a simple pattern matcher for testing purposes.
    Real validation should use parameterized queries.
    """
    sql_patterns = [
        r"';",
        r"--",
        r"DROP\s+TABLE",
        r"UNION\s+SELECT",
        r"OR\s+['\"]",  # OR with quotes
        r"OR\s+\d+=\d+",  # OR with numbers
        r"AND\s+['\"]",  # AND with quotes
    ]

    for pattern in sql_patterns:
        if re.search(pattern, input_str, re.IGNORECASE):
            return True
    return False


def is_path_traversal(path_str: str) -> bool:
    """
    Check if path contains traversal attempts.

    Detects:
    - Relative path traversal (../)
    - Absolute paths
    - Windows paths
    - Encoded traversal
    """
    dangerous_patterns = [
        r'\.\.',           # .. traversal
        r'^/',             # Absolute Unix path
        r'^[A-Za-z]:',     # Windows drive letter
        r'\\',             # Windows separator
        r'%2e%2e',         # URL-encoded ..
        r'%252e',          # Double URL-encoded .
        r'\.\.%2f',        # Mixed encoding
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, path_str, re.IGNORECASE):
            return True
    return False


def is_xss_attempt(input_str: str) -> bool:
    """
    Check if input contains XSS patterns.

    Detects common XSS vectors including:
    - Script tags
    - Event handlers
    - JavaScript URLs
    - SVG/img injection
    """
    xss_patterns = [
        r'<script',
        r'javascript:',
        r'onerror\s*=',
        r'onload\s*=',
        r'onclick\s*=',
        r'<svg',
        r'<img',
        r'alert\(',
        r'eval\(',
    ]

    for pattern in xss_patterns:
        if re.search(pattern, input_str, re.IGNORECASE):
            return True
    return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and command injection.

    Returns:
        Safe filename with only alphanumeric, dots, dashes, underscores
    """
    # Remove path separators first (gets basename)
    filename = os.path.basename(filename)

    # Remove null bytes
    filename = filename.replace('\x00', '')

    # Remove directory traversal patterns (.. becomes _)
    filename = filename.replace('..', '_')

    # Allow only safe characters
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

    # Prevent hidden files
    if filename.startswith('.'):
        filename = '_' + filename[1:]

    # Prevent empty filename
    if not filename:
        filename = 'unnamed'

    return filename


def validate_path_safety(base_path: Path, requested_path: Path) -> bool:
    """
    Validate that requested path is within base path (no traversal).

    Args:
        base_path: The base directory that should contain the file
        requested_path: The requested file path

    Returns:
        True if path is safe, False otherwise
    """
    try:
        # Resolve to absolute paths
        base = base_path.resolve()
        requested = requested_path.resolve()

        # Check if requested is within base
        return str(requested).startswith(str(base))
    except (ValueError, OSError):
        return False


def is_oversized_input(input_str: str, max_size: int = 10000) -> bool:
    """
    Check if input exceeds reasonable size limits.

    Args:
        input_str: Input to check
        max_size: Maximum allowed size in characters

    Returns:
        True if oversized, False otherwise
    """
    return len(input_str) > max_size


def contains_control_characters(input_str: str) -> bool:
    """
    Check if input contains control characters (except newline, tab, carriage return).

    Returns:
        True if contains dangerous control characters
    """
    for char in input_str:
        code = ord(char)
        # Allow tab (9), newline (10), carriage return (13)
        if 0 <= code < 32 and code not in (9, 10, 13):
            return True
        # Check for other control ranges
        if 127 <= code < 160:
            return True
    return False


def validate_metadata_field(field_name: str, value: Any, constraints: Dict) -> List[str]:
    """
    Validate metadata field against constraints.

    Args:
        field_name: Name of the field
        value: Value to validate
        constraints: Dictionary of constraints (type, min, max, pattern, etc.)

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Type validation
    if 'type' in constraints:
        expected_type = constraints['type']
        if not isinstance(value, expected_type):
            errors.append(f"{field_name} must be {expected_type.__name__}, got {type(value).__name__}")

    # Numeric range validation
    if isinstance(value, (int, float)):
        if 'min' in constraints and value < constraints['min']:
            errors.append(f"{field_name} must be >= {constraints['min']}, got {value}")
        if 'max' in constraints and value > constraints['max']:
            errors.append(f"{field_name} must be <= {constraints['max']}, got {value}")

    # String validation
    if isinstance(value, str):
        if 'max_length' in constraints and len(value) > constraints['max_length']:
            errors.append(f"{field_name} exceeds max length {constraints['max_length']}")
        if 'pattern' in constraints and not re.match(constraints['pattern'], value):
            errors.append(f"{field_name} does not match required pattern")
        if 'no_xss' in constraints and constraints['no_xss']:
            if is_xss_attempt(value):
                errors.append(f"{field_name} contains XSS patterns")
        if 'no_sql' in constraints and constraints['no_sql']:
            if is_sql_injection(value):
                errors.append(f"{field_name} contains SQL injection patterns")

    return errors


def create_malicious_file(path: Path, content_type: str = 'script') -> Path:
    """
    Create a malicious file for testing security measures.

    Args:
        path: Directory to create file in
        content_type: Type of malicious content ('script', 'executable', 'symlink')

    Returns:
        Path to created file
    """
    if content_type == 'script':
        file_path = path / 'malicious.sh'
        file_path.write_text('#!/bin/bash\necho "This should not execute"')
        os.chmod(file_path, 0o755)
        return file_path

    elif content_type == 'executable':
        file_path = path / 'fake_audio.mp3.exe'
        file_path.write_bytes(b'\x4d\x5a' + b'\x00' * 100)  # MZ header (Windows exe)
        return file_path

    elif content_type == 'symlink':
        target = path / 'target.txt'
        target.write_text('target content')
        link_path = path / 'symlink.txt'
        link_path.symlink_to(target)
        return link_path

    else:
        raise ValueError(f"Unknown content_type: {content_type}")


def detect_file_type(file_path: Path) -> str:
    """
    Detect actual file type by magic bytes (not extension).

    Returns:
        File type identifier
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(16)

        # Check common formats
        if header[:4] == b'RIFF' and header[8:12] == b'WAVE':
            return 'audio/wav'
        elif header[:3] == b'ID3' or header[:2] == b'\xff\xfb':
            return 'audio/mp3'
        elif header[:4] == b'fLaC':
            return 'audio/flac'
        elif header[:2] == b'MZ':
            return 'application/x-executable'
        elif header[:4] == b'\x7fELF':
            return 'application/x-elf'
        elif header[:2] == b'#!':
            return 'text/x-shellscript'
        else:
            return 'application/octet-stream'

    except Exception:
        return 'unknown'
