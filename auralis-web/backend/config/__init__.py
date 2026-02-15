"""
FastAPI Application Configuration

Modular configuration components extracted from monolithic main.py.
Handles app creation, middleware setup, startup events, and router registration.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from .app import create_app
from .middleware import setup_middleware
from .routes import setup_routers
from .startup import create_lifespan

__all__ = [
    'create_app',
    'setup_middleware',
    'create_lifespan',
    'setup_routers',
]
