from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

DEFAULT_REQUIRED_OBS: List[str] = [
    "source",
    "dataset_id",
    "sample_id",
    "species",
    "technology",
    "modality",
    "tissue",
    "region",
    "condition",
    "disease",
    "age",
    "sex",
    "batch",
]

@dataclass
class ObsPolicy:
    """Controls which obs fields must exist and how missing values are filled."""

    required: List[str] = field(default_factory=lambda: list(DEFAULT_REQUIRED_OBS))
    missing_value: str = "unknown"
    aliases: Dict[str, str] = field(default_factory=dict)

    def canonical_key(self, key: str) -> str:
        return self.aliases.get(key, key)
