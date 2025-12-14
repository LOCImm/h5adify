"""h5adify public API."""

from .highlevel import download, batch_download
from .merge import merge_h5ads

__all__ = ["download", "batch_download", "merge_h5ads"]
__version__ = "0.1.0"
