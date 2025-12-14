from __future__ import annotations

import argparse
import json
from typing import List, Optional

from .highlevel import batch_download, download
from .registry import get_source
from .utils import parse_kv_overrides


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="h5adify", description="Search + download + convert datasets to .h5ad")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Search a data source")
    p_search.add_argument("source", choices=["geo", "cellxgene", "scp", "sodb"])
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--max-results", type=int, default=20)

    p_dl = sub.add_parser("download", help="Download + convert a dataset")
    p_dl.add_argument("source", choices=["geo", "cellxgene", "scp", "sodb"])
    p_dl.add_argument("--gse", help="GSE accession (geo)")
    p_dl.add_argument("--id", help="Dataset identifier (cellxgene/scp/sodb)")
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


if __name__ == "__main__":
    main()
