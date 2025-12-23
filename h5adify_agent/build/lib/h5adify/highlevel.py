from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from .registry import get_source
from .merge import merge_h5ads
from .gene_converter import convert_gene_names, annotate_species_automatically
from .inspect_data import inspect_h5ad

_LOGGER = logging.getLogger(__name__)


def download(
    source: str,
    *,
    outdir: str,
    gse: Optional[str] = None,
    dataset_id: Optional[str] = None,
    merge_samples: bool = True,
    overrides: Optional[Dict[str, str]] = None,
    cleanup: bool = True,
    convert_genes: bool = False,
    annotate_species: bool = False,
) -> List[str]:
    """
    Enhanced download function with gene conversion and species annotation.
    
    Args:
        source: Data source (geo, cellxgene, sodb, scp, ucsc, ema)
        outdir: Output directory for downloaded files
        gse: GEO series ID (only for geo source)
        dataset_id: Dataset identifier (for other sources)
        merge_samples: Whether to merge multiple samples into one .h5ad
        overrides: Dictionary of metadata field overrides
        cleanup: Whether to clean up intermediate files
        convert_genes: Whether to convert gene names to human orthologs
        annotate_species: Whether to automatically infer and annotate species
    
    Returns:
        List of output file paths
    """
    _LOGGER.info(f"Starting download from {source}")
    
    # Get the appropriate source
    src = get_source(source)
    
    # Prepare download kwargs (exclude gene conversion parameters for source)
    download_kwargs = {
        "outdir": outdir,
        "merge_samples": merge_samples,
        "overrides": overrides or {},
        "cleanup": cleanup,
    }
    
    # Add source-specific arguments
    if source == "geo":
        if not gse:
            raise ValueError("GEO download requires gse parameter")
        download_kwargs["dataset_id"] = gse  # Pass GSE as dataset_id
    else:
        if not dataset_id:
            raise ValueError(f"{source} download requires dataset_id parameter")
        download_kwargs["dataset_id"] = dataset_id
    
    # Perform the download
    try:
        output_paths = src.download(**download_kwargs)
        _LOGGER.info(f"Download completed: {len(output_paths)} files produced")
        
        # Post-process downloaded files
        if output_paths and (convert_genes or annotate_species):
            output_paths = _post_process_downloads(output_paths, convert_genes, annotate_species)
        
        return output_paths
        
    except Exception as e:
        _LOGGER.error(f"Download failed: {e}")
        raise


def batch_download(
    items: List[str],
    *,
    outdir: str,
    merge_out: Optional[str] = None,
    overrides: Optional[Dict[str, str]] = None,
    convert_genes: bool = False,
    annotate_species: bool = False,
) -> Union[List[str], str, Dict[str, Union[List[str], str]]]:
    """
    Enhanced batch download with gene conversion and species annotation.
    
    Args:
        items: List of source:identifier specifications (e.g., "geo:GSE229409")
        outdir: Output directory
        merge_out: Optional path for merged output file
        overrides: Dictionary of metadata field overrides for all items
        convert_genes: Whether to convert gene names to human orthologs
        annotate_species: Whether to automatically infer and annotate species
    
    Returns:
        List of output paths, or merged path, or dict of results
    """
    _LOGGER.info(f"Starting batch download of {len(items)} items")
    
    results = {}
    all_output_paths = []
    
    for i, item in enumerate(items, 1):
        _LOGGER.info(f"Processing item {i}/{len(items)}: {item}")
        
        if ":" not in item:
            raise ValueError(f"Invalid item format: {item}. Expected 'source:identifier'")
        
        source, identifier = item.split(":", 1)
        source = source.strip().lower()
        identifier = identifier.strip()
        
        try:
            # Create source-specific outdir
            item_outdir = Path(outdir) / f"{source}_{i}"
            item_outdir.mkdir(parents=True, exist_ok=True)
            
            # Download the item
            output_paths = download(
                source=source,
                outdir=str(item_outdir),
                gse=identifier if source == "geo" else None,
                dataset_id=identifier if source != "geo" else None,
                merge_samples=True,
                overrides=overrides,
                cleanup=True,
                convert_genes=convert_genes,
                annotate_species=annotate_species,
            )
            
            results[item] = output_paths
            all_output_paths.extend(output_paths)
            
            _LOGGER.info(f"Item {item} completed: {len(output_paths)} files")
            
        except Exception as e:
            _LOGGER.error(f"Failed to process {item}: {e}")
            results[item] = f"ERROR: {e}"
    
    # Handle merging if requested
    if merge_out and all_output_paths:
        _LOGGER.info(f"Merging {len(all_output_paths)} files into {merge_out}")
        try:
            merged_adata = merge_h5ads(all_output_paths, join="outer")
            merged_path = Path(merge_out)
            merged_path.parent.mkdir(parents=True, exist_ok=True)
            merged_adata.write_h5ad(merged_path)
            
            # If merging, return the merged path and summary
            return {
                "merged_file": str(merged_path),
                "individual_files": all_output_paths,
                "n_files_merged": len(all_output_paths),
                "source_results": results
            }
            
        except Exception as e:
            _LOGGER.error(f"Merging failed: {e}")
            # Return individual files if merging fails
            return {
                "individual_files": all_output_paths,
                "merge_error": str(e),
                "source_results": results
            }
    
    # Return results based on what was requested
    if len(items) == 1:
        return results[items[0]]
    else:
        return results


