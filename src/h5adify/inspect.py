from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

import anndata as ad


_STD_FIELDS = ["source", "dataset_id", "species", "technology", "sex", "age", "condition", "disease", "batch"]


def inspect_h5ad(path: Union[str, Path], max_fields: int = 30) -> Dict[str, Any]:
    path = Path(path)
    adata = ad.read_h5ad(path, backed="r")

    # summary
    out: Dict[str, Any] = {
        "path": str(path.resolve()),
        "n_obs": int(adata.n_obs),
        "n_vars": int(adata.n_vars),
        "obs_cols": [],
        "var_cols": [],
        "layers": [],
        "obsm": [],
        "uns": [],
        "has_spatial": False,
        "has_raw_counts": False,
        "x_dtype": "",
        "x_is_sparse": False,
        "missing_std_fields": {},
    }

    # keys
    try:
        out["obs_cols"] = list(adata.obs.columns)[:max_fields]
    except Exception:
        out["obs_cols"] = []
    try:
        out["var_cols"] = list(adata.var.columns)[:max_fields]
    except Exception:
        out["var_cols"] = []
    try:
        out["layers"] = sorted(list(adata.layers.keys()))
    except Exception:
        out["layers"] = []
    try:
        out["obsm"] = sorted(list(adata.obsm.keys()))
    except Exception:
        out["obsm"] = []
    try:
        out["uns"] = sorted(list(adata.uns.keys()))[:max_fields]
    except Exception:
        out["uns"] = []

    out["has_spatial"] = "spatial" in (out["obsm"] or [])
    out["has_raw_counts"] = "raw_counts" in (out["layers"] or [])

    # X dtype
    try:
        out["x_dtype"] = str(getattr(adata.X, "dtype", ""))
        out["x_is_sparse"] = "scipy.sparse" in str(type(adata.X)).lower()
    except Exception:
        pass

    # std obs missingness
    missing = {}
    for k in _STD_FIELDS:
        if k not in adata.obs:
            missing[k] = 1.0
            continue
        col = adata.obs[k]
        try:
            frac = float(col.isna().mean())
        except Exception:
            frac = 0.0
        missing[k] = frac
    out["missing_std_fields"] = missing

    # close
    try:
        adata.file.close()
    except Exception:
        pass

    return out


def format_inspect_text(report: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"File: {report.get('path')}")
    lines.append(f"Shape: n_obs={report.get('n_obs')}  n_vars={report.get('n_vars')}")
    lines.append(f"X: dtype={report.get('x_dtype')}  sparse={report.get('x_is_sparse')}")
    lines.append(f"Layers: {', '.join(report.get('layers') or [])}")
    lines.append(f"obsm: {', '.join(report.get('obsm') or [])}")
    lines.append(f"has_spatial={report.get('has_spatial')}  has_raw_counts={report.get('has_raw_counts')}")
    lines.append("")
    lines.append("Missingness (standard .obs fields):")
    miss = report.get("missing_std_fields", {}) or {}
    for k, v in miss.items():
        lines.append(f"  - {k}: {v:.3f}")
    lines.append("")
    lines.append("obs columns (head): " + ", ".join(report.get("obs_cols") or []))
    lines.append("var columns (head): " + ", ".join(report.get("var_cols") or []))
    return "\n".join(lines)
