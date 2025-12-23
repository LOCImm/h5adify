#!/usr/bin/env python3
"""
h5adify GUI Launcher v5.0.0
Launch the PyQt5 GUI interface for h5adify
"""

import sys
import argparse
from pathlib import Path

# Add the package to Python path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Launch h5adify GUI."""
    parser = argparse.ArgumentParser(description="h5adify GUI v5.0.0")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    try:
        # Import and launch GUI
        from h5adify.qt_gui import main as gui_main
        gui_main()
    except ImportError as e:
        print(f"❌ Failed to import GUI components: {e}")
        print("💡 Make sure PyQt5 is installed: pip install PyQt5")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to launch GUI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()