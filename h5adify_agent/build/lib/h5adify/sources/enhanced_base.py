"""
Enhanced Base Classes for h5adify Enhanced

This module provides the foundation for enhanced search results and source protocols
with comprehensive metadata support, export functionality, and AI enhancement capabilities.
"""

from __future__ import annotations

import json
import csv
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Protocol, runtime_checkable, Union, Any
from pathlib import Path
from datetime import datetime
from enum import Enum


class ExportFormat(Enum):
    """Export format options for search results."""
    JSON = "json"
    CSV = "csv"


@dataclass
class EnhancedMetadata:
    """Enhanced metadata structure for comprehensive dataset information."""
    
    # Basic Information
    source: str
    dataset_id: str
    title: str
    description: str = ""
    url: str = ""
    
    # Biological Information
    species: List[str] = None
    organism: List[str] = None
    tissues: List[str] = None
    cell_types: List[str] = None
    conditions: List[str] = None
    diseases: List[str] = None
    
    # Technical Information
    technology: str = ""
    platform: str = ""
    library_prep: str = ""
    modality: str = ""  # scRNA, spatial, multi-omic, etc.
    
    # Publication Information
    journal: str = ""
    year: int = 0
    authors: List[str] = None
    doi: str = ""
    pmid: str = ""
    biorxiv_id: str = ""
    arxiv_id: str = ""
    paper_url: str = ""
    abstract: str = ""
    
    # Dataset Statistics
    sample_count: int = 0
    cells: int = 0
    genes: int = 0
    spots: int = 0  # for spatial data
    
    # Quality and Enhancement
    quality_score: float = 0.0
    enhancement_confidence: float = 0.0
    download_url: str = ""
    supplementary_data: List[str] = None
    analysis_notes: str = ""
    
    # Timestamps
    created_date: str = ""
    last_updated: str = ""
    
    def __post_init__(self):
        """Initialize empty lists and set default values."""
        if self.species is None:
            self.species = []
        if self.organism is None:
            self.organism = []
        if self.tissues is None:
            self.tissues = []
        if self.cell_types is None:
            self.cell_types = []
        if self.conditions is None:
            self.conditions = []
        if self.diseases is None:
            self.diseases = []
        if self.authors is None:
            self.authors = []
        if self.supplementary_data is None:
            self.supplementary_data = []
        
        # Set current timestamp if not provided
        if not self.created_date:
            self.created_date = datetime.now().isoformat()
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_csv_dict(self) -> Dict[str, str]:
        """Convert to CSV-compatible dictionary."""
        data = self.to_dict()
        # Convert lists to strings for CSV
        for key, value in data.items():
            if isinstance(value, list):
                data[key] = "; ".join(str(v) for v in value)
            elif value is None:
                data[key] = ""
        return data
    
    def enhance_from_paper(self, paper_data: Dict[str, Any]) -> None:
        """Enhance metadata from paper/publication data."""
        if 'journal' in paper_data:
            self.journal = paper_data['journal']
        if 'year' in paper_data:
            self.year = paper_data['year']
        if 'authors' in paper_data:
            self.authors = paper_data['authors']
        if 'doi' in paper_data:
            self.doi = paper_data['doi']
        if 'abstract' in paper_data:
            self.abstract = paper_data['abstract']
        if 'url' in paper_data:
            self.paper_url = paper_data['url']
        
        # Update enhancement confidence
        self.enhancement_confidence = min(1.0, self.enhancement_confidence + 0.3)
        self.last_updated = datetime.now().isoformat()
    
    def add_species(self, species: Union[str, List[str]]) -> None:
        """Add species information."""
        if isinstance(species, str):
            species = [species]
        self.species.extend(species)
        self.organism.extend(species)  # Keep both for compatibility
        # Remove duplicates
        self.species = list(set(self.species))
        self.organism = list(set(self.organism))
    
    def add_tissue(self, tissue: Union[str, List[str]]) -> None:
        """Add tissue information."""
        if isinstance(tissue, str):
            tissue = [tissue]
        self.tissues.extend(tissue)
        # Remove duplicates
        self.tissues = list(set(self.tissues))
    
    def set_technology(self, tech: str) -> None:
        """Set technology platform."""
        self.technology = tech
        # Detect platform from technology
        if '10x' in tech.lower():
            self.platform = '10x Genomics'
        elif 'visium' in tech.lower():
            self.platform = '10x Visium'
        elif 'smart-seq' in tech.lower():
            self.platform = 'Smart-seq'
        elif 'drop-seq' in tech.lower():
            self.platform = 'Drop-seq'
        
        # Set modality
        if 'spatial' in tech.lower():
            self.modality = 'spatial'
        elif 'single-cell' in tech.lower() or 'single cell' in tech.lower():
            self.modality = 'single-cell'
    
    def calculate_quality_score(self) -> float:
        """Calculate quality score based on available metadata."""
        score = 0.0
        
        # Basic information (30%)
        if self.title: score += 0.1
        if self.description: score += 0.1
        if self.dataset_id: score += 0.1
        
        # Biological information (25%)
        if self.species: score += 0.05
        if self.tissues: score += 0.05
        if self.technology: score += 0.05
        if self.modality: score += 0.05
        if self.cell_types: score += 0.05
        
        # Technical information (20%)
        if self.sample_count > 0: score += 0.05
        if self.cells > 0: score += 0.05
        if self.genes > 0: score += 0.05
        if self.platform: score += 0.05
        
        # Publication information (15%)
        if self.journal: score += 0.03
        if self.year > 0: score += 0.03
        if self.authors: score += 0.03
        if self.abstract: score += 0.03
        if self.doi: score += 0.03
        
        # Enhanced information (10%)
        if self.download_url: score += 0.02
        if self.paper_url: score += 0.02
        if self.supplementary_data: score += 0.02
        if self.enhancement_confidence > 0: score += 0.02
        if self.quality_score > 0: score += 0.02
        
        self.quality_score = min(1.0, score)
        return self.quality_score


