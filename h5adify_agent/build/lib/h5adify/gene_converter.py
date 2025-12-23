import logging
import requests
from typing import Optional, List, Dict, Any, Set, Tuple
from collections import Counter

import anndata as ad
import mygene
import pandas as pd
import numpy as np

_LOGGER = logging.getLogger(__name__)

# Enhanced mammalian species taxids with more species
MAMMALIAN_TAXIDS = {
    9606: "Homo sapiens",           # Human
    10090: "Mus musculus",          # Mouse
    10116: "Rattus norvegicus",     # Rat
    9544: "Macaca mulatta",         # Rhesus macaque
    9598: "Pan troglodytes",        # Chimpanzee
    9557: "Callithrix jacchus",     # Common marmoset
    9615: "Canis familiaris",       # Dog
    9913: "Bos taurus",             # Cow
    9823: "Sus scrofa",             # Pig
    9696: "Oryctolagus cuniculus",  # Rabbit
    9739: "Rattus rattus",          # Black rat
    13686: "Homo sapiens (cell lines)", # Human cell lines
    72275: "Drosophila melanogaster", # Drosophila (non-mammal but common in research)
}

# Gene name patterns for different species (helps with species detection)
SPECIES_GENE_PATTERNS = {
    9606: {  # Human
        "patterns": [r"^G\d+", r"^RP[LSA]"],  # Human genes often start with RP or have G numbers
        "markers": ["ACTB", "GAPDH", "ACTG1", "TUBB", "VIM", "FN1"]
    },
    10090: {  # Mouse
        "patterns": [r"^Gm\d+", r"^Rp[sl]"],  # Mouse genes often have Gm or Rp patterns
        "markers": ["Actb", "Gapdh", "Actg1", "Tubb", "Vim", "Fn1"]
    },
    10116: {  # Rat
        "patterns": [r"^RGD", r"^Rn\."],      # Rat genes often have RGD or Rn prefixes
        "markers": ["Actb", "Gapdh", "Actg1", "Tubb", "Vim", "Fn1"]
    }
}

# Initialize mygene client with caching
mg = mygene.MyGeneInfo()

class GeneAnnotationCache:
    """Cache for gene annotation queries to avoid repeated API calls."""
    def __init__(self):
        self.cache = {}
        self.failed_queries = set()
    
    def get(self, query: str, fields: str) -> Optional[Dict[str, Any]]:
        cache_key = f"{query}_{fields}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        return None
    
    def set(self, query: str, fields: str, result: Dict[str, Any]) -> None:
        cache_key = f"{query}_{fields}"
        self.cache[cache_key] = result
    
    def mark_failed(self, query: str) -> None:
        self.failed_queries.add(query)
    
    def is_failed(self, query: str) -> bool:
        return query in self.failed_queries

# Global cache instance
_gene_cache = GeneAnnotationCache()


def _infer_species_from_gene_patterns(gene_names: pd.Index) -> Optional[int]:
    """Infer species using gene name patterns and markers."""
    gene_list = gene_names.unique().tolist()
    
    # Score each species based on pattern matches and markers
    species_scores = {}
    
    for taxid, species_info in SPECIES_GENE_PATTERNS.items():
        score = 0
        
        # Check for pattern matches
        for pattern in species_info["patterns"]:
            matches = sum(1 for gene in gene_list if re.match(pattern, gene, re.IGNORECASE))
            score += matches * 2  # Pattern matches have higher weight
        
        # Check for marker genes
        for marker in species_info["markers"]:
            if marker in gene_list:
                score += 5  # Marker genes have highest weight
        
        if score > 0:
            species_scores[taxid] = score
    
    if species_scores:
        # Return the species with the highest score
        best_species = max(species_scores.items(), key=lambda x: x[1])
        species_name = MAMMALIAN_TAXIDS.get(best_species[0], f"Taxid {best_species[0]}")
        _LOGGER.info(f"Species inferred from gene patterns: {species_name} (Score: {best_species[1]})")
        return best_species[0]
    
    return None


