from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import anndata as ad
from .gene_converter import (
    convert_gene_names, 
    annotate_species_automatically, 
    get_gene_annotation_report,
    MAMMALIAN_TAXIDS
)

_LOGGER = logging.getLogger(__name__)

_STD_FIELDS = ["source", "dataset_id", "species", "technology", "sex", "age", "condition", "disease", "batch"]


def inspect_h5ad(
    path: Union[str, Path], 
    annotate_genes: bool = False,
    convert_to_hugo: bool = False,
    output_file: Optional[str] = None,
    max_fields: int = 30
) -> Dict[str, Any]:
    """
    Enhanced inspection of .h5ad files with optional gene annotation and conversion.
    
    Args:
        path: Path to .h5ad file
        annotate_genes: Perform comprehensive gene annotation analysis
        convert_to_hugo: Convert gene names to HUGO symbols
        output_file: Save updated dataset to this file path
        max_fields: Maximum number of fields to display
    
    Returns:
        Dictionary with inspection results and optionally gene conversion report
    """
    path = Path(path)
    adata = ad.read_h5ad(path, backed="r")

    # Standard inspection
    out = _perform_basic_inspection(adata, path, max_fields)
    
    # Gene annotation analysis if requested
    if annotate_genes:
        out['gene_annotation'] = _perform_gene_annotation_analysis(adata)
    
    # Gene conversion if requested
    if convert_to_hugo:
        out['gene_conversion'] = _perform_gene_conversion(adata, path, output_file)
    
    # Close the backed object
    try:
        adata.file.close()
    except Exception:
        pass

    return out


def _perform_basic_inspection(adata: ad.AnnData, path: Path, max_fields: int) -> Dict[str, Any]:
    """Perform basic .h5ad inspection."""
    out = {
        "path": str(path.resolve()),
        "n_obs": int(adata.n_obs),
        "n_vars": int(adata.n_vars),
        "obs_cols": [],
        "var_cols": [],
        "layers": [],
        "obsm": [],
        "uns": [],
        "has_spatial": False,
        "has_raw_counts": False,
        "x_dtype": "",
        "x_is_sparse": False,
        "missing_std_fields": {},
        "organism_info": {
            "taxid": adata.uns.get('organism_taxid'),
            "name": adata.uns.get('organism_name')
        }
    }

    # Collect metadata columns
    try:
        out["obs_cols"] = list(adata.obs.columns)[:max_fields]
    except Exception:
        out["obs_cols"] = []
    
    try:
        out["var_cols"] = list(adata.var.columns)[:max_fields]
    except Exception:
        out["var_cols"] = []
    
    try:
        out["layers"] = sorted(list(adata.layers.keys()))
    except Exception:
        out["layers"] = []
    
    try:
        out["obsm"] = sorted(list(adata.obsm.keys()))
    except Exception:
        out["obsm"] = []
    
    try:
        out["uns"] = sorted(list(adata.uns.keys()))[:max_fields]
    except Exception:
        out["uns"] = []

    # Check for spatial data
    out["has_spatial"] = "spatial" in (out["obsm"] or [])
    out["has_raw_counts"] = "raw_counts" in (out["layers"] or [])

    # X data type info
    try:
        out["x_dtype"] = str(getattr(adata.X, "dtype", ""))
        out["x_is_sparse"] = "scipy.sparse" in str(type(adata.X)).lower()
    except Exception:
        pass

    # Check missingness of standard fields
    missing = {}
    for k in _STD_FIELDS:
        if k not in adata.obs:
            missing[k] = 1.0
            continue
        col = adata.obs[k]
        try:
            frac = float(col.isna().mean())
        except Exception:
            frac = 0.0
        missing[k] = frac
    out["missing_std_fields"] = missing

    return out


def _perform_gene_annotation_analysis(adata: ad.AnnData) -> Dict[str, Any]:
    """Perform comprehensive gene annotation analysis."""
    _LOGGER.info("Performing comprehensive gene annotation analysis...")
    
    # Load the dataset for writing
    adata_loaded = ad.read_h5ad(adata.filename, backed=False)
    
    # Perform automatic species annotation
    adata_loaded = annotate_species_automatically(adata_loaded)
    
    # Get annotation report
    annotation_report = get_gene_annotation_report(adata_loaded)
    
    # Analyze gene name patterns
    gene_analysis = _analyze_gene_patterns(adata_loaded.var_names)
    
    # Check for existing gene annotations
    existing_annotations = _check_existing_annotations(adata_loaded)
    
    return {
        "species_inference": annotation_report['organism_info'],
        "gene_annotation_completeness": annotation_report['gene_annotation_completeness'],
        "gene_pattern_analysis": gene_analysis,
        "existing_annotations": existing_annotations,
        "recommendations": _generate_annotation_recommendations(adata_loaded)
    }


