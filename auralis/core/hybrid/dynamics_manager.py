# -*- coding: utf-8 -*-

"""
Dynamics Manager
~~~~~~~~~~~~~~~

Manages dynamics processing parameters and state

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Any, Optional
from ...dsp.advanced_dynamics import DynamicsProcessor, DynamicsMode
from ...utils.logging import info, debug


class DynamicsManager:
    """Manages dynamics processing operations for HybridProcessor"""

    def __init__(self, dynamics_processor: DynamicsProcessor):
        self.dynamics_processor = dynamics_processor
        self.last_dynamics_info: Optional[Dict[str, Any]] = None

    def get_info(self) -> Dict[str, Any]:
        """Get dynamics processing information"""
        dynamics_info = self.dynamics_processor.get_processing_info()

        # Add recent processing info if available
        if self.last_dynamics_info is not None:
            dynamics_info['last_processing'] = self.last_dynamics_info

        return dynamics_info

    def set_mode(self, mode: str):
        """Set dynamics processing mode"""
        if mode in ['transparent', 'musical', 'broadcast', 'mastering', 'adaptive']:
            dynamics_mode = DynamicsMode(mode)
            self.dynamics_processor.set_mode(dynamics_mode)
            info(f"Dynamics mode set to: {mode}")
        else:
            debug(f"Invalid dynamics mode: {mode}")

    def reset(self):
        """Reset dynamics processing state"""
        self.dynamics_processor.reset()
        self.last_dynamics_info = None
        info("Dynamics processor state reset")
