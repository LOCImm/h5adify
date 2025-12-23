from __future__ import annotations

import json
import csv
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

import anndata as ad

from .utils import compute_file_hash, human_readable_size, validate_h5ad_file

_LOGGER = logging.getLogger(__name__)


@dataclass
class ManifestRow:
    """Represents a single row in a manifest."""
    path: str
    filename: str
    n_obs: int
    n_vars: int
    x_dtype: str
    is_sparse: bool
    has_raw_counts: bool
    has_spatial: bool
    layers: str
    obsm: str
    source: str
    dataset_id: str
    species: str
    technology: str
    condition: str
    disease: str
    batch: str
    checksum_sha256: str
    file_size: str
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ManifestRow':
        """Create from dictionary."""
        return cls(**data)


def build_manifest(root: Path, recursive: bool = True) -> List[ManifestRow]:
    """
    Build a manifest of all .h5ad files in a directory.
    
    Args:
        root: Root directory to scan
        recursive: Whether to scan recursively
    
    Returns:
        List of ManifestRow objects
    """
    _LOGGER.info(f"Building manifest for directory: {root}")
    
    if not root.exists():
        raise ValueError(f"Directory does not exist: {root}")
    
    # Find all .h5ad files
    if recursive:
        h5ad_files = list(root.rglob("*.h5ad"))
    else:
        h5ad_files = list(root.glob("*.h5ad"))
    
    if not h5ad_files:
        _LOGGER.warning(f"No .h5ad files found in {root}")
        return []
    
    manifest_rows = []
    
    for file_path in h5ad_files:
        try:
            manifest_row = _create_manifest_row(file_path)
            manifest_rows.append(manifest_row)
            _LOGGER.debug(f"Added to manifest: {file_path}")
        except Exception as e:
            _LOGGER.warning(f"Failed to process {file_path}: {e}")
            continue
    
    _LOGGER.info(f"Built manifest with {len(manifest_rows)} entries")
    return manifest_rows


def _create_manifest_row(file_path: Path) -> ManifestRow:
    """Create a manifest row for a single .h5ad file."""
    
    # Validate the file
    validation = validate_h5ad_file(file_path)
    if not validation["valid"]:
        raise ValueError(f"Invalid .h5ad file {file_path}: {validation['errors']}")
    
    # Read the file to extract metadata
    try:
        adata = ad.read_h5ad(file_path, backed="r")
        
        # Extract basic information
        n_obs = int(adata.n_obs)
        n_vars = int(adata.n_vars)
        
        # Check X matrix properties
        x_dtype = str(getattr(adata.X, "dtype", ""))
        is_sparse = "scipy.sparse" in str(type(adata.X)).lower()
        
        # Check for layers
        layers = ",".join(sorted(adata.layers.keys())) if adata.layers else ""
        
        # Check for spatial data
        obsm_keys = list(adata.obsm.keys()) if adata.obsm else []
        has_spatial = "spatial" in obsm_keys
        obsm_str = ",".join(sorted(obsm_keys))
        
        # Extract metadata from .obs
        source = _safe_get_metadata(adata, "source", "unknown")
        dataset_id = _safe_get_metadata(adata, "dataset_id", "unknown")
        species = _safe_get_metadata(adata, "species", "unknown")
        technology = _safe_get_metadata(adata, "technology", "unknown")
        condition = _safe_get_metadata(adata, "condition", "unknown")
        disease = _safe_get_metadata(adata, "disease", "unknown")
        batch = _safe_get_metadata(adata, "batch", "unknown")
        
        # Check for raw counts
        has_raw_counts = "raw_counts" in adata.layers
        
        # Close the backed object
        try:
            adata.file.close()
        except Exception:
            pass
        
    except Exception as e:
        raise ValueError(f"Failed to read .h5ad file {file_path}: {e}")
    
    # Get file information
    file_stat = file_path.stat()
    file_size = human_readable_size(file_stat.st_size)
    
    # Compute checksum
    try:
        checksum_sha256 = compute_file_hash(file_path)
    except Exception as e:
        _LOGGER.warning(f"Could not compute checksum for {file_path}: {e}")
        checksum_sha256 = "unknown"
    
    return ManifestRow(
        path=str(file_path.resolve()),
        filename=file_path.name,
        n_obs=n_obs,
        n_vars=n_vars,
        x_dtype=x_dtype,
        is_sparse=is_sparse,
        has_raw_counts=has_raw_counts,
        has_spatial=has_spatial,
        layers=layers,
        obsm=obsm_str,
        source=source,
        dataset_id=dataset_id,
        species=species,
        technology=technology,
        condition=condition,
        disease=disease,
        batch=batch,
        checksum_sha256=checksum_sha256,
        file_size=file_size,
        created_at=None,  # Could be added if needed
        last_modified=None  # Could be added if needed
    )


def _safe_get_metadata(adata, field: str, default: str) -> str:
    """Safely get metadata from adata.obs with fallback."""
    try:
        if field in adata.obs.columns:
            # Get the most common value (mode) as representative
            value_counts = adata.obs[field].value_counts()
            if not value_counts.empty:
                return str(value_counts.index[0])
        return default
    except Exception:
        return default