def _post_process_downloads(
    output_paths: List[str], 
    convert_genes: bool, 
    annotate_species: bool
) -> List[str]:
    """
    Post-process downloaded files with gene conversion and species annotation.
    
    Args:
        output_paths: List of output file paths
        convert_genes: Whether to convert gene names
        annotate_species: Whether to annotate species
    
    Returns:
        List of processed output paths
    """
    processed_paths = []
    
    for output_path in output_paths:
        try:
            _LOGGER.info(f"Post-processing: {output_path}")
            
            # Load the dataset
            import anndata as ad
            adata = ad.read_h5ad(output_path)
            
            # Apply species annotation if requested
            if annotate_species:
                adata = annotate_species_automatically(adata)
                _LOGGER.info(f"Species annotation added to {output_path}")
            
            # Apply gene conversion if requested
            if convert_genes:
                adata = convert_gene_names(adata, target_taxid=9606, annotate_comprehensive=True)
                _LOGGER.info(f"Gene conversion applied to {output_path}")
            
            # Save the processed dataset (overwrite original)
            adata.write_h5ad(output_path)
            processed_paths.append(output_path)
            
            # Generate processing report
            _generate_processing_report(adata, output_path)
            
        except Exception as e:
            _LOGGER.error(f"Post-processing failed for {output_path}: {e}")
            # Keep original file if processing fails
            processed_paths.append(output_path)
    
    return processed_paths


def _generate_processing_report(adata, file_path: str):
    """Generate a processing report for a converted dataset."""
    try:
        from .gene_converter import get_gene_annotation_report
        
        report = get_gene_annotation_report(adata)
        
        # Create report file
        report_path = Path(file_path).with_suffix('.processing_report.json')
        
        # Add file information
        report['file_info'] = {
            'path': file_path,
            'n_obs': adata.n_obs,
            'n_vars': adata.n_vars,
            'processing_timestamp': _get_timestamp()
        }
        
        with open(report_path, 'w') as f:
            import json
            json.dump(report, f, indent=2, default=str)
        
        _LOGGER.info(f"Processing report saved: {report_path}")
        
    except Exception as e:
        _LOGGER.warning(f"Failed to generate processing report: {e}")


