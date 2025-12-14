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

If you are behind a firewall or `pip` cannot find a `pysodb` wheel, install it directly from GitHub:

```bash
pip install "git+https://github.com/TencentAILabHealthcare/pysodb.git"
```

Then reinstall h5adify:

```bash
pip install -e .
```
pip install -e ".[docs]"  # docs build dependencies
```

## Quickstart (CLI)

### 1) Search
```bash
h5adify search geo --query "human brain spatial transcriptomics" --max-results 20
```
Output
```bash
{
    "source": "cellxgene",
    "dataset_id": "b58c19c6-bc2d-4461-b9bf-60fa2ac91479",
    "title": "Fine needle aspirates of axillary lymph nodes before and after vaccination",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/b58c19c6-bc2d-4461-b9bf-60fa2ac91479.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "82691839-6879-4810-90f3-67e953f328a3",
    "title": "Aortic cell types of ascending aorta",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/82691839-6879-4810-90f3-67e953f328a3.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "e2a00644-0a48-4815-ae87-d562045114f5",
    "title": "Brain dataset",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/e2a00644-0a48-4815-ae87-d562045114f5.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "b57462e3-1df5-463a-a3fa-4d67b93ef087",
    "title": "Spinal cord dataset",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/b57462e3-1df5-463a-a3fa-4d67b93ef087.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "9ac3d74d-1d94-4ff9-abf9-fe5abe4bd2a6",
    "title": "Single-nucleus RNA-seq of the Mouse Kidney (Version 2.0)",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/9ac3d74d-1d94-4ff9-abf9-fe5abe4bd2a6.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "91f31e05-56d8-46fc-b408-d90c9228a81b",
    "title": "Single-cell RNA-seq of the Adult Human Kidney (Version 2.0)",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/91f31e05-56d8-46fc-b408-d90c9228a81b.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "7ff0197b-d175-49bf-b4fa-150fe0995d93",
    "title": "Single-nucleus RNA-seq of the Adult Human Kidney (Version 2.0)",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/7ff0197b-d175-49bf-b4fa-150fe0995d93.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "f760224a-fb9a-4dd2-9339-b72ee01e5825",
    "title": "Bone",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/f760224a-fb9a-4dd2-9339-b72ee01e5825.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "f71eeea6-aa46-4d14-a53e-fb862806acee",
    "title": "Colon",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/f71eeea6-aa46-4d14-a53e-fb862806acee.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "f69adac8-fc07-484f-9f17-9875958f56e4",
    "title": "Uterus",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/f69adac8-fc07-484f-9f17-9875958f56e4.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "ed839584-54ea-4914-ab0d-4ecc5a649bf1",
    "title": "Heart",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/ed839584-54ea-4914-ab0d-4ecc5a649bf1.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "dc7ba810-2668-4182-abcc-d97d25f9310c",
    "title": "Skin",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/dc7ba810-2668-4182-abcc-d97d25f9310c.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "d3bbb7e6-40df-4a4f-bfe0-49001bc06396",
    "title": "Lung",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/d3bbb7e6-40df-4a4f-bfe0-49001bc06396.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "cbb0cb42-75d3-404f-bb92-da551c9ff67a",
    "title": "Limb muscle",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/cbb0cb42-75d3-404f-bb92-da551c9ff67a.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "bf694f39-4342-4e75-aec0-d46db17f2036",
    "title": "Spleen",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/bf694f39-4342-4e75-aec0-d46db17f2036.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "bdf0abdf-f1a5-4480-a30b-1e34eaee53bb",
    "title": "Bladder",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/bdf0abdf-f1a5-4480-a30b-1e34eaee53bb.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "a9f69075-aa4f-44f4-bb6b-07504ed450de",
    "title": "Blood",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/a9f69075-aa4f-44f4-bb6b-07504ed450de.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "a7b46d3a-c85e-4ec2-b5c0-04fa3e50d28b",
    "title": "Small intestine",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/a7b46d3a-c85e-4ec2-b5c0-04fa3e50d28b.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "a3959096-c197-4dcf-8d25-8383481bd1c4",
    "title": "Trachea",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/a3959096-c197-4dcf-8d25-8383481bd1c4.cxg/",
    "extra": null
  },
  {
    "source": "cellxgene",
    "dataset_id": "a392ab34-9016-4f48-b45d-5b3a9cfa39fe",
    "title": "LCA complete",
    "description": "",
    "url": "https://cellxgene.cziscience.com/e/a392ab34-9016-4f48-b45d-5b3a9cfa39fe.cxg/",
    "extra": null
  }
]
```
> **CELLxGENE API timeouts**: if `h5adify search cellxgene ...` times out on your network, increase the read timeout and retries:

```bash
export H5ADIFY_READ_TIMEOUT=300
export H5ADIFY_HTTP_RETRIES=8
export H5ADIFY_HTTP_BACKOFF=0.8
```

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
