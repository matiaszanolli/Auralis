"""
API Routers for Auralis Web Backend

Modular router organization for maintainability.
Each router handles a specific domain of the API.

No re-exports here: `config/routes.py` imports every `create_*_router`
factory from its own module, and a package-level import of the routers would
force every `import routers.x` to eagerly pull in all of them.
"""
