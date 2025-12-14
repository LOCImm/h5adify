from __future__ import annotations

import contextlib
import os
import hashlib
import re
import shutil
import tempfile
from pathlib import Path
from typing import Iterable, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

# -----------------------------------------------------------------------------
# HTTP helpers (shared across sources)
#
# Some portals (CELLxGENE API, etc.) can be slow or rate-limited; we use
# retry-with-backoff + configurable timeouts to reduce transient failures.
#
# Environment variables:
#   H5ADIFY_CONNECT_TIMEOUT  (default: 10)
#   H5ADIFY_READ_TIMEOUT     (default: 120)
#   H5ADIFY_HTTP_RETRIES     (default: 5)
#   H5ADIFY_HTTP_BACKOFF     (default: 0.5)
# -----------------------------------------------------------------------------

_DEFAULT_CONNECT_TIMEOUT = float(os.getenv("H5ADIFY_CONNECT_TIMEOUT", "10"))
_DEFAULT_READ_TIMEOUT = float(os.getenv("H5ADIFY_READ_TIMEOUT", "120"))
_DEFAULT_HTTP_RETRIES = int(os.getenv("H5ADIFY_HTTP_RETRIES", "5"))
_DEFAULT_HTTP_BACKOFF = float(os.getenv("H5ADIFY_HTTP_BACKOFF", "0.5"))

_SESSION: Optional[requests.Session] = None


def get_timeout(timeout: Optional[float | tuple[float, float]] = None) -> tuple[float, float]:
    """Return a (connect, read) timeout tuple for `requests`."""
    if timeout is None:
        return (_DEFAULT_CONNECT_TIMEOUT, _DEFAULT_READ_TIMEOUT)
    if isinstance(timeout, (int, float)):
        return (_DEFAULT_CONNECT_TIMEOUT, float(timeout))
    return (float(timeout[0]), float(timeout[1]))


def get_session(
    retries: Optional[int] = None,
    backoff: Optional[float] = None,
    user_agent: str = "h5adify/0.x (+https://github.com/LOCImm/h5adify)",
) -> requests.Session:
    """Shared requests session with urllib3 Retry configured."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION

    r_total = _DEFAULT_HTTP_RETRIES if retries is None else int(retries)
    r_backoff = _DEFAULT_HTTP_BACKOFF if backoff is None else float(backoff)

    retry = Retry(
        total=r_total,
        connect=r_total,
        read=r_total,
        status=r_total,
        backoff_factor=r_backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent})
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    _SESSION = s
    return s




def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def safe_filename(name: str, max_len: int = 120) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_")
    return name[:max_len] if len(name) > max_len else name


def sha256_file(path: str | Path, chunk: int = 2**20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def download_file(
    url: str,
    out_path: str | Path,
    timeout: Optional[float | tuple[float, float]] = None,
    overwrite: bool = False,
    session: Optional[requests.Session] = None,
) -> Path:
    """Download a file with retries and a (connect, read) timeout."""
    out_path = Path(out_path)
    if out_path.exists() and not overwrite:
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)

    s = session or get_session()
    to = get_timeout(timeout)

    with s.get(url, stream=True, timeout=to) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        with open(out_path, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, desc=out_path.name, disable=(total == 0)
        ) as pbar:
            for chunk in r.iter_content(chunk_size=2**20):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
    return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(out_path, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, desc=out_path.name, disable=(total == 0)
        ) as pbar:
            for chunk in r.iter_content(chunk_size=2**20):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
    return out_path


@contextlib.contextmanager
def tempdir(prefix: str = "h5adify_") -> Iterable[Path]:
    d = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def rm_rf(path: str | Path) -> None:
    p = Path(path)
    if not p.exists():
        return
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    else:
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def parse_kv_overrides(items: Optional[list[str]]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if not items:
        return overrides
    for it in items:
        if "=" not in it:
            raise ValueError(f"Invalid --set '{it}', expected key=value")
        k, v = it.split("=", 1)
        overrides[k.strip()] = v.strip()
    return overrides
