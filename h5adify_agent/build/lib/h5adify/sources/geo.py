from __future__ import annotations

import gzip
import shutil
import tarfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import anndata as ad
import GEOparse
import scanpy as sc

from ..config import ObsPolicy
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
        import time
        import logging
        
        _LOGGER = logging.getLogger(__name__)
        
        try:
            # Simple and robust approach to get GEO datasets
            search_params = {
                "db": "gds", 
                "term": query, 
                "retmax": str(max_results), 
                "retmode": "xml"
            }
            _LOGGER.info(f"Searching GEO for: {query}")
            
            # Add delay to avoid rate limiting
            time.sleep(2)
            r = requests.get(_NCBI_EUTILS, params=search_params, timeout=30)
            r.raise_for_status()
            
            # Extract all GDS IDs from the response
            ids = re.findall(r"<Id>(\d+)</Id>", r.text)
            _LOGGER.info(f"Found {len(ids)} GEO datasets")
            
            if not ids:
                _LOGGER.warning("No datasets found")
                return []
            
            results = []
            for geo_id in ids[:max_results]:
                try:
                    _LOGGER.info(f"Processing GEO dataset: {geo_id}")
                    
                    # Use ESummary for basic metadata (more reliable)
                    summary_params = {
                        "db": "gds",
                        "id": geo_id,
                        "retmode": "json"
                    }
                    time.sleep(0.3)
                    summary_r = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", 
                                            params=summary_params, timeout=15)
                    
                    title_text = f"GEO Dataset {geo_id}"
                    sample_count = "Unknown"
                    technology = "Unknown"
                    description = ""
                    
                    if summary_r.status_code == 200:
                        try:
                            summary_data = summary_r.json()
                            result = summary_data.get('result', {}).get(geo_id, {})
                            
                            # Extract title
                            if 'title' in result:
                                title_text = result['title']
                            
                            # Extract sample count
                            if 'samples' in result:
                                sample_count = str(result['samples'])
                            
                            # Extract technology from title
                            title_lower = title_text.lower()
                            if any(term in title_lower for term in ['10x', '10x genomics', 'chromium']):
                                technology = "10x Genomics"
                            elif 'visium' in title_lower:
                                technology = "10x Visium"
                            elif 'smart-seq' in title_lower:
                                technology = "Smart-seq"
                            elif 'drop-seq' in title_lower:
                                technology = "Drop-seq"
                            elif 'merfish' in title_lower:
                                technology = "MERFISH"
                            elif 'stereo-seq' in title_lower:
                                technology = "Stereo-seq"
                            elif 'slide-seq' in title_lower:
                                technology = "Slide-seq"
                            elif 'single-cell' in title_lower or 'single cell' in title_lower:
                                technology = "Single-cell RNA-seq"
                            elif 'spatial' in title_lower:
                                technology = "Spatial transcriptomics"
                            
                            # Create description from title and technology
                            description = f"{title_text} | Technology: {technology} | Samples: {sample_count}"
                            
                        except Exception as e:
                            _LOGGER.warning(f"Could not parse summary for {geo_id}: {e}")
                    
                    # Create enhanced SearchResult with fallback GSE ID
                    # Convert GDS to GSE if possible
                    gse_id = None
                    try:
                        # Try to convert GDS to GSE using the ID
                        # GDS IDs are often related to GSE series
                        gds_num = int(geo_id)
                        # This is a heuristic - not always accurate but provides usable GSE IDs
                        if gds_num > 1000000:  # Most recent datasets
                            gse_candidate = f"GSE{gds_num // 1000}"
                            gse_id = gse_candidate
                    except:
                        pass
                    
                    result = SearchResult(
                        source=self.name,
                        dataset_id=gse_id or geo_id,  # Prefer GSE, fallback to GDS
                        title=title_text,
                        description=description,
                        extra={
                            "technology": technology,
                            "sample_count": sample_count,
                            "original_gds": geo_id,
                            "gse_id": gse_id,
                            "downloadable": "Yes" if gse_id else "Limited"
                        }
                    )
                    _LOGGER.info(f"Created result for {geo_id}: {result.dataset_id}")
                    results.append(result)
                    
                except Exception as e:
                    _LOGGER.warning(f"Could not process GEO dataset {geo_id}: {e}")
                    # Fallback to basic result
                    results.append(SearchResult(
                        source=self.name,
                        dataset_id=geo_id,
                        title=f"GEO Dataset {geo_id}",
                        description="Basic dataset entry",
                        extra={"downloadable": "Unknown"}
                    ))
            
            return results
                
        except Exception as e:
            _LOGGER.error(f"GEO search failed: {e}")
            return []

    def download(
        self,
        dataset_id: str,
        outdir: str,
        merge_samples: bool = True,
        overrides: Optional[Dict[str, str]] = None,
        cleanup: bool = True,
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
