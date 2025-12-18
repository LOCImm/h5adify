from __future__ import annotations

import contextlib
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


_DEFAULT_CONNECT_TIMEOUT = float(os.environ.get("H5ADIFY_CONNECT_TIMEOUT", "15"))
_DEFAULT_READ_TIMEOUT = float(os.environ.get("H5ADIFY_READ_TIMEOUT", "60"))
_DEFAULT_HTTP_RETRIES = int(os.environ.get("H5ADIFY_HTTP_RETRIES", "5"))
_DEFAULT_HTTP_BACKOFF = float(os.environ.get("H5ADIFY_HTTP_BACKOFF", "0.5"))


def get_timeout(connect: Optional[float] = None, read: Optional[float] = None) -> Tuple[float, float]:
    return (float(connect if connect is not None else _DEFAULT_CONNECT_TIMEOUT),
            float(read if read is not None else _DEFAULT_READ_TIMEOUT))


def get_session() -> requests.Session:
    """requests Session with retry/backoff."""
    s = requests.Session()
    retry = Retry(
        total=_DEFAULT_HTTP_RETRIES,
        read=_DEFAULT_HTTP_RETRIES,
        connect=_DEFAULT_HTTP_RETRIES,
        backoff_factor=_DEFAULT_HTTP_BACKOFF,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST", "HEAD"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def ensure_dir(path: Union[str, Path]) -> str:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def rm_rf(path: Union[str, Path]) -> None:
    p = Path(path)
    if not p.exists():
        return
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink(missing_ok=True)


def is_url(x: str) -> bool:
    return bool(re.match(r"^https?://", str(x).strip()))


def safe_filename(name: str, max_len: int = 180) -> str:
    name = str(name)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    if len(name) > max_len:
        name = name[:max_len]
    return name or "file"


def download_file(url: str, out_path: Union[str, Path], *, session: Optional[requests.Session] = None) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    sess = session or get_session()
    timeout = get_timeout()
    with sess.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with p.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    return str(p)


@contextlib.contextmanager
def tempdir(prefix: str = "h5adify_") -> Iterator[str]:
    d = tempfile.mkdtemp(prefix=prefix)
    try:
        yield d
    finally:
        rm_rf(d)


def safe_jsonable(obj: Any) -> Any:
    """Recursively convert common non-JSON types (numpy, Path, set) to JSON-safe types."""
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None  # type: ignore

    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (list, tuple)):
        return [safe_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): safe_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, set):
        return [safe_jsonable(x) for x in sorted(obj)]
    if np is not None:
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.ndarray,)):
            return safe_jsonable(obj.tolist())
    # fallback: try string
    return str(obj)