def _perform_gene_conversion(adata: ad.AnnData, original_path: Path, output_file: Optional[str]) -> Dict[str, Any]:
    """Perform gene name conversion to HUGO symbols."""
    _LOGGER.info("Performing gene name conversion to HUGO symbols...")
    
    # Load the dataset for modification
    adata_loaded = ad.read_h5ad(adata.filename, backed=False)
    
    # Store original gene names
    original_names = adata_loaded.var_names.tolist()
    
    # Perform conversion
    adata_converted = convert_gene_names(adata_loaded, target_taxid=9606, annotate_comprehensive=True)
    
    # Calculate conversion statistics
    converted_names = adata_converted.var_names.tolist()
    conversion_stats = _calculate_conversion_stats(original_names, converted_names)
    
    # Save converted dataset if output file specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        adata_converted.write_h5ad(output_path)
        _LOGGER.info(f"Converted dataset saved to: {output_path}")
    
    return {
        "conversion_statistics": conversion_stats,
        "output_file": output_file,
        "species_information": {
            "source": adata_converted.uns.get('organism_name'),
            "target": "Homo sapiens (HUGO symbols)"
        },
        "gene_annotation_report": get_gene_annotation_report(adata_converted)
    }


def _analyze_gene_patterns(gene_names) -> Dict[str, Any]:
    """Analyze gene name patterns to infer characteristics."""
    import re
    
    analysis = {
        "total_genes": len(gene_names),
        "gene_patterns": {},
        "potential_species": [],
        "annotation_quality": "unknown"
    }
    
    # Analyze common patterns
    patterns = {
        "human_style": len([g for g in gene_names if re.match(r"^[A-Z][0-9]+[A-Z]*$", g)]),
        "mouse_style": len([g for g in gene_names if re.match(r"^[A-Z][a-z][0-9]+$", g)]),
        "ensembl_style": len([g for g in gene_names if re.match(r"^ENS[A-Z]+G[0-9]+$", g)]),
        "refseq_style": len([g for g in gene_names if re.match(r"^[A-Z][A-Z][0-9]+$", g)]),
        "uppercase": len([g for g in gene_names if g.isupper()]),
        "lowercase": len([g for g in gene_names if g.islower()]),
        "mixed_case": len([g for g in gene_names if not (g.isupper() or g.islower())])
    }
    
    analysis["gene_patterns"] = patterns
    
    # Infer potential species based on patterns
    if patterns["human_style"] > len(gene_names) * 0.3:
        analysis["potential_species"].append("Human (HUGO style)")
    if patterns["mouse_style"] > len(gene_names) * 0.3:
        analysis["potential_species"].append("Mouse")
    if patterns["ensembl_style"] > len(gene_names) * 0.1:
        analysis["potential_species"].append("Ensembl style (multiple species)")
    
    # Assess annotation quality
    total_patterned = sum(patterns.values())
    if total_patterned > len(gene_names) * 0.8:
        analysis["annotation_quality"] = "good"
    elif total_patterned > len(gene_names) * 0.5:
        analysis["annotation_quality"] = "moderate"
    else:
        analysis["annotation_quality"] = "poor"
    
    return analysis


def _check_existing_annotations(adata: ad.AnnData) -> Dict[str, Any]:
    """Check for existing gene annotations in the dataset."""
    annotations = {}
    
    # Check for common annotation fields
    var_columns = adata.var.columns.tolist()
    
    annotation_fields = {
        'symbol': 'Gene symbol',
        'name': 'Gene name/description',
        'entrezgene': 'Entrez Gene ID',
        'ensembl_gene': 'Ensembl Gene ID',
        'refseq': 'RefSeq ID',
        'description': 'Gene description',
        'original_gene_symbol': 'Original gene symbol (before conversion)'
    }
    
    for field, description in annotation_fields.items():
        if field in var_columns:
            non_empty = adata.var[field].notna().sum()
            annotations[field] = {
                "present": True,
                "description": description,
                "annotated_genes": int(non_empty),
                "total_genes": len(adata.var),
                "coverage_percentage": float(non_empty / len(adata.var) * 100)
            }
        else:
            annotations[field] = {
                "present": False,
                "description": description
            }
    
    return annotations


