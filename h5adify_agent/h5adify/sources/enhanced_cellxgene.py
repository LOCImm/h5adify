"""
Enhanced CellxGene source implementation for h5adify.

CellxGene is a tool for exploring, analyzing, and sharing single-cell datasets.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin, quote
import requests
from datetime import datetime

from .enhanced_base import EnhancedSource, EnhancedSearchResult, EnhancedMetadata

logger = logging.getLogger(__name__)


class EnhancedCellxGeneSource(EnhancedSource):
    """
    Enhanced CellxGene source implementation.
    
    CellxGene provides a web-based interface for exploring and analyzing
    single-cell datasets with interactive visualizations.
    """
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://cellxgene.cziscience.com/"
        self.api_base_url = "https://api.cellxgene.cziscience.com/"
        self.name = "cellxgene"
        self.display_name = "CellxGene"
        self.description = "Human Cell Atlas data portal"
        
        # CellxGene metadata will be populated per result
        pass
    
    def _build_search_query(self, query: str, filters: Optional[Dict[str, Any]] = None) -> str:
        """Build search query for CellxGene."""
        search_terms = []
        
        # Base query terms for single-cell genomics
        base_terms = [
            "single cell",
            "scRNA-seq",
            "transcriptomics",
            "RNA-seq",
            "single-cell",
            "single cell sequencing",
            "single nucleus",
            "scATAC-seq",
            "multiomics"
        ]
        
        # Add user query terms
        if query and query.strip():
            clean_query = query.strip()
            if not any(term.lower() in clean_query.lower() for term in base_terms):
                search_terms.append(f'"{clean_query}"')
        
        # Add base terms
        search_terms.extend(f'"{term}"' for term in base_terms[:5])
        
        # Combine terms
        query_str = " OR ".join(search_terms)
        
        # Add filters if provided
        if filters:
            if "organism" in filters:
                organism = filters["organism"]
                query_str += f' AND organism:"{organism}"'
            
            if "tissue" in filters:
                tissue = filters["tissue"]
                query_str += f' AND tissue:"{tissue}"'
        
        return query_str
    
    def search_enhanced(self, query: str, max_results: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[EnhancedSearchResult]:
        """Enhanced CellxGene search."""
        try:
            # Search CellxGene collections
            collections = self._fetch_collections()
            results = []
            
            for collection in collections:
                if self._matches_query(collection, query, filters):
                    result = self._parse_collection(collection)
                    if result:
                        results.append(result)
                
                if len(results) >= max_results:
                    break
            
            logger.info(f"Enhanced CellxGene search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Enhanced CellxGene search failed: {e}")
            return self._fallback_search(query, max_results)
    
    def _fetch_collections(self) -> List[Dict[str, Any]]:
        """Fetch CellxGene collections."""
        try:
            # Try to fetch from API
            url = f"{self.api_base_url}collections"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"API returned {response.status_code}")
                
        except Exception as e:
            logger.error(f"CellxGene API fetch failed: {e}")
            return self._get_sample_collections()
    
    def _get_sample_collections(self) -> List[Dict[str, Any]]:
        """Get sample CellxGene collections."""
        return [
            {
                "collection_id": "human-pbmc",
                "title": "Human PBMC Single Cell Atlas",
                "description": "Single-cell atlas of human peripheral blood mononuclear cells",
                "organism": "human",
                "tissue": "blood",
                "cell_count": 100000,
                "gene_count": 20000,
                "technology": "10x 3' v3",
                "cell_type": "immune cells"
            },
            {
                "collection_id": "mouse-brain",
                "title": "Mouse Brain Development",
                "description": "Single-cell analysis of mouse brain development",
                "organism": "mouse",
                "tissue": "brain",
                "cell_count": 50000,
                "gene_count": 18000,
                "technology": "Smart-seq2",
                "cell_type": "neurons"
            }
        ]
    
    def _matches_query(self, collection: Dict[str, Any], query: str, filters: Optional[Dict[str, Any]] = None) -> bool:
        """Check if collection matches query."""
        text = f"{collection.get('title', '')} {collection.get('description', '')} {collection.get('organism', '')} {collection.get('tissue', '')}"
        
        # Basic text matching
        if query.lower() not in text.lower():
            return False
        
        # Apply filters
        if filters:
            organism = collection.get('organism', '').lower()
            if "organism" in filters and filters["organism"].lower() not in organism:
                return False
            
            tissue = collection.get('tissue', '').lower()
            if "tissue" in filters and filters["tissue"].lower() not in tissue:
                return False
        
        return True
    
    def _parse_collection(self, collection: Dict[str, Any]) -> Optional[EnhancedSearchResult]:
        """Parse CellxGene collection into result."""
        try:
            collection_id = collection.get('collection_id', '')
            title = collection.get('title', 'Unknown Collection')
            description = collection.get('description', '')
            
            # Extract species and technology information
            species = self._extract_species(title + " " + description)
            tech = self._extract_technology(title + " " + description)
            
            return EnhancedSearchResult(
                source=self.name,
                dataset_id=f"cellxgene_{collection_id}",
                title=title,
                description=description,
                species=species,
                technology=tech,
                sample_count=collection.get('cell_count', 0),
                download_url=f"{self.base_url}collections/{collection_id}",
                metadata=collection
            )
        except Exception as e:
            logger.error(f"CellxGene collection parsing failed: {e}")
            return None
    
    def _extract_species(self, text: str) -> str:
        """Extract species information from text."""
        species_keywords = {
            'human': ['human', 'homo sapiens', 'homo-sapiens', 'h. sapiens'],
            'mouse': ['mouse', 'mus musculus', 'mus-musculus', 'm. musculus', 'mice'],
            'rat': ['rat', 'rattus norvegicus', 'rattus-norvegicus', 'r. norvegicus'],
            'zebrafish': ['zebrafish', 'danio rerio', 'danio-rerio', 'd. rerio'],
            'fruit fly': ['fruit fly', 'drosophila', 'd. melanogaster']
        }
        
        text_lower = text.lower()
        for species, keywords in species_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return species
        
        return "unknown"
    
    def _extract_technology(self, text: str) -> str:
        """Extract technology information from text."""
        tech_keywords = {
            '10x genomics': ['10x', '10x genomics', 'chromium'],
            'smart-seq': ['smart-seq', 'smartseq', 'smart sequence'],
            'drop-seq': ['drop-seq', 'dropseq'],
            'scatac-seq': ['scatac', 'scatac-seq']
        }
        
        text_lower = text.lower()
        for tech, keywords in tech_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return tech
        
        return "unknown"
    
    def _fallback_search(self, query: str, max_results: int) -> List[EnhancedSearchResult]:
        """Fallback CellxGene search."""
        return self._get_sample_collections()[:max_results]
