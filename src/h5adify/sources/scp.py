from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import anndata as ad
import requests
from bs4 import BeautifulSoup

from ..config import ObsPolicy
from ..metadata import apply_obs_policy
from ..utils import download_file, ensure_dir, is_url, rm_rf, safe_filename
from .base import SearchResult


class SingleCellPortalSource:
    name = "scp"

    def __init__(self, policy: Optional[ObsPolicy] = None):
        self.policy = policy or ObsPolicy()

    def search(self, query: str, max_results: int = 20) -> List[SearchResult]:
        url = "https://singlecell.broadinstitute.org/single_cell"
        params = {"terms": query, "type": "study", "page": 1}
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        out: List[SearchResult] = []
        for a in soup.select("a[href*='/single_cell/study/']"):
            href = a.get("href", "")
            m = re.search(r"/single_cell/study/(SCP\d+)", href)
            if not m:
                continue
            scp = m.group(1)
            title = a.get_text(strip=True) or scp
            out.append(SearchResult(source=self.name, dataset_id=scp, title=title, url="https://singlecell.broadinstitute.org" + href))
            if len(out) >= max_results:
                break
        return out

    def download(
        self,
        dataset_id: str,
        outdir: str,
        merge_samples: bool = True,
        overrides: Optional[Dict[str, str]] = None,
        cleanup: bool = True,
    ) -> List[str]:
        outdir = str(ensure_dir(outdir))
        workdir = ensure_dir(Path(outdir) / f"_work_scp_{safe_filename(dataset_id)}")
        produced: List[str] = []

        if is_url(dataset_id) and dataset_id.lower().endswith(".h5ad"):
            h5ad_path = download_file(dataset_id, workdir / "source.h5ad")
            adata = ad.read_h5ad(h5ad_path)
        else:
            if not re.fullmatch(r"SCP\d+", dataset_id):
                raise ValueError("SCP dataset_id must be like SCP263 (or a direct .h5ad URL).")
            adata = self._download_best_h5ad_from_study(dataset_id, workdir)

        sample_overrides = dict(overrides or {})
        sample_overrides.setdefault("source", self.name)
        sample_overrides.setdefault("dataset_id", dataset_id)
        sample_overrides.setdefault("sample_id", dataset_id)
        sample_overrides.setdefault("modality", "spatial" if "spatial" in adata.obsm else "sc/snRNA")

        apply_obs_policy(adata, self.policy, overrides=sample_overrides, source=self.name)
        out_path = Path(outdir) / f"scp_{safe_filename(dataset_id)}.h5ad"
        adata.write_h5ad(out_path)
        produced.append(str(out_path))

        if cleanup:
            rm_rf(workdir)
        return produced

    def _download_best_h5ad_from_study(self, scp_id: str, workdir: Path) -> ad.AnnData:
        url = f"https://singlecell.broadinstitute.org/single_cell/study/{scp_id}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        links = []
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if ".h5ad" in href.lower():
                if href.startswith("/"):
                    href = "https://singlecell.broadinstitute.org" + href
                links.append(href)

        if not links:
            raise RuntimeError(
                f"[{scp_id}] Could not find a direct public .h5ad link by scraping the study page. "
                "Try downloading from the portal UI and then convert locally."
            )

        best = links[0]
        best_size = -1
        for href in links:
            try:
                head = requests.head(href, timeout=30, allow_redirects=True)
                size = int(head.headers.get("content-length", 0))
            except Exception:
                size = 0
            if size > best_size:
                best_size = size
                best = href

        h5ad_path = download_file(best, workdir / f"{safe_filename(scp_id)}.h5ad")
        return ad.read_h5ad(h5ad_path)
