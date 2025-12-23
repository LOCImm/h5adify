from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
import logging

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

_LOGGER = logging.getLogger(__name__)


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def rm_rf(path: Path) -> None:
    """Remove a file or directory tree, ignoring errors."""
    path = Path(path)
    if path.exists():
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path, ignore_errors=True)


@contextmanager
def tempdir(prefix: str = "", suffix: str = "", dir: Optional[Path] = None):
    """Context manager for creating temporary directories."""
    if dir is None:
        dir = Path(tempfile.gettempdir())
    
    temp_dir = tempfile.mkdtemp(prefix=prefix, suffix=suffix, dir=str(dir))
    try:
        yield Path(temp_dir)
    finally:
        rm_rf(Path(temp_dir))


def download_file(url: str, dest: str, chunk_size: int = 8192, timeout: int = 300) -> None:
    """Download a file from URL to destination with progress logging."""
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    _LOGGER.info(f"Downloading {url} to {dest_path}")
    
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            
            with open(dest_path, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            if downloaded % (1024 * 1024) == 0:  # Log every MB
                                _LOGGER.debug(f"Download progress: {progress:.1f}%")
        
        _LOGGER.info(f"Download completed: {dest_path}")
        
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink()
        raise RuntimeError(f"Failed to download {url}: {e}")


def get_session() -> requests.Session:
    """Get a configured requests session with retry logic."""
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def get_timeout() -> int:
    """Get default timeout for requests."""
    return 60


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """Compute hash of a file."""
    hash_func = hashlib.new(algorithm)
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human readable format."""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"


def find_h5ad_files(directory: Path, recursive: bool = True) -> list[Path]:
    """Find all .h5ad files in a directory."""
    if recursive:
        return list(directory.rglob("*.h5ad"))
    else:
        return list(directory.glob("*.h5ad"))


def validate_h5ad_file(file_path: Path) -> dict:
    """Validate that a file is a proper .h5ad file."""
    validation = {
        "valid": False,
        "errors": [],
        "warnings": [],
        "file_size": 0,
        "file_hash": None
    }
    
    try:
        # Check if file exists and is readable
        if not file_path.exists():
            validation["errors"].append("File does not exist")
            return validation
        
        if not file_path.is_file():
            validation["errors"].append("Path is not a file")
            return validation
        
        validation["file_size"] = file_path.stat().st_size
        
        # Try to compute hash
        try:
            validation["file_hash"] = compute_file_hash(file_path)
        except Exception as e:
            validation["warnings"].append(f"Could not compute file hash: {e}")
        
        # Try to read with anndata
        import anndata as ad
        try:
            adata = ad.read_h5ad(file_path, backed="r")
            validation["valid"] = True
            
            # Additional validation checks
            if adata.n_obs == 0:
                validation["warnings"].append("Dataset has no observations")
            
            if adata.n_vars == 0:
                validation["warnings"].append("Dataset has no variables")
            
            # Close the backed object
            try:
                adata.file.close()
            except Exception:
                pass
                
        except Exception as e:
            validation["errors"].append(f"Could not read as AnnData: {e}")
        
    except Exception as e:
        validation["errors"].append(f"File validation failed: {e}")
    
    return validation


def merge_dicts(*dicts: dict) -> dict:
    """Merge multiple dictionaries, with later dicts overwriting earlier ones."""
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def safe_filename(filename: str) -> str:
    """Convert a string to a safe filename."""
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    safe_chars = '_' * len(unsafe_chars)
    
    filename = filename.translate(str.maketrans(unsafe_chars, safe_chars))
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Ensure filename is not empty
    if not filename:
        filename = "unnamed"
    
    return filename


def is_url(string: str) -> bool:
    """Check if a string is a valid URL."""
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(string) is not None


def get_file_extension(file_path: Path) -> str:
    """Get file extension in lowercase without dot."""
    return file_path.suffix.lower()[1:] if file_path.suffix else ""


def is_text_file(file_path: Path, max_check_bytes: int = 1024) -> bool:
    """Check if a file is likely a text file."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(max_check_bytes)
            
        # Check for high proportion of printable characters
        printable = sum(1 for b in chunk if 32 <= b <= 126 or b in (9, 10, 13))
        return printable / len(chunk) > 0.7 if chunk else False
        
    except Exception:
        return False


def extract_tar_gz(file_path: Path, extract_dir: Path) -> list[Path]:
    """Extract tar.gz file and return list of extracted files."""
    import tarfile
    
    extract_dir = ensure_dir(extract_dir)
    extracted_files = []
    
    try:
        with tarfile.open(file_path, "r:gz") as tar:
            tar.extractall(path=extract_dir)
            
            # Collect all extracted files
            for member in tar.getmembers():
                if member.isfile():
                    extracted_path = extract_dir / member.name
                    extracted_files.append(extracted_path)
                    
    except Exception as e:
        raise RuntimeError(f"Failed to extract {file_path}: {e}")
    
    return extracted_files


def estimate_memory_usage(adata) -> dict:
    """Estimate memory usage of an AnnData object."""
    import sys
    
    try:
        # Estimate size of different components
        obs_size = sys.getsizeof(adata.obs) if hasattr(adata.obs, '__sizeof__') else 0
        var_size = sys.getsizeof(adata.var) if hasattr(adata.var, '__sizeof__') else 0
        x_size = sys.getsizeof(adata.X) if hasattr(adata.X, '__sizeof__') else 0
        
        # Estimate actual data size (approximation)
        estimated_total = (adata.n_obs * adata.n_vars * 4)  # Assuming float32
        
        return {
            "estimated_data_size_bytes": estimated_total,
            "estimated_data_size_human": human_readable_size(estimated_total),
            "n_obs": adata.n_obs,
            "n_vars": adata.n_vars,
            "sparsity_estimate": estimated_total / (adata.n_obs * adata.n_vars * 4) if adata.n_obs * adata.n_vars > 0 else 0
        }
        
    except Exception as e:
        return {"error": f"Could not estimate memory usage: {e}"}


def create_backup(file_path: Path) -> Optional[Path]:
    """Create a backup of a file."""
    if not file_path.exists():
        return None
    
    backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
    
    try:
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception as e:
        _LOGGER.warning(f"Failed to create backup of {file_path}: {e}")
        return None


def restore_from_backup(file_path: Path) -> bool:
    """Restore file from backup."""
    backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
    
    if not backup_path.exists():
        _LOGGER.warning(f"No backup found for {file_path}")
        return False
    
    try:
        shutil.move(str(backup_path), str(file_path))
        return True
    except Exception as e:
        _LOGGER.error(f"Failed to restore from backup: {e}")
        return False