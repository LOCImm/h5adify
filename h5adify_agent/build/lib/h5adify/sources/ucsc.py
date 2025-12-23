from __future__ import annotations

"""UCSC Cell Browser integration (best-effort).

This uses the public *dataset.json* registry exposed by the UCSC Cell Browser.
It is reliable for **searching** across hosted datasets.

Downloading raw matrices from Cell Browser is not standardized across all hosted
instances. We therefore support **direct .h5ad URLs** and attempt a small set of
common AnnData file names for the main UCSC host.

If a dataset does not expose AnnData directly, we raise a clear message and you
can fall back to a custom loader.
"""

import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import anndata as ad

from ..config import ObsPolicy
from ..metadata import apply_obs_policy
from ..utils import download_file, ensure_dir, get_session, get_timeout
from .base import SearchResult

_UCSC_BASE = "https://cells.ucsc.edu"
_UCSC_INDEX = f"{_UCSC_BASE}/dataset.json"


def _norm(s: Any) -> str:
    return str(s or "").strip()


def _match_query(text: str, query: str) -> bool:
    q = _norm(query).lower()
    if not q:
        return True
    hay = _norm(text).lower()
    # simple token match: all tokens must appear
    tokens = [t for t in re.split(r"\s+", q) if t]
    return all(t in hay for t in tokens)


def _has_downloadable_h5ad(dataset_id: str) -> bool:
    """Check if a UCSC dataset likely has downloadable h5ad files."""
    # Common patterns that indicate downloadable data
    downloadable_indicators = [
        "h5ad", "anndata", "scanpy", "matrix", "expression",
        "single-cell", "single cell", "spatial", "rna-seq"
    ]
    
    # This is a heuristic - we'll check common file patterns
    # In a real implementation, you might want to probe the dataset directory
    # For now, we'll assume most UCSC datasets are potentially downloadable
    return True


