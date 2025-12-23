from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Union


@dataclass
class ObsPolicy:
    """Policy for standardizing .obs (observation) metadata fields."""
    
    # Standard field names and their acceptable values
    species_values: List[str] = None
    technology_values: List[str] = None
    sex_values: List[str] = None
    condition_values: List[str] = None
    disease_values: List[str] = None
    modality_values: List[str] = None
    
    # Default values for missing fields
    default_species: str = "unknown"
    default_technology: str = "unknown"
    default_sex: str = "unknown"
    default_condition: str = "unknown"
    default_disease: str = "unknown"
    default_modality: str = "sc/snRNA"
    
    # Field normalization settings
    normalize_case: bool = True
    remove_whitespace: bool = True
    map_synonyms: bool = True
    
    def __post_init__(self):
        """Initialize default values for list fields."""
        if self.species_values is None:
            self.species_values = [
                "human", "mouse", "rat", "macaque", "chimpanzee", "marmoset",
                "dog", "cow", "pig", "rabbit", "unknown"
            ]
        
        if self.technology_values is None:
            self.technology_values = [
                "10x", "10x visium", "smart-seq", "smart-seq2", "drop-seq", 
                "merfish", "stereo-seq", "slide-seq", "seqFISH", "seqFISH+",
                "unknown"
            ]
        
        if self.sex_values is None:
            self.sex_values = ["male", "female", "unknown"]
        
        if self.condition_values is None:
            self.condition_values = [
                "control", "treated", "diseased", "unknown", "naive", 
                "stimulated", "activated"
            ]
        
        if self.disease_values is None:
            self.disease_values = [
                "healthy", "alzheimer", "parkinson", "cancer", "diabetes",
                "autoimmune", "infectious", "unknown"
            ]
        
        if self.modality_values is None:
            self.modality_values = [
                "sc/snRNA", "spatial", "multiomic", "atac", "proteomics", "unknown"
            ]
    
    def normalize_value(self, field: str, value: str) -> str:
        """Normalize a metadata field value according to the policy."""
        if not value or value == "unknown":
            return "unknown"
        
        # Get the appropriate list for this field
        if field == "species":
            allowed_values = self.species_values
            default_value = self.default_species
        elif field == "technology":
            allowed_values = self.technology_values
            default_value = self.default_technology
        elif field == "sex":
            allowed_values = self.sex_values
            default_value = self.default_sex
        elif field == "condition":
            allowed_values = self.condition_values
            default_value = self.default_condition
        elif field == "disease":
            allowed_values = self.disease_values
            default_value = self.default_disease
        elif field == "modality":
            allowed_values = self.modality_values
            default_value = self.default_modality
        else:
            return value
        
        # Normalize the value
        normalized = value.lower().strip()
        
        if self.remove_whitespace:
            normalized = " ".join(normalized.split())
        
        # Check for exact match
        for allowed in allowed_values:
            if normalized == allowed:
                return allowed
        
        # Check for synonym mapping
        if self.map_synonyms:
            normalized = self._map_synonyms(field, normalized)
        
        # Check for partial matches (fuzzy matching)
        for allowed in allowed_values:
            if allowed in normalized or normalized in allowed:
                return allowed
        
        # Return normalized value if no match found
        return normalized if normalized else default_value
    
    def _map_synonyms(self, field: str, value: str) -> str:
        """Map common synonyms to standard values."""
        synonyms = {
            "species": {
                "homo sapiens": "human",
                "mus musculus": "mouse", 
                "rattus norvegicus": "rat",
                "macaca mulatta": "macaque",
                "pan troglodytes": "chimpanzee",
                "callithrix jacchus": "marmoset",
                "canis familiaris": "dog",
                "bos taurus": "cow",
                "sus scrofa": "pig",
                "oryctolagus cuniculus": "rabbit"
            },
            "technology": {
                "10x genomics": "10x",
                "10x chromium": "10x",
                "visium": "10x visium",
                "10x visium": "10x visium",
                "smartseq": "smart-seq",
                "smart-seq2": "smart-seq2",
                "smartseq2": "smart-seq2",
                "dropseq": "drop-seq",
                "merfish": "merfish",
                "stereoseq": "stereo-seq",
                "stereo seq": "stereo-seq",
                "slideseq": "slide-seq",
                "slide seq": "slide-seq",
                "seqfish": "seqFISH",
                "seqfish+": "seqFISH+"
            },
            "sex": {
                "m": "male",
                "f": "female",
                "male": "male",
                "female": "female"
            },
            "condition": {
                "ctrl": "control",
                "control": "control",
                "treated": "treated",
                "treatment": "treated",
                "disease": "diseased",
                "diseased": "diseased",
                "naive": "naive",
                "unstimulated": "naive",
                "stimulated": "stimulated",
                "activated": "activated"
            },
            "disease": {
                "healthy": "healthy",
                "control": "healthy",
                "normal": "healthy",
                "alzheimer": "alzheimer",
                "alzheimers": "alzheimer",
                "ad": "alzheimer",
                "parkinson": "parkinson",
                "pd": "parkinson",
                "cancer": "cancer",
                "tumor": "cancer",
                "carcinoma": "cancer",
                "diabetes": "diabetes",
                "autoimmune": "autoimmune",
                "infection": "infectious",
                "infected": "infectious"
            },
            "modality": {
                "single cell": "sc/snRNA",
                "single-nucleus": "sc/snRNA",
                "single cell rna": "sc/snRNA",
                "scrna": "sc/snRNA",
                "snrna": "sc/snRNA",
                "spatial": "spatial",
                "spatially resolved": "spatial",
                "multiomic": "multiomic",
                "multi-omic": "multiomic",
                "atac": "atac",
                "assay for transposase-accessible chromatin": "atac",
                "proteomics": "proteomics",
                "protein": "proteomics"
            }
        }
        
        field_synonyms = synonyms.get(field, {})
        return field_synonyms.get(value, value)


# Global default policy
DEFAULT_POLICY = ObsPolicy()


def get_policy() -> ObsPolicy:
    """Get the default observation policy."""
    return DEFAULT_POLICY


def create_custom_policy(**kwargs) -> ObsPolicy:
    """Create a custom observation policy with overridden settings."""
    return ObsPolicy(**kwargs)