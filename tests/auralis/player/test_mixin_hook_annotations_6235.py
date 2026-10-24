"""
Mixin host-hook annotations (#6235)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Split mixins used to declare "the host must provide this" hooks as real
``raise NotImplementedError`` methods — a runtime stub for a typing-only
concern: it occupies the MRO ahead of any sibling mixin that might later
legitimately provide the method, shows up in NotImplementedError censuses
as fake debt, and duplicates signatures across sibling mixins. The
replacement is the bare ``Callable[...]`` annotation idiom
(player_queue_navigation_mixin.py's precedent): the mixin adds no name to
its ``__dict__`` and the host's own method always wins the MRO.

This pins both halves for every converted host: the hook name is absent
from each mixin's ``__dict__``, and ``getattr(Host, name)`` resolves to
the host class itself.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path

_BACKEND = str(Path(__file__).resolve().parents[3] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from auralis.analysis.dynamic_range import DynamicRangeAnalyzer  # noqa: E402
from auralis.analysis.dynamic_range_dynamics import DynamicsMetricsMixin  # noqa: E402
from auralis.library.metadata_editor.batch import BatchUpdateMixin  # noqa: E402
from auralis.library.metadata_editor.metadata_editor import MetadataEditor  # noqa: E402
from auralis.player.gapless_playback_engine import GaplessPlaybackEngine  # noqa: E402
from auralis.player.gapless_prebuffer import PrebufferMixin  # noqa: E402
from auralis.player.integration_library import LibraryLoadingMixin  # noqa: E402
from auralis.player.integration_manager import IntegrationManager  # noqa: E402
from auralis.player.integration_reporting import PlaybackReportingMixin  # noqa: E402
from auralis.player.components.queue_manager import QueueManager  # noqa: E402
from auralis.player.components.queue_navigation import QueueNavigationMixin  # noqa: E402
from auralis.player.components.queue_shuffle import ShuffleMixin  # noqa: E402
from auralis.player.queue_controller import QueueController  # noqa: E402
from auralis.player.queue_loading import QueueLoadingMixin  # noqa: E402
from core.streamlined_lifecycle import WorkerLifecycleMixin  # noqa: E402
from services.library_auto_scanner import LibraryAutoScanner  # noqa: E402
from services.scanner_watchdog import WatchdogMixin  # noqa: E402

# core.streamlined_worker (the WorkerLifecycleMixin host) is currently
# unimportable: the 66931f63 split left core.chunk_cache_manager and
# core/encoding/wav_encoder in a cycle, which breaks every
# test_streamlined_worker_* collection at clean HEAD too. Its host-MRO
# half joins this table when that lands; the mixin's __dict__ half (the
# part this issue changed) is checked below regardless.
from core.streamlined_worker import StreamlinedCacheWorker  # noqa: E402

# (mixin, hook name, composed host)
SITES = [
    (DynamicsMetricsMixin, "_get_dynamic_range_recommendations", DynamicRangeAnalyzer),
    (LibraryLoadingMixin, "set_current_track", IntegrationManager),
    (LibraryLoadingMixin, "_notify_callbacks", IntegrationManager),
    (PlaybackReportingMixin, "_notify_callbacks", IntegrationManager),
    (QueueLoadingMixin, "add_track", QueueController),
    (QueueLoadingMixin, "_notify_changed", QueueController),
    (PrebufferMixin, "_load_audio", GaplessPlaybackEngine),
    (QueueNavigationMixin, "_get_current_track_unlocked", QueueManager),
    (ShuffleMixin, "_get_current_track_unlocked", QueueManager),
    (BatchUpdateMixin, "write_metadata", MetadataEditor),
    (WatchdogMixin, "reload_config", LibraryAutoScanner),
]

# Host checks run only for the importable hosts (see the note above).
HOST_CHECKS = SITES + [
    (WorkerLifecycleMixin, "_process_priorities", StreamlinedCacheWorker),
]


def test_no_mixin_adds_a_hook_name_to_its_dict():
    """The annotation idiom must not occupy the mixin's ``__dict__``."""
    for mixin, hook, _host in HOST_CHECKS:
        assert hook not in vars(mixin), (mixin.__name__, hook)


def test_every_host_resolves_the_hook_to_itself():
    """The composed host's own method wins the MRO for every hook."""
    for _mixin, hook, host in SITES:
        for klass in type.mro(host):
            if hook in vars(klass):
                assert klass is host, (host.__name__, hook, klass.__name__)
                break
        else:
            raise AssertionError(f"{host.__name__} does not define {hook} anywhere")


def test_the_folded_get_repos_helper_left_no_method_behind():
    """The duplicate _get_repos wrappers were folded; nothing remains."""
    assert "_get_repos" not in vars(LibraryLoadingMixin)
    assert "_get_repos" not in vars(QueueLoadingMixin)