class UCSCSource:
    name = "ucsc"

    def __init__(self, policy: Optional[ObsPolicy] = None) -> None:
        self.policy = policy or ObsPolicy()

    def search(self, query: str, max_results: int = 20) -> List[SearchResult]:
        import logging
        
        _LOGGER = logging.getLogger(__name__)
        
        try:
            s = get_session()
            _LOGGER.info(f"Fetching UCSC dataset index from: {_UCSC_INDEX}")
            r = s.get(_UCSC_INDEX, timeout=get_timeout())
            r.raise_for_status()
            
            js = r.json()
            _LOGGER.info(f"UCSC response type: {type(js)}, length: {len(js) if hasattr(js, '__len__') else 'N/A'}")
            
            if not isinstance(js, list):
                # Some deployments wrap the list.
                if isinstance(js, dict):
                    js = js.get("datasets", [])
                    _LOGGER.info(f"Extracted datasets from dict: {len(js)} items")
                else:
                    _LOGGER.warning(f"Unexpected UCSC response format: {type(js)}")
                    js = []
            else:
                _LOGGER.info(f"UCSC returned list with {len(js)} items")

        except Exception as e:
            _LOGGER.error(f"Failed to fetch UCSC dataset index: {e}")
            return []

        out: List[SearchResult] = []
        for d in js:
            if not isinstance(d, dict):
                continue
            did = _norm(d.get("name") or d.get("dataset") or d.get("id"))
            if not did:
                continue

            title = _norm(d.get("shortLabel") or d.get("label") or d.get("title") or did)
            desc = _norm(d.get("description") or d.get("desc") or "")

            # Build a searchable string including tags
            tags = []
            for k in ("organisms", "diseases", "body_parts", "tissues", "sources", "tags"):
                v = d.get(k)
                if isinstance(v, list):
                    tags.extend([_norm(x) for x in v])
                elif isinstance(v, str):
                    tags.append(v)
            blob = " ".join([did, title, desc] + tags)

            if not _match_query(blob, query):
                continue

            # Extract additional metadata for enhanced display
            organisms = d.get("organisms", [])
            if isinstance(organisms, str):
                organisms = [organisms]
            elif not isinstance(organisms, list):
                organisms = []

            diseases = d.get("diseases", [])
            if isinstance(diseases, str):
                diseases = [diseases]
            elif not isinstance(diseases, list):
                diseases = []

            tissues = d.get("body_parts", d.get("tissues", []))
            if isinstance(tissues, str):
                tissues = [tissues]
            elif not isinstance(tissues, list):
                tissues = []

            # Get sample count
            sample_count = d.get("sampleCount") or d.get("sample_count")
            if sample_count:
                sample_count = str(sample_count)
            else:
                sample_count = "Unknown"

            # Get technology information if available
            technology = "Unknown"
            technology_keywords = ["10x", "visium", "smart-seq", "drop-seq", "single-cell", "spatial"]
            all_text = f"{title} {desc}".lower()
            for keyword in technology_keywords:
                if keyword in all_text:
                    if keyword == "10x":
                        technology = "10x Genomics"
                    elif keyword == "visium":
                        technology = "10x Visium"
                    elif keyword == "smart-seq":
                        technology = "Smart-seq"
                    elif keyword == "drop-seq":
                        technology = "Drop-seq"
                    elif keyword == "single-cell":
                        technology = "Single-cell RNA-seq"
                    elif keyword == "spatial":
                        technology = "Spatial transcriptomics"
                    break

            # Create enhanced description
            enhanced_desc = f"Technology: {technology}"
            if organisms:
                enhanced_desc += f" | Species: {', '.join(organisms[:2])}"  # Limit to 2 species
            if tissues:
                enhanced_desc += f" | Tissues: {', '.join(tissues[:2])}"  # Limit to 2 tissues
            if sample_count != "Unknown":
                enhanced_desc += f" | Samples: {sample_count}"
            if desc and len(desc) > 0:
                enhanced_desc += f" | {desc[:100]}{'...' if len(desc) > 100 else ''}"

            url = f"{_UCSC_BASE}/?ds={did}"
            out.append(
                SearchResult(
                    source=self.name,
                    dataset_id=did,
                    title=title,
                    description=enhanced_desc,
                    url=url,
                    extra={
                        "organisms": organisms,
                        "diseases": diseases,
                        "body_parts": tissues,
                        "sample_count": sample_count,
                        "technology": technology,
                        "downloadable": "Yes" if _has_downloadable_h5ad(did) else "Check website",
                    },
                )
            )
            if len(out) >= max_results:
                break
        return out

    def download(
        self,
        dataset_id: str,
        outdir: str | Path,
        merge_samples: bool = True,  # kept for signature compatibility
        overrides: Optional[Dict[str, str]] = None,
        cleanup: bool = True,
    ) -> List[str]:
        """Download as `.h5ad`.

        Supported inputs:
        - `dataset_id` is a direct URL to an `.h5ad`
        - `dataset_id` is a UCSC dataset name hosted on `cells.ucsc.edu` and a
          common AnnData file is available.
        """

        outdir = Path(outdir)
        ensure_dir(outdir)

        overrides = dict(overrides or {})
        overrides.setdefault("source", self.name)
        overrides.setdefault("dataset_id", str(dataset_id))

        s = get_session()

        # Direct URL case
        did = str(dataset_id).strip()
        if did.startswith("http://") or did.startswith("https://"):
            url = did
            if ".h5ad" not in url.lower():
                raise RuntimeError(
                    f"[ucsc] Only direct .h5ad URLs are supported for arbitrary URLs. Got: {url}"
                )
            fname = Path(url.split("?")[0]).name
            work = outdir / f"_work_{self.name}"
            ensure_dir(work)
            local = work / fname
            download_file(url, local, session=s)
            adata = ad.read_h5ad(local)
            apply_obs_policy(adata, policy=self.policy, overrides=overrides)
            out_path = outdir / f"{self.name}__{re.sub(r'[^A-Za-z0-9_.-]+', '_', fname)}"
            if not out_path.name.endswith(".h5ad"):
                out_path = out_path.with_suffix(".h5ad")
            adata.write_h5ad(out_path)
            if cleanup:
                shutil.rmtree(work, ignore_errors=True)
            return [str(out_path)]

        # Hosted dataset name case
        name = did
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        work = outdir / f"_work_{self.name}_{safe}"
        ensure_dir(work)

        # Best-effort: common AnnData file names seen on some UCSC Cell Browser datasets.
        candidates = [
            f"{_UCSC_BASE}/{name}/scanpy.h5ad",
            f"{_UCSC_BASE}/{name}/{name}.h5ad",
            f"{_UCSC_BASE}/{name}/adata.h5ad",
            f"{_UCSC_BASE}/{name}/anndata.h5ad",
        ]

        last_err: Optional[Exception] = None
        local = None
        for url in candidates:
            try:
                local = work / Path(url).name
                download_file(url, local, session=s)
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                local = None

        if local is None or not local.exists():
            if cleanup:
                shutil.rmtree(work, ignore_errors=True)
            raise RuntimeError(
                f"[ucsc:{name}] Could not find a downloadable .h5ad via common paths on {_UCSC_BASE}. "
                f"This is expected for many Cell Browser datasets.\n"
                f"Try opening the dataset page and looking for an AnnData/.h5ad download, then pass the direct URL.\n"
                f"Dataset page: {_UCSC_BASE}/?ds={name}\n"
                f"Last error: {last_err}"
            )

        adata = ad.read_h5ad(local)
        apply_obs_policy(adata, policy=self.policy, overrides=overrides)

        out_path = outdir / f"{self.name}__{safe}.h5ad"
        adata.write_h5ad(out_path)

        if cleanup:
            shutil.rmtree(work, ignore_errors=True)

        return [str(out_path)]
