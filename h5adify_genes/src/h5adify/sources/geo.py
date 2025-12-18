from __future__ import annotations

import gzip
import shutil
import tarfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import anndata as ad
import GEOparse
import scanpy as sc

from ..config import ObsPolicy, GeneOptions
from ..genes import apply_gene_policy
from ..metadata import apply_obs_policy
from ..utils import ensure_dir, rm_rf, tempdir
from .base import SearchResult

_NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


class GEOSource:
    name = "geo"

    def __init__(self, policy: Optional[ObsPolicy] = None):
        self.policy = policy or ObsPolicy()

    def search(self, query: str, max_results: int = 20) -> List[SearchResult]:
        import requests, re

        params = {"db": "gds", "term": query, "retmax": str(max_results), "retmode": "xml"}
        r = requests.get(_NCBI_EUTILS, params=params, timeout=30)
        r.raise_for_status()
        ids = re.findall(r"<Id>(\d+)</Id>", r.text)
        return [SearchResult(source=self.name, dataset_id=str(i), title=f"GDS {i}") for i in ids]

    def download(
        self,
        dataset_id: str,
        outdir: str,
        merge_samples: bool = True,
        overrides: Optional[Dict[str, str]] = None,
        cleanup: bool = True,
        gene_options: Optional[GeneOptions] = None,
    ) -> List[str]:
        if not dataset_id.upper().startswith("GSE"):
            raise ValueError("For GEO source, dataset_id must be a GSE accession like GSE229409")

        outdir = str(ensure_dir(outdir))
        workdir = ensure_dir(Path(outdir) / f"_work_geo_{dataset_id}")
        soft_dir = ensure_dir(workdir / "soft")
        supp_dir = ensure_dir(workdir / "supp")

        gse = GEOparse.get_GEO(geo=dataset_id, destdir=str(soft_dir), how="full")

        produced: List[str] = []
        adatas: List[ad.AnnData] = []

        for gsm_id, gsm in gse.gsms.items():
            gsm_out = ensure_dir(supp_dir / gsm_id)
            try:
                gsm.download_supplementary_files(str(gsm_out))
            except Exception:
                pass

            adata = self._load_any_matrix(gsm_out)
            if gene_options is not None:
                apply_gene_policy(
                adata,
                policy=str(gene_options.policy),
                rename_var_names=gene_options.rename_var_names,
                write_var_columns=gene_options.write_var_columns,
                keep_unmapped=gene_options.keep_unmapped,
                species_hint=gene_options.species_hint,
                )
            if adata is None:
                continue

            meta = self._extract_gsm_metadata(gsm)
            sample_overrides = dict(overrides or {})
            sample_overrides.setdefault("sample_id", gsm_id)
            sample_overrides.setdefault("dataset_id", dataset_id)
            sample_overrides.setdefault("technology", meta.get("technology", "unknown"))
            sample_overrides.setdefault("species", meta.get("species", "unknown"))
            sample_overrides.setdefault("tissue", meta.get("tissue", "brain"))
            sample_overrides.setdefault("condition", meta.get("condition", "unknown"))
            sample_overrides.setdefault("disease", meta.get("disease", "unknown"))
            sample_overrides.setdefault("modality", meta.get("modality", "sc/snRNA"))

            apply_obs_policy(adata, self.policy, overrides=sample_overrides, source=self.name)
            adatas.append(adata)

        if not adatas:
            raise RuntimeError(
                f"[{dataset_id}] Could not auto-load expression matrix from supplementary files. "
                "Tip: dataset may be raw-only (SRA), or Seurat .rds; handle with a custom loader."
            )

        if merge_samples:
            merged = ad.concat(
                adatas,
                join="outer",
                label="sample_id",
                keys=[a.obs["sample_id"][0] for a in adatas],
                index_unique="-",
            )
            out_path = Path(outdir) / f"geo_{dataset_id}.h5ad"
            merged.write_h5ad(out_path)
            produced.append(str(out_path))
        else:
            for a in adatas:
                sid = str(a.obs["sample_id"][0])
                out_path = Path(outdir) / f"geo_{dataset_id}_{sid}.h5ad"
                a.write_h5ad(out_path)
                produced.append(str(out_path))

        if cleanup:
            rm_rf(workdir)

        return produced

    def _extract_gsm_metadata(self, gsm: GEOparse.GSM) -> Dict[str, str]:
        chars = [str(x) for x in gsm.metadata.get("characteristics_ch1", [])]
        title = " ".join(gsm.metadata.get("title", []) or [])
        organism = " ".join(gsm.metadata.get("organism_ch1", []) or [])
        txt = (" ".join([title, organism] + chars)).lower()

        def pick(specs: List[Tuple[str, str]], default: str = "unknown") -> str:
            for needle, val in specs:
                if needle in txt:
                    return val
            return default

        tech = pick(
            [
                ("visium", "10x visium"),
                ("stereo", "stereo-seq"),
                ("merfish", "merfish"),
                ("slideseq", "slide-seq"),
                ("10x", "10x"),
                ("smart-seq", "smart-seq"),
                ("drop-seq", "drop-seq"),
            ]
        )
        modality = pick([("visium", "spatial"), ("stereo", "spatial"), ("merfish", "spatial"), ("slideseq", "spatial")], default="sc/snRNA")
        species = pick([("homo sapiens", "human"), ("mus musculus", "mouse"), ("rattus norvegicus", "rat"), ("macaca", "macaque"), ("callithrix", "marmoset")])

        disease = "unknown"
        condition = "unknown"
        for c in chars:
            if ":" in c:
                k, v = c.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                if k in {"disease", "diagnosis", "phenotype"}:
                    disease = v
                if k in {"condition", "group", "treatment"}:
                    condition = v

        return {"technology": tech, "modality": modality, "species": species, "tissue": "brain", "disease": disease, "condition": condition}

    def _load_any_matrix(self, folder: Path) -> Optional[ad.AnnData]:
        mtx = list(folder.glob("*matrix.mtx")) + list(folder.glob("*matrix.mtx.gz"))
        if mtx:
            with tempdir(prefix="geo_mtx_") as td:
                for f in folder.glob("*"):
                    if f.is_file() and any(s in f.name for s in ["matrix.mtx", "barcodes", "features", "genes"]):
                        dst = td / f.name
                        shutil.copy2(f, dst)
                        if dst.suffix == ".gz":
                            self._gunzip_inplace(dst)
                try:
                    return sc.read_10x_mtx(str(td), var_names="gene_symbols", make_unique=True)
                except Exception:
                    pass

        for f in list(folder.glob("*.h5ad")):
            try:
                return ad.read_h5ad(f)
            except Exception:
                continue

        for f in list(folder.glob("*.h5")):
            try:
                return sc.read_10x_h5(str(f))
            except Exception:
                continue

        for t in list(folder.glob("*.tar.gz")) + list(folder.glob("*.tgz")):
            with tempdir(prefix="geo_tar_") as td:
                try:
                    with tarfile.open(t, "r:gz") as tar:
                        tar.extractall(path=td)
                    for sub in td.rglob("matrix.mtx"):
                        try:
                            return sc.read_10x_mtx(str(sub.parent), var_names="gene_symbols", make_unique=True)
                        except Exception:
                            pass
                except Exception:
                    continue

        return None

    def _gunzip_inplace(self, gz_path: Path) -> Path:
        out_path = gz_path.with_suffix("")
        with gzip.open(gz_path, "rb") as fin, open(out_path, "wb") as fout:
            shutil.copyfileobj(fin, fout)
        gz_path.unlink(missing_ok=True)
        return out_path
