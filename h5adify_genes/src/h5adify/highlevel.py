from __future__ import annotations

from typing import Dict, List, Optional, Union

from .config import GeneOptions, ObsMode
from .registry import get_source


def download(
    source: str,
    *,
    dataset_id: str,
    outdir: str,
    merge_samples: bool = True,
    overrides: Optional[Dict[str, str]] = None,
    obs_policy: ObsMode = ObsMode.loose,
    gene_options: Optional[GeneOptions] = None,
) -> Union[str, List[str]]:
    """High-level convenience wrapper around a source downloader."""
    overrides = overrides or {}
    src = get_source(source)
    paths = src.download(
        dataset_id=dataset_id,
        outdir=outdir,
        merge_samples=merge_samples,
        overrides=overrides,
        obs_policy=obs_policy,
        gene_options=gene_options,
    )
    if isinstance(paths, list) and len(paths) == 1:
        return paths[0]
    return paths


def batch_download(
    ids: List[str],
    *,
    outdir: str,
    merge_samples: bool = True,
    overrides: Optional[Dict[str, str]] = None,
    obs_policy: ObsMode = ObsMode.loose,
    gene_options: Optional[GeneOptions] = None,
) -> List[str]:
    """Download multiple datasets. IDs are 'source:dataset_id'."""
    overrides = overrides or {}
    out: List[str] = []
    for item in ids:
        if ":" not in item:
            raise ValueError(f"Invalid id '{item}'. Expected 'source:dataset_id'")
        source, dataset_id = item.split(":", 1)
        res = download(
            source,
            dataset_id=dataset_id,
            outdir=outdir,
            merge_samples=merge_samples,
            overrides=overrides,
            obs_policy=obs_policy,
            gene_options=gene_options,
        )
        if isinstance(res, list):
            out.extend(res)
        else:
            out.append(res)
    return out