def _infer_species_taxid(gene_names: pd.Index, max_sample_size: int = 1000) -> Optional[int]:
    """
    Enhanced species inference using multiple approaches:
    1. Gene name patterns
    2. MyGene.info API sampling
    3. Statistical analysis of results
    """
    if gene_names.empty:
        return None

    # First try pattern-based inference (fastest)
    pattern_species = _infer_species_from_gene_patterns(gene_names)
    if pattern_species:
        return pattern_species

    # Sample genes for API query
    sample_size = min(max_sample_size, len(gene_names))
    sample_genes = gene_names.unique().to_list()[:sample_size]

    _LOGGER.info(f"Inferring species from {len(sample_genes)} gene names using MyGene.info...")
    
    # Query MyGene.info with caching
    results = []
    for gene in sample_genes:
        if _gene_cache.is_failed(gene):
            continue
            
        cached_result = _gene_cache.get(gene, 'taxid')
        if cached_result:
            results.append(cached_result)
            continue
            
        try:
            res = mg.querymany(
                [gene], 
                scopes='symbol,ensembl.gene,entrezgene', 
                fields='taxid', 
                species='all', 
                returnall=True, 
                as_dataframe=False
            )
            
            if 'out' in res and res['out']:
                result = res['out'][0]
                _gene_cache.set(gene, 'taxid', result)
                results.append(result)
            else:
                _gene_cache.mark_failed(gene)
                
        except Exception as e:
            _LOGGER.debug(f"Failed to query {gene}: {e}")
            _gene_cache.mark_failed(gene)

    if not results:
        _LOGGER.warning("MyGene.info query failed to return results for species inference.")
        return None

    # Analyze taxid distribution
    taxid_counts = Counter()
    for result in results:
        if isinstance(result, dict) and 'taxid' in result:
            taxid = result['taxid']
            if isinstance(taxid, (int, str)):
                taxid_counts[int(taxid)] += 1

    if not taxid_counts:
        _LOGGER.warning("No taxid found in the query results.")
        return None

    # Filter for known species and apply confidence threshold
    total_queries = len([r for r in results if isinstance(r, dict) and 'taxid' in r])
    mammalian_taxids = {k: v for k, v in taxid_counts.items() if k in MAMMALIAN_TAXIDS}
    
    if mammalian_taxids:
        # Find the most frequent mammalian taxid
        best_taxid, best_count = max(mammalian_taxids.items(), key=lambda x: x[1])
        confidence = best_count / total_queries
        
        # Require reasonable confidence (at least 30% and at least 3 genes)
        if confidence >= 0.3 and best_count >= 3:
            species_name = MAMMALIAN_TAXIDS.get(best_taxid, f"Taxid {best_taxid}")
            _LOGGER.info(f"Inferred species: {species_name} (Taxid: {best_taxid}, Confidence: {confidence:.2f})")
            return best_taxid
        else:
            _LOGGER.warning(f"Low confidence species inference: {confidence:.2f} (need >= 0.3)")
    
    # Fallback to most frequent taxid if no mammalian one found or confidence too low
    fallback_taxid, fallback_count = max(taxid_counts.items(), key=lambda x: x[1])
    fallback_confidence = fallback_count / total_queries
    
    if fallback_confidence >= 0.5:  # Higher threshold for fallback
        species_name = MAMMALIAN_TAXIDS.get(fallback_taxid, f"Taxid {fallback_taxid}")
        _LOGGER.warning(f"Low confidence fallback species: {species_name} (Taxid: {fallback_taxid}, Confidence: {fallback_confidence:.2f})")
        return fallback_taxid
    
    _LOGGER.warning("Could not infer species with sufficient confidence.")
    return None