@dataclass
class EnhancedSearchResult:
    """Enhanced search result with comprehensive metadata and export capabilities."""
    
    # Search metadata
    total_available: int = 0
    returned_results: int = 0
    search_query: str = ""
    search_time: str = ""
    sources_searched: List[str] = None
    
    # Results
    results: List[EnhancedMetadata] = None
    
    # Export information
    export_format: str = ""
    export_time: str = ""
    export_file: str = ""
    total_metadata_enhanced: int = 0
    
    def __post_init__(self):
        """Initialize empty lists and set default values."""
        if self.sources_searched is None:
            self.sources_searched = []
        if self.results is None:
            self.results = []
        
        # Set current timestamp if not provided
        if not self.search_time:
            self.search_time = datetime.now().isoformat()
        if not self.export_time:
            self.export_time = datetime.now().isoformat()
    
    def add_result(self, result: EnhancedMetadata) -> None:
        """Add a search result."""
        self.results.append(result)
        self.returned_results = len(self.results)
        
        # Calculate quality score for the result
        result.calculate_quality_score()
        
        # Count enhanced results
        if result.enhancement_confidence > 0:
            self.total_metadata_enhanced += 1
    
    def export_to_json(self, filepath: Union[str, Path]) -> None:
        """Export search results to JSON file."""
        data = {
            'total_available': self.total_available,
            'returned_results': self.returned_results,
            'search_query': self.search_query,
            'search_time': self.search_time,
            'sources_searched': self.sources_searched,
            'results': [result.to_dict() for result in self.results],
            'export_info': {
                'format': 'json',
                'export_time': self.export_time,
                'export_file': str(filepath),
                'total_metadata_enhanced': self.total_metadata_enhanced
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def export_to_csv(self, filepath: Union[str, Path]) -> None:
        """Export search results to CSV file."""
        if not self.results:
            return
        
        # Get all unique keys from all results
        all_keys = set()
        for result in self.results:
            all_keys.update(result.to_dict().keys())
        
        # Sort keys for consistent output
        fieldnames = sorted(all_keys)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.results:
                writer.writerow(result.to_csv_dict())
    
    def get_summary(self) -> Dict[str, Any]:
        """Get search summary statistics."""
        if not self.results:
            return {}
        
        # Calculate statistics
        total_samples = sum(r.sample_count for r in self.results if r.sample_count)
        total_cells = sum(r.cells for r in self.results if r.cells)
        avg_quality = sum(r.quality_score for r in self.results) / len(self.results)
        
        # Count by source
        source_counts = {}
        for result in self.results:
            source_counts[result.source] = source_counts.get(result.source, 0) + 1
        
        # Count by technology
        tech_counts = {}
        for result in self.results:
            if result.technology:
                tech_counts[result.technology] = tech_counts.get(result.technology, 0) + 1
        
        # Count by species
        species_counts = {}
        for result in self.results:
            for species in result.species:
                species_counts[species] = species_counts.get(species, 0) + 1
        
        return {
            'total_results': len(self.results),
            'total_samples': total_samples,
            'total_cells': total_cells,
            'average_quality_score': avg_quality,
            'enhanced_results': self.total_metadata_enhanced,
            'source_distribution': source_counts,
            'technology_distribution': tech_counts,
            'species_distribution': species_counts,
            'search_duration': self.search_time
        }
    
    def filter_results(self, filters: Dict[str, Any]) -> List[EnhancedMetadata]:
        """Filter results based on criteria."""
        filtered = self.results.copy()
        
        for key, value in filters.items():
            if key == 'species':
                filtered = [r for r in filtered if value in r.species]
            elif key == 'technology':
                filtered = [r for r in filtered if r.technology and value.lower() in r.technology.lower()]
            elif key == 'tissue':
                filtered = [r for r in filtered if value in r.tissues]
            elif key == 'source':
                filtered = [r for r in filtered if r.source == value]
            elif key == 'min_quality':
                filtered = [r for r in filtered if r.quality_score >= value]
            elif key == 'year':
                filtered = [r for r in filtered if r.year == value]
        
        return filtered


@runtime_checkable
class EnhancedSource(Protocol):
    """Enhanced protocol for data sources with comprehensive metadata support."""
    
    name: str
    
    def search(
        self, 
        query: str, 
        max_results: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[EnhancedMetadata]:
        ...
    
    def get_download_link(self, dataset_id: str) -> Optional[str]:
        """Get direct download link for a dataset."""
        ...
    
    def get_paper_info(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get paper/publication information for a dataset."""
        ...
    
    def get_total_count(self, query: str) -> int:
        """Get total number of available results for a query."""
        ...
    
    def enhance_metadata(self, metadata: EnhancedMetadata) -> EnhancedMetadata:
        """Enhance metadata using paper analysis or other sources."""
        ...


class SearchExportManager:
    """Manager for exporting search results in various formats."""
    
    @staticmethod
    def export_result(result: EnhancedSearchResult, filepath: Union[str, Path], format_type: str = 'json') -> None:
        """Export a search result to specified format."""
        filepath = Path(filepath)
        
        if format_type.lower() == 'json':
            result.export_to_json(filepath.with_suffix('.json'))
        elif format_type.lower() == 'csv':
            result.export_to_csv(filepath.with_suffix('.csv'))
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    @staticmethod
    def export_summary(summary: Dict[str, Any], filepath: Union[str, Path]) -> None:
        """Export search summary to file."""
        filepath = Path(filepath)
        
        with open(filepath.with_suffix('.json'), 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def create_download_links(results: List[EnhancedMetadata]) -> List[EnhancedMetadata]:
        """Create download links for results that don't have them."""
        enhanced_results = []
        
        for result in results:
            if not result.download_url:
                # Try to generate download link based on source
                if result.source == 'geo':
                    result.download_url = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={result.dataset_id}"
                elif result.source == 'cellxgene':
                    result.download_url = f"https://cellxgene.cziscience.com/dataset/{result.dataset_id}"
                elif result.source == 'ucsc':
                    result.download_url = f"https://cells.ucsc.edu/?ds={result.dataset_id}"
                elif result.source == 'ema':
                    result.download_url = f"https://www.ebi.ac.uk/biostudies/arrayexpress/datasets/{result.dataset_id}"
                elif result.source == 'zenodo':
                    result.download_url = f"https://doi.org/{result.doi}" if result.doi else ""
            
            enhanced_results.append(result)
        
        return enhanced_results
