from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import anndata as ad

from ..config import ObsPolicy, GeneOptions
from ..genes import apply_gene_policy
from ..metadata import apply_obs_policy
from ..utils import download_file, ensure_dir, is_url, rm_rf, safe_filename, get_session, get_timeout
from .base import SearchResult

_CXG_SEARCH = "https://api.cellxgene.cziscience.com/curation/v1/datasets"
_CXG_DATASETS_HOST = "https://datasets.cellxgene.cziscience.com"


class CellxGeneSource:
    name = "cellxgene"

    def __init__(self, policy: Optional[ObsPolicy] = None):
        self.policy = policy or ObsPolicy()

    def search(self, query: str, max_results: int = 20) -> List[SearchResult]:
        params = {"limit": max_results, "q": query}
        s = get_session()
        r = s.get(_CXG_SEARCH, params=params, timeout=get_timeout())
        r.raise_for_status()
        js = r.json()
        hits = js.get("datasets", js.get("data", []))
        out: List[SearchResult] = []
        for d in hits[:max_results]:
            did = d.get("id") or d.get("dataset_id") or ""
            title = d.get("title") or d.get("name") or did
            url = d.get("collection_url") or d.get("explorer_url") or ""
            out.append(SearchResult(source=self.name, dataset_id=str(did), title=str(title), url=str(url)))
        return out

    def download(
        self,
        dataset_id: str,
        outdir: str,
        merge_samples: bool = True,
        overrides: Optional[Dict[str, str]] = None,
        cleanup: bool = True,
        gene_options: Optional[GeneOptions] = None,
    ) -> List[str]:
        outdir = str(ensure_dir(outdir))
        workdir = ensure_dir(Path(outdir) / f"_work_cellxgene_{safe_filename(dataset_id)}")
        produced: List[str] = []

        if is_url(dataset_id) and dataset_id.lower().endswith(".h5ad"):
            session = get_session()
            h5ad_path = download_file(dataset_id, workdir / "source.h5ad", session=session)
            canonical_id = Path(dataset_id).stem
        else:
            if not self._is_uuid(dataset_id):
                raise ValueError("CELLxGENE id must be a dataset UUID or a direct .h5ad URL.")
            url = f"{_CXG_DATASETS_HOST}/{dataset_id}.h5ad"
            session = get_session()
            h5ad_path = download_file(url, workdir / f"{dataset_id}.h5ad", session=session)
            canonical_id = dataset_id

        adata = ad.read_h5ad(h5ad_path)
        if gene_options is not None:
            apply_gene_policy(
                adata,
                policy=str(gene_options.policy),
                rename_var_names=gene_options.rename_var_names,
                write_var_columns=gene_options.write_var_columns,
                keep_unmapped=gene_options.keep_unmapped,
                species_hint=gene_options.species_hint,
            )

        sample_overrides = dict(overrides or {})
        sample_overrides.setdefault("source", self.name)
        sample_overrides.setdefault("dataset_id", canonical_id)
        sample_overrides.setdefault("sample_id", canonical_id)
        sample_overrides.setdefault("modality", "spatial" if "spatial" in adata.obsm else "sc/snRNA")

        apply_obs_policy(adata, self.policy, overrides=sample_overrides, source=self.name)
        out_path = Path(outdir) / f"cellxgene_{safe_filename(canonical_id)}.h5ad"
        adata.write_h5ad(out_path)
        produced.append(str(out_path))

        if cleanup:
            rm_rf(workdir)
        return produced

    @staticmethod
    def _is_uuid(s: str) -> bool:
        """Check if string is a valid UUID."""
        pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        return bool(re.match(pattern, s))