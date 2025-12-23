"""
h5adify GUI Application - PyQt5 Compatible Version
Simple but functional GUI for single-cell data processing
Version: 5.0.0 (PyQt5 Compatible)
"""

import sys
import json
import csv
import os
import logging
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import requests
import re

# PyQt5 imports (compatible with user's installation)
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
        QTextEdit, QLineEdit, QPushButton, QComboBox, QCheckBox, 
        QProgressBar, QTabWidget, QLabel, QTableWidget, QTableWidgetItem,
        QFileDialog, QMessageBox, QSplitter, QFrame, QGroupBox,
        QSpinBox, QTextBrowser, QScrollArea, QListWidget, QListWidgetItem,
        QTreeWidget, QTreeWidgetItem, QFormLayout, QDialog, QDialogButtonBox
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
    from PyQt5.QtGui import QFont, QIcon, QPixmap, QDesktopServices
    PYQT5_AVAILABLE = True
except ImportError:
    print("❌ PyQt5 not available. Please install: pip install PyQt5")
    PYQT5_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_LOGGER = logging.getLogger(__name__)

# Try importing sources with fallbacks
try:
    from .sources import (
        WorkingGEOSource,
        WorkingUCSCSource,
        WorkingZenodoSource,
        WorkingEMASource,
        WorkingCellxGeneSource,
        WorkingSCPSource
    )
    HAS_WORKING_SOURCES = True
except ImportError:
    HAS_WORKING_SOURCES = False
    _LOGGER.warning("Working sources not available")


class SearchWorker(QThread):
    """Worker thread for search operations."""
    search_completed = pyqtSignal(list, str)
    search_error = pyqtSignal(str)
    
    def __init__(self, source_name: str, query: str, max_results: int, source_instance):
        super().__init__()
        self.source_name = source_name
        self.query = query
        self.max_results = max_results
        self.source_instance = source_instance
    
    def run(self):
        try:
            results = self.source_instance.search(self.query, max_results=self.max_results)
            self.search_completed.emit(results, self.source_name)
        except Exception as e:
            _LOGGER.error(f"Search error: {e}")
            self.search_error.emit(str(e))


