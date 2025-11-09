"""
Security Test Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides fixtures and utilities for security testing.
"""

import pytest
import sys
import tempfile
import os
import shutil
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add paths for imports
backend_path = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from auralis.library.models import Base


@pytest.fixture
def temp_db():
    """Create temporary database for testing. Yields sessionmaker callable."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    db_path = temp_file.name

    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    yield SessionLocal

    # Cleanup
    engine.dispose()
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest.fixture
def malicious_inputs():
    """Common malicious input patterns for testing."""
    return {
        'sql_injection': [
            "'; DROP TABLE tracks; --",
            "' OR '1'='1",
            "' OR 1=1--",
            "admin'--",
            "' UNION SELECT * FROM tracks--",
            "1' AND '1'='1",
        ],
        'xss': [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg/onload=alert('XSS')>",
            "'-alert(1)-'",
        ],
        'path_traversal': [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32',
            '/etc/passwd',
            'C:\\Windows\\System32\\config\\sam',
            './../../sensitive_file.txt',
            '....//....//....//etc/passwd',
        ],
        'command_injection': [
            "; ls -la",
            "| cat /etc/passwd",
            "& whoami",
            "`cat /etc/passwd`",
            "$(cat /etc/passwd)",
        ],
        'null_bytes': [
            "test\x00.txt",
            "file.txt\x00.exe",
        ],
        'format_strings': [
            "%s%s%s%s",
            "%x%x%x%x",
            "%n%n%n%n",
        ],
        'ldap_injection': [
            "*)(uid=*",
            "admin*",
            "*()|&'",
        ],
    }
