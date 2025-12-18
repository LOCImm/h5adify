from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import anndata as ad

from .config import GeneOptions, GenePolicy, ObsPolicy, ObsMode
from .genes import apply_gene_policy
from .highlevel import batch_download, download
from .inspect import inspect_h5ad
from .manifest import build_manifest, save_manifest
from .registry import get_source
from .utils import safe_jsonable


def _parse_kv(items: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError(f"Invalid --set '{it}', expected key=value")
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _parse_ids(items: List[str]) -> List[str]:
    # argparse with nargs='+' gives list[str]; keep as-is
    return list(items or [])


def _parse_gene_options(args) -> GeneOptions:
    policy = GenePolicy(str(args.gene_policy))
    return GeneOptions(
        policy=policy,
        rename_var_names=bool(args.gene_rename_var_names),
        write_var_columns=bool(args.gene_write_var_columns),
        keep_unmapped=bool(args.gene_keep_unmapped),
        species_hint=str(args.gene_species_hint or ""),
    )


def _add_gene_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--gene-policy",
        default=os.environ.get("H5ADIFY_GENE_POLICY", "detect"),
        choices=["detect", "symbol", "ensembl", "hugo"],
        help="Gene ID policy: detect only, or convert/annotate to symbol/ensembl, or map to human symbols (hugo) when possible.",
    )
    p.add_argument(
        "--gene-rename-var-names",
        action="store_true",
        default=os.environ.get("H5ADIFY_GENE_RENAME", "0") == "1",
        help="If set, rename adata.var_names to the target gene name (best-effort).",
    )
    p.add_argument(
        "--gene-write-var-columns",
        action="store_true",
        default=os.environ.get("H5ADIFY_GENE_WRITE_VAR", "1") != "0",
        help="If set, write gene-related columns into adata.var (gene_id, gene_symbol, gene_ensembl, etc).",
    )
    p.add_argument(
        "--gene-keep-unmapped",
        action="store_true",
        default=os.environ.get("H5ADIFY_GENE_KEEP_UNMAPPED", "1") != "0",
        help="Keep unmapped genes as-is when converting (recommended).",
    )
    p.add_argument(
        "--gene-species-hint",
        default=os.environ.get("H5ADIFY_GENE_SPECIES_HINT", ""),
        help="Optional species hint for homology mapping (e.g., mouse, rat). If empty, inferred from Ensembl ID prefixes when possible.",
    )


def cmd_search(args) -> None:
    src = get_source(args.source)
    res = src.search(args.query, max_results=args.max_results)
    print(json.dumps(safe_jsonable([r.__dict__ for r in res]), indent=2, ensure_ascii=False))


def cmd_download(args) -> None:
    overrides = _parse_kv(args.set or [])
    gene_options = _parse_gene_options(args)
    obs_policy = ObsPolicy(ObsMode(str(args.obs_policy)))

    if args.source == "geo":
        if not args.gse:
            raise SystemExit("For GEO, please provide --gse GSE12345 (you can pass multiple).")
        out = []
        for gse in args.gse:
            out.append(
                download(
                    "geo",
                    dataset_id=gse,
                    outdir=args.outdir,
                    merge_samples=not args.no_merge,
                    overrides=overrides,
                    obs_policy=obs_policy,
                    gene_options=gene_options,
                )
            )
        print(json.dumps(safe_jsonable(out), indent=2, ensure_ascii=False))
        return

    if not args.id:
        raise SystemExit("Please provide --id <dataset_id_or_url> for this source.")
    out = download(
        args.source,
        dataset_id=args.id,
        outdir=args.outdir,
        merge_samples=not args.no_merge,
        overrides=overrides,
        obs_policy=obs_policy,
        gene_options=gene_options,
    )
    print(out)


def cmd_batch(args) -> None:
    overrides = _parse_kv(args.set or [])
    gene_options = _parse_gene_options(args)
    obs_policy = ObsPolicy(ObsMode(str(args.obs_policy)))
    ids = _parse_ids(args.ids)

    # download() already accepts ObsPolicy and GeneOptions; wire via gene_options in batch_download
    # For now, batch_download uses download() internally, so obs_policy must be passed via overrides? We'll use per-item download here.
    outs: List[str] = []
    for item in ids:
        if ":" not in item:
            raise SystemExit(f"Invalid id '{item}'. Expected 'source:dataset_id'")
        source, dataset_id = item.split(":", 1)
        outs.append(
            download(
                source,
                dataset_id=dataset_id,
                outdir=args.outdir,
                merge_samples=not args.no_merge,
                overrides=overrides,
                obs_policy=obs_policy,
                gene_options=gene_options,
            )
        )
    if args.merge_out:
        from .merge import merge_h5ads

        merged = merge_h5ads(outs, join=args.merge_join)
        Path(args.merge_out).parent.mkdir(parents=True, exist_ok=True)
        merged.write_h5ad(args.merge_out)
        print(args.merge_out)
    else:
        print(json.dumps(safe_jsonable(outs), indent=2, ensure_ascii=False))


def cmd_manifest(args) -> None:
    rows = build_manifest(args.root, recursive=not args.no_recursive, compute_hash=not args.no_hash)
    save_manifest(rows, args.out)
    print(args.out)


