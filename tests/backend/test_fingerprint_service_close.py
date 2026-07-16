"""
Regression: FingerprintService disposes its self-created engine (#4501)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When constructed without a session_factory (both production owners do this),
FingerprintService builds its own SQLAlchemy engine but previously exposed no
disposal path, so each discarded owner leaked the engine's connection pool
until GC. close() now disposes the self-created engine (only), idempotently,
and both owners call it during teardown.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.analysis.fingerprint.fingerprint_service import FingerprintService


def test_close_disposes_self_created_engine_and_is_idempotent(tmp_path):
    svc = FingerprintService(db_path=tmp_path / "fp.db")
    engine = svc._engine
    assert engine is not None, "expected a self-created engine when no factory injected"

    with patch.object(engine, "dispose") as disposed:
        svc.close()
        disposed.assert_called_once()
        # Second close must be a safe no-op (engine already dropped).
        svc.close()
        disposed.assert_called_once()

    assert svc._engine is None


def test_close_does_not_dispose_injected_factory_engine():
    """RETURN VALUE: an injected session_factory's engine is owned by the caller
    and must NOT be disposed."""
    factory = MagicMock()
    svc = FingerprintService(session_factory=factory)
    assert svc._engine is None
    svc.close()  # must not raise and has nothing to dispose
    assert svc._engine is None


def test_del_safety_net_disposes(tmp_path):
    """__del__ disposes the engine for owners that forget to call close()."""
    svc = FingerprintService(db_path=tmp_path / "fp.db")
    engine = svc._engine
    assert engine is not None
    with patch.object(engine, "dispose") as disposed:
        svc.__del__()
        disposed.assert_called_once()


def test_simple_mastering_pipeline_close_disposes_service():
    """The SimpleMasteringPipeline owner disposes the service on close()."""
    from auralis.core.simple_mastering import SimpleMasteringPipeline

    pipeline = SimpleMasteringPipeline()
    # Touch the lazy property so a service (and engine) actually exists.
    svc = pipeline.fingerprint_service
    assert svc._engine is not None
    with patch.object(svc, "close", wraps=svc.close) as spy:
        pipeline.close()
        spy.assert_called_once()
    assert pipeline._fingerprint_service is None
