"""
Core audio processing modules for Auralis.

Extracted from monolithic chunked_processor.py to improve maintainability and
testability. Every consumer imports from the defining submodule
(`core.chunk_boundaries`, `core.encoding`, `core.level_manager`), so this
package carries no re-exports.
"""
