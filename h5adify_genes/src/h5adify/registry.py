from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .sources.geo import GEOSource
from .sources.cellxgene import CellxGeneSource
from .sources.sodb import SODBSource
from .sources.scp import SingleCellPortalSource
from .sources.ucsc import UCSCSource
from .sources.ema import EMASource


@lru_cache(maxsize=1)
def _sources() -> Dict[str, object]:
    return {
        "geo": GEOSource(),
        "cellxgene": CellxGeneSource(),
        "sodb": SODBSource(),
        "scp": SingleCellPortalSource(),
        "ucsc": UCSCSource(),
        "ema": EMASource(),
    }


def get_source(name: str):
    name = (name or "").lower().strip()
    if name not in _sources():
        raise ValueError(f"Unknown source '{name}'. Available: {', '.join(sorted(_sources().keys()))}")
    return _sources()[name]
