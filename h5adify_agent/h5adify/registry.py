from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

# Import both legacy and enhanced sources for compatibility
from .sources.base import Source
from .sources.geo import GEOSource
from .sources.ema import EMASource
from .sources.cellxgene import CellxGeneSource
from .sources.scp import SingleCellPortalSource
from .sources.ucsc import UCSCSource

# Import enhanced sources
from .sources.enhanced_base import EnhancedSource
from .sources.enhanced_geo import EnhancedGeoSource
from .sources.enhanced_ucsc import EnhancedUCSCCource
from .sources.enhanced_zenodo import EnhancedZenodoSource
from .sources.enhanced_ema import EnhancedEmaSource
from .sources.enhanced_cellxgene import EnhancedCellxGeneSource
from .sources.enhanced_scp import EnhancedScpSource

# Note: SODB is intentionally excluded as requested by user

_LOGGER = logging.getLogger(__name__)


class SourceRegistry:
    """Registry for managing data sources."""
    
    def __init__(self):
        self._sources: Dict[str, Type[Source]] = {}
        self._instances: Dict[str, Source] = {}
        self._register_enhanced_sources()  # Use enhanced sources by default
    
    def _register_enhanced_sources(self):
        """Register the enhanced sources."""
        # Register enhanced sources (which inherit from EnhancedSource)
        self.register("geo", EnhancedGeoSource)
        self.register("ucsc", EnhancedUCSCCource)
        self.register("zenodo", EnhancedZenodoSource)  # New source
        self.register("ema", EnhancedEmaSource)
        self.register("cellxgene", EnhancedCellxGeneSource)
        self.register("scp", EnhancedScpSource)
        
        _LOGGER.info("Registered enhanced sources: geo, ucsc, zenodo, ema, cellxgene, scp")
        _LOGGER.info("Note: SODB source has been removed as requested")
    
    def register(self, name: str, source_class: Type[Source]) -> None:
        """
        Register a new data source.
        
        Args:
            name: Name of the source
            source_class: Class that implements Source
        """
        # Note: We don't check inheritance since Source is a Protocol
        # The Protocol will be checked at runtime when methods are called
        
        self._sources[name] = source_class
        _LOGGER.debug(f"Registered source: {name}")
    
    def unregister(self, name: str) -> None:
        """
        Unregister a data source.
        
        Args:
            name: Name of the source to unregister
        """
        if name in self._sources:
            del self._sources[name]
            # Remove cached instance if exists
            if name in self._instances:
                del self._instances[name]
            _LOGGER.debug(f"Unregistered source: {name}")
        else:
            _LOGGER.warning(f"Source {name} not found for unregistration")
    
    def get_source_class(self, name: str) -> Optional[Type[Source]]:
        """
        Get the source class by name.
        
        Args:
            name: Name of the source
        
        Returns:
            Source class or None if not found
        """
        return self._sources.get(name)
    
    def get_source(self, name: str, **kwargs) -> Optional[Source]:
        """
        Get a source instance by name.
        
        Args:
            name: Name of the source
            **kwargs: Additional arguments for source initialization
        
        Returns:
            Source instance or None if not found
        """
        if name not in self._sources:
            return None
        
        # Use cached instance if available and no additional kwargs
        if not kwargs and name in self._instances:
            return self._instances[name]
        
        # Create new instance
        source_class = self._sources[name]
        try:
            instance = source_class(**kwargs)
            
            # Cache instance if no additional kwargs
            if not kwargs:
                self._instances[name] = instance
            
            return instance
            
        except Exception as e:
            _LOGGER.error(f"Failed to create source instance {name}: {e}")
            return None
    
    def list_sources(self) -> List[str]:
        """
        List all registered source names.
        
        Returns:
            List of source names
        """
        return list(self._sources.keys())
    
    def get_source_info(self, name: str) -> Optional[Dict[str, str]]:
        """
        Get information about a source.
        
        Args:
            name: Name of the source
        
        Returns:
            Dictionary with source information or None
        """
        source_class = self.get_source_class(name)
        if not source_class:
            return None
        
        return {
            "name": name,
            "class_name": source_class.__name__,
            "module": source_class.__module__,
            "description": getattr(source_class, "__doc__", "No description available")
        }
    
    def validate_source(self, name: str) -> Dict[str, any]:
        """
        Validate a registered source.
        
        Args:
            name: Name of the source to validate
        
        Returns:
            Dictionary with validation results
        """
        validation = {
            "valid": False,
            "errors": [],
            "warnings": []
        }
        
        source_class = self.get_source_class(name)
        if not source_class:
            validation["errors"].append(f"Source {name} not registered")
            return validation
        
        # Check required methods
        required_methods = ["search", "download"]
        for method_name in required_methods:
            if not hasattr(source_class, method_name):
                validation["errors"].append(f"Missing required method: {method_name}")
            elif not callable(getattr(source_class, method_name)):
                validation["errors"].append(f"Method {method_name} is not callable")
        
        # Check required attributes
        required_attributes = ["name"]
        for attr_name in required_attributes:
            if not hasattr(source_class, attr_name):
                validation["errors"].append(f"Missing required attribute: {attr_name}")
        
        # Try to create an instance
        try:
            instance = source_class()
            validation["valid"] = True
        except Exception as e:
            validation["errors"].append(f"Cannot create instance: {e}")
        
        return validation
    
    def clear_cache(self) -> None:
        """Clear cached source instances."""
        self._instances.clear()
        _LOGGER.debug("Cleared source instance cache")


