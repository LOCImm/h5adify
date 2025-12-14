# h5adify

`h5adify` is a small Python library + CLI to **search**, **download**, and **convert** public single-cell / spatial datasets into **standardized `.h5ad` (AnnData)** with consistent metadata fields (`obs`), optionally **merging** multiple datasets across sources into a single `.h5ad`.

Supported sources (best-effort, depends on what each dataset provides publicly):

- **GEO (GSE/GSM)**: downloads *supplementary processed matrices* (10x MTX/H5, etc.) and converts to `.h5ad` (does **not** require SRA).
- **CZ CELLxGENE Discover**: accepts **dataset UUIDs** or direct **`.h5ad` URLs**.
- **SODB (Spatial Omics DataBase)** via `pysodb` (optional extra): downloads an AnnData directly (dataset- or experiment-level).
- **Broad Single Cell Portal (SCP)**: best-effort download via direct file links (when public) and/or API endpoints (if reachable).

> Why “best-effort”? Public portals vary widely: some provide direct `.h5ad`, some provide 10x matrices, some provide Seurat `.rds`, and many clinical datasets are controlled-access.

---

## Install (local)

```bash
git clone <your-fork-or-local-repo>
cd h5adify
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .          # core
pip install -e ".[sodb]"  # optional SODB via pysodb
pip install -e ".[docs]"  # docs build dependencies
```

## Quickstart (CLI)

### 1) Search
```bash
h5adify search geo --query "human brain spatial transcriptomics" --max-results 20
h5adify search cellxgene --query "glioblastoma" --max-results 10
h5adify search sodb --query "brain" --max-results 20   # requires pysodb
```

### 2) Download + convert (per dataset -> one h5ad)
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
```

### 3) Multi-source batch + merge
```bash
h5adify batch   --ids geo:GSE229409 cellxgene:e52ed1cc-d59f-4bf5-9716-8d81f14a89fd sodb:"Mouse brain atlas::exp_001"   --outdir data/out   --merge-out data/out/merged_all.h5ad
```

By default, `h5adify` tries to fill standard `obs` fields (e.g., `species`, `technology`, `sex`, `age`, `condition`, `disease`, `batch`, `source`, `dataset_id`).
You can override any fields via `--set key=value` (repeatable).

---

## Python usage (notebook)

```python
from h5adify import download, merge_h5ads

path = download("geo", gse="GSE229409", outdir="data/out")

merged = merge_h5ads(["data/out/A.h5ad", "data/out/B.h5ad"], join="outer")
merged.write_h5ad("data/out/merged.h5ad")
```

---

## Documentation (Read the Docs-style)

Docs live in `docs/` and can be built locally:

```bash
pip install -e ".[docs]"
cd docs
make html
open _build/html/index.html
```

---

## Notes on GEO (GSE) conversion

- `h5adify download geo` focuses on **processed supplementary matrices** (e.g., 10x MTX/H5).
- If a GEO series only provides **raw SRA**, you’ll need a dedicated pipeline (SRA → FASTQ → CellRanger/STARsolo → matrix).  
  `h5adify` will detect “raw-only” cases and explain what’s missing.

---

## License

MIT
