from __future__ import annotations

import contextlib
import hashlib
import re
import shutil
import tempfile
from pathlib import Path
from typing import Iterable, Optional

import requests
from tqdm import tqdm


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


def download_file(url: str, out_path: str | Path, timeout: int = 60, overwrite: bool = False) -> Path:
    out_path = Path(out_path)
    if out_path.exists() and not overwrite:
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
