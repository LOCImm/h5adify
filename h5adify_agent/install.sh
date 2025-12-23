#!/bin/bash
# h5adify v5.0.0 (FIXED) - Installation and Usage Guide

echo "🚀 h5adify v5.0.0 (FIXED) - Installation Guide"
echo "================================================"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.7"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo "✅ Python $python_version is compatible"
else
    echo "❌ Python $python_version is too old. Please upgrade to Python 3.7+"
    exit 1
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip3 install -e .

# Test the installation
echo ""
echo "🧪 Testing the installation..."
python3 test_fixes.py

# Make executables
echo ""
echo "🔧 Making executables..."
chmod +x h5adify-agent
chmod +x h5adify/h5adify-agent
chmod +x h5adify/working_gui_launcher.py

echo ""
echo "✅ Installation complete!"
echo ""
echo "🎯 Usage Examples:"
echo "=================="
echo ""
echo "📊 Command Line Interface:"
echo "  h5adify-agent                              # Interactive mode"
echo "  h5adify-agent search geo 'human brain'     # Search GEO"
echo "  h5adify-agent search ucsc 'mouse atlas'    # Search UCSC"
echo "  h5adify-agent search zenodo 'single cell'  # Search Zenodo"
echo ""
echo "🖥️  Graphical User Interface:"
echo "  h5adify-gui                                # Launch GUI"
echo ""
echo "🤖 AI Features (requires Ollama):"
echo "  h5adify-agent llm 'What is scRNA-seq?'     # Ask AI"
echo "  h5adify-agent ai_annotate 10.1038/nature12373  # Extract paper metadata"
echo ""
echo "📋 Available Commands:"
echo "  h5adify-agent help                         # Show all commands"
echo ""
echo "🔍 Database Sources:"
echo "  geo, ucsc, zenodo, ema, cellxgene, scp"
echo ""
echo "📝 Example Searches:"
echo "  h5adify-agent search geo 'human brain spatial atlas'"
echo "  h5adify-agent search ucsc 'mouse development' --max 20"
echo "  h5adify-agent search zenodo 'spatial transcriptomics'"
echo ""
echo "🎉 Happy analyzing!"
