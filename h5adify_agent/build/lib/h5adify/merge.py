from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import anndata as ad
import numpy as np
import pandas as pd

from .utils import validate_h5ad_file, human_readable_size

_LOGGER = logging.getLogger(__name__)


def merge_h5ads(
    file_paths: List[Union[str, Path]],
    join: str = "outer",
    label: str = "batch",
    index_unique: str = "-",
    **kwargs
) -> ad.AnnData:
    """
    Merge multiple .h5ad files into a single AnnData object.
    
    This function validates input files and merges them with proper handling of:
    - Variable alignment across datasets
    - Metadata standardization
    - Batch information tracking
    
    Args:
        file_paths: List of paths to .h5ad files
        join: How to join datasets ('inner' or 'outer')
        label: Column name for batch labels
        index_unique: Separator for unique index creation
        **kwargs: Additional arguments passed to ad.concat
    
    Returns:
        Merged AnnData object
    """
    _LOGGER.info(f"Starting merge of {len(file_paths)} files")
    
    if not file_paths:
        raise ValueError("No file paths provided")
    
    # Validate input files
    valid_files = []
    for file_path in file_paths:
        file_path = Path(file_path)
        validation = validate_h5ad_file(file_path)
        
        if validation["valid"]:
            valid_files.append(file_path)
            _LOGGER.debug(f"Validated file: {file_path}")
        else:
            _LOGGER.warning(f"Skipping invalid file {file_path}: {validation['errors']}")
    
    if not valid_files:
        raise ValueError("No valid .h5ad files found")
    
    # Load all datasets
    adatas = []
    batch_info = []
    
    for i, file_path in enumerate(valid_files):
        try:
            _LOGGER.debug(f"Loading {file_path}")
            adata = ad.read_h5ad(file_path, backed=False)
            
            # Add batch information
            batch_name = f"batch_{i+1}_{file_path.stem}"
            adata.obs[label] = batch_name
            
            # Add source file information
            adata.uns["source_file"] = str(file_path)
            adata.uns["original_shape"] = (adata.n_obs, adata.n_vars)
            
            adatas.append(adata)
            batch_info.append({
                "file_path": str(file_path),
                "batch_name": batch_name,
                "n_obs": adata.n_obs,
                "n_vars": adata.n_vars
            })
            
        except Exception as e:
            _LOGGER.error(f"Failed to load {file_path}: {e}")
            raise
    
    _LOGGER.info(f"Loaded {len(adatas)} datasets for merging")
    
    # Perform the merge
    try:
        merged_adata = ad.concat(
            adatas,
            join=join,
            label=label,
            keys=[adata.obs[label][0] for adata in adatas],
            index_unique=index_unique,
            **kwargs
        )
        
        _LOGGER.info(f"Merge completed. Shape: {merged_adata.n_obs} × {merged_adata.n_vars}")
        
    except Exception as e:
        _LOGGER.error(f"Merge failed: {e}")
        raise
    
    # Post-process merged dataset
    merged_adata = _post_process_merge(merged_adata, batch_info)
    
    return merged_adata


def _post_process_merge(merged_adata: ad.AnnData, batch_info: List[Dict]) -> ad.AnnData:
    """Post-process merged dataset to ensure consistency."""
    
    _LOGGER.debug("Post-processing merged dataset")
    
    # Add merge information to uns
    merged_adata.uns["merge_info"] = {
        "n_datasets": len(batch_info),
        "batch_info": batch_info,
        "merge_timestamp": _get_timestamp(),
        "join_method": "ad.concat"
    }
    
    # Standardize column names across batches
    merged_adata = _standardize_metadata_columns(merged_adata)
    
    # Handle categorical data
    merged_adata = _fix_categorical_dtypes(merged_adata)
    
    # Ensure unique observation names
    merged_adata.obs_names_make_unique()
    
    # Ensure unique variable names
    merged_adata.var_names_make_unique()
    
    _LOGGER.debug("Post-processing completed")
    
    return merged_adata


