from .geo import GEO
from .cellxgene import CellxGene
from .broad_scp import BroadSCP
from .ema_biostudies import EMABioStudies
from .ucsc_cellbrowser import UCSCCellBrowser

SOURCES = {
    "geo": GEO(),
    "cellxgene": CellxGene(),
    "scp": BroadSCP(),
    "ema": EMABioStudies(),
    "ucsc": UCSCCellBrowser(),
}
