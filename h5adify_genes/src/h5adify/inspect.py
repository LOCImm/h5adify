from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

import anndata as ad

from .genes import genes_info_from_adata


def inspect_h5ad(path: Union[str, Path], backed: bool = True) -> Dict[str, Any]:
    """Inspect a single .h5ad and return a JSON-serializable summary."""
    p = Path(path)
    adata = ad.read_h5ad(p, backed="r" if backed else None)

    layers = list(getattr(adata, "layers", {}).keys())
    obsm = list(getattr(adata, "obsm", {}).keys())
    obs_keys = list(getattr(adata, "obs", {}).keys())
    var_keys = list(getattr(adata, "var", {}).keys())

    info: Dict[str, Any] = {
        "path": str(p),
        "filename": p.name,
        "n_obs": int(adata.n_obs),
        "n_vars": int(adata.n_vars),
        "layers": layers,
        "obsm": obsm,
        "has_spatial": "spatial" in obsm,
        "obs_keys": obs_keys,
        "var_keys": var_keys,
        "uns_keys": list(getattr(adata, "uns", {}).keys()),
        "genes": genes_info_from_adata(adata),
    }

    # convenience: include first-row metadata if present
    for k in ("species", "technology", "sex", "age", "condition", "batch", "disease"):
        if k in getattr(adata, "obs", {}).columns:
            try:
                info[k] = str(adata.obs[k].iloc[0])
            except Exception:
                pass

    return info
