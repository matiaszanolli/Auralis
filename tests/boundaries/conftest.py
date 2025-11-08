"""
Boundary Test Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides fixtures and configuration for boundary testing.
"""

import pytest
import sys
from pathlib import Path

# Add backend to Python path for chunked processor imports
backend_path = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))
