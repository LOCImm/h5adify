from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import anndata as ad

from ..config import ObsPolicy, GeneOptions
from ..genes import apply_gene_policy
from ..metadata import apply_obs_policy
from ..utils import ensure_dir, rm_rf, safe_filename
from .base import SearchResult


class SODBSource:
    name = "sodb"

    def __init__(self, policy: Optional[ObsPolicy] = None):
        self.policy = policy or ObsPolicy()
        try:
            from pysodb import SODB  # type: ignore
            self._SODB = SODB
        except Exception as e:
            raise ImportError(
                "SODB support requires pysodb. Install with: pip install 'h5adify[sodb]' "
                f"(import error: {e})"
            )

    def _client(self):
        """Create and return a SODB client instance."""
        return self._SODB()

    def search(self, query: str, max_results: int = 25) -> List[SearchResult]:
        sodb = self._client()
        ds = sodb.list_dataset()

        out: List[SearchResult] = []
        q = query.lower()

        # pysodb has changed return types across versions:
        # - some return a pandas.DataFrame (has .iterrows)
        # - others return a list[dict] / list[str]
        if hasattr(ds, "iterrows"):
            row_iter = (row for _, row in ds.iterrows())  # type: ignore[attr-defined]
        elif isinstance(ds, dict):
            row_iter = ds.get("data") or ds.get("datasets") or ds.get("results") or []
        else:
            row_iter = ds or []

        for row in row_iter:
            if isinstance(row, str):
                name = row
                desc = ""
                url = ""
            else:
                getter = row.get if hasattr(row, "get") else (lambda _k, _d=None: _d)
                name = str(
                    getter("dataset")
                    or getter("dataset_name")
                    or getter("name")
                    or getter("title")
                    or ""
                )
                desc = str(getter("description", "") or "")
                url = str(getter("url", "") or getter("homepage", "") or "")

            if not name:
                continue

            if (q in name.lower()) or (desc and q in desc.lower()):
                out.append(
                    SearchResult(
                        source=self.name,
                        dataset_id=name,
                        title=name,
                        description=desc,
                        url=url,
                    )
                )
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
        gene_options: Optional[GeneOptions] = None,
    ) -> List[str]:
        outdir = str(ensure_dir(outdir))
        workdir = ensure_dir(Path(outdir) / f"_work_sodb_{safe_filename(dataset_id)}")

        sodb = self._client()
        dataset_name, experiment_id = self._parse_id(dataset_id)

        produced: List[str] = []
        if experiment_id is not None:
            adata = sodb.load_experiment(experiment_id)
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
            sample_overrides.setdefault("dataset_id", dataset_name)
            sample_overrides.setdefault("sample_id", experiment_id)
            sample_overrides.setdefault("source", self.name)
            apply_obs_policy(adata, self.policy, overrides=sample_overrides, source=self.name)
            out_path = Path(outdir) / f"sodb_{safe_filename(dataset_name)}__{safe_filename(experiment_id)}.h5ad"
            adata.write_h5ad(out_path)
            produced.append(str(out_path))
        else:
            exp_map = sodb.load_dataset(dataset_name)  # dict[exp_id]->AnnData
            adatas = []
            keys = []
            for exp_id, adata in exp_map.items():
                sample_overrides = dict(overrides or {})
                sample_overrides.setdefault("dataset_id", dataset_name)
                sample_overrides.setdefault("sample_id", str(exp_id))
                sample_overrides.setdefault("source", self.name)
                apply_obs_policy(adata, self.policy, overrides=sample_overrides, source=self.name)
                adatas.append(adata)
                keys.append(str(exp_id))

            if merge_samples and len(adatas) > 1:
                merged = ad.concat(adatas, join="outer", label="sample_id", keys=keys, index_unique="-")
                out_path = Path(outdir) / f"sodb_{safe_filename(dataset_name)}.h5ad"
                merged.write_h5ad(out_path)
                produced.append(str(out_path))
            else:
                for a, k in zip(adatas, keys):
                    out_path = Path(outdir) / f"sodb_{safe_filename(dataset_name)}__{safe_filename(k)}.h5ad"
                    a.write_h5ad(out_path)
                    produced.append(str(out_path))

        if cleanup:
            rm_rf(workdir)
        return produced

    @staticmethod
    def _parse_id(dataset_id: str) -> Tuple[str, Optional[str]]:
        if "::" in dataset_id:
            ds, exp = dataset_id.split("::", 1)
            return ds.strip(), exp.strip()
        return dataset_id.strip(), None
