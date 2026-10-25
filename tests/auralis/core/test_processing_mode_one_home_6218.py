"""
The processing-mode vocabulary has one home (#6218)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"reference"/"adaptive"/"hybrid" was re-typed in six places — an inline
validation list in HybridProcessor right before the config method that
validates the same list, an if/elif chain in job_config that silently
skipped unknown modes where the config raises, and four Literal copies.
One definition (settings.ProcessingMode) now feeds them all.
"""

from typing import get_args

import pytest

from auralis.core.config.settings import PROCESSING_MODES, ProcessingMode
from auralis.core.config.unified_config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor


def test_modes_derive_from_the_literal():
    assert PROCESSING_MODES == get_args(ProcessingMode)
    assert set(PROCESSING_MODES) == {"reference", "adaptive", "hybrid"}


@pytest.mark.parametrize("mode", ["reference", "adaptive", "hybrid"])
def test_every_mode_is_accepted(mode):
    config = UnifiedConfig()
    config.set_processing_mode(mode)
    assert config.adaptive.mode == mode


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        UnifiedConfig().set_processing_mode("bogus")  # type: ignore[arg-type]


def test_hybrid_processor_still_raises_on_unknown_without_its_own_list():
    import inspect
    source = inspect.getsource(HybridProcessor.set_processing_mode)
    assert '"reference", "adaptive", "hybrid"' not in source
    processor = HybridProcessor.__new__(HybridProcessor)
    with pytest.raises(ValueError):
        HybridProcessor.set_processing_mode(processor, "nope")


def test_job_builder_uses_one_call():
    import sys
    from pathlib import Path
    backend = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    import inspect
    from core import job_config
    source = inspect.getsource(job_config)
    assert "elif job.mode ==" not in source, "the if/elif chain is back (#6218)"
    # The single dispatch: one set_processing_mode(job.mode) call.
    assert source.count("config.set_processing_mode(job.mode)") == 1
