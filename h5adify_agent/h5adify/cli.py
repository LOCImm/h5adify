from __future__ import annotations

import argparse
import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict, is_dataclass
from pathlib import Path


from .highlevel import download as hl_download, batch_download
from .manifest import build_manifest, write_manifest_csv, write_manifest_jsonl
from .inspect_data import inspect_h5ad
from .registry import get_source


SUPPORTED_SOURCES = ["geo", "cellxgene", "sodb", "scp", "ucsc", "ema"]


def _parse_kv_list(items: Optional[List[str]]) -> Dict[str, str]:
    """Parse repeated --set key=value into a dict."""
    out: Dict[str, str] = {}
    if not items:
        return out
    for it in items:
        if "=" not in it:
            raise SystemExit(f"Invalid --set '{it}'. Expected key=value")
        k, v = it.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            raise SystemExit(f"Invalid --set '{it}'. Empty key")
        out[k] = v
    return out
    
def _jsonable(x):
    """Convert common objects (dataclasses, Paths, etc.) to JSON-serializable types."""
    if is_dataclass(x):
        return asdict(x)
    if isinstance(x, Path):
        return str(x)
    # pydantic v2
    if hasattr(x, "model_dump") and callable(getattr(x, "model_dump")):
        return x.model_dump()
    # pydantic v1 / dict-like objects
    if hasattr(x, "dict") and callable(getattr(x, "dict")):
        return x.dict()
    if hasattr(x, "to_dict") and callable(getattr(x, "to_dict")):
        return x.to_dict()
    return x

def _collect_h5ads(root: Path) -> List[Path]:
    if not root.exists():
        raise SystemExit(f"Root does not exist: {root}")
    return sorted([p for p in root.rglob("*.h5ad") if p.is_file()])


def _cmd_search(args: argparse.Namespace) -> None:
    src = get_source(args.source)
    res = src.search(args.query, max_results=args.max_results)
    print(json.dumps([r.__dict__ for r in res], indent=2, ensure_ascii=False))


def _cmd_download(args: argparse.Namespace) -> None:
    overrides = _parse_kv_list(args.set)

    # Source-specific kwargs
    kwargs = dict(
        outdir=args.outdir, 
        merge_samples=not args.no_merge, 
        overrides=overrides, 
        cleanup=not args.no_cleanup,
        convert_genes=args.convert_genes,
        annotate_species=args.annotate_species,
    )

    if args.source == "geo":
        if not args.gse:
            raise SystemExit("geo download requires --gse")
        kwargs["gse"] = args.gse
    else:
        if not args.id:
            raise SystemExit(f"{args.source} download requires --id")
        kwargs["dataset_id"] = args.id

    out_paths = hl_download(args.source, **kwargs)
    print(json.dumps([str(p) for p in out_paths], indent=2, ensure_ascii=False))


def _cmd_batch(args: argparse.Namespace) -> None:
    overrides = _parse_kv_list(args.set)
    # batch_download currently expects per-item overrides; we apply the same overrides to all items
    items = []
    for spec in args.ids:
        if ":" not in spec:
            raise SystemExit(f"Invalid --ids entry '{spec}'. Expected source:identifier")
        src, ident = spec.split(":", 1)
        src = src.strip().lower()
        ident = ident.strip()
        if src not in SUPPORTED_SOURCES:
            raise SystemExit(f"Unknown source '{src}'. Supported: {', '.join(SUPPORTED_SOURCES)}")
        items.append(f"{src}:{ident}")

    out = batch_download(items, outdir=args.outdir, merge_out=args.merge_out, 
                        convert_genes=args.convert_genes, annotate_species=args.annotate_species)
    # If merge_out is set, batch_download returns a single path (string) of merged file
    if isinstance(out, list):
    	out = [_jsonable(r) for r in out]
    elif isinstance(out, dict):
	    out = {k: _jsonable(v) for k, v in out.items()}

    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_manifest(args: argparse.Namespace) -> None:
    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Root does not exist: {root}")

    mf = build_manifest(root)

    out = Path(args.out)
    # If --out looks like a directory (no suffix) or is an existing directory,
    # write both JSONL + CSV inside it.
    if (out.exists() and out.is_dir()) or out.suffix == "":
        out_dir = out
        out_dir.mkdir(parents=True, exist_ok=True)
        out_jsonl = out_dir / "manifest.jsonl"
        out_csv = out_dir / "manifest.csv"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl = out
        out_csv = out.with_suffix(".csv")

    if not mf:
        out_jsonl.write_text("", encoding="utf-8")
        out_csv.write_text("", encoding="utf-8")
        print(json.dumps({"jsonl": str(out_jsonl), "csv": str(out_csv), "n": 0}, ensure_ascii=False))
        return

    write_manifest_jsonl(mf, out_jsonl)
    write_manifest_csv(mf, out_csv)
    print(json.dumps({"jsonl": str(out_jsonl), "csv": str(out_csv), "n": len(mf)}, ensure_ascii=False))