def _annotate_genes_comprehensive(adata: ad.AnnData, target_taxid: int = 9606) -> pd.DataFrame:
    """Comprehensive gene annotation with multiple data sources."""
    gene_names = adata.var_names.tolist()
    
    annotation_data = []
    
    # Query MyGene.info for comprehensive annotation
    _LOGGER.info(f"Performing comprehensive gene annotation for {len(gene_names)} genes...")
    
    batch_size = 500  # Process in batches to avoid timeout
    for i in range(0, len(gene_names), batch_size):
        batch_genes = gene_names[i:i+batch_size]
        
        try:
            res = mg.querymany(
                batch_genes,
                scopes='symbol,ensembl.gene,entrezgene',
                fields='symbol,name,description,entrezgene,ensembl.gene,refseq,mgi_symbol,zfin_symbol,go,mim,summary',
                species='all',
                returnall=True,
                as_dataframe=False
            )
            
            if 'out' in res:
                for result in res['out']:
                    if result and '_query' in result:
                        gene_annotation = {
                            'query': result['_query'],
                            'symbol': result.get('symbol', result.get('_query')),
                            'name': result.get('name', ''),
                            'description': result.get('description', ''),
                            'entrezgene': result.get('entrezgene', ''),
                            'ensembl_gene': result.get('ensembl.gene', ''),
                            'refseq': result.get('refseq', ''),
                            'summary': result.get('summary', ''),
                        }
                        annotation_data.append(gene_annotation)
                        
        except Exception as e:
            _LOGGER.warning(f"Batch annotation failed for genes {i}-{i+batch_size-1}: {e}")
    
    # Create annotation DataFrame
    if annotation_data:
        annotation_df = pd.DataFrame(annotation_data)
        annotation_df = annotation_df.set_index('query')
        return annotation_df
    else:
        # Return basic annotation if API fails
        return pd.DataFrame({
            'symbol': gene_names,
            'name': gene_names,
            'description': '',
            'entrezgene': '',
            'ensembl_gene': '',
            'refseq': '',
            'summary': ''
        }, index=gene_names)


def convert_gene_names(
    adata: ad.AnnData, 
    target_taxid: int = 9606,  # Human (HUGO equivalent)
    target_field: str = "symbol",
    annotate_comprehensive: bool = True,
) -> ad.AnnData:
    """
    Enhanced gene name conversion with comprehensive annotation.
    
    This function:
    1. Infers species using multiple methods
    2. Performs comprehensive gene annotation
    3. Converts to target species orthologs
    4. Adds detailed metadata
    """
    original_gene_names = adata.var_names.to_list()
    
    # Infer species
    inferred_taxid = _infer_species_taxid(adata.var_names)
    
    if inferred_taxid is None:
        _LOGGER.warning("Species could not be inferred. Skipping gene name conversion.")
        # Still perform basic annotation
        if annotate_comprehensive:
            annotation_df = _annotate_genes_comprehensive(adata, target_taxid)
            adata.var = adata.var.join(annotation_df, how='left')
        return adata

    # Add species information
    adata.uns['organism_taxid'] = inferred_taxid
    adata.uns['organism_name'] = MAMMALIAN_TAXIDS.get(inferred_taxid, f"Taxid {inferred_taxid}")
    
    # Perform comprehensive gene annotation
    if annotate_comprehensive:
        annotation_df = _annotate_genes_comprehensive(adata, target_taxid)
        adata.var = adata.var.join(annotation_df, how='left')
    
    if inferred_taxid == target_taxid:
        _LOGGER.info(f"Inferred species is already the target species ({MAMMALIAN_TAXIDS[target_taxid]}). Skipping ortholog conversion.")
        # Save original names
        adata.var['original_gene_symbol'] = original_gene_names
        return adata

    _LOGGER.info(f"Converting gene names from {MAMMALIAN_TAXIDS.get(inferred_taxid, inferred_taxid)} to {MAMMALIAN_TAXIDS.get(target_taxid, target_taxid)}...")

    # Query for orthologs with caching
    res = mg.querymany(
        original_gene_names, 
        scopes='symbol,ensembl.gene,entrezgene', 
        fields=target_field, 
        species=inferred_taxid,
        returnall=True, 
        as_dataframe=False,
        orthologs=target_taxid
    )

    if 'out' not in res or not res['out']:
        _LOGGER.error("MyGene.info query for orthologs failed.")
        adata.var['original_gene_symbol'] = original_gene_names
        return adata

    # Process ortholog results
    mapping = {name: name for name in original_gene_names}  # Initialize with original names
    
    for result in res['out']:
        if not isinstance(result, dict) or '_query' not in result:
            continue
            
        original_name = result['_query']
        
        # Extract ortholog information
        orthologs = result.get('ortholog')
        if isinstance(orthologs, list):
            for orth in orthologs:
                orth_taxid = str(orth.get('taxid', ''))
                target_taxid_str = str(target_taxid)
                
                if orth_taxid == target_taxid_str and target_field in orth:
                    mapping[original_name] = orth[target_field]
                    break

    # Apply mapping
    new_gene_names = [mapping.get(name, name) for name in original_gene_names]
    
    # Save original names and update
    adata.var['original_gene_symbol'] = original_gene_names
    
    # Update var_names
    adata.var_names_make_unique()
    adata.var_names = new_gene_names
    adata.var_names_make_unique()
    
    # Update comprehensive annotation with new names
    if annotate_comprehensive and 'symbol' in adata.var.columns:
        adata.var['symbol'] = new_gene_names
    
    conversion_stats = {
        'total_genes': len(original_gene_names),
        'converted_genes': sum(1 for orig, new in zip(original_gene_names, new_gene_names) if orig != new),
        'source_taxid': inferred_taxid,
        'target_taxid': target_taxid,
        'source_species': MAMMALIAN_TAXIDS.get(inferred_taxid, f"Taxid {inferred_taxid}"),
        'target_species': MAMMALIAN_TAXIDS.get(target_taxid, f"Taxid {target_taxid}")
    }
    
    adata.uns['gene_conversion_stats'] = conversion_stats
    _LOGGER.info(f"Gene conversion completed: {conversion_stats['converted_genes']}/{conversion_stats['total_genes']} genes converted")
    
    return adata


