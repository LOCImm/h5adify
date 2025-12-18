from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from .config import ObsPolicy


def _ensure_obs_col(adata, key: str, value: str) -> None:
    if key not in adata.obs:
        adata.obs[key] = value
    else:
        s = adata.obs[key]
        if pd.api.types.is_categorical_dtype(s):
            s = s.astype(str)
        adata.obs[key] = s.fillna(value).replace({"": value})


def apply_obs_policy(
    adata,
    policy: ObsPolicy,
    overrides: Optional[Dict[str, str]] = None,
    sample_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    source: Optional[str] = None,
) -> None:
    overrides = overrides or {}

    if source:
        overrides.setdefault("source", source)
    if dataset_id:
        overrides.setdefault("dataset_id", dataset_id)
    if sample_id:
        overrides.setdefault("sample_id", sample_id)

    for alias, canon in policy.aliases.items():
        if alias in adata.obs and canon not in adata.obs:
            adata.obs[canon] = adata.obs[alias].astype(str)

    for k in policy.required:
        _ensure_obs_col(adata, k, policy.missing_value)

    for k, v in overrides.items():
        canon = policy.canonical_key(k)
        adata.obs[canon] = str(v)
