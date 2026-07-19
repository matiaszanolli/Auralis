"""
Material Classifier
~~~~~~~~~~~~~~~~~~~~

Classifies audio material by dynamics and dispatches the matching processing
branch (#4252).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import TYPE_CHECKING

from ..mastering_config import SimpleMasteringConfig
from .base import ProcessingBranch
from .compressed_loud import CompressedLoudBranch
from .dynamic_loud import DynamicLoudBranch
from .quiet import QuietBranch

if TYPE_CHECKING:
    from ..simple_mastering import SimpleMasteringPipeline


class MaterialClassifier:
    """
    Classify audio material based on dynamics for processing branch selection.

    Uses 2D Loudness-War Restraint Principle:
    - LUFS (integrated loudness)
    - Crest factor (peak-to-RMS ratio)

    Material types:
    - **Compressed loud**: LUFS > -12, crest < 13 dB (modern mastering, needs gentle expansion)
    - **Dynamic loud**: LUFS > -12, crest >= 13 dB (well-mastered, preserve dynamics)
    - **Quiet**: LUFS <= -12 (needs full processing with makeup gain)
    """

    @staticmethod
    def classify(lufs: float, crest_db: float, config: SimpleMasteringConfig) -> str:
        """
        Determine processing branch based on LUFS and crest factor.

        Args:
            lufs: Integrated loudness in LUFS
            crest_db: Crest factor in dB
            config: Configuration with thresholds

        Returns:
            Material type: 'compressed_loud', 'dynamic_loud', or 'quiet'

        Examples:
            >>> config = SimpleMasteringConfig()
            >>> MaterialClassifier.classify(-10.0, 9.0, config)
            'compressed_loud'
            >>> MaterialClassifier.classify(-10.0, 15.0, config)
            'dynamic_loud'
            >>> MaterialClassifier.classify(-18.0, 12.0, config)
            'quiet'
        """
        if lufs > config.COMPRESSED_LOUD_THRESHOLD_LUFS:
            if crest_db < config.MODERATE_COMPRESSED_MIN_CREST:
                return 'compressed_loud'
            else:
                return 'dynamic_loud'
        else:
            return 'quiet'

    @staticmethod
    def get_branch(material_type: str, pipeline: 'SimpleMasteringPipeline') -> ProcessingBranch:
        """
        Factory method for branch instances.

        Args:
            material_type: Material classification from classify()
            pipeline: SimpleMasteringPipeline instance for method delegation

        Returns:
            Appropriate ProcessingBranch instance

        Raises:
            ValueError: If material_type is unknown
        """
        branches = {
            'compressed_loud': CompressedLoudBranch(pipeline),
            'dynamic_loud': DynamicLoudBranch(pipeline),
            'quiet': QuietBranch(pipeline)
        }

        if material_type not in branches:
            raise ValueError(f"Unknown material type: {material_type}")

        return branches[material_type]
