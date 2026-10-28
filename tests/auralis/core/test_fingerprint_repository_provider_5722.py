"""The engine gets its fingerprint repository from a registered provider (#5722).

hybrid_setup imported the backend's top-level `config.globals`, which only resolves when
auralis-web/backend is on sys.path and otherwise silently degraded to "no repository". A provider
the application registers at startup replaces that import; with none registered the processor
runs on the legacy deficit EQ, as it did in a bare context.
"""

import ast
from pathlib import Path

import pytest

from auralis.core import fingerprint_repository_provider as provider
from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor

ENGINE = Path(__file__).resolve().parents[3] / "auralis"


@pytest.fixture(autouse=True)
def _restore_provider():
    saved = provider._provider
    yield
    provider.set_fingerprint_repository_provider(saved)


def test_no_provider_means_no_repository():
    provider.set_fingerprint_repository_provider(None)

    assert provider.get_fingerprint_repository() is None


def test_a_registered_provider_is_called_each_time():
    repositories = iter(["first", "second"])
    provider.set_fingerprint_repository_provider(lambda: next(repositories))

    assert [provider.get_fingerprint_repository(), provider.get_fingerprint_repository()] == ["first", "second"]


def test_a_failing_provider_degrades_to_none():
    def broken():
        raise RuntimeError("library closed")

    provider.set_fingerprint_repository_provider(broken)

    assert provider.get_fingerprint_repository() is None


def test_a_new_processor_hands_the_repository_to_continuous_mode():
    sentinel = object()
    provider.set_fingerprint_repository_provider(lambda: sentinel)

    processor = HybridProcessor(UnifiedConfig())

    assert processor.continuous_mode.fingerprint_repository is sentinel


def test_a_processor_without_a_provider_still_builds():
    provider.set_fingerprint_repository_provider(None)

    processor = HybridProcessor(UnifiedConfig())

    assert processor.continuous_mode.fingerprint_repository is None


def test_the_engine_package_imports_nothing_from_backend_config():
    offenders = []
    for path in ENGINE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "").split(".")[0] == "config":
                offenders.append(f"{path.relative_to(ENGINE)}:{node.lineno}")

    assert offenders == []