def _standardize_metadata_columns(merged_adata: ad.AnnData) -> ad.AnnData:
    """Standardize metadata column names and values across merged datasets."""
    
    # Define standard column mappings
    column_mappings = {
        "cell_type": "cell_type",
        "celltype": "cell_type",
        "cell_type_ annotations": "cell_type",
        "annotation": "cell_type",
        "cluster": "cluster",
        "leiden": "cluster", 
        "louvain": "cluster",
        "cell_state": "cell_state",
        "cell_cycle": "cell_cycle",
        "tissue": "tissue",
        "region": "tissue",
        "anatomical_region": "tissue",
        "treatment": "condition",
        "genotype": "condition"
    }
    
    # Check for columns that should be standardized
    obs_columns = set(merged_adata.obs.columns)
    
    for old_col, new_col in column_mappings.items():
        if old_col in obs_columns and new_col not in obs_columns:
            # Rename column
            merged_adata.obs = merged_data.obs.rename(columns={old_col: new_col})
            _LOGGER.debug(f"Renamed column: {old_col} -> {new_col}")
    
    return merged_adata


def _fix_categorical_dtypes(merged_adata: ad.AnnData) -> ad.AnnData:
    """Fix categorical data types after merging."""
    
    # Columns that should be categorical
    categorical_columns = [
        "source", "dataset_id", "sample_id", "species", "technology",
        "sex", "condition", "disease", "batch", "modality", "cell_type",
        "cluster", "tissue", "cell_state", "cell_cycle"
    ]
    
    for col in categorical_columns:
        if col in merged_adata.obs.columns:
            try:
                # Convert to categorical if not already
                if not pd.api.types.is_categorical_dtype(merged_adata.obs[col]):
                    merged_adata.obs[col] = pd.Categorical(merged_adata.obs[col])
                    _LOGGER.debug(f"Converted {col} to categorical")
            except Exception as e:
                _LOGGER.debug(f"Could not convert {col} to categorical: {e}")
    
    return merged_adata


def _get_timestamp() -> str:
    """Get current timestamp string."""
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def merge_with_alignment(
    file_paths: List[Union[str, Path]],
    alignment_method: str = "intersect",
    **merge_kwargs
) -> ad.AnnData:
    """
    Merge datasets with gene/variable alignment.
    
    Args:
        file_paths: List of .h5ad file paths
        alignment_method: How to align variables ('intersect', 'union', 'custom')
        **merge_kwargs: Additional merge arguments
    
    Returns:
        Aligned and merged AnnData object
    """
    _LOGGER.info(f"Starting aligned merge of {len(file_paths)} files")
    
    # Load all datasets
    adatas = []
    all_genes = set()
    
    for file_path in file_paths:
        adata = ad.read_h5ad(file_path)
        adatas.append(adata)
        all_genes.update(adata.var_names)
    
    # Determine alignment strategy
    if alignment_method == "intersect":
        # Find common genes across all datasets
        common_genes = set(adatas[0].var_names)
        for adata in adatas[1:]:
            common_genes = common_genes.intersection(set(adata.var_names))
        
        target_genes = sorted(common_genes)
        _LOGGER.info(f"Using {len(target_genes)} common genes for alignment")
        
    elif alignment_method == "union":
        # Use all genes from all datasets
        target_genes = sorted(all_genes)
        _LOGGER.info(f"Using {len(target_genes)} genes (union) for alignment")
        
    else:
        raise ValueError(f"Unknown alignment method: {alignment_method}")
    
    # Align each dataset to target gene set
    aligned_adatas = []
    for i, adata in enumerate(adatas):
        if alignment_method == "intersect":
            # Subset to common genes
            common_mask = adata.var_names.isin(target_genes)
            aligned_adata = adata[:, common_mask].copy()
        else:  # union
            # Reorder to match target gene set
            gene_map = {gene: idx for idx, gene in enumerate(adata.var_names)}
            target_indices = [gene_map.get(gene, -1) for gene in target_genes]
            valid_indices = [idx for idx in target_indices if idx >= 0]
            
            if len(valid_indices) < len(target_genes):
                # Some genes are missing, create placeholder columns
                aligned_adata = _add_missing_genes(adata, target_genes)
            else:
                aligned_adata = adata[:, valid_indices].copy()
                aligned_adata.var_names = [target_genes[i] for i in valid_indices]
        
        aligned_adatas.append(aligned_adata)
    
    # Merge aligned datasets
    return merge_h5ads(
        [str(Path.cwd() / f"temp_aligned_{i}.h5ad") for i in range(len(aligned_adatas))],
        **merge_kwargs
    )