def cmd_query(args) -> None:
    rows = build_manifest(args.root, recursive=not args.no_recursive, compute_hash=False)
    data = [r.to_dict() for r in rows]
    print(json.dumps(safe_jsonable(data), indent=2, ensure_ascii=False))


def cmd_inspect(args) -> None:
    info = inspect_h5ad(args.path, backed=not args.no_backed)
    print(json.dumps(safe_jsonable(info), indent=2, ensure_ascii=False))


def cmd_genes(args) -> None:
    policy = str(args.gene_policy)
    root = Path(args.root)
    outdir = Path(args.outdir) if args.outdir else None
    inplace = bool(args.inplace)

    if outdir and inplace:
        raise SystemExit("Use either --outdir or --inplace, not both.")

    targets: List[Path] = []
    if root.is_file() and root.suffix.lower() == ".h5ad":
        targets = [root]
    else:
        pattern = "**/*.h5ad" if not args.no_recursive else "*.h5ad"
        targets = list(root.glob(pattern))

    for fp in targets:
        adata = ad.read_h5ad(fp)
        apply_gene_policy(
            adata,
            policy=policy,
            rename_var_names=args.gene_rename_var_names,
            write_var_columns=args.gene_write_var_columns,
            keep_unmapped=args.gene_keep_unmapped,
            species_hint=args.gene_species_hint or "",
        )
        if inplace:
            adata.write_h5ad(fp)
        else:
            od = outdir or fp.parent
            od.mkdir(parents=True, exist_ok=True)
            outp = od / fp.name
            adata.write_h5ad(outp)
    print(json.dumps({"processed": len(targets)}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="h5adify", description="Search, download, standardize and inspect single-cell/spatial datasets as .h5ad.")
    sub = p.add_subparsers(dest="cmd", required=True)

    # search
    ps = sub.add_parser("search", help="Search datasets in a source")
    ps.add_argument("source", choices=["geo", "cellxgene", "sodb", "scp", "ucsc", "ema"], help="Data source")
    ps.add_argument("--query", required=True)
    ps.add_argument("--max-results", type=int, default=20)
    ps.set_defaults(func=cmd_search)

    # download
    pd = sub.add_parser("download", help="Download + convert a dataset to .h5ad")
    pd.add_argument("source", choices=["geo", "cellxgene", "sodb", "scp", "ucsc", "ema"])
    pd.add_argument("--outdir", default="data/out")
    pd.add_argument("--id", help="Dataset id (UUID/name) or direct .h5ad URL (for compatible sources)")
    pd.add_argument("--gse", nargs="+", help="GEO Series ids (GSE...), can pass multiple")
    pd.add_argument("--no-merge", action="store_true", help="Do not merge multiple samples into one .h5ad")
    pd.add_argument("--set", nargs="*", default=[], help="Override obs metadata: key=value (repeatable)")
    pd.add_argument("--obs-policy", default="loose", choices=["loose", "strict"])
    _add_gene_flags(pd)
    pd.set_defaults(func=cmd_download)

    # batch
    pb = sub.add_parser("batch", help="Download multiple datasets and optionally merge")
    pb.add_argument("--ids", nargs="+", required=True, help="List of source:dataset_id items")
    pb.add_argument("--outdir", default="data/out")
    pb.add_argument("--merge-out", default="", help="If set, write merged output .h5ad to this path")
    pb.add_argument("--merge-join", default="outer", choices=["inner", "outer"])
    pb.add_argument("--no-merge", action="store_true")
    pb.add_argument("--set", nargs="*", default=[], help="Override obs metadata: key=value (repeatable)")
    pb.add_argument("--obs-policy", default="loose", choices=["loose", "strict"])
    _add_gene_flags(pb)
    pb.set_defaults(func=cmd_batch)

    # manifest
    pm = sub.add_parser("manifest", help="Create a manifest JSON for a folder of .h5ad files")
    pm.add_argument("--root", required=True, help="Folder (or single .h5ad) to scan")
    pm.add_argument("--out", required=True, help="Where to write manifest JSON")
    pm.add_argument("--no-recursive", action="store_true", help="Do not recurse into subfolders")
    pm.add_argument("--no-hash", action="store_true", help="Skip SHA256 computation")
    pm.set_defaults(func=cmd_manifest)

    # query
    pq = sub.add_parser("query", help="Query a folder (or file) and print manifest rows as JSON")
    pq.add_argument("--root", required=True)
    pq.add_argument("--no-recursive", action="store_true")
    pq.set_defaults(func=cmd_query)

    # inspect
    pi = sub.add_parser("inspect", help="Inspect a single .h5ad and print a JSON summary")
    pi.add_argument("--path", required=True)
    pi.add_argument("--no-backed", action="store_true", help="Load fully (not backed)")
    pi.set_defaults(func=cmd_inspect)

    # genes
    pg = sub.add_parser("genes", help="Apply gene policy to existing .h5ad files (rewrite)")
    pg.add_argument("--root", required=True, help="Folder or .h5ad to process")
    pg.add_argument("--outdir", default="", help="Output directory (defaults to input folder).")
    pg.add_argument("--inplace", action="store_true", help="Rewrite files in place.")
    pg.add_argument("--no-recursive", action="store_true")
    _add_gene_flags(pg)
    pg.set_defaults(func=cmd_genes)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    args.func(args)
    return 0
