from .geo import GEO
from .cellxgene import CellxGene
from .broad_scp import BroadSCP
from .ema_biostudies import EMABioStudies
from .ucsc_cellbrowser import UCSCCellBrowser
from .manifest import build_manifest, write_manifest_csv, write_manifest_jsonl
from .inspect import inspect_h5ad
from .local_query import local_search

SOURCES = {
    "geo": GEO(),
    "cellxgene": CellxGene(),
    "scp": BroadSCP(),
    "ema": EMABioStudies(),
    "ucsc": UCSCCellBrowser(),
}
