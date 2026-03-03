# h5adify

<p align="center">
  <a href="https://www.biorxiv.org/content/10.64898/2026.02.28.708740v1">
    <img src="https://img.shields.io/badge/bioRxiv-2026.02.28.708740v1-BD2736?logo=biorxiv" alt="bioRxiv"/>
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%E2%80%933.11-informational.svg" />
  <img src="https://img.shields.io/badge/AnnData-.h5ad%20native-blueviolet.svg" />
  <img src="https://img.shields.io/badge/Scanpy-compatible-brightgreen.svg" />
  <img src="https://img.shields.io/badge/Modality-single--cell%20%2B%20spatial-success.svg" />
  <img src="https://img.shields.io/badge/Sources-GEO%20%7C%20CELLxGENE%20%7C%20%7C%20Zenodo%20%7C%20UCSC%20%7C%20EMA-orange.svg" />
</p>

<p align="center">
  <a href="https://pypi.org/project/h5adify/">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/h5adify.svg">
  </a>
  <a href="https://test.pypi.org/project/h5adify/">
    <img alt="TestPyPI" src="https://img.shields.io/badge/TestPyPI-available-orange.svg">
  </a>

  <a href="https://github.com/locImm/h5adify/stargazers">
    <img alt="GitHub stars" src="https://img.shields.io/github/stars/locImm/h5adify?style=flat">
  </a>
  <a href="https://github.com/locImm/h5adify/releases">
    <img alt="GitHub release" src="https://img.shields.io/github/v/release/locImm/h5adify">
  </a>
  
  <a href="LICENSE">
    <img alt="License" src="https://img.shields.io/badge/License-MIT-green.svg">
  </a>
</p>


`h5adify` is a small Python library + CLI to **search**, **download**, and **convert** public single-cell / spatial datasets into **standardized `.h5ad` (AnnData)** with consistent metadata fields (`.obs`).  
It can also **merge** multiple datasets (even across sources) into a single `.h5ad`.

> **Best-effort by design**: public portals vary wildly. Some provide direct `.h5ad`, others provide 10x MTX/H5 and many clinical datasets are controlled-access. `h5adify` focuses on workflows that can be automated reliably without proprietary tooling being able to homogenously, automatically and download and annotate a very large number of datasets.

---

## Supported sources

- **GEO (GSE/GSM)**  
  Downloads *processed supplementary matrices* (10x MTX/H5, etc.) and converts to `.h5ad` (**does not require SRA**).

- **CZ CELLxGENE Discover**  
  Accepts **dataset UUIDs** or direct **`.h5ad` URLs**.  
  Search is best-effort (API schema can vary and may return different JSON shapes depending on endpoint/proxy).

- **Zenodo**  
  Best-effort download via public endpoints / direct file links (when available).

- **UCSC Cell Browser (single-cell + some spatial datasets)**  
  Search via UCSC dataset registry, and download when a dataset exposes a direct `.h5ad` in the dataset directory.

- **EMA (EBI) — BioStudies / ArrayExpress**  
  Search via EBI BioStudies API (ArrayExpress collection).  
  Download works **only** when a study provides an attached **`.h5ad`** file.

---

## Install (local)

### 1) Clone + venv
```bash
git clone <your-fork-or-local-repo>
cd h5adify
python -m venv .venv
source .venv/bin/activate
pip install -U pip

### 2) Install h5adify
```bash
pip install -e .          # core
pip install -e ".[docs]"  # docs build dependencies (optional)
```

## Install (from pip)

```bash
pip install h5adify
```

or

```bash
pip install -i https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  h5adify
```

## Quickstart (CLI)

```bash
h5adify
```
```bash
╔══════════════════════════════════════════════════════════════╗
║           🧬 h5adify Terminal Agent v0.0.7 🧬                ║
║      Complete Single-Cell Data Processing & Annotation       ║
╚══════════════════════════════════════════════════════════════╝

📁 Working Directory: /home/aalentorn/Projects/FoundationModel/h5adify_new
📊 Database Sources:  geo, zenodo, ema, ucsc, cellxgene
📦 AnnData:           ✅
🧬 Gene Harmonization:✅
🤖 4-Stage Annotation:✅
🧩 Prompts:           ✅ (prompt list/use/...)
🤖 Ollama LLM:        ✅ qwen2.5:3b (13 models available)

────────────────────────────────────────────────────────────
Type 'help' for all commands, 'llm' for AI model options
────────────────────────────────────────────────────────────
```

```bash
h5adify> help  
```

```bash
╔══════════════════════════════════════════════════════════════╗
║                    h5adify v0.0.7 HELP                       ║
╚══════════════════════════════════════════════════════════════╝

