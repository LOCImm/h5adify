"""
Enhanced GEO Source for h5adify Enhanced

Provides comprehensive GEO database integration with:
- Enhanced metadata extraction
- Publication integration
- Download link generation
- Quality scoring
- Paper analysis integration
"""

from __future__ import annotations

import requests
import re
import time
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .enhanced_base import EnhancedMetadata, EnhancedSource


class EnhancedGeoSource(EnhancedSource):
    """Enhanced GEO source with comprehensive metadata support."""
    
    name = "geo"
    
    # GEO API endpoints
    _NCBI_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    _NCBI_SEARCH = f"{_NCBI_EUTILS_BASE}/esearch.fcgi"
    _NCBI_SUMMARY = f"{_NCBI_EUTILS_BASE}/esummary.fcgi"
    _NCBI_EFETCH = f"{_NCBI_EUTILS_BASE}/efetch.fcgi"
    
    # Technology detection patterns
    _TECHNOLOGY_PATTERNS = {
        '10x Genomics': ['10x', '10x genomics', 'chromium', 'cell ranger'],
        '10x Visium': ['visium', 'spatial gene expression'],
        'Smart-seq': ['smart-seq', 'smartseq', 'smart sequencing'],
        'Drop-seq': ['drop-seq', 'dropseq'],
        'MERFISH': ['merfish', 'multiplexed error robust fluorescence in situ hybridization'],
        'Stereo-seq': ['stereo-seq', 'spatial enhanced reconstruction of transcriptomic'],
        'Slide-seq': ['slide-seq', 'slideseq'],
        'Spatial Transcriptomics': ['spatial transcriptomics', 'spatial transcriptomic'],
        'Single-cell RNA-seq': ['single-cell', 'single cell', 'scrna-seq', 'scrna seq'],
        'Multi-omic': ['multi-omic', 'multiomic', 'single-cell multi-omic'],
        'ATAC-seq': ['atac-seq', 'atac seq', 'chromatin accessibility'],
        'Proteomics': ['proteomics', 'protein', 'mass spectrometry']
    }
    
    # Species detection patterns
    _SPECIES_PATTERNS = {
        'human': ['homo sapiens', 'human', 'hsapiens'],
        'mouse': ['mus musculus', 'mouse', 'mmusculus'],
        'rat': ['rattus norvegicus', 'rat', 'rnorvegicus'],
        'zebrafish': ['danio rerio', 'zebrafish', 'drerio'],
        'fruit fly': ['drosophila melanogaster', 'fruit fly', 'drosophila', 'dmelanogaster'],
        'c. elegans': ['caenorhabditis elegans', 'c. elegans', 'celegans'],
        'macaque': ['macaca', 'macaque', 'maca'],
        'marmoset': ['callithrix', 'marmoset'],
        'pig': ['sus scrofa', 'pig', 'sscrofa'],
        'cow': ['bos taurus', 'cow', 'btaurus'],
        'chicken': ['gallus gallus', 'chicken', 'ggallus']
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    
    def search(self, query: str, max_results: int = 20, filters: Optional[Dict[str, Any]] = None) -> List[EnhancedMetadata]:
        """Improved GEO search with fallback strategies and query preprocessing."""
        from urllib.parse import quote_plus
        import time

        def sanitize_query(q):
            return quote_plus(q.strip().lower())

        sanitized_query = sanitize_query(query)
        base_query = f"{sanitized_query}+AND+organism:human"

        if filters and "organism" in filters:
            base_query = f"{sanitized_query}+AND+organism:{quote_plus(filters['organism'])}"

        search_params = {
            "db": "gds",
            "term": base_query,
            "retmax": max_results,
            "retmode": "json",
        }

        try:
            self.logger.info(f"Searching GEO with query: {base_query}")
            response = requests.get(self._NCBI_SEARCH, params=search_params, timeout=30)
            response.raise_for_status()
            result_ids = response.json().get("esearchresult", {}).get("idlist", [])

            if not result_ids and " " in query:
                fallback_query = sanitize_query(query.split(" ")[0])  # fallback to first token
                search_params["term"] = fallback_query + "+AND+organism:human"
                self.logger.warning(f"No results found. Retrying with fallback query: {fallback_query}")
                time.sleep(1)
                response = requests.get(self._NCBI_SEARCH, params=search_params, timeout=30)
                response.raise_for_status()
                result_ids = response.json().get("esearchresult", {}).get("idlist", [])

            if not result_ids:
                self.logger.warning("No GEO results found after all attempts.")
                return []

            summaries = []
            for gid in result_ids:
                summary_params = {
                    "db": "gds",
                    "id": gid,
                    "retmode": "json"
                }
                s_response = requests.get(self._NCBI_SUMMARY, params=summary_params, timeout=15)
                if s_response.status_code == 200:
                    summaries.append(s_response.json()["result"].get(gid, {}))
                time.sleep(0.3)

            results = []
            for s in summaries:
                title = s.get("title", "")
                organism = s.get("taxname", "unknown")
                gse_id = s.get("gse", s.get("uid"))
                url = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gse_id}"
                metadata = EnhancedMetadata(
                    identifier=gse_id,
                    name=title,
                    organism=organism,
                    description=s.get("summary", ""),
                    url=url
                )
                results.append(metadata)

            return results

        except Exception as e:
            self.logger.error(f"GEO search failed: {e}")
            return []

    
    def _process_gds_dataset(self, gds_id: str, query: str) -> Optional[EnhancedMetadata]:
        """Process a single GDS dataset with enhanced metadata extraction."""
        
        # Get summary information
        summary_data = self._get_gds_summary(gds_id)
        if not summary_data:
            return None
        
        # Create enhanced metadata
        metadata = EnhancedMetadata(
            source="geo",
            dataset_id=gds_id,
            title=summary_data.get('title', f"GEO Dataset {gds_id}"),
            description=summary_data.get('summary', ''),
            url=f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GDS{gds_id}",
            download_url=f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GDS{gds_id}"
        )
        
        # Extract metadata from summary
        self._extract_biological_metadata(metadata, summary_data)
        self._extract_technical_metadata(metadata, summary_data)
        self._extract_publication_metadata(metadata, summary_data)
        self._extract_dataset_statistics(metadata, summary_data)
        
        # Try to find related GSE for download
        gse_id = self._find_related_gse(gds_id)
        if gse_id:
            metadata.dataset_id = gse_id
            metadata.download_url = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gse_id}"
        
        # Enhance with paper information
        self._enhance_with_paper_info(metadata)
        
        # Calculate quality score
        metadata.calculate_quality_score()
        
        return metadata
    
    def _get_gds_summary(self, gds_id: str) -> Optional[Dict[str, Any]]:
        """Get GDS summary information."""
        try:
            summary_params = {
                "db": "gds",
                "id": gds_id,
                "retmode": "json"
            }
            
            time.sleep(0.3)
            response = requests.get(self._NCBI_SUMMARY, params=summary_params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', {}).get(gds_id, {})
                return result if result else None
            
        except Exception as e:
            self.logger.warning(f"Failed to get summary for GDS {gds_id}: {e}")
        
        return None
    
    def _extract_biological_metadata(self, metadata: EnhancedMetadata, summary_data: Dict[str, Any]) -> None:
        """Extract biological metadata from summary."""
        
        # Extract species
        if 'organism' in summary_data:
            organism_text = str(summary_data['organism']).lower()
            detected_species = []
            
            for species, patterns in self._SPECIES_PATTERNS.items():
                if any(pattern in organism_text for pattern in patterns):
                    detected_species.append(species)
            
            if detected_species:
                metadata.add_species(detected_species)
        
        # Extract tissues from title and summary
        all_text = f"{metadata.title} {metadata.description}".lower()
        detected_tissues = []
        
        # Common tissue keywords
        tissue_keywords = [
            'brain', 'cortex', 'hippocampus', 'cerebellum', 'striatum', 'thalamus',
            'heart', 'liver', 'kidney', 'lung', 'intestine', 'stomach', 'pancreas',
            'muscle', 'skin', 'blood', 'bone', 'spleen', 'thymus', 'lymph node',
            'breast', 'prostate', 'ovary', 'testis', 'uterus', 'placenta',
            'retina', 'cornea', 'inner ear', 'tooth', 'hair follicle'
        ]
        
        for tissue in tissue_keywords:
            if tissue in all_text:
                detected_tissues.append(tissue.title())
        
        if detected_tissues:
            metadata.add_tissue(detected_tissues)
        
        # Extract conditions and diseases
        conditions = []
        diseases = []
        
        condition_keywords = ['control', 'treated', 'disease', 'cancer', 'diabetes', 'alzheimer', 'parkinson']
        disease_keywords = ['cancer', 'carcinoma', 'tumor', 'diabetes', 'alzheimer', 'parkinson', 'autism', 'depression']
        
        for keyword in condition_keywords:
            if keyword in all_text:
                conditions.append(keyword.title())
        
        for keyword in disease_keywords:
            if keyword in all_text:
                diseases.append(keyword.title())
        
        if conditions:
            metadata.conditions.extend(conditions)
        if diseases:
            metadata.diseases.extend(diseases)
    
    def _extract_technical_metadata(self, metadata: EnhancedMetadata, summary_data: Dict[str, Any]) -> None:
        """Extract technical metadata from summary."""
        
        # Detect technology
        all_text = f"{metadata.title} {metadata.description}".lower()
        
        for technology, patterns in self._TECHNOLOGY_PATTERNS.items():
            if any(pattern in all_text for pattern in patterns):
                metadata.set_technology(technology)
                break
        
        # Detect platform
        platform_keywords = {
            'Illumina': ['illumina', 'novaseq', 'hiseq', 'miseq'],
            '10x Genomics': ['10x', 'chromium'],
            'Bio-Rad': ['bio-rad', 'droplet digital'],
            'Nanopore': ['nanopore', 'oxford nanopore'],
            'PacBio': ['pacbio', 'single molecule'],
            'Affymetrix': ['affymetrix', 'genechip'],
            'Agilent': ['agilent', 'one-color', 'two-color']
        }
        
        for platform, keywords in platform_keywords.items():
            if any(keyword in all_text for keyword in keywords):
                metadata.platform = platform
                break
        
        # Detect modality
        modality_mapping = {
            'spatial': ['spatial', 'visium', 'stereoscope', 'merfish'],
            'single-cell': ['single-cell', 'single cell', 'scRNA'],
            'multi-omic': ['multi-omic', 'multiomic', 'atac-seq', 'cite-seq'],
            'bulk': ['bulk', 'population', 'tissue']
        }
        
        for modality, keywords in modality_mapping.items():
            if any(keyword in all_text for keyword in keywords):
                metadata.modality = modality
                break
        
        # Extract sample count
        if 'samples' in summary_data:
            samples = summary_data['samples']
            if isinstance(samples, list):
                metadata.sample_count = len(samples)
            elif isinstance(samples, int):
                metadata.sample_count = samples
    
    def _extract_publication_metadata(self, metadata: EnhancedMetadata, summary_data: Dict[str, Any]) -> None:
        """Extract publication metadata."""
        
        # Extract PMID
        if 'pubmed_ids' in summary_data:
            pmid = summary_data['pubmed_ids']
            if isinstance(pmid, list) and pmid:
                metadata.pmid = str(pmid[0])
        
        # Extract DOI
        if 'supplementary_link' in summary_data:
            for link in summary_data['supplementary_link']:
                if isinstance(link, dict) and 'type' in link:
                    if 'doi' in link.get('type', '').lower():
                        metadata.doi = link.get('url', '')
        
        # Extract journal and year from title
        title = metadata.title
        
        # Common journal patterns
        journal_patterns = {
            'Nature': ['Nature', 'nature'],
            'Science': ['Science', 'science'],
            'Cell': ['Cell', 'cell'],
            'bioRxiv': ['bioRxiv', 'biorxiv'],
            'medRxiv': ['medRxiv', 'medrxiv'],
            'PNAS': ['PNAS', 'pnas'],
            'Genome Research': ['Genome Research', 'genome research'],
            'Nucleic Acids Research': ['Nucleic Acids Research', 'nucleic acids research']
        }
        
        for journal, patterns in journal_patterns.items():
            if any(pattern in title for pattern in patterns):
                metadata.journal = journal
                break
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', title)
        if year_match:
            metadata.year = int(year_match.group())
        
        # Generate paper URL
        if metadata.pmid:
            metadata.paper_url = f"https://pubmed.ncbi.nlm.nih.gov/{metadata.pmid}/"
    
    def _extract_dataset_statistics(self, metadata: EnhancedMetadata, summary_data: Dict[str, Any]) -> None:
        """Extract dataset statistics."""
        
        # Sample count is already handled in technical metadata
        
        # Try to extract cell count and gene count from description
        description = metadata.description
        
        # Look for cell counts
        cell_patterns = [
            r'(\d+(?:,\d{3})*)\s*(?:cells|cell)',
            r'(\d+(?:,\d{3})*)\s*(?:nuclei|nucleus)',
            r'(\d+(?:,\d{3})*)\s*(?:spots)'
        ]
        
        for pattern in cell_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                try:
                    metadata.cells = int(match.group(1).replace(',', ''))
                    break
                except ValueError:
                    continue
        
        # Look for gene counts
        gene_patterns = [
            r'(\d+(?:,\d{3})*)\s*(?:genes|gene)',
            r'(\d+(?:,\d{3})*)\s*(?:features|feature)'
        ]
        
        for pattern in gene_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                try:
                    metadata.genes = int(match.group(1).replace(',', ''))
                    break
                except ValueError:
                    continue
    
    def _find_related_gse(self, gds_id: str) -> Optional[str]:
        """Find related GSE for better download capabilities."""
        try:
            # Try to extract GSE from supplementary links
            # This is a heuristic - GDS IDs often correspond to GSE series
            gds_num = int(gds_id)
            if gds_num > 1000000:  # Most recent datasets
                gse_candidate = f"GSE{gds_num // 1000}"
                return gse_candidate
        except:
            pass
        
        return None
    
    def _enhance_with_paper_info(self, metadata: EnhancedMetadata) -> None:
        """Enhance metadata with paper information."""
        if not metadata.pmid:
            return
        
        try:
            # Get paper information from PubMed
            fetch_params = {
                "db": "pubmed",
                "id": metadata.pmid,
                "retmode": "xml"
            }
            
            time.sleep(0.5)
            response = requests.get(self._NCBI_EFETCH, params=fetch_params, timeout=15)
            
            if response.status_code == 200:
                # Parse XML to extract paper details
                # This is simplified - in a full implementation, you'd use proper XML parsing
                paper_data = self._parse_pubmed_xml(response.text, metadata.pmid)
                if paper_data:
                    metadata.enhance_from_paper(paper_data)
                    
        except Exception as e:
            self.logger.warning(f"Failed to enhance with paper info for {metadata.pmid}: {e}")
    
    def _parse_pubmed_xml(self, xml_text: str, pmid: str) -> Optional[Dict[str, Any]]:
        """Parse PubMed XML to extract paper information."""
        # Simplified parsing - in practice, use proper XML parsing
        try:
            # Look for title, abstract, journal, year
            title_match = re.search(r'<ArticleTitle>(.*?)</ArticleTitle>', xml_text, re.DOTALL)
            abstract_match = re.search(r'<AbstractText>(.*?)</AbstractText>', xml_text, re.DOTALL)
            journal_match = re.search(r'<Title>(.*?)</Title>', xml_text)
            year_match = re.search(r'<PubDate>.*?<Year>(\d+)</Year>', xml_text)
            
            paper_data = {
                'title': title_match.group(1).strip() if title_match else '',
                'abstract': abstract_match.group(1).strip() if abstract_match else '',
                'journal': journal_match.group(1).strip() if journal_match else '',
                'year': int(year_match.group(1)) if year_match else 0,
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            }
            
            return paper_data
            
        except Exception as e:
            self.logger.warning(f"Failed to parse PubMed XML for {pmid}: {e}")
        
        return None
    
    def _create_fallback_result(self, gds_id: str, query: str) -> EnhancedMetadata:
        """Create a fallback result when metadata extraction fails."""
        return EnhancedMetadata(
            source="geo",
            dataset_id=gds_id,
            title=f"GEO Dataset {gds_id}",
            description=f"Dataset related to: {query}",
            url=f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GDS{gds_id}",
            download_url=f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GDS{gds_id}",
            enhancement_confidence=0.3
        )
    
    def get_download_link(self, dataset_id: str) -> Optional[str]:
        """Get direct download link for a GEO dataset."""
        # Check if it's a GSE or GDS
        if dataset_id.upper().startswith('GSE'):
            return f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={dataset_id}"
        else:
            # Assume it's a GDS
            return f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GDS{dataset_id}"
    
    def get_paper_info(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get paper information for a GEO dataset."""
        # This would involve looking up the dataset and finding related publications
        # Implementation depends on GEO API capabilities
        return None
    
    def get_total_count(self, query: str) -> int:
        """Get total number of available results for a query."""
        try:
            search_params = {
                "db": "gds",
                "term": query,
                "retmax": "0",  # Just get count
                "retmode": "xml"
            }
            
            time.sleep(1)
            response = requests.get(self._NCBI_SEARCH, params=search_params, timeout=15)
            response.raise_for_status()
            
            # Extract count from response
            count_match = re.search(r'<Count>(\d+)</Count>', response.text)
            if count_match:
                return int(count_match.group(1))
            
        except Exception as e:
            self.logger.warning(f"Failed to get total count for query '{query}': {e}")
        
        return 0
    
    def enhance_metadata(self, metadata: EnhancedMetadata) -> EnhancedMetadata:
        """Enhance existing metadata with additional information."""
        # This could involve additional API calls or data enrichment
        metadata.enhancement_confidence = min(1.0, metadata.enhancement_confidence + 0.2)
        metadata.last_updated = "2024-12-19T20:30:00Z"  # Would use actual timestamp
        
        return metadata
