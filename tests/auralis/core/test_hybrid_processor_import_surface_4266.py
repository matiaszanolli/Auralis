"""
Import-surface guard for the hybrid-processor free functions (#4266)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#4266 moved `process_adaptive`/`process_reference`/`process_hybrid` and their
shared LRU processor cache out of `hybrid_processor.py` into
`hybrid_processor_singleton.py`, leaving the class file holding only
`HybridProcessor`. The functions are public package API, so the move must be
invisible to importers: these tests pin the `auralis`-level surface so a future
relocation cannot silently drop it, and pin the class-file/free-function split
so the two APIs do not drift back into one module.
"""

import auralis
import auralis.core.hybrid_processor as class_module
import auralis.core.hybrid_processor_singleton as singleton_module


class TestPublicImportSurface:
    """`from auralis import ...` must keep working post-move."""

    def test_top_level_reexports_are_importable(self) -> None:
        from auralis import process_adaptive, process_reference

        assert callable(process_adaptive)
        assert callable(process_reference)

    def test_reexports_are_advertised_in_dunder_all(self) -> None:
        assert "process_adaptive" in auralis.__all__
        assert "process_reference" in auralis.__all__
        assert "HybridProcessor" in auralis.__all__

    def test_reexports_are_the_singleton_module_objects(self) -> None:
        """The top-level names must be the moved functions, not stale copies."""
        assert auralis.process_adaptive is singleton_module.process_adaptive
        assert auralis.process_reference is singleton_module.process_reference

    def test_all_three_wrappers_live_in_the_singleton_module(self) -> None:
        for name in ("process_adaptive", "process_reference", "process_hybrid"):
            assert callable(getattr(singleton_module, name)), name


class TestClassFileHoldsOnlyTheClass:
    """The free-function API must not creep back into the class file (#4266)."""

    def test_class_file_still_exports_the_class(self) -> None:
        assert singleton_module.HybridProcessor is class_module.HybridProcessor

    def test_class_file_defines_no_process_wrappers(self) -> None:
        for name in ("process_adaptive", "process_reference", "process_hybrid"):
            assert not hasattr(class_module, name), (
                f"{name} is back in hybrid_processor.py — it belongs in "
                "hybrid_processor_singleton.py (#4266)"
            )

    def test_class_file_owns_no_processor_cache(self) -> None:
        for name in ("_processor_cache", "_processor_cache_lock",
                     "_PROCESSOR_CACHE_MAX_SIZE", "_get_or_create_processor"):
            assert not hasattr(class_module, name), (
                f"{name} is back in hybrid_processor.py (#4266)"
            )
