# CLI

## `h5adify search`

```bash
h5adify search <source> --query "<text>" --max-results 20
```

## `h5adify download`

```bash
h5adify download <source> --outdir <dir> (--gse GSE... | --id <id-or-url>) \
  [--no-merge-samples] [--keep-work] [--set key=value ...]
```

## `h5adify batch`

```bash
h5adify batch --ids source:dataset_id [source:dataset_id ...] --outdir <dir> \
  [--merge-out merged.h5ad] [--merge-join outer|inner] [--merge-label batch] \
  [--keep-work] [--no-merge-samples] [--set key=value ...]
```