def write_manifest_jsonl(manifest: List[ManifestRow], output_path: Path) -> None:
    """
    Write manifest to JSONL file.
    
    Args:
        manifest: List of manifest rows
        output_path: Output file path
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for row in manifest:
            json_line = json.dumps(row.to_dict(), ensure_ascii=False)
            f.write(json_line + '\n')
    
    _LOGGER.info(f"Written JSONL manifest: {output_path}")


def write_manifest_csv(manifest: List[ManifestRow], output_path: Path) -> None:
    """
    Write manifest to CSV file.
    
    Args:
        manifest: List of manifest rows
        output_path: Output file path
    """
    if not manifest:
        # Create empty CSV with headers
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header
            writer.writerow(ManifestRow.__annotations__.keys())
        return
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(ManifestRow.__annotations__.keys())
        
        # Write data rows
        for row in manifest:
            # Convert row to dict and extract values in the same order as headers
            row_dict = row.to_dict()
            values = [row_dict[field] for field in ManifestRow.__annotations__.keys()]
            writer.writerow(values)
    
    _LOGGER.info(f"Written CSV manifest: {output_path}")


def read_manifest_jsonl(input_path: Path) -> List[ManifestRow]:
    """
    Read manifest from JSONL file.
    
    Args:
        input_path: Input file path
    
    Returns:
        List of manifest rows
    """
    manifest_rows = []
    
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                manifest_row = ManifestRow.from_dict(data)
                manifest_rows.append(manifest_row)
            except Exception as e:
                _LOGGER.warning(f"Failed to parse line {line_num} in {input_path}: {e}")
                continue
    
    _LOGGER.info(f"Read {len(manifest_rows)} rows from JSONL manifest: {input_path}")
    return manifest_rows


def filter_manifest(
    manifest: List[ManifestRow], 
    filters: Dict[str, Any]
) -> List[ManifestRow]:
    """
    Filter manifest based on criteria.
    
    Args:
        manifest: List of manifest rows
        filters: Dictionary of filter criteria
    
    Returns:
        Filtered list of manifest rows
    """
    filtered = manifest
    
    for field, value in filters.items():
        if field in ['n_obs', 'n_vars']:
            # Numeric filters
            if isinstance(value, dict):
                # Range filters like {"min": 1000, "max": 10000}
                if 'min' in value and filtered:
                    filtered = [row for row in filtered if getattr(row, field) >= value['min']]
                if 'max' in value and filtered:
                    filtered = [row for row in filtered if getattr(row, field) <= value['max']]
            else:
                # Exact match
                filtered = [row for row in filtered if getattr(row, field) == value]
        else:
            # String filters (case-insensitive partial match)
            filtered = [row for row in filtered if value.lower() in getattr(row, field, "").lower()]
    
    return filtered


def generate_manifest_summary(manifest: List[ManifestRow]) -> Dict[str, Any]:
    """
    Generate summary statistics for a manifest.
    
    Args:
        manifest: List of manifest rows
    
    Returns:
        Dictionary with summary statistics
    """
    if not manifest:
        return {
            "total_files": 0,
            "total_cells": 0,
            "total_genes": 0,
            "sources": {},
            "species": {},
            "technologies": {},
            "file_size_total": 0
        }
    
    # Basic counts
    total_files = len(manifest)
    total_cells = sum(row.n_obs for row in manifest)
    total_genes = sum(row.n_vars for row in manifest)
    
    # Source distribution
    sources = {}
    for row in manifest:
        source = row.source
        sources[source] = sources.get(source, 0) + 1
    
    # Species distribution
    species = {}
    for row in manifest:
        sp = row.species
        species[sp] = species.get(sp, 0) + 1
    
    # Technology distribution
    technologies = {}
    for row in manifest:
        tech = row.technology
        technologies[tech] = technologies.get(tech, 0) + 1
    
    # Calculate total file size
    total_size_bytes = 0
    for row in manifest:
        try:
            # Parse human readable size back to bytes
            size_str = row.file_size
            if size_str.endswith('GB'):
                total_size_bytes += float(size_str[:-2]) * 1024**3
            elif size_str.endswith('MB'):
                total_size_bytes += float(size_str[:-2]) * 1024**2
            elif size_str.endswith('KB'):
                total_size_bytes += float(size_str[:-2]) * 1024
            elif size_str.endswith('B'):
                total_size_bytes += float(size_str[:-1])
        except Exception:
            pass
    
    return {
        "total_files": total_files,
        "total_cells": total_cells,
        "total_genes": total_genes,
        "sources": sources,
        "species": species,
        "technologies": technologies,
        "file_size_total_human": human_readable_size(int(total_size_bytes)),
        "file_size_total_bytes": int(total_size_bytes),
        "avg_cells_per_file": total_cells // total_files if total_files > 0 else 0,
        "avg_genes_per_file": total_genes // total_files if total_files > 0 else 0
    }


def validate_manifest(manifest: List[ManifestRow]) -> Dict[str, Any]:
    """
    Validate a manifest for consistency and completeness.
    
    Args:
        manifest: List of manifest rows
    
    Returns:
        Dictionary with validation results
    """
    validation = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "stats": {}
    }
    
    if not manifest:
        validation["warnings"].append("Empty manifest")
        return validation
    
    # Check for duplicate files
    paths = [row.path for row in manifest]
    if len(paths) != len(set(paths)):
        validation["warnings"].append("Duplicate file paths found")
    
    # Check file existence
    missing_files = []
    for row in manifest:
        if not Path(row.path).exists():
            missing_files.append(row.path)
    
    if missing_files:
        validation["errors"].append(f"Missing files: {len(missing_files)}")
        validation["valid"] = False
    
    # Check for reasonable values
    zero_observation_files = [row for row in manifest if row.n_obs == 0]
    if zero_observation_files:
        validation["warnings"].append(f"Files with zero observations: {len(zero_observation_files)}")
    
    zero_gene_files = [row for row in manifest if row.n_vars == 0]
    if zero_gene_files:
        validation["errors"].append(f"Files with zero genes: {len(zero_gene_files)}")
        validation["valid"] = False
    
    # Generate stats
    validation["stats"] = generate_manifest_summary(manifest)
    
    return validation