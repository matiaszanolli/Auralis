"""
Normalizer statistics and persistence (split from normalizer.py, #5838): the
per-dimension statistics record and the JSON save/load of a fitted normalizer.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...utils.logging import error, info, warning


@dataclass
class DimensionStats:
    """Statistics for a single fingerprint dimension"""
    name: str
    min_val: float
    max_val: float
    mean: float
    std: float
    count: int  # Number of samples used to calculate stats

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'min': self.min_val,
            'max': self.max_val,
            'mean': self.mean,
            'std': self.std,
            'count': self.count
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DimensionStats:
        """Create from dictionary"""
        return cls(
            name=data['name'],
            min_val=data['min'],
            max_val=data['max'],
            mean=data['mean'],
            std=data['std'],
            count=data['count']
        )


class NormalizerPersistenceMixin:
    """State is created by FingerprintNormalizer.__init__."""

    use_robust: bool
    percentile_range: tuple[float, float]
    stats: dict[str, DimensionStats]
    fitted: bool

    def save(self, filepath: str) -> bool:
        """
        Save normalization statistics to JSON file

        Args:
            filepath: Path to save statistics

        Returns:
            True if successful, False otherwise
        """
        if not self.fitted:
            warning("Normalizer not fitted, nothing to save")
            return False

        try:
            data = {
                'use_robust': self.use_robust,
                'percentile_range': list(self.percentile_range),
                'dimensions': {
                    name: stats.to_dict()
                    for name, stats in self.stats.items()
                }
            }

            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            info(f"Normalization statistics saved to {filepath}")
            return True

        except Exception as e:
            error(f"Failed to save normalization statistics: {e}")
            return False

    def load(self, filepath: str) -> bool:
        """
        Load normalization statistics from JSON file

        Args:
            filepath: Path to load statistics from

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filepath) as f:
                data = json.load(f)

            self.use_robust = data['use_robust']
            self.percentile_range = tuple(data['percentile_range'])
            self.stats = {
                name: DimensionStats.from_dict(stats_data)
                for name, stats_data in data['dimensions'].items()
            }

            self.fitted = True
            info(f"Normalization statistics loaded from {filepath}")
            return True

        except Exception as e:
            error(f"Failed to load normalization statistics: {e}")
            return False