class SearchWidget(QWidget):
    """Widget for search operations with working implementations."""
    
    def __init__(self, sources: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.sources = sources
        self.search_results = []
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Search controls
        search_frame = QFrame()
        search_frame.setFrameStyle(QFrame.StyledPanel)
        search_layout = QFormLayout()
        
        # Source selection
        self.source_combo = QComboBox()
        self.source_combo.addItems(list(self.sources.keys()))
        search_layout.addRow("Source:", self.source_combo)
        
        # Query input
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("Enter search query...")
        search_layout.addRow("Query:", self.query_edit)
        
        # Max results
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setMinimum(1)
        self.max_results_spin.setMaximum(100)
        self.max_results_spin.setValue(10)
        search_layout.addRow("Max Results:", self.max_results_spin)
        
        # Search button
        self.search_button = QPushButton("🔍 Search")
        self.search_button.clicked.connect(self.perform_search)
        search_layout.addRow("", self.search_button)
        
        search_frame.setLayout(search_layout)
        layout.addWidget(search_frame)
        
        # Results display
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "ID", "Title", "Species", "Technology", "Samples", "Actions"
        ])
        self.results_table.setSortingEnabled(True)
        layout.addWidget(self.results_table)
        
        # Status label
        self.status_label = QLabel("Ready to search")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def perform_search(self):
        """Perform search operation."""
        source_name = self.source_combo.currentText()
        query = self.query_edit.text().strip()
        max_results = self.max_results_spin.value()
        
        if not query:
            QMessageBox.warning(self, "Warning", "Please enter a search query.")
            return
        
        if source_name not in self.sources:
            QMessageBox.warning(self, "Warning", f"Source '{source_name}' not available.")
            return
        
        self.search_button.setEnabled(False)
        self.search_button.setText("🔍 Searching...")
        self.status_label.setText("Searching...")
        
        # Start search worker
        self.search_worker = SearchWorker(
            source_name, query, max_results, self.sources[source_name]
        )
        self.search_worker.search_completed.connect(self.on_search_completed)
        self.search_worker.search_error.connect(self.on_search_error)
        self.search_worker.start()
    
    def on_search_completed(self, results: List[Dict[str, Any]], source_name: str):
        """Handle search completion."""
        self.search_results = results
        self.search_button.setEnabled(True)
        self.search_button.setText("🔍 Search")
        self.status_label.setText(f"Found {len(results)} results")
        
        # Update results table
        self.update_results_table()
        
        # Show message
        QMessageBox.information(
            self, "Search Complete", 
            f"Found {len(results)} results in {source_name.upper()}"
        )
    
    def on_search_error(self, error_message: str):
        """Handle search error."""
        self.search_button.setEnabled(True)
        self.search_button.setText("🔍 Search")
        self.status_label.setText("Search failed")
        QMessageBox.critical(self, "Search Error", f"Search failed: {error_message}")
    
    def update_results_table(self):
        """Update results table with search results."""
        self.results_table.setRowCount(len(self.search_results))
        
        for row, result in enumerate(self.search_results):
            # ID
            self.results_table.setItem(row, 0, QTableWidgetItem(result.get('dataset_id', '')))
            
            # Title (truncated)
            title = result.get('title', '')
            if len(title) > 50:
                title = title[:50] + "..."
            self.results_table.setItem(row, 1, QTableWidgetItem(title))
            
            # Species
            self.results_table.setItem(row, 2, QTableWidgetItem(result.get('species', 'Unknown')))
            
            # Technology
            self.results_table.setItem(row, 3, QTableWidgetItem(result.get('technology', 'Unknown')))
            
            # Sample count
            sample_count = result.get('sample_count', 0)
            self.results_table.setItem(row, 4, QTableWidgetItem(str(sample_count) if sample_count > 0 else 'N/A'))
            
            # Actions
            open_btn = QPushButton("🔗")
            open_btn.clicked.connect(lambda checked, r=row: self.open_link(r))
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(5, 2, 5, 2)
            actions_layout.addWidget(open_btn)
            actions_widget.setLayout(actions_layout)
            
            self.results_table.setCellWidget(row, 5, actions_widget)
        
        # Resize columns
        self.results_table.resizeColumnsToContents()
    
    def open_link(self, row: int):
        """Open URL in default browser."""
        if row < len(self.search_results):
            result = self.search_results[row]
            url = result.get('download_url', '')
            if url:
                QDesktopServices.openUrl(QUrl(url))
            else:
                QMessageBox.information(self, "Info", "No URL available for this dataset")


