import os
import sys
from pathlib import Path

# Ensure src/ is importable (works even if install step changes)
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

project = "h5adify"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

autodoc_mock_imports = [
    "scanpy",
    "h5py",
    "torch",
    "anndata",
    "numpy",
    "pandas",
]

# If you use Markdown docs
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
root_doc = "index"
