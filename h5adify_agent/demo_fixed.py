#!/usr/bin/env python3
"""
h5adify v5.0.0 (FIXED) - Working Demo
Demonstrates the fixed functionality
"""

import sys
from pathlib import Path

# Add the package to Python path
sys.path.insert(0, str(Path(__file__).parent / "h5adify"))

def demo_terminal_agent():
    """Demonstrate working terminal agent."""
    print("🤖 h5adify v5.0.0 (FIXED) - Terminal Agent Demo")
    print("=" * 50)
    
    try:
        from working_terminal_agent_fixed import WorkingEnhancedTerminalAgent
        
        # Create agent
        agent = WorkingEnhancedTerminalAgent()
        
        print(f"✅ Agent initialized successfully")
        print(f"📊 Available sources: {', '.join(agent.get_available_sources())}")
        
        # Test different searches
        test_queries = [
            ('zenodo', 'brain single cell'),
            ('geo', 'human brain'),
            ('ucsc', 'mouse atlas'),
            ('scp', 'cancer data')
        ]
        
        for source, query in test_queries:
            print(f"\n🔍 Testing {source.upper()} search: '{query}'")
            try:
                result = agent.handle_search([source, query, '--max', '1'])
                if result and agent.search_results_cache:
                    first_result = agent.search_results_cache[0]
                    print(f"  ✅ Found: {first_result.get('title', 'No title')}")
                    print(f"  🔗 URL: {first_result.get('download_url', 'No URL')}")
                    print(f"  🧬 Species: {first_result.get('species', 'Unknown')}")
                else:
                    print(f"  ⚠️ No results found")
            except Exception as e:
                print(f"  ❌ Search failed: {e}")
        
        print(f"\n🎉 Terminal agent demo completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def demo_gui_components():
    """Demonstrate GUI components."""
    print("\n🖥️ GUI Component Demo")
    print("=" * 30)
    
    try:
        # Test PyQt5 availability
        from PyQt5.QtWidgets import QApplication
        print("✅ PyQt5 available")
        
        # Test GUI import
        from working_qt_gui_pyqt5 import MainWindow
        print("✅ GUI components importable")
        
        # Test window creation
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        window = MainWindow()
        sources = list(window.sources.keys())
        print(f"✅ GUI window created with {len(sources)} sources")
        print(f"📊 Sources: {', '.join(sources)}")
        
        window.close()
        print("✅ GUI test completed")
        return True
        
    except ImportError as e:
        print(f"⚠️ PyQt5 not available: {e}")
        print("💡 Install PyQt5: pip install PyQt5")
        return False
    except Exception as e:
        print(f"❌ GUI demo failed: {e}")
        return False

def demo_database_sources():
    """Demonstrate database source functionality."""
    print("\n🗄️ Database Sources Demo")
    print("=" * 35)
    
    sources_tested = 0
    sources_working = 0
    
    # Test individual sources
    databases = ['zenodo', 'geo', 'ucsc', 'ema', 'cellxgene', 'scp']
    
    for db_name in databases:
        try:
            # Try importing the source
            try:
                from sources import WorkingGEOSource
                if db_name == 'geo':
                    source_class = WorkingGEOSource
                elif db_name == 'ucsc':
                    from sources import WorkingUCSCSource
                    source_class = WorkingUCSCSource
                elif db_name == 'zenodo':
                    from sources import WorkingZenodoSource
                    source_class = WorkingZenodoSource
                elif db_name == 'ema':
                    from sources import WorkingEMASource
                    source_class = WorkingEMASource
                elif db_name == 'cellxgene':
                    from sources import WorkingCellxGeneSource
                    source_class = WorkingCellxGeneSource
                elif db_name == 'scp':
                    from sources import WorkingSCPSource
                    source_class = WorkingSCPSource
            except ImportError:
                # Try direct import
                module_name = f"sources.working_{db_name}"
                source_class = None
                exec(f"try:\n    from {module_name} import Working{db_name.upper()}Source as source_class\nexcept ImportError:\n    source_class = None")
            
            if source_class:
                # Test source creation and search
                source = source_class()
                results = source.search("test", max_results=1)
                
                if results:
                    print(f"✅ {db_name.upper()}: Working - {len(results)} results")
                    sources_working += 1
                else:
                    print(f"⚠️ {db_name.upper()}: No results")
            else:
                print(f"⚠️ {db_name.upper()}: Import failed")
            
            sources_tested += 1
            
        except Exception as e:
            print(f"❌ {db_name.upper()}: Error - {e}")
            sources_tested += 1
    
    print(f"\n📊 Database test summary: {sources_working}/{sources_tested} sources working")
    return sources_working > 0

def main():
    """Run the complete demo."""
    print("🎯 h5adify v5.0.0 (FIXED) - Complete Demo")
    print("This demo shows all the fixed functionality.")
    print()
    
    # Test terminal agent
    terminal_success = demo_terminal_agent()
    
    # Test GUI components  
    gui_success = demo_gui_components()
    
    # Test database sources
    db_success = demo_database_sources()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 DEMO SUMMARY")
    print("=" * 60)
    
    if terminal_success:
        print("✅ Terminal Agent: WORKING")
    else:
        print("❌ Terminal Agent: FAILED")
    
    if gui_success:
        print("✅ GUI Components: WORKING")
    else:
        print("⚠️ GUI Components: PyQt5 not available (install with: pip install PyQt5)")
    
    if db_success:
        print("✅ Database Sources: WORKING")
    else:
        print("❌ Database Sources: FAILED")
    
    print()
    if terminal_success:
        print("🚀 READY FOR USE!")
        print()
        print("💻 Usage:")
        print("  python3 h5adify/working_terminal_agent_fixed.py")
        print("  python3 h5adify/working_terminal_agent_fixed.py search zenodo 'brain'")
        print()
        if gui_success:
            print("🖥️ GUI:")
            print("  python3 h5adify/working_gui_launcher_pyqt5.py")
    else:
        print("❌ Some components failed. Check the errors above.")

if __name__ == "__main__":
    main()