class MainWindow(QMainWindow):
    """Main application window with PyQt5 compatibility."""
    
    def __init__(self):
        super().__init__()
        self.sources = self.initialize_sources()
        self.init_ui()
    
    def initialize_sources(self) -> Dict[str, Any]:
        """Initialize data sources."""
        sources = {}
        
        # Try working implementations
        if HAS_WORKING_SOURCES:
            try:
                sources['geo'] = WorkingGEOSource()
                sources['ucsc'] = WorkingUCSCSource()
                sources['zenodo'] = WorkingZenodoSource()
                sources['ema'] = WorkingEMASource()
                sources['cellxgene'] = WorkingCellxGeneSource()
                sources['scp'] = WorkingSCPSource()
                
                _LOGGER.info("Successfully initialized working database sources")
                
            except Exception as e:
                _LOGGER.error(f"Failed to initialize working sources: {e}")
        
        # Fallback to mock sources if working sources failed
        if not sources:
            _LOGGER.warning("Using mock sources for demonstration")
            sources = self.create_mock_sources()
        
        return sources
    
    def create_mock_sources(self) -> Dict[str, Any]:
        """Create mock sources for demonstration."""
        
        class MockSource:
            def __init__(self, name: str):
                self.name = name
            
            def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
                return [
                    {
                        'source': self.name,
                        'dataset_id': f'{self.name}_demo_1',
                        'title': f'{self.name.upper()} Demo Dataset for {query}',
                        'description': f'Demonstration dataset from {self.name} database',
                        'species': 'human',
                        'technology': '10x Genomics',
                        'sample_count': 1000,
                        'download_url': f'https://example.com/{self.name}/demo',
                        'extra': {'demo': True}
                    },
                    {
                        'source': self.name,
                        'dataset_id': f'{self.name}_demo_2',
                        'title': f'{self.name.upper()} Brain Atlas for {query}',
                        'description': f'Single-cell brain atlas from {self.name}',
                        'species': 'mouse',
                        'technology': 'Smart-seq2',
                        'sample_count': 500,
                        'download_url': f'https://example.com/{self.name}/brain',
                        'extra': {'demo': True}
                    }
                ][:max_results]
        
        return {
            'geo': MockSource('geo'),
            'ucsc': MockSource('ucsc'),
            'zenodo': MockSource('zenodo'),
            'ema': MockSource('ema'),
            'cellxgene': MockSource('cellxgene'),
            'scp': MockSource('scp')
        }
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("h5adify v5.0.0 - Single-Cell Data Processing Toolkit (PyQt5)")
        self.setGeometry(100, 100, 1000, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Add search tab
        self.search_widget = SearchWidget(self.sources, self)
        self.tab_widget.addTab(self.search_widget, "🔍 Search Databases")
        
        # Add help tab
        self.help_widget = QWidget()
        help_layout = QVBoxLayout()
        help_text = QTextBrowser()
        help_text.setHtml(self.generate_help_content())
        help_layout.addWidget(help_text)
        self.help_widget.setLayout(help_layout)
        self.tab_widget.addTab(self.help_widget, "❓ Help")
        
        # Status bar
        self.statusBar().showMessage(f"Ready - {len(self.sources)} sources available")
        
        # Show window
        self.show()
    
    def generate_help_content(self) -> str:
        """Generate help content."""
        sources_list = ', '.join(self.sources.keys())
        
        return f"""
        <h1>🤖 h5adify v5.0.0 - User Guide (PyQt5 Version)</h1>
        
        <h2>📊 Overview</h2>
        <p>h5adify is a comprehensive single-cell data processing toolkit. 
        This PyQt5 version provides a simple but functional GUI interface.</p>
        
        <h2>🔍 Search Functionality</h2>
        <p>Search across multiple genomic databases for single-cell datasets:</p>
        <ul>
            <li><b>GEO:</b> NCBI Gene Expression Omnibus</li>
            <li><b>UCSC:</b> UCSC Cell Browser</li>
            <li><b>Zenodo:</b> Open access research repository</li>
            <li><b>EMA:</b> EBI Expression Atlas</li>
            <li><b>CellxGene:</b> Chan Zuckerberg CellxGene</li>
            <li><b>SCP:</b> Broad Institute Single Cell Portal</li>
        </ul>
        
        <h2>💾 Available Sources</h2>
        <p>Currently available sources: <b>{sources_list}</b></p>
        
        <h2>🚀 Usage</h2>
        <ol>
            <li>Select a database source from the dropdown</li>
            <li>Enter your search query (e.g., "human brain", "mouse development")</li>
            <li>Set the maximum number of results</li>
            <li>Click "Search" to find datasets</li>
            <li>Click the link button to open dataset URLs</li>
        </ol>
        
        <h2>📚 Example Searches</h2>
        <ul>
            <li><b>Human brain:</b> "human brain single cell"</li>
            <li><b>Mouse development:</b> "mouse development atlas"</li>
            <li><b>Spatial transcriptomics:</b> "spatial transcriptomics"</li>
            <li><b>Cancer:</b> "cancer single cell"</li>
        </ul>
        
        <h2>🔗 Useful Links</h2>
        <ul>
            <li><a href="https://anndata.readthedocs.io/">AnnData Documentation</a></li>
            <li><a href="https://scanpy.readthedocs.io/">ScanPy Documentation</a></li>
            <li><a href="https://single-cell.readthedocs.io/">Single Cell Best Practices</a></li>
        </ul>
        """


def main():
    """Main application entry point."""
    if not PYQT5_AVAILABLE:
        print("❌ PyQt5 is required but not available.")
        print("Install PyQt5: pip install PyQt5")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("h5adify")
    app.setApplicationVersion("5.0.0")
    app.setOrganizationName("MiniMax Agent")
    
    # Create and show main window
    window = MainWindow()
    
    # Start event loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