def _read_manifest_jsonl(path: Path) -> List[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _cmd_query(args: argparse.Namespace) -> None:
    # Load manifest
    if args.manifest:
        mpath = Path(args.manifest)
        rows = _read_manifest_jsonl(mpath)  # list[dict]
    else:
        if not args.root:
            raise SystemExit("query requires either --manifest or --root")
        root = Path(args.root)
        rows = build_manifest(root)  # list[ManifestRow] (dataclass)

    # ✅ Normalize rows to list[dict] for filtering + JSON output
    if rows and not isinstance(rows[0], dict):
        rows = [_jsonable(r) for r in rows]  # dataclass -> dict

    # Apply filters
    text = (args.text or "").strip().lower()
    kv_filters = _parse_kv_list(args.where)

    def _match(row: dict) -> bool:
        if text:
            hay = " ".join([str(row.get(k, "")) for k in ("path", "source", "dataset_id", "title")]).lower()
            if text not in hay:
                return False
        for k, v in kv_filters.items():
            if str(row.get(k, "")) != v:
                return False
        return True

    out = [r for r in rows if _match(r)]
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_pack(args: argparse.Namespace) -> None:
    import tarfile

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load manifest
    if args.manifest:
        mpath = Path(args.manifest)
        rows = _read_manifest_jsonl(mpath)
    else:
        root = Path(args.root)
        rows = build_manifest(root)  
        # Normalize to dict for JSONL writing below
    if rows and not isinstance(rows[0], dict):
        rows = [_jsonable(r) for r in rows]
        # Write a temporary manifest inside the tar
        mpath = None

    # Collect file paths
    files: List[Path] = []
    for r in rows:
        p = Path(r.get("path", ""))
        if p.exists() and p.is_file():
            files.append(p)

    with tarfile.open(out_path, "w:gz") as tf:
        # Include manifest
        if args.manifest:
            tf.add(str(Path(args.manifest)), arcname="manifest.jsonl")
        else:
            # write manifest content to a temp file
            import tempfile

            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".jsonl", encoding="utf-8") as tmp:
                for r in rows:
                    tmp.write(json.dumps(r, ensure_ascii=False) + "\n")
                tmp_path = Path(tmp.name)
            tf.add(str(tmp_path), arcname="manifest.jsonl")
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

        # Add datasets
        for p in files:
            tf.add(str(p), arcname=os.path.join("h5ads", p.name))

    print(str(out_path))


def _cmd_inspect(args: argparse.Namespace) -> None:
    info = inspect_h5ad(args.path, annotate_genes=args.annotate_genes, 
                       convert_to_hugo=args.convert_to_hugo,
                       output_file=args.output_file)
    print(json.dumps(info, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="h5adify", description="Search, download, standardize and package public single-cell/spatial datasets as .h5ad")
    sp = p.add_subparsers(dest="cmd", required=True)

    # search
    ps = sp.add_parser("search", help="Search a source for datasets")
    ps.add_argument("source", choices=SUPPORTED_SOURCES)
    ps.add_argument("--query", required=True)
    ps.add_argument("--max-results", type=int, default=20)
    ps.set_defaults(func=_cmd_search)

    # download
    pd = sp.add_parser("download", help="Download + convert a dataset into standardized .h5ad")
    pd.add_argument("source", choices=SUPPORTED_SOURCES)
    pd.add_argument("--outdir", required=True)
    pd.add_argument("--id", help="Dataset id / UUID / URL (source-dependent)")
    pd.add_argument("--gse", help="GEO series id (only for source=geo)")
    pd.add_argument("--no-merge", action="store_true", help="Do not merge multiple samples into one .h5ad")
    pd.add_argument("--no-cleanup", action="store_true", help="Keep downloaded intermediate files")
    pd.add_argument("--set", action="append", help="Override metadata fields (repeatable): key=value")
    pd.add_argument("--convert-genes", action="store_true", help="Convert gene symbols to human orthologs (HUGO equivalent).")
    pd.add_argument("--annotate-species", action="store_true", help="Automatically infer and annotate organism/species from gene names.")
    pd.set_defaults(func=_cmd_download)

    # batch
    pb = sp.add_parser("batch", help="Batch download multiple datasets, optionally merging")
    pb.add_argument("--ids", nargs="+", required=True, help="List of source:identifier specs")
    pb.add_argument("--outdir", required=True)
    pb.add_argument("--merge-out", help="Path to merged output .h5ad")
    pb.add_argument("--set", action="append", help="Override metadata fields for all items: key=value")
    pb.add_argument("--convert-genes", action="store_true", help="Convert gene symbols to human orthologs (HUGO equivalent).")
    pb.add_argument("--annotate-species", action="store_true", help="Automatically infer and annotate organism/species from gene names.")
    pb.set_defaults(func=_cmd_batch)

    # manifest
    pm = sp.add_parser("manifest", help="Build a JSONL manifest for a folder of .h5ad files")
    pm.add_argument("--root", required=True)
    pm.add_argument("--out", required=True)
    pm.set_defaults(func=_cmd_manifest)

    # query
    pq = sp.add_parser("query", help="Query an existing manifest (or a folder) and print matching entries")
    pq.add_argument("--manifest", help="Path to manifest.jsonl")
    pq.add_argument("--root", help="Alternatively, scan this folder for .h5ad")
    pq.add_argument("--text", help="Free-text filter over path/source/dataset_id/title")
    pq.add_argument("--where", action="append", help="Exact match filter (repeatable): key=value")
    pq.set_defaults(func=_cmd_query)

    # inspect
    pi = sp.add_parser("inspect", help="Inspect a single .h5ad and print summary JSON")
    pi.add_argument("--path", required=True)
    pi.add_argument("--annotate-genes", action="store_true", help="Perform gene annotation analysis on the dataset.")
    pi.add_argument("--convert-to-hugo", action="store_true", help="Convert gene names to HUGO symbols and save updated dataset.")
    pi.add_argument("--output-file", help="Save updated dataset to this file path.")
    pi.set_defaults(func=_cmd_inspect)

    # pack
    pp = sp.add_parser("pack", help="Pack a manifest + .h5ad files into a tar.gz bundle")
    pp.add_argument("--manifest", help="Path to manifest.jsonl")
    pp.add_argument("--root", help="Alternatively, scan this folder for .h5ad and build an in-tar manifest")
    pp.add_argument("--out", required=True, help="Output .tar.gz path")
    pp.set_defaults(func=_cmd_pack)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0