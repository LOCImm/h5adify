"""h5adify public API."""

from .highlevel import download, batch_download
from .merge import merge_h5ads

# These are imported from sources.base
from .sources.base import SearchResult, Source

__all__ = ["download", "batch_download", "merge_h5ads", "SearchResult", "Source"]
__version__ = "0.1.0"
