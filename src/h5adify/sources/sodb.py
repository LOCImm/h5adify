from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import anndata as ad

from ..config import ObsPolicy
from ..metadata import apply_obs_policy
from ..utils import ensure_dir, rm_rf, safe_filename
from .base import SearchResult


class SODBSource:
    name = "sodb"

    def __init__(self, policy: Optional[ObsPolicy] = None):
        self.policy = policy or ObsPolicy()
        try:
            from pysodb import SODB  # type: ignore
        except Exception as e:
            raise ImportError(
                "SODB support requires pysodb. Install with: pip install 'h5adify[sodb]' "
                f"(import error: {e})"
            )
        self._SODB = SODB

    def search(self, query: str, max_results: int = 20) -> List[SearchResult]:
        sodb = self._SODB()
        ds = sodb.list_dataset()
        out: List[SearchResult] = []
        q = query.lower()
        for _, row in ds.iterrows():
            name = str(row.get("dataset", ""))
            if q in name.lower():
                out.append(
                    SearchResult(
                        source=self.name,
                        dataset_id=name,
                        title=name,
                        description=str(row.get("description", "")),
                        url=str(row.get("url", "")),
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
    ) -> List[str]:
        outdir = str(ensure_dir(outdir))
        workdir = ensure_dir(Path(outdir) / f"_work_sodb_{safe_filename(dataset_id)}")

        sodb = self._SODB()
        dataset_name, experiment_id = self._parse_id(dataset_id)

        produced: List[str] = []
        if experiment_id is not None:
            adata = sodb.load_experiment(experiment_id)
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
