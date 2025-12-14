from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import anndata as ad

from ..metadata import apply_obs_policy
from ..utils import download_file, ensure_dir, get_session, get_timeout
from .base import BaseSource, DownloadResult, SearchResult


_UCSC_ROOT_INDEX = "https://cells.ucsc.edu/dataset.json"  # top-level dataset registry
_UCSC_BASE = "https://cells.ucsc.edu/"


def _safe_lower(x: Any) -> str:
    return str(x or "").lower()


def _match_query(query: str, *fields: str) -> bool:
    q = _safe_lower(query).strip()
    if not q:
        return True
    hay = " ".join(_safe_lower(f) for f in fields)
    # AND over tokens (simple, robust)
    toks = [t for t in re.split(r"\s+", q) if t]
    return all(t in hay for t in toks)


def _get_json(url: str) -> Dict[str, Any]:
    s = get_session()
    r = s.get(url, timeout=get_timeout())
    r.raise_for_status()
    js = r.json()
    if isinstance(js, dict):
        return js
    # UCSC should return dict; if not, wrap
    return {"data": js}


def _flatten_ucsc_datasets(max_to_scan: int = 10_000) -> Iterable[Dict[str, Any]]:
    """
    Traverse the UCSC Cell Browser dataset hierarchy.
    Approach per UCSC docs: root dataset.json -> per-collection dataset.json -> children datasets. :contentReference[oaicite:2]{index=2}
    """
    root = _get_json(_UCSC_ROOT_INDEX)
    top = root.get("datasets", []) or root.get("data", [])
    if not isinstance(top, list):
        return

    scanned = 0
    for parent in top:
        if not isinstance(parent, dict):
            continue
        parent_name = str(parent.get("name", "")).strip().strip("/")
        if not parent_name:
            continue

        # Emit the parent as a searchable hit too
        yield {
            "name": parent_name,
            "title": parent.get("shortLabel") or parent.get("label") or parent_name,
            "desc": parent.get("longLabel") or parent.get("description") or "",
            "type": "collection",
        }

        # Pull children from parent dataset.json
        try:
            parent_js = _get_json(f"{_UCSC_BASE}{parent_name}/dataset.json")
        except Exception:
            continue

        children = parent_js.get("datasets", [])
        if isinstance(children, list):
            for ch in children:
                if not isinstance(ch, dict):
                    continue
                ch_name = str(ch.get("name", "")).strip().strip("/")
                if not ch_name:
                    continue
                # some dataset.json already uses fully-qualified names (e.g., "mouse-limb/10x")
                if "/" not in ch_name:
                    ch_name = f"{parent_name}/{ch_name}"

                yield {
                    "name": ch_name,
                    "title": ch.get("shortLabel") or ch.get("label") or ch_name,
                    "desc": ch.get("longLabel") or ch.get("description") or "",
                    "type": "dataset",
                }

                scanned += 1
                if scanned >= max_to_scan:
                    return


def _find_first_h5ad_in_index_html(html: str) -> Optional[str]:
    # Apache-style listing: href="something.h5ad"
    m = re.search(r'href="([^"]+\.h5ad)"', html, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    # Sometimes plain text: something.h5ad
    m = re.search(r"([A-Za-z0-9_.-]+\.h5ad)", html, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


class UCSCSource(BaseSource):
    name = "ucsc"

    def search(self, query: str, max_results: int = 20) -> List[SearchResult]:
        out: List[SearchResult] = []
        for item in _flatten_ucsc_datasets():
            if _match_query(query, item.get("name", ""), item.get("title", ""), item.get("desc", "")):
                did = str(item.get("name", ""))
                title = str(item.get("title", did))
                url = f"{_UCSC_BASE}?ds={did}"
                out.append(SearchResult(source=self.name, dataset_id=did, title=title, url=url))
                if len(out) >= max_results:
                    break
        return out

    def download(
        self,
        dataset_id: str,
        outdir: str | Path,
        policy=None,
        overrides: Optional[Dict[str, str]] = None,
        keep_work: bool = False,
        no_merge_samples: bool = False,  # unused (UCSC datasets are already assembled)
    ) -> DownloadResult:
        if policy is None:
            policy = self.default_policy()
        overrides = dict(overrides or {})
        overrides.setdefault("source", self.name)
        overrides.setdefault("dataset_id", dataset_id)

        outdir = Path(outdir)
        ensure_dir(outdir)

        work = outdir / f"_work_{self.name}_{re.sub(r'[^A-Za-z0-9_.-]+', '_', dataset_id)}"
        ensure_dir(work)

        base_url = f"{_UCSC_BASE}{dataset_id.strip('/')}/"
        s = get_session()

        # Try to find a .h5ad file in the directory listing
        r = s.get(base_url, timeout=get_timeout())
        r.raise_for_status()
        h5ad_name = _find_first_h5ad_in_index_html(r.text)

        if not h5ad_name:
            raise RuntimeError(
                f"[ucsc:{dataset_id}] Could not locate a .h5ad in {base_url}. "
                f"Many UCSC datasets ship as exprMatrix/meta.tsv instead; add a custom loader if needed."
            )

        h5ad_url = base_url + h5ad_name
        local_h5ad = work / h5ad_name
        download_file(h5ad_url, local_h5ad, session=s)

        adata = ad.read_h5ad(local_h5ad)
        apply_obs_policy(adata, policy=policy, overrides=overrides)

        out_path = outdir / f"{self.name}__{re.sub(r'[^A-Za-z0-9_.-]+', '_', dataset_id)}.h5ad"
        adata.write_h5ad(out_path)

        if not keep_work:
            shutil.rmtree(work, ignore_errors=True)

        return DownloadResult(
            source=self.name,
            dataset_id=dataset_id,
            out_paths=[out_path],
            workdir=work if keep_work else None,
        )
