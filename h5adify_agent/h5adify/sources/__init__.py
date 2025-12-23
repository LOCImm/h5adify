"""
Working sources package for h5adify - Package initialization
"""

# Import all working source implementations
from .working_geo import WorkingGEOSource
from .working_ucsc import WorkingUCSCSource  
from .working_zenodo import WorkingZenodoSource
from .working_ema import WorkingEMASource
from .working_cellxgene import WorkingCellxGeneSource
from .working_scp import WorkingSCPSource

__all__ = [
    'WorkingGEOSource',
    'WorkingUCSCSource',
    'WorkingZenodoSource', 
    'WorkingEMASource',
    'WorkingCellxGeneSource',
    'WorkingSCPSource'
]
