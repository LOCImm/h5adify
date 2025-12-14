from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .merge import merge_h5ads
from .registry import get_source
from .utils import ensure_dir


def download(
    source: str,
    outdir: str,
    merge_samples: bool = True,
    cleanup: bool = True,
    overrides: Optional[Dict[str, str]] = None,
    **kwargs,
) -> str | List[str]:
    src = get_source(source)
    did = kwargs.get("id") or kwargs.get("gse") or kwargs.get("dataset_id")
    outs = src.download(
        dataset_id=did,
        outdir=outdir,
        merge_samples=merge_samples,
        overrides=overrides,
        cleanup=cleanup,
    )
    return outs[0] if len(outs) == 1 else outs


def batch_download(
    ids: Sequence[str],
    outdir: str,
    merge_out: Optional[str] = None,
    merge_join: str = "outer",
    merge_label: str = "batch",
    merge_keys: Optional[List[str]] = None,
    merge_samples: bool = True,
    cleanup: bool = True,
    overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, List[str]]:
    outdir = str(ensure_dir(outdir))
    produced: Dict[str, List[str]] = {}
    all_paths: List[str] = []

    for item in ids:
        if ":" not in item:
            raise ValueError(f"Invalid id '{item}'. Expected 'source:dataset_id'")
        source, did = item.split(":", 1)
        src = get_source(source.strip())
        outs = src.download(did.strip(), outdir=outdir, merge_samples=merge_samples, overrides=overrides, cleanup=cleanup)
        produced[item] = outs
        all_paths.extend(outs)

    if merge_out:
        merged = merge_h5ads(all_paths, join=merge_join, label=merge_label, keys=merge_keys)
        Path(merge_out).parent.mkdir(parents=True, exist_ok=True)
        merged.write_h5ad(merge_out)

    return produced
