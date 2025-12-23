#!/usr/bin/env python3
"""
h5adify - Setup script (Fixed Version)
Complete single-cell data processing toolkit
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
README = Path("README.md")
long_description = README.read_text() if README.exists() else "Complete single-cell data processing toolkit"

# Read requirements
REQUIREMENTS = [
    "anndata>=0.8.0",
    "pandas>=1.3.0",
    "numpy>=1.21.0",
    "requests>=2.25.0",
    "PyQt6>=6.0.0",
    "click>=8.0.0",
    "tqdm>=4.60.0",
    "requests-cache>=0.9.0",
]

# Optional dependencies
EXTRAS = {
    "ai": [
        "requests>=2.25.0",
    ],
    "dev": [
        "pytest>=6.0.0",
        "pytest-cov>=2.12.0",
        "black>=21.0.0",
        "flake8>=3.9.0",
        "mypy>=0.910",
    ],
}

setup(
    name="h5adify-fixed",
    version="5.0.0",
    author="MiniMax Agent",
    author_email="agent@minimax.chat",
    description="Complete single-cell data processing toolkit with working database searches",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/minimax/h5adify",
    project_urls={
        "Bug Reports": "https://github.com/minimax/h5adify/issues",
        "Source": "https://github.com/minimax/h5adify",
        "Documentation": "https://h5adify.readthedocs.io/",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Environment :: Console",
        "Environment :: Web Environment",
    ],
    python_requires=">=3.7",
    install_requires=REQUIREMENTS,
    extras_require=EXTRAS,
    entry_points={
        "console_scripts": [
            "h5adify-agent=h5adify.working_terminal_agent:main",
            "h5adify-gui=h5adify.working_gui_launcher:main",
        ],
    },
    package_data={
        "h5adify": [
            "data/*.json",
            "data/*.yaml",
            "data/*.yml",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
