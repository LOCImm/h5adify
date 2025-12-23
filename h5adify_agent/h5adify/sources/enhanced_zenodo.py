"""
Enhanced Zenodo source implementation for h5adify.

Zenodo is a general-purpose open-access repository developed under
the European OpenAIRE program and operated by CERN.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin, quote
import requests
from datetime import datetime
import os

from .enhanced_base import EnhancedSource, EnhancedSearchResult, EnhancedMetadata, ExportFormat

logger = logging.getLogger(__name__)


class EnhancedZenodoSource(EnhancedSource):
    """
    Enhanced Zenodo source implementation.
    
    Zenodo provides open access to research outputs from all fields of science.
    This implementation searches for single-cell genomics datasets and related research.
    """
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://zenodo.org/api/"
        self.search_endpoint = "records"
        self.name = "zenodo"
        self.display_name = "Zenodo"
        self.description = "Open access repository for research data"
        
        # Zenodo-specific metadata structure
        # The actual metadata will be populated per result
    
    def _build_search_query(self, query: str, filters: Optional[Dict[str, Any]] = None) -> str:
        """Build search query for Zenodo API."""
        # Start with user query, clean it up
        if query and query.strip():
            clean_query = query.strip()
            # Remove quotes and special characters that might break the API
            clean_query = clean_query.replace('"', '').replace("'", '')
            clean_query = re.sub(r'[^\w\s\-]', ' ', clean_query)
            # URL encode the query
            from urllib.parse import quote_plus
            return quote_plus(clean_query)
        else:
            # Default query for single-cell data
            from urllib.parse import quote_plus
            return quote_plus("single cell transcriptomics")
    def search_enhanced(self, query: str, max_results: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[EnhancedSearchResult]:
        """
        Enhanced search for Zenodo with better result processing and filtering.
        """
        results = []
        
        try:
            # Try multiple search strategies
            search_queries = [
                f'single cell {query}',
                f'scRNA-seq {query}',
                f'transcriptomics {query}',
                f'10x genomics {query}',
                query  # Original query
            ]
            
            for search_query in search_queries:
                if len(results) >= max_results:
                    break
                    
                query_results = self._enhanced_search_query(search_query, max_results - len(results), filters)
                results.extend(query_results)
            
            # Remove duplicates and sort by relevance
            unique_results = []
            seen_ids = set()
            for result in results:
                if result.dataset_id not in seen_ids:
                    unique_results.append(result)
                    seen_ids.add(result.dataset_id)
            
            # Sort by relevance score (higher is better)
            unique_results.sort(key=lambda x: getattr(x, 'relevance_score', 0), reverse=True)
            
            logger.info(f"Enhanced Zenodo search returned {len(unique_results[:max_results])} unique results")
            return unique_results[:max_results]
            
        except Exception as e:
            logger.error(f"Enhanced Zenodo search failed: {e}")
            return self._fallback_search(query, max_results)
    
    def _enhanced_search_query(self, query: str, max_results: int, filters: Optional[Dict[str, Any]] = None) -> List[EnhancedSearchResult]:
        """Perform enhanced search query with better error handling."""
        try:
            # Clean and encode the query
            clean_query = query.replace('"', '').replace("'", '')
            clean_query = re.sub(r'[^\w\s\-]', ' ', clean_query)
            from urllib.parse import quote_plus
            encoded_query = quote_plus(clean_query)
            
            params = {
                'q': encoded_query,
                'size': min(max_results, 50),
                'page': 1,
                'all_versions': False
            }
            
            url = "https://zenodo.org/api/records"
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 400:
                # Fallback to simple query
                logger.warning(f"Zenodo enhanced query 400 error, using fallback")
                params['q'] = "single cell"
                response = requests.get(url, params=params, timeout=30)
                
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if 'hits' in data and 'hits' in data['hits']:
                for hit in data['hits']['hits']:
                    result = self._parse_hit_enhanced(hit, query)
                    if result:
                        results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Enhanced query failed: {e}")
            return []
    
    def _parse_hit_enhanced(self, hit: Dict[str, Any], query: str) -> Optional[EnhancedSearchResult]:
        """Enhanced hit parsing with better relevance scoring."""
        try:
            result = self._parse_hit(hit)
            if result:
                # Calculate relevance score
                title = hit.get('metadata', {}).get('title', '').lower()
                description = hit.get('metadata', {}).get('description', '').lower()
                query_terms = query.lower().split()
                
                relevance_score = 0
                for term in query_terms:
                    if term in title:
                        relevance_score += 10
                    if term in description:
                        relevance_score += 5
                
                # Boost score for single-cell keywords
                sc_keywords = ['single cell', 'scrna', 'transcriptomics', '10x', 'scatac']
                for keyword in sc_keywords:
                    if keyword in title or keyword in description:
                        relevance_score += 3
                
                setattr(result, 'relevance_score', relevance_score)
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Enhanced hit parsing failed: {e}")
            return None

    def _fallback_zenodo_search(self, query: str, max_results: int) -> List[EnhancedSearchResult]:
        """Fallback search using direct Zenodo API."""
        try:
            # Try direct search with simplified parameters
            params = {
                'q': f'single cell {query}',
                'size': max_results,
                'page': 1,
                'all_versions': False
            }
            
            url = "https://zenodo.org/api/records"
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if 'hits' in data and 'hits' in data['hits']:
                for hit in data['hits']['hits'][:max_results]:
                    result = self._parse_hit(hit)
                    if result:
                        results.append(result)
            
            logger.info(f"Zenodo fallback search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Fallback Zenodo search failed: {e}")
            return []

    
    def search(self, query: str, max_results: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[EnhancedSearchResult]:
        """
        Search Zenodo for single-cell genomics datasets.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            filters: Additional search filters
            
        Returns:
            List of EnhancedSearchResult objects
        """
        results = []
        
        try:
            # Build search parameters with simple, effective query
            search_query = self._build_search_query(query, filters)
            
            params = {
                'q': search_query,
                'size': min(max_results, 50),  # Zenodo max is 50
                'page': 1,
                'all_versions': False
            }
            
            # Make request to Zenodo API
            url = urljoin(self.base_url, self.search_endpoint)
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 400:
                # Try with a simpler query if the original fails
                logger.warning(f"Zenodo API 400 error with query '{search_query}', trying fallback")
                fallback_query = "single cell transcriptomics"
                params['q'] = fallback_query
                response = requests.get(url, params=params, timeout=30)
                
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different Zenodo API response formats
            if 'hits' in data and 'hits' in data['hits']:
                # Standard Zenodo API format
                for hit in data['hits']['hits']:
                    result = self._parse_hit(hit)
                    if result:
                        results.append(result)
            
            logger.info(f"Zenodo search returned {len(results)} results for query: {query}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching Zenodo: {e}")
            # Fallback to direct Zenodo search
            return self._fallback_zenodo_search(query, max_results)
        except Exception as e:
            logger.error(f"Unexpected error searching Zenodo: {e}")
            # Fallback to direct Zenodo search
            return self._fallback_zenodo_search(query, max_results)
        
        return results
    
    def _parse_hit(self, hit: Dict[str, Any]) -> Optional[EnhancedSearchResult]:
        """Parse a Zenodo API hit into an EnhancedSearchResult."""
        try:
            # Extract basic information
            record_id = hit.get('id', '')
            title = hit.get('metadata', {}).get('title', 'No title')
            description = hit.get('metadata', {}.get('description', ''))
            
            # Extract creators
            creators = []
            if 'creators' in hit.get('metadata', {}):
                creators = [creator.get('name', '') for creator in hit['metadata']['creators']]
                creators = [c for c in creators if c]  # Remove empty names
            
            # Extract publication date
            publication_date = hit.get('metadata', {}).get('publication_date', '')
            
            # Extract keywords
            keywords = []
            if 'keywords' in hit.get('metadata', {}):
                keywords = hit['metadata']['keywords']
            
            # Extract DOI
            doi = ''
            if 'doi' in hit.get('metadata', {}):
                doi = hit['metadata']['doi']
            elif 'doi' in hit.get('prereserve_doi', {}):
                doi = hit['prereserve_doi']['doi']
            
            # Extract upload type
            upload_type = hit.get('metadata', {}).get('upload_type', '')
            
            # Extract communities
            communities = []
            if 'communities' in hit.get('metadata', {}):
                communities = [comm.get('identifier', '') for comm in hit['metadata']['communities']]
            
            # Extract file information
            file_count = 0
            file_size = 0
            file_types = []
            download_url = ''
            
            if 'files' in hit:
                file_count = len(hit['files'])
                for file_info in hit['files']:
                    file_size += file_info.get('size', 0)
                    file_name = file_info.get('filename', '')
                    file_type = file_name.split('.')[-1].lower() if '.' in file_name else ''
                    if file_type:
                        file_types.append(file_type)
                    
                    # Get download URL for first file
                    if not download_url and 'links' in file_info:
                        download_url = file_info['links'].get('download', '')
            
            # Extract license
            license_info = hit.get('metadata', {}).get('license', {})
            license_name = license_info if isinstance(license_info, str) else license_info.get('title', '')
            
            # Extract access right
            access_right = hit.get('metadata', {}).get('access_right', '')
            
            # Build rich metadata
            rich_metadata = {
                'creators': creators,
                'description': description,
                'publication_date': publication_date,
                'keywords': keywords,
                'doi': doi,
                'upload_type': upload_type,
                'communities': communities,
                'file_count': file_count,
                'file_size': file_size,
                'file_types': file_types,
                'license': license_name,
                'access_right': access_right,
                'record_id': record_id,
                'created': hit.get('created', ''),
                'modified': hit.get('modified', ''),
                'conceptdoi': hit.get('conceptdoi', ''),
                'conceptrecid': hit.get('conceptrecid', '')
            }
            
            # Extract species and technology information from title, description, and keywords
            species = self._extract_species(title + " " + description + " " + " ".join(keywords))
            technology = self._extract_technology(title + " " + description + " " + " ".join(keywords))
            
            # Estimate sample count from file size and type
            sample_count = self._estimate_sample_count(file_size, file_types)
            
            # Add to rich metadata
            rich_metadata.update({
                'species': species,
                'technology': technology,
                'sample_count': sample_count
            })
            
            # Build dataset ID
            dataset_id = f"zenodo_{record_id}"
            if doi:
                dataset_id += f"_{doi.replace('/', '_').replace('.', '_')}"
            
            # Get download URL
            if not download_url and 'links' in hit:
                download_url = hit['links'].get('html', '')
            
            # Create EnhancedSearchResult
            result = EnhancedSearchResult(
                source=self.name,
                dataset_id=dataset_id,
                title=title,
                description=description,
                species=species,
                technology=technology,
                sample_count=sample_count,
                download_url=download_url,
                metadata=rich_metadata,
                extra={
                    'record_id': record_id,
                    'creators': creators,
                    'doi': doi,
                    'publication_date': publication_date,
                    'keywords': keywords,
                    'upload_type': upload_type,
                    'communities': communities,
                    'file_count': file_count,
                    'file_size': file_size,
                    'file_types': file_types,
                    'license': license_name,
                    'access_right': access_right,
                    'created': hit.get('created', ''),
                    'modified': hit.get('modified', ''),
                    'conceptdoi': hit.get('conceptdoi', ''),
                    'conceptrecid': hit.get('conceptrecid', ''),
                    'api_url': hit.get('links', {}).get('html', ''),
                    'json_url': hit.get('links', {}).get('json', '')
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing Zenodo hit: {e}")
            return None
    
    def _extract_species(self, text: str) -> str:
        """Extract species information from text."""
        species_keywords = {
            'human': ['human', 'homo sapiens', 'homo-sapiens', 'h. sapiens'],
            'mouse': ['mouse', 'mus musculus', 'mus-musculus', 'm. musculus', 'mice'],
            'rat': ['rat', 'rattus norvegicus', 'rattus-norvegicus', 'r. norvegicus'],
            'zebrafish': ['zebrafish', 'danio rerio', 'danio-rerio', 'd. rerio'],
            'fruit fly': ['fruit fly', 'drosophila', 'd. melanogaster'],
            'c. elegans': ['c. elegans', 'caenorhabditis elegans', 'caenorhabditis-elegans'],
            'pig': ['pig', 'sus scrofa', 'sus-scrofa', 's. scrofa'],
            'cow': ['cow', 'bos taurus', 'bos-taurus', 'b. taurus'],
            'chicken': ['chicken', 'gallus gallus', 'gallus-gallus', 'g. gallus'],
            'arabidopsis': ['arabidopsis', 'arabidopsis thaliana', 'arabidopsis-thaliana']
        }
        
        text_lower = text.lower()
        for species, keywords in species_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return species
        
        return "unknown"
    
    def _extract_technology(self, text: str) -> str:
        """Extract technology information from text."""
        tech_keywords = {
            '10x genomics': ['10x', '10x genomics', 'chromium', 'cell ranger'],
            'smart-seq': ['smart-seq', 'smartseq', 'smart sequencing'],
            'drop-seq': ['drop-seq', 'dropseq', 'drop sequencing'],
            'spatial transcriptomics': ['spatial transcriptomics', 'spatial sequencing', 'visium', '10x visium'],
            'scATAC-seq': ['scatac', 'sc atac', 'single cell atac', 'chromatin accessibility'],
            'multiomics': ['multiomics', 'multi-omics', 'multi omics', 'cite-seq', 'cITE-seq'],
            'nanopore': ['nanopore', 'long read', 'third generation sequencing'],
            'single nucleus': ['single nucleus', 'snrna', 'sn rna', 'nucleus rna'],
            'inDrop': ['indrop', 'in-drop', 'in drop sequencing'],
            'sci-seq': ['sci-seq', 'sci sequencing', 'single cell combinatorial indexing']
        }
        
        text_lower = text.lower()
        for technology, keywords in tech_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return technology
        
        # Check for general RNA-seq
        if any(term in text_lower for term in ['rna-seq', 'rna seq', 'transcriptomics', 'rna sequencing']):
            return "RNA-seq"
        
        return "unknown"
    
    def _estimate_sample_count(self, file_size: int, file_types: List[str]) -> int:
        """Estimate sample count from file size and type."""
        if file_size == 0:
            return 0
        
        # Very rough estimation based on file size
        # Single-cell datasets are typically hundreds of MB to few GB
        # Assume average sample size of 50MB for scRNA-seq data
        
        estimated_samples = max(1, file_size // (50 * 1024 * 1024))  # 50MB per sample
        
        # Cap at reasonable maximum
        return min(estimated_samples, 10000)
    
    def get_download_url(self, dataset_id: str) -> Optional[str]:
        """
        Get download URL for a specific dataset.
        
        Args:
            dataset_id: Dataset identifier
            
        Returns:
            Download URL or None if not available
        """
        try:
            # Extract record ID from dataset_id
            if dataset_id.startswith("zenodo_"):
                record_id = dataset_id.replace("zenodo_", "").split("_")[0]
                
                # Get record details
                url = urljoin(self.base_url, f"records/{record_id}")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                # Get file download URLs
                if 'files' in data and data['files']:
                    # Return the first file's download URL
                    first_file = data['files'][0]
                    if 'links' in first_file:
                        return first_file['links'].get('download', '')
                
                # Fallback to the record's HTML page
                if 'links' in data:
                    return data['links'].get('html', '')
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting download URL for {dataset_id}: {e}")
            return None
    
    def export_results(self, results: List[EnhancedSearchResult], format: ExportFormat, 
                      output_file: str) -> bool:
        """
        Export search results to specified format.
        
        Args:
            results: List of search results
            format: Export format (JSON or CSV)
            output_file: Output file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if format == ExportFormat.JSON:
                # Export to JSON
                export_data = []
                for result in results:
                    export_item = {
                        'source': result.source,
                        'dataset_id': result.dataset_id,
                        'title': result.title,
                        'description': result.description,
                        'species': result.species,
                        'technology': result.technology,
                        'sample_count': result.sample_count,
                        'download_url': result.download_url,
                        'metadata': result.metadata,
                        'extra': result.extra
                    }
                    export_data.append(export_item)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            elif format == ExportFormat.CSV:
                # Export to CSV
                import csv
                
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    if not results:
                        return False
                    
                    # Get all unique keys from results
                    fieldnames = set()
                    for result in results:
                        fieldnames.update([
                            'source', 'dataset_id', 'title', 'description', 
                            'species', 'technology', 'sample_count', 'download_url'
                        ])
                        # Add common metadata keys
                        if result.metadata:
                            fieldnames.update(result.metadata.keys())
                        if result.extra:
                            fieldnames.update(result.extra.keys())
                    
                    fieldnames = sorted(list(fieldnames))
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for result in results:
                        row = {
                            'source': result.source,
                            'dataset_id': result.dataset_id,
                            'title': result.title,
                            'description': result.description,
                            'species': result.species,
                            'technology': result.technology,
                            'sample_count': result.sample_count,
                            'download_url': result.download_url
                        }
                        
                        # Add metadata
                        if result.metadata:
                            for key, value in result.metadata.items():
                                if key in fieldnames:
                                    if isinstance(value, (list, dict)):
                                        row[key] = json.dumps(value)
                                    else:
                                        row[key] = str(value)
                        
                        # Add extra data
                        if result.extra:
                            for key, value in result.extra.items():
                                if key in fieldnames:
                                    if isinstance(value, (list, dict)):
                                        row[key] = json.dumps(value)
                                    else:
                                        row[key] = str(value)
                        
                        writer.writerow(row)
            
            logger.info(f"Successfully exported {len(results)} results to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting results: {e}")
            return False
    
    def get_metadata_schema(self) -> EnhancedMetadata:
        """Get the metadata schema for this source."""
        return self.metadata_schema
    
    def validate_result(self, result: EnhancedSearchResult) -> bool:
        """Validate a search result."""
        if not result.title or not result.dataset_id:
            return False
        
        # Check if result has minimum required information
        if not result.source or not result.metadata:
            return False
        
        return True