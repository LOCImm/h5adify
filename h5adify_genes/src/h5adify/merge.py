from __future__ import annotations

from pathlib import Path
from typing import List, Union

import anndata as ad


def merge_h5ads(paths: List[Union[str, Path]], join: str = "outer") -> ad.AnnData:
    """Merge multiple .h5ad files by concatenating observations."""
    adatas = [ad.read_h5ad(str(p)) for p in paths]
    merged = ad.concat(adatas, join=join, axis=0, merge="same", label="batch", keys=[Path(p).stem for p in paths])
    try:
        merged.obs_names_make_unique()
    except Exception:
        pass
    return merged
