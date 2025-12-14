from __future__ import annotations

from .sources.cellxgene import CellxGeneSource
from .sources.geo import GEOSource
from .sources.scp import SingleCellPortalSource
from .sources.ucsc import UCSCSource
from .sources.ema import EMASource

SOURCES = {
    "geo": GEOSource,
    "cellxgene": CellxGeneSource,
    "scp": SingleCellPortalSource,
    "ucsc": UCSCSource,
    "ema": EMASource,
}

def get_source(name: str, **kwargs):
    name = name.lower()
    if name == "sodb":
        from .sources.sodb import SODBSource
        return SODBSource(**kwargs)
    if name not in SOURCES:
        raise ValueError(
            f"Unknown source '{name}'. Available: {sorted(list(SOURCES.keys()) + ['sodb'])}"
        )
    return SOURCES[name](**kwargs)
