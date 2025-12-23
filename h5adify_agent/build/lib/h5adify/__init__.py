"""h5adify - Enhanced single-cell data processing toolkit with AI capabilities."""

__version__ = "5.0.0"
__author__ = "MiniMax Agent"

# Core imports
from .highlevel import download, batch_download, analyze_dataset
from .merge import merge_h5ads
from .inspect_data import inspect_h5ad, format_inspect_text
from .gene_converter import (
    convert_gene_names, 
    annotate_species_automatically, 
    get_gene_annotation_report,
    MAMMALIAN_TAXIDS
)

# Source registry
from .registry import get_source, list_sources

# Enhanced terminal agent with GUI support (v5.0.0)
from .enhanced_terminal_agent import main as agent_main
from .enhanced_terminal_agent import H5ADEnhancedTerminalAgent as IntegratedTerminalAgent

__all__ = [
    # High-level functions
    "download",
    "batch_download", 
    "analyze_dataset",
    
    # Data manipulation
    "merge_h5ads",
    
    # Inspection and analysis
    "inspect_h5ad",
    "format_inspect_text",
    
    # Gene conversion and annotation
    "convert_gene_names",
    "annotate_species_automatically", 
    "get_gene_annotation_report",
    "MAMMALIAN_TAXIDS",
    
    # Source management
    "get_source",
    "list_sources",
    
    # Enhanced terminal agent with GUI support (v5.0.0)
    "agent_main",
    "IntegratedTerminalAgent",
    
    # Version
    "__version__",
]