from __future__ import annotations

import logging
from typing import Dict, Optional, Union
from pathlib import Path

import anndata as ad
import pandas as pd

from .config import ObsPolicy, get_policy

_LOGGER = logging.getLogger(__name__)


def apply_obs_policy(
    adata: ad.AnnData,
    policy: Optional[ObsPolicy] = None,
    overrides: Optional[Dict[str, str]] = None,
    source: str = "unknown"
) -> ad.AnnData:
    """
    Apply standardized metadata policy to an AnnData object.
    
    This function:
    1. Standardizes .obs field values according to the policy
    2. Applies user-provided overrides
    3. Ensures required fields are present
    4. Updates uns metadata with source information
    
    Args:
        adata: AnnData object to process
        policy: Observation policy to apply (uses default if None)
        overrides: Dictionary of field overrides
        source: Source identifier for metadata
    
    Returns:
        Processed AnnData object
    """
    policy = policy or get_policy()
    overrides = overrides or {}
    
    _LOGGER.debug(f"Applying obs policy for source: {source}")
    
    # Ensure required columns exist in .obs
    required_fields = ["source", "dataset_id", "sample_id", "species", "technology", 
                      "sex", "age", "condition", "disease", "batch", "modality"]
    
    for field in required_fields:
        if field not in adata.obs.columns:
            # Set default values based on field type
            if field in ["source"]:
                adata.obs[field] = source
            elif field in ["dataset_id", "sample_id"]:
                adata.obs[field] = "unknown"
            elif field == "species":
                adata.obs[field] = policy.default_species
            elif field == "technology":
                adata.obs[field] = policy.default_technology
            elif field == "sex":
                adata.obs[field] = policy.default_sex
            elif field == "age":
                adata.obs[field] = "unknown"
            elif field == "condition":
                adata.obs[field] = policy.default_condition
            elif field == "disease":
                adata.obs[field] = policy.default_disease
            elif field == "batch":
                adata.obs[field] = "batch1"
            elif field == "modality":
                adata.obs[field] = policy.default_modality
    
    # Apply policy normalization to existing values
    for field in required_fields:
        if field in adata.obs.columns:
            # Normalize values according to policy
            adata.obs[field] = adata.obs[field].astype(str).apply(
                lambda x: policy.normalize_value(field, x)
            )
    
    # Apply overrides
    for field, value in overrides.items():
        if field in adata.obs.columns:
            adata.obs[field] = value
            _LOGGER.debug(f"Applied override {field} = {value}")
        else:
            # Add new column if it doesn't exist
            adata.obs[field] = value
            _LOGGER.debug(f"Added new field {field} = {value}")
    
    # Update uns metadata
    if "processing_info" not in adata.uns:
        adata.uns["processing_info"] = {}
    
    adata.uns["processing_info"]["source"] = source
    adata.uns["processing_info"]["policy_applied"] = True
    adata.uns["processing_info"]["fields_standardized"] = required_fields
    
    _LOGGER.debug(f"Applied obs policy. Standardized fields: {required_fields}")
    
    return adata


def infer_metadata_from_adata(adata: ad.AnnData) -> Dict[str, str]:
    """
    Infer metadata fields from existing AnnData structure.
    
    This function attempts to extract meaningful metadata from:
    - Existing .obs columns
    - adata.uns metadata
    - Filename patterns
    - Variable names (for species inference)
    
    Args:
        adata: AnnData object to analyze
    
    Returns:
        Dictionary of inferred metadata
    """
    inferred = {}
    
    # Try to infer from existing columns
    obs_cols = adata.obs.columns.tolist()
    
    # Common field mappings
    field_mappings = {
        "cell_type": "cell_type",
        "celltype": "cell_type", 
        "celltype_ annotations": "cell_type",
        "cell_type_ annotations": "cell_type",
        "cluster": "cluster",
        "leiden": "cluster",
        "louvain": "cluster",
        "cell_type": "cell_type",
        "annotation": "cell_type",
        "annotations": "cell_type",
        "cell_state": "cell_state",
        "cell_cycle": "cell_cycle",
        "cell_line": "cell_line",
        "tissue": "tissue",
        "region": "tissue",
        "anatomical_region": "tissue",
        "anatomical_site": "tissue",
        "treatment": "condition",
        "genotype": "condition",
        "cell_line": "cell_line",
        "celltype": "cell_type"
    }
    
    for col in obs_cols:
        col_lower = col.lower()
        
        # Check for direct matches
        if col_lower in field_mappings:
            target_field = field_mappings[col_lower]
            # Get the most common value as representative
            most_common = adata.obs[col].mode().iloc[0] if not adata.obs[col].empty else "unknown"
            inferred[target_field] = str(most_common)
        
        # Check for partial matches
        elif "species" in col_lower or "organism" in col_lower:
            species_val = adata.obs[col].mode().iloc[0] if not adata.obs[col].empty else "unknown"
            inferred["species"] = str(species_val)
        
        elif "tech" in col_lower or "method" in col_lower or "platform" in col_lower:
            tech_val = adata.obs[col].mode().iloc[0] if not adata.obs[col].empty else "unknown"
            inferred["technology"] = str(tech_val)
        
        elif "sex" in col_lower or "gender" in col_lower:
            sex_val = adata.obs[col].mode().iloc[0] if not adata.obs[col].empty else "unknown"
            inferred["sex"] = str(sex_val)
    
    # Infer from uns metadata
    if "organism" in adata.uns:
        inferred["species"] = str(adata.uns["organism"])
    elif "organism_taxid" in adata.uns:
        taxid = adata.uns["organism_taxid"]
        # Map taxid to species name (simplified)
        taxid_species_map = {
            9606: "human",
            10090: "mouse",
            10116: "rat"
        }
        inferred["species"] = taxid_species_map.get(taxid, "unknown")
    
    if "technology" in adata.uns:
        inferred["technology"] = str(adata.uns["technology"])
    
    # Infer from filename patterns
    # This would require the file path, which we don't have here
    # Could be enhanced by passing file_path parameter
    
    _LOGGER.debug(f"Inferred metadata: {inferred}")
    
    return inferred