# Global registry instance
_registry = SourceRegistry()


def register_source(name: str, source_class: Type[Source]) -> None:
    """
    Register a new data source globally.
    
    Args:
        name: Name of the source
        source_class: Class that implements Source
    """
    _registry.register(name, source_class)


def unregister_source(name: str) -> None:
    """
    Unregister a data source globally.
    
    Args:
        name: Name of the source to unregister
    """
    _registry.unregister(name)


def get_source(name: str, **kwargs) -> Optional[Source]:
    """
    Get a source instance by name.
    
    Args:
        name: Name of the source
        **kwargs: Additional arguments for source initialization
    
    Returns:
        Source instance or None if not found
    """
    return _registry.get_source(name, **kwargs)


def get_source_class(name: str) -> Optional[Type[Source]]:
    """
    Get the source class by name.
    
    Args:
        name: Name of the source
    
    Returns:
        Source class or None if not found
    """
    return _registry.get_source_class(name)


def list_sources() -> List[str]:
    """
    List all registered source names.
    
    Returns:
        List of source names
    """
    return _registry.list_sources()


def get_source_info(name: str) -> Optional[Dict[str, str]]:
    """
    Get information about a source.
    
    Args:
        name: Name of the source
    
    Returns:
        Dictionary with source information or None
    """
    return _registry.get_source_info(name)


def validate_source(name: str) -> Dict[str, any]:
    """
    Validate a registered source.
    
    Args:
        name: Name of the source to validate
    
    Returns:
        Dictionary with validation results
    """
    return _registry.validate_source(name)


def clear_source_cache() -> None:
    """Clear cached source instances."""
    _registry.clear_cache()


# Backward compatibility functions
def get_all_sources() -> List[str]:
    """Get list of all registered sources (backward compatibility)."""
    return list_sources()


def get_registered_sources() -> Dict[str, Dict[str, str]]:
    """
    Get all registered sources with their information.
    
    Returns:
        Dictionary mapping source names to their information
    """
    sources_info = {}
    for source_name in list_sources():
        info = get_source_info(source_name)
        if info:
            sources_info[source_name] = info
    return sources_info


def create_custom_source(
    name: str,
    search_method,
    download_method,
    **source_attributes
) -> Type[Source]:
    """
    Create a custom source class dynamically.
    
    Args:
        name: Name of the source
        search_method: Search method function
        download_method: Download method function
        **source_attributes: Additional attributes for the source
    
    Returns:
        Custom source class
    """
    from types import MethodType
    
    # Create a new class that inherits from BaseSource
    class CustomSource(Source):
        def __init__(self, **kwargs):
            # Initialize parent class
            super().__init__()
            # Set additional attributes
            for attr, value in source_attributes.items():
                setattr(self, attr, value)
            # Set instance-specific attributes
            for attr, value in kwargs.items():
                setattr(self, attr, value)
        
        def search(self, query: str, max_results: int = 20):
            """Custom search method."""
            return search_method(self, query, max_results)
        
        def download(self, **kwargs):
            """Custom download method."""
            return download_method(self, **kwargs)
    
    # Set the name attribute
    CustomSource.name = name
    
    return CustomSource


def auto_register_sources() -> None:
    """
    Automatically discover and register sources from the sources package.
    
    This function scans the sources package for source classes and registers them.
    """
    import inspect
    from .sources import base
    
    # Get all classes in the base module that inherit from BaseSource
    for name, obj in inspect.getmembers(base):
        if (inspect.isclass(obj) and 
            issubclass(obj, base.Source) and 
            obj != base.Source and
            hasattr(obj, 'name')):
            
            source_name = getattr(obj, 'name')
            if source_name:
                try:
                    register_source(source_name, obj)
                    _LOGGER.debug(f"Auto-registered source: {source_name}")
                except Exception as e:
                    _LOGGER.warning(f"Failed to auto-register source {source_name}: {e}")


# Initialize sources on import
try:
    auto_register_sources()
except Exception as e:
    _LOGGER.warning(f"Failed to auto-register sources: {e}")