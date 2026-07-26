"""
Player Properties Mixin
~~~~~~~~~~~~~~~~~~~~~~~

Backward-compatible property surface for AudioPlayer, extracted from
enhanced_audio_player.py (#4249).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

from .audio_file_manager import AudioFileManager
from .integration_manager import IntegrationManager


class PlayerPropertiesMixin:
    """Delegating properties onto AudioPlayer's component objects.

    Mixed into AudioPlayer so ``player.audio_data``, ``player.current_track``,
    etc. keep working exactly as before — the properties read/write
    ``self.file_manager`` / ``self.integration``, which AudioPlayer.__init__
    sets on the same instance. (``position`` stays on AudioPlayer itself; see
    note below.)

    Lock discipline (#4574) — every data-bearing setter here acquires the same
    lock its readers hold, so a reader never observes a half-updated composite:

    ==================  ====================================================
    Property            Guarding lock
    ==================  ====================================================
    ``current_track``   ``IntegrationManager._position_lock``, via
                        :py:meth:`IntegrationManager.set_current_track`
    ``audio_data``      ``AudioFileManager._audio_lock`` (#3443)
    ``reference_data``  ``AudioFileManager._audio_lock``
    ``sample_rate``     ``AudioFileManager._audio_lock``
    ``current_file``    read-only here; written by ``AudioFileManager``
                        under ``_audio_lock``
    ``reference_file``  read-only here; written by ``AudioFileManager``
                        under ``_audio_lock``
    ==================  ====================================================

    The raw *read* side of ``AudioFileManager`` is tracked separately by #3785.
    """

    file_manager: AudioFileManager
    integration: IntegrationManager

    @property
    def current_file(self) -> str | None:
        """Get current audio file path"""
        return self.file_manager.current_file

    @property
    def current_track(self) -> Any:
        """Get current track object from library"""
        return self.integration.current_track

    @current_track.setter
    def current_track(self, value: Any) -> None:
        """Set current track under _position_lock (#4574)"""
        self.integration.set_current_track(value)

    @property
    def reference_file(self) -> str | None:
        """Get current reference file path"""
        return self.file_manager.reference_file

    @property
    def audio_data(self) -> Any:
        """Get raw audio data"""
        return self.file_manager.audio_data

    @audio_data.setter
    def audio_data(self, value: Any) -> None:
        """Set audio data under lock with dtype enforcement (#3443)"""
        import numpy as np
        with self.file_manager._audio_lock:
            if value is not None and isinstance(value, np.ndarray):
                if value.dtype not in (np.float32, np.float64):
                    value = value.astype(np.float32)
            self.file_manager.audio_data = value

    @property
    def reference_data(self) -> Any:
        """Get raw reference audio data"""
        return self.file_manager.reference_data

    @reference_data.setter
    def reference_data(self, value: Any) -> None:
        """Set reference data under _audio_lock (#4574)"""
        with self.file_manager._audio_lock:
            self.file_manager.reference_data = value

    # `position` stays on AudioPlayer itself, not this mixin — a white-box
    # regression test (test_no_direct_attribute_bypass) inspects
    # `type(player).__dict__["position"]` directly (no MRO walk) to verify
    # the setter delegates to `playback.seek()`.

    @property
    def sample_rate(self) -> int:
        """Get current sample rate"""
        return self.file_manager.sample_rate

    @sample_rate.setter
    def sample_rate(self, value: int) -> None:
        """Set sample rate under _audio_lock (#4574)"""
        with self.file_manager._audio_lock:
            self.file_manager.sample_rate = value
