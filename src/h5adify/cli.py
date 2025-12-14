from __future__ import annotations

import argparse
import json
from typing import List, Optional

from .highlevel import batch_download, download
from .registry import get_source
from .utils import parse_kv_overrides

from .inspect import inspect_h5ad, format_inspect_text
from .local_query import local_search
from .manifest import build_manifest, write_manifest_csv, write_manifest_jsonl


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="h5adify", description="Search + download + convert datasets to .h5ad")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Search a data source")
    p_search.add_argument("source", choices=["geo", "cellxgene", "scp", "sodb", "ucsc", "ema"])
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--max-results", type=int, default=20)

    p_dl = sub.add_parser("download", help="Download + convert a dataset")
    p_dl.add_argument("source", choices=["geo", "cellxgene", "scp", "sodb", "ucsc", "ema"])
    p_dl.add_argument("--gse", help="GSE accession (geo)")
    p_dl.add_argument("--id", help="Dataset identifier (cellxgene/scp/sodb/ucsc/ema)")
    p_dl.add_argument("--outdir", required=True)
    p_dl.add_argument("--no-merge-samples", action="store_true")
    p_dl.add_argument("--keep-work", action="store_true")
    p_dl.add_argument("--set", action="append", default=[], help="Override obs field: key=value (repeatable)")

    p_batch = sub.add_parser("batch", help="Download multiple datasets across sources")
    p_batch.add_argument("--ids", nargs="+", required=True, help="List of source:dataset_id")
    p_batch.add_argument("--outdir", required=True)
    p_batch.add_argument("--merge-out", help="If set, merge all outputs into this .h5ad")
    p_batch.add_argument("--merge-join", default="outer", choices=["outer", "inner"])
    p_batch.add_argument("--merge-label", default="batch")
    p_batch.add_argument("--set", action="append", default=[], help="Override obs field: key=value (repeatable)")
    p_batch.add_argument("--keep-work", action="store_true")
    p_batch.add_argument("--no-merge-samples", action="store_true")
    
    # -----------------------
    # manifest / pack
    # -----------------------
    p_mani = sub.add_parser("manifest", help="Scan local .h5ad files and write a manifest (csv/jsonl).")
    p_mani.add_argument("root", help="Folder (or single .h5ad) to scan")
    p_mani.add_argument("--no-recursive", action="store_true", help="Do not recurse into subfolders")
    p_mani.add_argument("--csv", default="", help="Output CSV path (default: <root>/manifest.csv if root is a folder)")
    p_mani.add_argument("--jsonl", default="", help="Output JSONL path (default: <root>/manifest.jsonl if root is a folder)")
    p_mani.add_argument("--checksum", action="store_true", help="Compute sha256 checksums (slower)")
    
    # alias: pack (same args as manifest)
    p_pack = sub.add_parser("pack", help="Alias of 'manifest'.")
    p_pack.add_argument("root", help="Folder (or single .h5ad) to scan")
    p_pack.add_argument("--no-recursive", action="store_true", help="Do not recurse into subfolders")
    p_pack.add_argument("--csv", default="", help="Output CSV path (default: <root>/manifest.csv if root is a folder)")
    p_pack.add_argument("--jsonl", default="", help="Output JSONL path (default: <root>/manifest.jsonl if root is a folder)")
    p_pack.add_argument("--checksum", action="store_true", help="Compute sha256 checksums (slower)")
    
    # -----------------------
    # inspect
    # -----------------------
    p_insp = sub.add_parser("inspect", help="Inspect a local .h5ad (sanity checks / metadata completeness).")
    p_insp.add_argument("path", help="Path to .h5ad file")
    p_insp.add_argument("--json", action="store_true", help="Print JSON instead of text")
    p_insp.add_argument("--max-fields", type=int, default=30, help="Max number of obs/var columns to display")
    
    # -----------------------
    # local-search / query
    # -----------------------
    p_lq = sub.add_parser("local-search", help="Search locally across .h5ad files using a pandas query on a generated manifest.")
    p_lq.add_argument("root", help="Folder (or single .h5ad) to scan")
    p_lq.add_argument("--where", required=True, help="pandas query expression, e.g. \"species == 'human' and has_spatial == True\"")
    p_lq.add_argument("--no-recursive", action="store_true", help="Do not recurse into subfolders")
    p_lq.add_argument("--max-results", type=int, default=200, help="Limit number of returned rows")
    p_lq.add_argument("--json", action="store_true", help="Print JSON (records) instead of a text table")
    p_lq.add_argument("--checksum", action="store_true", help="Compute sha256 checksums (slower)")

    args = parser.parse_args(argv)

    if args.cmd == "search":
        src = get_source(args.source)
        res = src.search(args.query, max_results=args.max_results)
        print(json.dumps([r.__dict__ for r in res], indent=2, ensure_ascii=False))
        return

    if args.cmd == "download":
        overrides = parse_kv_overrides(args.set)
        merge_samples = not args.no_merge_samples
        cleanup = not args.keep_work
        did = args.id or args.gse
        if not did:
            parser.error("download requires --id (or --gse for geo)")
        outs = download(args.source, outdir=args.outdir, merge_samples=merge_samples, cleanup=cleanup, overrides=overrides, id=did, gse=did, dataset_id=did)
        if isinstance(outs, str):
            print(outs)
        else:
            print("\n".join(outs))
        return

    if args.cmd == "batch":
        overrides = parse_kv_overrides(args.set)
        merge_samples = not args.no_merge_samples
        cleanup = not args.keep_work
        produced = batch_download(
            ids=args.ids,
            outdir=args.outdir,
            merge_out=args.merge_out,
            merge_join=args.merge_join,
            merge_label=args.merge_label,
            merge_samples=merge_samples,
            cleanup=cleanup,
            overrides=overrides,
        )
        print(json.dumps(produced, indent=2, ensure_ascii=False))
        return

        if args.cmd in ("manifest", "pack"):
        root = Path(args.root)
        recursive = not args.no_recursive

        rows = build_manifest(root, recursive=recursive, compute_checksum=args.checksum)

        # default output paths
        if root.is_dir():
            default_csv = root / "manifest.csv"
            default_jsonl = root / "manifest.jsonl"
        else:
            default_csv = root.parent / "manifest.csv"
            default_jsonl = root.parent / "manifest.jsonl"

        out_csv = Path(args.csv) if args.csv else default_csv
        out_jsonl = Path(args.jsonl) if args.jsonl else default_jsonl

        if rows:
            write_manifest_csv(rows, out_csv)
            write_manifest_jsonl(rows, out_jsonl)
        else:
            # still write empty files for reproducibility
            write_manifest_csv([], out_csv)
            write_manifest_jsonl([], out_jsonl)

        print(f"Wrote: {out_csv}")
        print(f"Wrote: {out_jsonl}")
        return 0

    if args.cmd == "inspect":
        rep = inspect_h5ad(args.path, max_fields=args.max_fields)
        if args.json:
            import json
            print(json.dumps(rep, indent=2, ensure_ascii=False))
        else:
            print(format_inspect_text(rep))
        return 0

    if args.cmd == "local-search":
        root = Path(args.root)
        recursive = not args.no_recursive
        rows = local_search(root, where=args.where, recursive=recursive, compute_checksum=args.checksum)

        if args.max_results and len(rows) > args.max_results:
            rows = rows[: args.max_results]

        if args.json:
            import json
            print(json.dumps(rows, indent=2, ensure_ascii=False))
            return 0

        # pretty text table without extra deps
        if not rows:
            print("No matches.")
            return 0

        cols = ["filename", "n_obs", "n_vars", "species", "technology", "has_spatial", "source", "dataset_id", "path"]
        # compute column widths
        def _w(c):
            return max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows))
        widths = {c: min(_w(c), 80) for c in cols}

        header = " | ".join(c.ljust(widths[c]) for c in cols)
        sep = "-+-".join("-" * widths[c] for c in cols)
        print(header)
        print(sep)
        for r in rows:
            line = " | ".join(str(r.get(c, ""))[: widths[c]].ljust(widths[c]) for c in cols)
            print(line)
        return 0



if __name__ == "__main__":
    main()