🔍 DATABASE SEARCH
────────────────────────────────────────────────────────────────
  search <source> <query> [--max N]
      Sources: cellxgene, ema, geo, ucsc, zenodo
      Example: search geo brain tumor spatial --max 30

  open_link <number>
      Open search result URL in browser

💾 LOCAL FILE MANAGEMENT
────────────────────────────────────────────────────────────────
  list_local [directory] [-r/--recursive]
      List .h5ad files with analysis
      Example: list_local /data -r

  inspect_local <file|number|directory> [-r]
      Detailed file inspection

🧬 GENE HARMONIZATION (pyorthogene features)
────────────────────────────────────────────────────────────────
  detect_species <file|number>
      Detect species from gene IDs (Ensembl prefix, casing, etc.)
      
  harmonize <file|number> [--target auto|human|mouse] [--output file.h5ad]
      Harmonize genes to target species (HUGO symbols)
      Uses Ensembl orthology mapping
      Default: --target auto (auto-detects species from gene names)
      
  deduplicate <file|number> [--how sum|mean|first] [--output file.h5ad]
      Deduplicate genes by aggregating duplicate entries

🔀 DATASET MERGING
────────────────────────────────────────────────────────────────
  analyze_overlap <file1> <file2> [file3...]
      Analyze feature overlap across datasets
      
  find_common <file1> <file2> [file3...]
      Find common features (genes) across datasets
      
  merge <file1> <file2> [file3...] [--output merged.h5ad] [--join inner|outer]
      Merge datasets with common/all features
      Options:
        --features file.txt  Use specific feature list
        --batch-key batch    Column name for batch labels
        --harmonize          Harmonize genes before merging

📝 4-STAGE ANNOTATION PIPELINE
────────────────────────────────────────────────────────────────
  annotate <file|number> [--doi DOI] [--no-verify]
      Full 4-stage annotation:
        Stage A: Deterministic extraction (h5ad signals)
        Stage B: RAG retrieval 
        Stage C: Constrained LLM extraction
        Stage D: Verification pass
      
  annotate_doi <DOI>
      Annotate from paper DOI only (no h5ad)
      
  extract_deterministic <file|number>
      Run Stage A only (no LLM)

🤖 LLM / AI MODELS
────────────────────────────────────────────────────────────────
  llm                 Show LLM status and available models
  llm status          Check Ollama connection and model info
  llm list            List all available models
  llm select <model>  Select a model for annotation
  llm test [prompt]   Test the selected model
  llm refresh         Refresh model list from Ollama

⚙️ SETTINGS
────────────────────────────────────────────────────────────────
  verbose         Toggle verbose output
  json            Toggle JSON output format
  help [command]  Show help
  exit/quit/q     Exit

📊 AVAILABLE SOURCES: cellxgene, ema, geo, ucsc, zenodo
```


### 1) Search datasets

```bash
# GEO
h5adify search geo --query "human brain spatial transcriptomics" --max-results 20

# CELLxGENE
h5adify search cellxgene --query "human brain spatial transcriptomics" --max-results 20

# UCSC Cell Browser
h5adify search ucsc --query "human hippocampus" --max-results 20

# EMA / EBI (BioStudies / ArrayExpress)
h5adify search ema --query "single cell brain" --max-results 20
```
### 2) Download + convert (per dataset -> one .h5ad)

```bash
# GEO: converts all samples with parseable supplementary matrices
h5adify download geo --gse GSE229409 --outdir data/out

# CELLxGENE: dataset UUID or direct .h5ad URL
h5adify download cellxgene --id e52ed1cc-d59f-4bf5-9716-8d81f14a89fd --outdir data/out
h5adify download cellxgene --id https://datasets.cellxgene.cziscience.com/e52ed1cc-d59f-4bf5-9716-8d81f14a89fd.h5ad --outdir data/out

# SODB: dataset-level (downloads all experiments -> one merged file)
h5adify download sodb --id "Mouse brain atlas" --outdir data/out

# SODB: single experiment
h5adify download sodb --id "Mouse brain atlas::exp_001" --outdir data/out

# UCSC: dataset id from search results (download works when a .h5ad is exposed)
h5adify download ucsc --id human-hippo-axis --outdir data/out

# EMA: E-MTAB / E-XXXX study accession (download works when an attached .h5ad is present)
h5adify download ema --id E-MTAB-XXXX --outdir data/out
```

### 3) Multi-source batch + merge
```bash
h5adify batch \
  --ids geo:GSE229409 \
       cellxgene:e52ed1cc-d59f-4bf5-9716-8d81f14a89fd \
       sodb:"Mouse brain atlas::exp_001" \
  --outdir data/out \
  --merge-out data/out/merged_all.h5ad
