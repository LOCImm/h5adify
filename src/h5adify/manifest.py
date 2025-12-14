from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Union

import anndata as ad


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
    source: str
    dataset_id: str
    species: str
    technology: str
    condition: str
    disease: str
    batch: str
    checksum_sha256: str = ""


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _pick_obs_value(adata: ad.AnnData, key: str) -> str:
    if key not in adata.obs:
        return ""
    col = adata.obs[key]
    # Often constant per dataset; take the mode-ish
    try:
        if hasattr(col, "value_counts"):
            vc = col.value_counts(dropna=True)
            if len(vc) > 0:
                return str(vc.index[0])
    except Exception:
        pass
    try:
        # fallback
        v = col.iloc[0]
        return "" if v is None else str(v)
    except Exception:
        return ""


def _safe_bool_has(adata: ad.AnnData, where: str, key: str) -> bool:
    try:
        if where == "layers":
            return key in adata.layers
        if where == "obsm":
            return key in adata.obsm
        if where == "uns":
            return key in adata.uns
    except Exception:
        return False
    return False


def iter_h5ad_files(root: Union[str, Path], recursive: bool = True) -> Iterable[Path]:
    root = Path(root)
    if root.is_file() and root.suffix.lower() == ".h5ad":
        yield root
        return
    if not root.exists():
        return
    pattern = "**/*.h5ad" if recursive else "*.h5ad"
    for p in root.glob(pattern):
        if p.is_file():
            yield p


def build_manifest(
    root: Union[str, Path],
    recursive: bool = True,
    compute_checksum: bool = False,
    checksum_field: str = "sha256",
) -> List[ManifestRow]:
    rows: List[ManifestRow] = []

    for fp in iter_h5ad_files(root, recursive=recursive):
        # backed='r' avoids loading the full matrix
        adata = ad.read_h5ad(fp, backed="r")

        # X dtype / sparse check (best-effort)
        x_dtype = ""
        is_sparse = False
        try:
            x_dtype = str(getattr(adata.X, "dtype", ""))
            is_sparse = "scipy.sparse" in str(type(adata.X)).lower()
        except Exception:
            pass

        layers = ""
        obsm = ""
        try:
            layers = ",".join(sorted(list(adata.layers.keys())))
        except Exception:
            layers = ""
        try:
            obsm = ",".join(sorted(list(adata.obsm.keys())))
        except Exception:
            obsm = ""

        has_raw_counts = _safe_bool_has(adata, "layers", "raw_counts")
        has_spatial = _safe_bool_has(adata, "obsm", "spatial")

        # standardized obs fields (best-effort)
        source = _pick_obs_value(adata, "source")
        dataset_id = _pick_obs_value(adata, "dataset_id")
        species = _pick_obs_value(adata, "species")
        technology = _pick_obs_value(adata, "technology")
        condition = _pick_obs_value(adata, "condition")
        disease = _pick_obs_value(adata, "disease")
        batch = _pick_obs_value(adata, "batch")

        csum = ""
        if compute_checksum:
            csum = _sha256(fp)

        rows.append(
            ManifestRow(
                path=str(fp.resolve()),
                filename=fp.name,
                n_obs=int(adata.n_obs),
                n_vars=int(adata.n_vars),
                x_dtype=x_dtype,
                is_sparse=bool(is_sparse),
                has_raw_counts=bool(has_raw_counts),
                has_spatial=bool(has_spatial),
                layers=layers,
                obsm=obsm,
                source=source,
                dataset_id=dataset_id,
                species=species,
                technology=technology,
                condition=condition,
                disease=disease,
                batch=batch,
                checksum_sha256=csum if checksum_field == "sha256" else csum,
            )
        )

        try:
            adata.file.close()
        except Exception:
            pass

    return rows


def write_manifest_csv(rows: Sequence[ManifestRow], out_csv: Union[str, Path]) -> None:
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    # avoid importing pandas by default, keep it lightweight
    import csv

    fields = list(asdict(rows[0]).keys()) if rows else list(ManifestRow.__annotations__.keys())
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))


def write_manifest_jsonl(rows: Sequence[ManifestRow], out_jsonl: Union[str, Path]) -> None:
    out_jsonl = Path(out_jsonl)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
