from __future__ import annotations

"""EMBL-EBI / BioStudies integration (best-effort).

In practice, EBI-hosted studies for single-cell/spatial data are often
registered in **BioStudies**. Many provide direct downloadable processed files
(including `.h5ad`).

This source:

* searches via the BioStudies `api/v1/search` endpoint (best-effort)
* downloads a study by accession and looks for `.h5ad` files (best-effort)

If no `.h5ad` is available, the command fails with a clear message so you can
fall back to a custom loader.
"""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import anndata as ad

from ..config import ObsPolicy
from ..metadata import apply_obs_policy
from ..utils import download_file, get_session, get_timeout
from .base import SearchResult

_EBI_SEARCH = "https://www.ebi.ac.uk/biostudies/api/v1/search"
_EBI_STUDY = "https://www.ebi.ac.uk/biostudies/api/v1/studies/{acc}"
_EBI_FILES = "https://www.ebi.ac.uk/biostudies/files/{acc}/{fname}"


def _flatten_files(obj: Any) -> Iterable[Dict[str, Any]]:
    """Yield file-like dicts from a BioStudies study JSON."""
    if isinstance(obj, dict):
        # Direct file records are usually dictionaries with fileName / path
        if any(k in obj for k in ("fileName", "path", "name")):
            yield obj
        for v in obj.values():
            yield from _flatten_files(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _flatten_files(it)


def _best_title(hit: Dict[str, Any]) -> str:
    for k in ("title", "studyTitle", "name", "accession"):
        v = hit.get(k)
        if v:
            return str(v)
    return ""


def _safe_json(r) -> Any:
    try:
        return r.json()
    except Exception:
        return json.loads(r.text)


def _is_h5ad(name: str) -> bool:
    n = name.lower()
    return n.endswith(".h5ad")


class EMASource:
    name = "ema"

    def __init__(self, policy: Optional[ObsPolicy] = None):
        self.policy = policy or ObsPolicy()

    def search(self, query: str, max_results: int = 20) -> List[SearchResult]:
        """Search BioStudies for matching studies.

        Note: this is best-effort; BioStudies search ranking can be broad.
        """
        s = get_session()
        # BioStudies uses a Lucene-like query; we keep it simple.
        params = {"query": query, "page": 1, "pageSize": max_results}
        r = s.get(_EBI_SEARCH, params=params, timeout=get_timeout())
        r.raise_for_status()
        js = _safe_json(r)

        hits: List[Dict[str, Any]] = []
        if isinstance(js, dict):
            # Common shapes: {"hits": [...]} or {"...": {"hits": [...]}}
            if isinstance(js.get("hits"), list):
                hits = js["hits"]
            elif isinstance(js.get("results"), dict) and isinstance(js["results"].get("hits"), list):
                hits = js["results"]["hits"]
            elif isinstance(js.get("data"), dict) and isinstance(js["data"].get("hits"), list):
                hits = js["data"]["hits"]
        elif isinstance(js, list):
            hits = js

        out: List[SearchResult] = []
        for h in hits[:max_results]:
            if not isinstance(h, dict):
                continue
            acc = h.get("accession") or h.get("acc") or h.get("id") or ""
            if not acc:
                continue
            title = _best_title(h) or str(acc)
            url = f"https://www.ebi.ac.uk/biostudies/studies/{acc}"
            out.append(SearchResult(source=self.name, dataset_id=str(acc), title=title, url=url, description=""))
        return out

    def download(
        self,
        dataset_id: str,
        outdir: str,
        merge_samples: bool = True,
        overrides: Optional[Dict[str, str]] = None,
        cleanup: bool = True,
    ) -> List[str]:
        """Download the first `.h5ad` found in a BioStudies study.

        If multiple `.h5ad` exist and `merge_samples=True`, they are concatenated.
        """
        Path(outdir).mkdir(parents=True, exist_ok=True)
        overrides = overrides or {}

        # If user passes direct URL to an h5ad, just download it.
        if re.match(r"^https?://", dataset_id) and dataset_id.lower().endswith(".h5ad"):
            target = Path(outdir) / (Path(dataset_id).name or "ebi.h5ad")
            download_file(dataset_id, str(target))
            adata = ad.read_h5ad(target)
            apply_obs_policy(adata, self.policy, {"source": self.name, "dataset_id": dataset_id, **overrides})
            adata.write_h5ad(target)
            return [str(target)]

        acc = dataset_id
        s = get_session()
        r = s.get(_EBI_STUDY.format(acc=acc), timeout=get_timeout())
        r.raise_for_status()
        study = _safe_json(r)

        files = list(_flatten_files(study))
        h5ads: List[str] = []
        for f in files:
            fname = f.get("fileName") or f.get("name") or f.get("path")
            if not fname:
                continue
            fname = str(fname)
            if _is_h5ad(fname):
                h5ads.append(fname)

        if not h5ads:
            raise ValueError(
                f"[EMA] No .h5ad found for study {acc}. "
                "This study may only provide raw data (FASTQ/SRA) or Seurat .rds. "
                "Consider using a custom loader for this accession."
            )

        work = Path(outdir) / f"_tmp_ema_{acc}"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True, exist_ok=True)

        downloaded: List[Path] = []
        try:
            for fname in h5ads:
                url = f.get("url") if isinstance(f, dict) else None  # not reliable; ignore
                # Build canonical file URL
                file_url = _EBI_FILES.format(acc=acc, fname=fname.lstrip("/"))
                out_path = work / Path(fname).name
                download_file(file_url, str(out_path))
                downloaded.append(out_path)

            # Load and optionally merge
            adatas = [ad.read_h5ad(p) for p in downloaded]
            if len(adatas) == 1:
                merged = adatas[0]
            else:
                merged = ad.concat(adatas, join="outer", label="ema_file", keys=[p.name for p in downloaded])

            apply_obs_policy(
                merged,
                self.policy,
                {
                    "source": self.name,
                    "dataset_id": acc,
                    **overrides,
                },
            )

            final = Path(outdir) / f"ema_{acc}.h5ad"
            merged.write_h5ad(final)
            return [str(final)]
        finally:
            if cleanup:
                shutil.rmtree(work, ignore_errors=True)