def _get_timestamp() -> str:
    """Get current timestamp string."""
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def analyze_dataset(
    file_path: Union[str, Path],
    *,
    annotate_genes: bool = True,
    convert_to_hugo: bool = False,
    output_file: Optional[str] = None,
    generate_report: bool = True,
) -> Dict:
    """
    Comprehensive analysis of a dataset with optional gene annotation and conversion.
    
    Args:
        file_path: Path to .h5ad file
        annotate_genes: Whether to perform gene annotation
        convert_to_hugo: Whether to convert to HUGO symbols
        output_file: Optional output file for converted dataset
        generate_report: Whether to generate analysis report
    
    Returns:
        Dictionary with analysis results
    """
    _LOGGER.info(f"Starting comprehensive analysis of {file_path}")
    
    # Load the dataset
    import anndata as ad
    adata = ad.read_h5ad(file_path)
    
    results = {
        'file_path': str(file_path),
        'basic_info': {
            'n_obs': adata.n_obs,
            'n_vars': adata.n_vars,
            'obs_columns': list(adata.obs.columns),
            'var_columns': list(adata.var.columns),
            'layers': list(adata.layers.keys()),
            'obsm': list(adata.obsm.keys())
        }
    }
    
    # Perform gene annotation analysis
    if annotate_genes:
        _LOGGER.info("Performing gene annotation analysis...")
        from .gene_converter import annotate_species_automatically, get_gene_annotation_report
        
        # Annotate species
        adata = annotate_species_automatically(adata)
        
        # Get annotation report
        annotation_report = get_gene_annotation_report(adata)
        results['gene_annotation'] = annotation_report
    
    # Perform gene conversion if requested
    if convert_to_hugo:
        _LOGGER.info("Converting gene names to HUGO symbols...")
        from .gene_converter import convert_gene_names
        
        original_genes = adata.var_names.tolist()
        adata = convert_gene_names(adata, target_taxid=9606, annotate_comprehensive=True)
        
        # Calculate conversion statistics
        new_genes = adata.var_names.tolist()
        converted_count = sum(1 for orig, new in zip(original_genes, new_genes) if orig != new)
        
        results['gene_conversion'] = {
            'original_genes': len(original_genes),
            'converted_genes': converted_count,
            'conversion_rate': (converted_count / len(original_genes)) * 100,
            'source_species': adata.uns.get('organism_name'),
            'target_species': 'Homo sapiens'
        }
        
        # Save converted dataset if output file specified
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            adata.write_h5ad(output_path)
            results['output_file'] = str(output_path)
            _LOGGER.info(f"Converted dataset saved: {output_path}")
    
    # Perform quality assessment
    results['quality_assessment'] = _assess_quality(adata)
    
    # Generate comprehensive report
    if generate_report:
        report_path = _generate_comprehensive_report(results, file_path)
        results['report_file'] = str(report_path)
    
    _LOGGER.info(f"Analysis completed for {file_path}")
    return results


def _assess_quality(adata) -> Dict:
    """Assess the quality of a dataset."""
    quality = {
        'overall_score': 0,
        'issues': [],
        'recommendations': [],
        'metrics': {}
    }
    
    score = 100
    
    # Check basic structure
    if adata.n_obs == 0:
        quality['issues'].append("No observations in dataset")
        score -= 50
    
    if adata.n_vars == 0:
        quality['issues'].append("No variables in dataset")
        score -= 50
    
    # Check metadata completeness
    important_fields = ['source', 'dataset_id', 'species', 'technology']
    for field in important_fields:
        if field in adata.obs.columns:
            missing_pct = adata.obs[field].isna().mean() * 100
            quality['metrics'][f'{field}_missing_pct'] = missing_pct
            
            if missing_pct > 50:
                quality['issues'].append(f"High missing values in {field}: {missing_pct:.1f}%")
                score -= 10
        else:
            quality['issues'].append(f"Missing field: {field}")
            score -= 5
    
    # Check for spatial data
    has_spatial = 'spatial' in adata.obsm
    quality['metrics']['has_spatial'] = has_spatial
    
    # Check for raw counts
    has_raw_counts = 'raw_counts' in adata.layers
    quality['metrics']['has_raw_counts'] = has_raw_counts
    
    # Check gene annotation quality
    if 'symbol' in adata.var.columns:
        annotated_genes = adata.var['symbol'].notna().sum()
        annotation_rate = (annotated_genes / len(adata.var)) * 100
        quality['metrics']['gene_annotation_rate'] = annotation_rate
        
        if annotation_rate < 80:
            quality['issues'].append(f"Low gene annotation rate: {annotation_rate:.1f}%")
            score -= 10
    
    # Generate recommendations
    if 'species' in adata.obs.columns:
        species_values = adata.obs['species'].value_counts()
        if len(species_values) > 1:
            quality['recommendations'].append("Multiple species detected - consider species-specific analysis")
    
    if not has_raw_counts:
        quality['recommendations'].append("Consider adding raw counts layer for proper analysis")
    
    if adata.n_obs > 100000:
        quality['recommendations'].append("Large dataset - consider using efficient analysis methods")
    
    quality['overall_score'] = max(0, score)
    
    return quality


def _generate_comprehensive_report(results: Dict, file_path: Union[str, Path]) -> Path:
    """Generate a comprehensive analysis report."""
    report_path = Path(file_path).with_suffix('.analysis_report.json')
    
    with open(report_path, 'w') as f:
        import json
        json.dump(results, f, indent=2, default=str)
    
    _LOGGER.info(f"Comprehensive report saved: {report_path}")
    return report_path