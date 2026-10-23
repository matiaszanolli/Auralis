"""
FastAPI Application Configuration

Modular configuration components extracted from monolithic main.py.
Handles app creation, middleware setup, startup events, and router registration.

Every consumer imports the piece it needs from its own submodule
(`config.app`, `config.middleware`, `config.routes`, `config.startup`), so
this package carries no re-exports — an eager one here would re-create the
routers → config → routes cycle #4033 fixed.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""
