import os
import sys
from datetime import datetime

project = "h5adify"
author = "h5adify contributors"
copyright = f"{datetime.now().year}, {author}"

extensions = ["myst_parser"]
myst_enable_extensions = ["colon_fence", "deflist"]

templates_path = ["_templates"]
exclude_patterns = ["_build"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