```
### 4) Batch multiple files from different databases
```bash
h5adify batch --ids geo:GSE229409 \
                    cellxgene:e52ed1cc-d59f-4bf5-9716-8d81f14a89fd \
              --outdir data/out \
              --merge-out data/out/merged.h5ad
```

### 5) Provide a manifest of a list of h5ad files
```bash
h5adify manifest --root data/stereo_seq_mouse_embryo/ \
                 --out data/stereo_seq_mouse_embryo/out
```
It gives a `.csv` and `.jsonl` files, allowing to analyze the metadata of a large list of samples.

### 6) Query the metadata of a list of h5ad files

There are 2 .h5ad in this folder:

```bash
h5adify query --root data/stereo_seq_mouse_embryo/
UserWarning: Observation names are not unique. To make them unique, call `.obs_names_make_unique`.
  utils.warn_names_duplicates("obs")
[
  {
    "path": "data/stereo_seq_mouse_embryo/mouse_embryo_all_slices.h5ad",
    "filename": "mouse_embryo_all_slices.h5ad",
    "n_obs": 176711,
    "n_vars": 1923,
    "x_dtype": "float32",
    "is_sparse": false,
    "has_raw_counts": false,
    "has_spatial": true,
    "layers": "count,norm",
    "obsm": "spatial,spatial_aligned,spatial_pair",
    "source": "",
    "dataset_id": "",
    "species": "",
    "technology": "",
    "condition": "",
    "disease": "",
    "batch": "real",
    "checksum_sha256": ""
  },
  {
    "path": "data/stereo_seq_mouse_embryo/E16.5_E1S3_cell_bin.h5ad",
    "filename": "E16.5_E1S3_cell_bin.h5ad",
    "n_obs": 281377,
    "n_vars": 28103,
    "x_dtype": "float32",
    "is_sparse": false,
    "has_raw_counts": false,
    "has_spatial": true,
    "layers": "counts",
    "obsm": "spatial",
    "source": "",
    "dataset_id": "",
    "species": "",
    "technology": "",
    "condition": "",
    "disease": "",
    "batch": "",
    "checksum_sha256": ""
  }
]
```
### 7) Inspect the metadata of h5ad

```bash
h5adify inspect --path data/stereo_seq_mouse_embryo/mouse_embryo_all_slices.h5ad 
UserWarning: Observation names are not unique. To make them unique, call `.obs_names_make_unique`.
  utils.warn_names_duplicates("obs")

{
  "path": "/home/aalentorn/Téléchargements/data/stereo_seq_mouse_embryo/mouse_embryo_all_slices.h5ad",
  "n_obs": 176711,
  "n_vars": 1923,
  "obs_cols": [
    "n_genes_by_counts",
    "log1p_n_genes_by_counts",
    "total_counts",
    "log1p_total_counts",
    "annotation"
  ],
  "var_cols": [],
  "layers": [
    "count",
    "norm"
  ],
  "obsm": [
    "spatial",
    "spatial_aligned",
    "spatial_pair"
  ],
  "uns": [],
  "has_spatial": true,
  "has_raw_counts": false,
  "x_dtype": "float32",
  "x_is_sparse": false,
  "missing_std_fields": {
    "source": 1.0,
    "dataset_id": 1.0,
    "species": 1.0,
    "technology": 1.0,
    "sex": 1.0,
    "age": 1.0,
    "condition": 1.0,
    "disease": 1.0,
    "batch": 0.0
  }
}
```

### Standardized metadata (`.obs`)

By default, h5adify tries to fill a standard set of .obs fields where possible, e.g.:

`species`
`technology`
`sex`
`age`
`condition`
`disease`
`batch`
`source`
`dataset_id`

You can override any fields via repeatable `--set`:

```bash
h5adify download geo --gse GSE229409 --outdir data/out \
  --set species=human --set condition=control --set technology=10x_visium
```

### Python usage (notebook)

```python
from h5adify import download, merge_h5ads

# Download one dataset into standardized .h5ad
paths = download("geo", gse="GSE229409", outdir="data/out")

# Merge multiple .h5ad files
merged = merge_h5ads(["data/out/A.h5ad", "data/out/B.h5ad"], join="outer")
merged.write_h5ad("data/out/merged.h5ad")
```

### Notes on GEO (GSE) conversion

h5adify download geo focuses on processed supplementary matrices (e.g., 10x MTX/H5).

If a GEO series only provides raw SRA, you’ll need a dedicated pipeline (SRA → FASTQ → CellRanger/STARsolo → matrix).
h5adify will detect “raw-only” cases and explain what’s missing.

---

## License

MIT
