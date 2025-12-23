#!/usr/bin/env python3
"""
h5adify v2.0 main entry point

This module allows direct execution of h5adify via python -m h5adify
"""

import sys
import argparse
from pathlib import Path

def main():
    """Main entry point when run as python -m h5adify."""
    
    # Setup paths for the enhanced version
    script_dir = Path(__file__).parent.absolute()
    
    # Add current directory to path for direct imports
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    
    try:
        # Import the CLI main function
        from h5adify.cli import main as cli_main
        cli_main()
    except ImportError as e:
        print(f"❌ Import error: {e}", file=sys.stderr)
        print("🔧 Please ensure you're using the enhanced h5adify version", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
