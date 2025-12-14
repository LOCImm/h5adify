from __future__ import annotations

"""Source registry.

Imports are performed lazily so optional extras (e.g. pysodb) are only required
when actually used.
"""


def get_source(name: str, **kwargs):
    """Instantiate a source by name.

    Parameters
    ----------
    name:
        One of: geo, cellxgene, sodb, scp, ucsc, ema
    kwargs:
        Forwarded to the source constructor (typically: policy=ObsPolicy(...)).
    """

    n = (name or "").lower().strip()

    if n == "geo":
        from .sources.geo import GEOSource
        return GEOSource(**kwargs)

    if n in ("cellxgene", "cxg", "cz", "cziscience"):
        from .sources.cellxgene import CellxGeneSource
        return CellxGeneSource(**kwargs)

    if n == "sodb":
        from .sources.sodb import SODBSource
        return SODBSource(**kwargs)

    if n in ("scp", "singlecellportal", "single-cell-portal", "broad"):
        from .sources.scp import SingleCellPortalSource
        return SingleCellPortalSource(**kwargs)

    if n == "ucsc":
        from .sources.ucsc import UCSCSource
        return UCSCSource(**kwargs)

    if n in ("ema", "ebi", "biostudies"):
        from .sources.ema import EMASource
        return EMASource(**kwargs)

    raise ValueError(
        f"Unknown source '{name}'. Supported: geo, cellxgene, sodb, scp, ucsc, ema"
    )
