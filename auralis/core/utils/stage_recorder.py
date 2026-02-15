"""
Stage Recorder
~~~~~~~~~~~~~~

Recording utility for processing stages in mastering pipeline.

Eliminates repetitive null-check patterns when accumulating stage information.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


class StageRecorder:
    """
    Record processing stages for debugging and analysis.

    Consolidates the pattern of conditionally appending stage info dicts
    to a stages list. Eliminates repetitive null-check patterns throughout
    the mastering pipeline.

    Usage:
        >>> recorder = StageRecorder()
        >>> recorder.add({'stage': 'peak_reduction', 'target': -2.0})
        >>> recorder.add(None)  # Ignored
        >>> recorder.to_dict()
        {'stages': [{'stage': 'peak_reduction', 'target': -2.0}]}

    Benefits:
    - Eliminates 12+ "if info: info['stages'].append()" patterns
    - Central point for stage logging
    - Could add timing/validation in future
    """

    def __init__(self):
        """Initialize empty stage recorder."""
        self.stages: list[dict] = []

    def add(self, stage_info: dict | None) -> None:
        """
        Append stage info if not None.

        Args:
            stage_info: Stage information dict or None

        Examples:
            >>> recorder = StageRecorder()
            >>> recorder.add({'stage': 'bass_enhance', 'boost_db': 2.0})
            >>> recorder.add(None)  # Silently ignored
            >>> len(recorder.stages)
            1
        """
        if stage_info is not None:
            self.stages.append(stage_info)

    def to_dict(self) -> dict:
        """
        Return stages as dict.

        Returns:
            Dict with 'stages' key containing list of stage info dicts

        Example:
            >>> recorder = StageRecorder()
            >>> recorder.add({'stage': 'test'})
            >>> recorder.to_dict()
            {'stages': [{'stage': 'test'}]}
        """
        return {'stages': self.stages}

    def merge(self, other: 'StageRecorder') -> None:
        """
        Merge another recorder's stages into this one.

        Useful when combining stages from different processing paths
        or sub-processors.

        Args:
            other: Another StageRecorder instance

        Example:
            >>> recorder1 = StageRecorder()
            >>> recorder1.add({'stage': 'A'})
            >>> recorder2 = StageRecorder()
            >>> recorder2.add({'stage': 'B'})
            >>> recorder1.merge(recorder2)
            >>> len(recorder1.stages)
            2
        """
        self.stages.extend(other.stages)

    def __len__(self) -> int:
        """Return number of stages recorded."""
        return len(self.stages)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"StageRecorder(stages={len(self.stages)})"
