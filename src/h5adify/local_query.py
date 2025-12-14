from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from .manifest import ManifestRow, build_manifest


def local_search(
    root: Union[str, Path],
    where: str,
    recursive: bool = True,
    compute_checksum: bool = False,
) -> List[Dict[str, Any]]:
    """
    Build (or rebuild) a manifest and apply a pandas-style query expression on it.

    Example where:
      "species == 'human' and has_spatial == True and technology.str.contains('visium', case=False, na=False)"
    """
    rows = build_manifest(root, recursive=recursive, compute_checksum=compute_checksum)

    # convert to DataFrame (pandas is the right tool for query expressions)
    import pandas as pd

    df = pd.DataFrame([r.__dict__ for r in rows])
    if df.empty:
        return []

    if where and where.strip():
        df = df.query(where, engine="python")

    # return dict records
    return df.to_dict(orient="records")