def _add_missing_genes(adata: ad.AnnData, target_genes: List[str]) -> ad.AnnData:
    """Add missing genes to dataset to match target gene set."""
    
    current_genes = set(adata.var_names)
    missing_genes = [gene for gene in target_genes if gene not in current_genes]
    
    if not missing_genes:
        return adata
    
    # Add missing genes with zero expression
    n_missing = len(missing_genes)
    n_obs = adata.n_obs
    
    # Create zero matrix for missing genes
    if hasattr(adata.X, 'toarray'):
        # Sparse matrix
        from scipy.sparse import csr_matrix
        missing_data = csr_matrix((n_obs, n_missing), dtype=adata.X.dtype)
    else:
        # Dense matrix
        missing_data = np.zeros((n_obs, n_missing), dtype=adata.X.dtype)
    
    # Create new AnnData with all genes
    new_var = pd.DataFrame(index=target_genes)
    
    # Add existing var columns for current genes
    for col in adata.var.columns:
        new_var[col] = np.nan
        for i, gene in enumerate(adata.var_names):
            if gene in target_genes:
                new_var.loc[gene, col] = adata.var.iloc[i][col]
    
    # Create new AnnData
    new_adata = ad.AnnData(
        X=missing_data if hasattr(adata.X, 'toarray') else np.zeros((n_obs, 0)),
        obs=adata.obs.copy(),
        var=new_var
    )
    
    # Combine with original data
    combined = ad.concat([adata, new_adata], axis=1, join='inner', index_unique=None)
    
    _LOGGER.debug(f"Added {len(missing_genes)} missing genes")
    return combined


def split_by_batch(merged_adata: ad.AnnData, batch_column: str = "batch") -> Dict[str, ad.AnnData]:
    """
    Split a merged dataset back into individual batches.
    
    Args:
        merged_adata: Merged AnnData object
        batch_column: Column name containing batch information
    
    Returns:
        Dictionary mapping batch names to AnnData objects
    """
    if batch_column not in merged_adata.obs.columns:
        raise ValueError(f"Batch column '{batch_column}' not found in obs")
    
    batches = {}
    
    for batch_name in merged_adata.obs[batch_column].cat.categories:
        batch_mask = merged_adata.obs[batch_column] == batch_name
        batch_adata = merged_adata[batch_mask].copy()
        
        # Remove batch column from individual datasets
        if batch_column in batch_adata.obs.columns:
            batch_adata = batch_adata.copy()
            batch_adata.obs = batch_adata.obs.drop(columns=[batch_column])
        
        batches[batch_name] = batch_adata
    
    _LOGGER.info(f"Split merged dataset into {len(batches)} batches")
    return batches


def validate_merge_quality(merged_adata: ad.AnnData) -> Dict[str, any]:
    """
    Validate the quality of a merged dataset.
    
    Args:
        merged_adata: Merged AnnData object
    
    Returns:
        Dictionary with quality metrics
    """
    quality = {
        "valid": True,
        "issues": [],
        "metrics": {},
        "batch_statistics": {}
    }
    
    # Basic structure checks
    if merged_adata.n_obs == 0:
        quality["issues"].append("No observations in merged dataset")
        quality["valid"] = False
    
    if merged_adata.n_vars == 0:
        quality["issues"].append("No variables in merged dataset")
        quality["valid"] = False
    
    # Check for batch information
    if "batch" in merged_adata.obs.columns:
        batch_counts = merged_adata.obs["batch"].value_counts()
        quality["batch_statistics"] = {
            "n_batches": len(batch_counts),
            "batch_sizes": batch_counts.to_dict(),
            "min_batch_size": int(batch_counts.min()),
            "max_batch_size": int(batch_counts.max()),
            "avg_batch_size": float(batch_counts.mean())
        }
        
        # Check for batch balance
        size_variance = batch_counts.var()
        if size_variance > batch_counts.mean():
            quality["issues"].append("Uneven batch sizes detected")
    else:
        quality["issues"].append("No batch information found")
    
    # Check metadata consistency
    metadata_fields = ["source", "species", "technology"]
    for field in metadata_fields:
        if field in merged_adata.obs.columns:
            unique_values = merged_adata.obs[field].nunique()
            quality["metrics"][f"{field}_unique_values"] = unique_values
            
            if unique_values > 1:
                value_counts = merged_adata.obs[field].value_counts()
                quality["metrics"][f"{field}_distribution"] = value_counts.to_dict()
    
    # Check for data quality issues
    if hasattr(merged_adata.X, 'toarray'):
        # Sparse matrix - check for reasonable sparsity
        sparsity = 1 - (merged_adata.X.nnz / (merged_adata.n_obs * merged_adata.n_vars))
        quality["metrics"]["sparsity"] = sparsity
    else:
        # Dense matrix
        quality["metrics"]["sparsity"] = 0.0
    
    return quality