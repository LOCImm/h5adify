from __future__ import annotations

from typing import List, Optional

import anndata as ad


def merge_h5ads(
    paths: List[str],
    join: str = "outer",
    label: Optional[str] = "batch",
    keys: Optional[List[str]] = None,
) -> ad.AnnData:
    adatas = [ad.read_h5ad(p) for p in paths]
    if keys is None:
        keys = [f"ds{i}" for i in range(len(adatas))]
    merged = ad.concat(adatas, join=join, label=label, keys=keys, index_unique="-")
    return merged