def _generate_annotation_recommendations(adata: ad.AnnData) -> List[str]:
    """Generate recommendations for gene annotation improvements."""
    recommendations = []
    
    # Check organism information
    if not adata.uns.get('organism_taxid'):
        recommendations.append("Species information is missing. Use --annotate-species to automatically infer.")
    
    # Check for gene conversion
    if 'original_gene_symbol' not in adata.var.columns:
        recommendations.append("Gene names appear to be in original format. Consider using --convert-to-hugo for standardization.")
    
    # Check annotation completeness
    if 'symbol' not in adata.var.columns:
        recommendations.append("Gene symbols are missing. Comprehensive annotation could improve analysis.")
    
    if 'name' not in adata.var.columns or adata.var['name'].isna().sum() > len(adata.var) * 0.5:
        recommendations.append("Gene names/descriptions are incomplete. Full annotation recommended.")
    
    # Check for species-specific issues
    organism_name = adata.uns.get('organism_name', '')
    if 'mouse' in organism_name.lower():
        recommendations.append("Mouse dataset detected. Consider converting to human orthologs for cross-species analysis.")
    
    return recommendations


def _calculate_conversion_stats(original_names: list, converted_names: list) -> Dict[str, Any]:
    """Calculate detailed conversion statistics."""
    if len(original_names) != len(converted_names):
        return {"error": "Length mismatch between original and converted gene lists"}
    
    stats = {
        "total_genes": len(original_names),
        "genes_converted": 0,
        "genes_unchanged": 0,
        "conversion_rate": 0.0,
        "unique_original": len(set(original_names)),
        "unique_converted": len(set(converted_names))
    }
    
    for orig, conv in zip(original_names, converted_names):
        if orig != conv:
            stats["genes_converted"] += 1
        else:
            stats["genes_unchanged"] += 1
    
    stats["conversion_rate"] = stats["genes_converted"] / stats["total_genes"] * 100
    
    return stats


def format_inspect_text(report: Dict[str, Any]) -> str:
    """Format inspection report as readable text."""
    lines = []
    lines.append(f"File: {report.get('path')}")
    lines.append(f"Shape: n_obs={report.get('n_obs')}  n_vars={report.get('n_vars')}")
    lines.append(f"X: dtype={report.get('x_dtype')}  sparse={report.get('x_is_sparse')}")
    lines.append(f"Layers: {', '.join(report.get('layers') or [])}")
    lines.append(f"obsm: {', '.join(report.get('obsm') or [])}")
    lines.append(f"has_spatial={report.get('has_spatial')}  has_raw_counts={report.get('has_raw_counts')}")
    
    # Organism information
    organism_info = report.get('organism_info', {})
    if organism_info.get('name'):
        lines.append(f"Organism: {organism_info['name']}")
    
    lines.append("")
    lines.append("Missingness (standard .obs fields):")
    miss = report.get("missing_std_fields", {}) or {}
    for k, v in miss.items():
        lines.append(f"  - {k}: {v:.3f}")
    lines.append("")
    lines.append("obs columns (head): " + ", ".join(report.get("obs_cols") or []))
    lines.append("var columns (head): " + ", ".join(report.get("var_cols") or []))
    
    # Gene annotation information if available
    if 'gene_annotation' in report:
        lines.append("")
        lines.append("Gene Annotation Analysis:")
        gene_ann = report['gene_annotation']
        
        if gene_ann.get('species_inference', {}).get('name'):
            lines.append(f"  Inferred species: {gene_ann['species_inference']['name']}")
        
        if gene_ann.get('gene_annotation_completeness'):
            lines.append("  Annotation completeness:")
            for field, info in gene_ann['gene_annotation_completeness'].items():
                if info.get('annotated', 0) > 0:
                    lines.append(f"    {field}: {info['annotated']}/{info.get('total_genes', 'N/A')} ({info.get('percentage', 0):.1f}%)")
    
    # Gene conversion information if available
    if 'gene_conversion' in report:
        lines.append("")
        lines.append("Gene Conversion Results:")
        conv_stats = report['gene_conversion'].get('conversion_statistics', {})
        if 'genes_converted' in conv_stats:
            lines.append(f"  Genes converted: {conv_stats['genes_converted']}/{conv_stats['total_genes']} ({conv_stats.get('conversion_rate', 0):.1f}%)")
        
        if report['gene_conversion'].get('output_file'):
            lines.append(f"  Converted file saved: {report['gene_conversion']['output_file']}")
    
    return "\n".join(lines)