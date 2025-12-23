#!/bin/bash
# h5adify v5.0.0 (FIXED) - Installation and Usage Guide

echo "🚀 h5adify v5.0.0 (FIXED) - Installation and Usage Guide"
echo "========================================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.7"

echo "📋 System Information:"
echo "  • Python version: $python_version"
echo "  • Current directory: $(pwd)"
echo ""

# Check if we're in the right directory
if [ ! -f "setup_fixed.py" ]; then
    echo "❌ Error: setup_fixed.py not found. Please run this script from the h5adify_fixed directory."
    exit 1
fi

# Install basic dependencies
echo "📦 Installing basic dependencies..."
pip3 install requests

# Install PyQt5 if not present
echo "📦 Checking PyQt5..."
if ! python3 -c "import PyQt5" 2>/dev/null; then
    echo "📦 Installing PyQt5..."
    pip3 install PyQt5
else
    echo "  ✅ PyQt5 already installed"
fi

# Make executables
echo ""
echo "🔧 Making executables..."
chmod +x h5adify-agent-fixed
chmod +x h5adify/working_gui_launcher_pyqt5.py
chmod +x h5adify/working_terminal_agent_fixed.py

# Test basic functionality
echo ""
echo "🧪 Testing basic functionality..."
python3 test_comprehensive.py

echo ""
echo "✅ Installation and testing complete!"
echo ""
echo "🎯 Usage Examples:"
echo "=================="
echo ""
echo "📊 Command Line Interface:"
echo "  ./h5adify-agent-fixed                           # Interactive mode"
echo "  ./h5adify-agent-fixed search geo 'human brain'  # Search GEO"
echo "  ./h5adify-agent-fixed search ucsc 'mouse atlas' # Search UCSC"
echo "  ./h5adify-agent-fixed search zenodo 'single cell' # Search Zenodo"
echo ""
echo "🖥️  Graphical User Interface:"
echo "  python3 h5adify/working_gui_launcher_pyqt5.py   # Launch GUI"
echo ""
echo "🤖 AI Features (requires Ollama):"
echo "  ./h5adify-agent-fixed llm 'What is scRNA-seq?'   # Ask AI"
echo "  ./h5adify-agent-fixed ai_annotate 10.1038/nature12373  # Extract paper metadata"
echo ""
echo "📋 Available Commands:"
echo "  ./h5adify-agent-fixed help                      # Show all commands"
echo ""
echo "🔍 Database Sources:"
echo "  geo, ucsc, zenodo, ema, cellxgene, scp"
echo ""
echo "📝 Example Searches:"
echo "  ./h5adify-agent-fixed search geo 'human brain spatial atlas'"
echo "  ./h5adify-agent-fixed search ucsc 'mouse development' --max 20"
echo "  ./h5adify-agent-fixed search zenodo 'spatial transcriptomics'"
echo ""
echo "🎉 Happy analyzing!"