def annotate_species_automatically(adata: ad.AnnData) -> ad.AnnData:
    """
    Automatically annotate species/organism information in the dataset.
    This is called when --annotate-species flag is used.
    """
    inferred_taxid = _infer_species_taxid(adata.var_names)
    
    if inferred_taxid is not None:
        adata.uns['organism_taxid'] = inferred_taxid
        adata.uns['organism_name'] = MAMMALIAN_TAXIDS.get(inferred_taxid, f"Taxid {inferred_taxid}")
        
        # Also update obs metadata if these fields exist
        if 'species' in adata.obs.columns:
            species_name = MAMMALIAN_TAXIDS.get(inferred_taxid, f"Taxid {inferred_taxid}").lower()
            adata.obs['species'] = species_name
            
        _LOGGER.info(f"Species automatically annotated: {adata.uns['organism_name']}")
    else:
        _LOGGER.warning("Could not automatically infer species")
    
    return adata


def get_gene_annotation_report(adata: ad.AnnData) -> Dict[str, Any]:
    """Generate a comprehensive gene annotation report."""
    report = {
        'total_genes': len(adata.var_names),
        'organism_info': {
            'taxid': adata.uns.get('organism_taxid'),
            'name': adata.uns.get('organism_name')
        },
        'gene_annotation_completeness': {},
        'conversion_stats': adata.uns.get('gene_conversion_stats', {})
    }
    
    # Check annotation completeness
    annotation_fields = ['symbol', 'name', 'description', 'entrezgene', 'ensembl_gene', 'refseq']
    for field in annotation_fields:
        if field in adata.var.columns:
            non_empty = adata.var[field].notna().sum()
            report['gene_annotation_completeness'][field] = {
                'annotated': int(non_empty),
                'percentage': float(non_empty / len(adata.var) * 100)
            }
    
    # Check for gene conversion
    if 'original_gene_symbol' in adata.var.columns:
        converted = (adata.var['original_gene_symbol'] != adata.var_names).sum()
        report['conversion_stats']['converted_genes'] = int(converted)
        report['conversion_stats']['conversion_rate'] = float(converted / len(adata.var) * 100)
    
    return report


# Import re for pattern matching
import re