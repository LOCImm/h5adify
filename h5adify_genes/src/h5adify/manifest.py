from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Union

import hashlib
import json
import os

import anndata as ad

from .utils import safe_jsonable
from .genes import genes_info_from_adata


@dataclass
class ManifestRow:
    path: str
    filename: str
    n_obs: int
    n_vars: int
    x_dtype: str
    is_sparse: bool
    has_raw_counts: bool
    has_spatial: bool
    layers: str
    obsm: str
    source: str = ""
    dataset_id: str = ""
    species: str = ""
    technology: str = ""

    # gene summary (best-effort)
    gene_id_style: str = ""
    gene_target: str = ""
    gene_policy: str = ""
    gene_ensembl_rate: float = 0.0
    gene_symbol_rate: float = 0.0

    # convenience / provenance
    obs_keys: str = ""
    var_keys: str = ""
    size_mb: float = 0.0
    sha256: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _sha256(path: Path, block_size: int = 2**20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_h5ad_files(root: Union[str, Path], recursive: bool = True) -> Iterable[Path]:
    rootp = Path(root)
    if rootp.is_file() and rootp.suffix.lower() == ".h5ad":
        yield rootp
        return
    if not rootp.exists():
        return
    pattern = "**/*.h5ad" if recursive else "*.h5ad"
    for p in rootp.glob(pattern):
        if p.is_file():
            yield p


def _iter_from_root_or_list(
    root_or_files: Union[str, Path, Sequence[Union[str, Path]]],
    recursive: bool = True,
) -> Iterable[Path]:
    if isinstance(root_or_files, (list, tuple)):
        for x in root_or_files:
            yield Path(x)
        return
    yield from iter_h5ad_files(root_or_files, recursive=recursive)


def build_manifest(
    root_or_files: Union[str, Path, Sequence[Union[str, Path]]],
    recursive: bool = True,
    compute_hash: bool = True,
) -> List[ManifestRow]:
    rows: List[ManifestRow] = []
    for fp in _iter_from_root_or_list(root_or_files, recursive=recursive):
        try:
            stat = fp.stat()
            size_mb = float(stat.st_size) / (1024.0 * 1024.0)
        except Exception:
            size_mb = 0.0

        # Read in backed mode to avoid loading X
        adata = ad.read_h5ad(fp, backed="r")
        try:
            x_dtype = str(getattr(adata.X, "dtype", ""))
            is_sparse = bool(hasattr(adata.X, "tocsc"))
        except Exception:
            x_dtype, is_sparse = "", False

        layers = ",".join(list(getattr(adata, "layers", {}).keys()))
        obsm = ",".join(list(getattr(adata, "obsm", {}).keys()))
        has_spatial = "spatial" in getattr(adata, "obsm", {})

        # Try to detect raw counts presence
        has_raw_counts = "raw_counts" in getattr(adata, "layers", {})

        obs_keys = ",".join(list(getattr(adata, "obs", {}).keys()))
        var_keys = ",".join(list(getattr(adata, "var", {}).keys()))

        source = str(adata.uns.get("h5adify", {}).get("source", "") or adata.uns.get("source", "") or "")
        dataset_id = str(adata.uns.get("h5adify", {}).get("dataset_id", "") or adata.uns.get("dataset_id", "") or "")

        # common obs fields (best-effort)
        species = ""
        technology = ""
        for k in ("species", "organism"):
            if k in adata.obs.columns:
                species = str(adata.obs[k].iloc[0])
                break
        for k in ("technology", "tech", "assay", "platform"):
            if k in adata.obs.columns:
                technology = str(adata.obs[k].iloc[0])
                break

        ginfo = genes_info_from_adata(adata)
        gene_id_style = str(ginfo.get("id_style", "") or "")
        gene_target = str(ginfo.get("target", "") or "")
        gene_policy = str(ginfo.get("policy", "") or "")
        gene_ensembl_rate = float(ginfo.get("ensembl_rate", 0.0) or 0.0)
        gene_symbol_rate = float(ginfo.get("symbol_rate", 0.0) or 0.0)

        row = ManifestRow(
            path=str(fp),
            filename=fp.name,
            n_obs=int(adata.n_obs),
            n_vars=int(adata.n_vars),
            x_dtype=x_dtype,
            is_sparse=is_sparse,
            has_raw_counts=has_raw_counts,
            has_spatial=has_spatial,
            layers=layers,
            obsm=obsm,
            source=source,
            dataset_id=dataset_id,
            species=species,
            technology=technology,
            gene_id_style=gene_id_style,
            gene_target=gene_target,
            gene_policy=gene_policy,
            gene_ensembl_rate=gene_ensembl_rate,
            gene_symbol_rate=gene_symbol_rate,
            obs_keys=obs_keys,
            var_keys=var_keys,
            size_mb=size_mb,
            sha256=_sha256(fp) if compute_hash else "",
        )
        rows.append(row)
    return rows


def save_manifest(rows: List[ManifestRow], out_path: Union[str, Path]) -> None:
    outp = Path(out_path)
    outp.parent.mkdir(parents=True, exist_ok=True)
    data = [r.to_dict() for r in rows]
    outp.write_text(json.dumps(safe_jsonable(data), indent=2, ensure_ascii=False), encoding="utf-8")
