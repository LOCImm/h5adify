# h5adify

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%E2%80%933.11-informational.svg" />
  <img src="https://img.shields.io/badge/AnnData-.h5ad%20native-blueviolet.svg" />
  <img src="https://img.shields.io/badge/Scanpy-compatible-brightgreen.svg" />
  <img src="https://img.shields.io/badge/Modality-single--cell%20%2B%20spatial-success.svg" />
  <img src="https://img.shields.io/badge/Sources-GEO%20%7C%20CELLxGENE%20%7C%20SODB%20%7C%20SCP%20%7C%20UCSC%20%7C%20EMA-orange.svg" />
</p>

`h5adify` is a small Python library + CLI to **search**, **download**, and **convert** public single-cell / spatial datasets into **standardized `.h5ad` (AnnData)** with consistent metadata fields (`.obs`).  
It can also **merge** multiple datasets (even across sources) into a single `.h5ad`.

> **Best-effort by design**: public portals vary wildly. Some provide direct `.h5ad`, others provide 10x MTX/H5, others provide Seurat `.rds`, and many clinical datasets are controlled-access. `h5adify` focuses on workflows that can be automated reliably without proprietary tooling.

---

## Supported sources

- **GEO (GSE/GSM)**  
  Downloads *processed supplementary matrices* (10x MTX/H5, etc.) and converts to `.h5ad` (**does not require SRA**).

- **CZ CELLxGENE Discover**  
  Accepts **dataset UUIDs** or direct **`.h5ad` URLs**.  
  Search is best-effort (API schema can vary and may return different JSON shapes depending on endpoint/proxy).

- **SODB (Spatial Omics DataBase)** via `pysodb` *(optional extra)*  
  Downloads an AnnData directly (dataset- or experiment-level).  
  `pysodb` is installed from GitHub as an extra dependency.

- **Broad Single Cell Portal (SCP)**  
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
If pip fails (common behind firewalls / when wheels are missing), install pysodb directly from GitHub:
```bash

pip install "git+https://github.com/TencentAILabHealthcare/pysodb.git"
pip install -e ".[sodb]"
```

## Quickstart (CLI)
### 1) Search datasets

```bash
# GEO
h5adify search geo --query "human brain spatial transcriptomics" --max-results 20

# CELLxGENE
h5adify search cellxgene --query "human brain spatial transcriptomics" --max-results 20

# SODB (requires pysodb)
h5adify search sodb --query "brain" --max-results 20

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

## 5) Provide a manifest of a list of h5ad files
```bash
h5adify manifest --root data/stereo_seq_mouse_embryo/ \
                 --out data/stereo_seq_mouse_embryo/out
```
It gives a `.csv` and `.jsonl` files, allowing to analyze the metadata of a large list of samples.

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