def standardize_obs_schema(adata: ad.AnnData, schema_version: str = "1.0") -> ad.AnnData:
    """
    Standardize .obs schema to a specific version.
    
    Args:
        adata: AnnData object
        schema_version: Target schema version
    
    Returns:
        Standardized AnnData object
    """
    _LOGGER.info(f"Standardizing obs schema to version {schema_version}")
    
    if schema_version == "1.0":
        return _standardize_schema_v1(adata)
    else:
        _LOGGER.warning(f"Unknown schema version {schema_version}, skipping standardization")
        return adata


def _standardize_schema_v1(adata: ad.AnnData) -> ad.AnnData:
    """Standardize to schema version 1.0."""
    
    # Required fields for schema 1.0
    required_fields = [
        "source", "dataset_id", "sample_id", "species", "technology", 
        "sex", "age", "condition", "disease", "batch", "modality"
    ]
    
    # Ensure all required fields exist
    for field in required_fields:
        if field not in adata.obs.columns:
            if field == "source":
                adata.obs[field] = "unknown"
            elif field == "dataset_id":
                adata.obs[field] = "unknown"
            elif field == "sample_id":
                # Generate sample IDs if not present
                if "sample" in adata.obs.columns:
                    adata.obs["sample_id"] = adata.obs["sample"]
                else:
                    adata.obs["sample_id"] = "sample1"
            else:
                adata.obs[field] = "unknown"
    
    # Add schema version to uns
    adata.uns["schema_version"] = schema_version
    adata.uns["schema_standardized"] = True
    
    return adata


def validate_obs_metadata(adata: ad.AnnData, strict: bool = False) -> Dict[str, Union[bool, List[str]]]:
    """
    Validate .obs metadata against expected schema.
    
    Args:
        adata: AnnData object to validate
        strict: Whether to perform strict validation
    
    Returns:
        Dictionary with validation results
    """
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "schema_compliance": {}
    }
    
    required_fields = ["source", "dataset_id", "sample_id", "species", "technology"]
    optional_fields = ["sex", "age", "condition", "disease", "batch", "modality"]
    
    # Check required fields
    for field in required_fields:
        if field not in adata.obs.columns:
            validation_result["errors"].append(f"Missing required field: {field}")
            validation_result["valid"] = False
        elif adata.obs[field].isna().all():
            validation_result["errors"].append(f"Required field {field} has all NaN values")
            validation_result["valid"] = False
    
    # Check optional fields
    for field in optional_fields:
        if field not in adata.obs.columns:
            validation_result["warnings"].append(f"Missing optional field: {field}")
        elif adata.obs[field].isna().all():
            validation_result["warnings"].append(f"Optional field {field} has all NaN values")
    
    # Check data types
    for field in adata.obs.columns:
        if adata.obs[field].dtype == 'object':
            # Check for mixed types that might cause issues
            unique_types = set(type(x).__name__ for x in adata.obs[field].dropna())
            if len(unique_types) > 1:
                validation_result["warnings"].append(
                    f"Field {field} has mixed types: {unique_types}"
                )
    
    # Schema compliance check
    validation_result["schema_compliance"] = {
        "has_required_fields": all(field in adata.obs.columns for field in required_fields),
        "has_optional_fields": sum(field in adata.obs.columns for field in optional_fields),
        "total_fields": len(adata.obs.columns),
        "required_field_coverage": sum(
            1 - adata.obs[field].isna().mean() 
            for field in required_fields 
            if field in adata.obs.columns
        ) / len(required_fields)
    }
    
    # Strict validation additional checks
    if strict:
        # Check for reasonable values
        if "species" in adata.obs.columns:
            valid_species = {"human", "mouse", "rat", "unknown"}
            invalid_species = set(adata.obs["species"].dropna().unique()) - valid_species
            if invalid_species:
                validation_result["warnings"].append(
                    f"Non-standard species values: {invalid_species}"
                )
        
        # Check for duplicates in sample_id
        if "sample_id" in adata.obs.columns:
            duplicate_samples = adata.obs["sample_id"].duplicated().sum()
            if duplicate_samples > 0:
                validation_result["warnings"].append(
                    f"Found {duplicate_samples} duplicate sample IDs"
                )
    
    return validation_result