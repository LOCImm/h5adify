# Quickstart

## Search

```bash
h5adify search cellxgene --query "glioblastoma" --max-results 10
h5adify search geo --query "visium brain" --max-results 10
h5adify search sodb --query "brain" --max-results 10
```

## Download

```bash
h5adify download geo --gse GSE229409 --outdir data/out
h5adify download cellxgene --id e52ed1cc-d59f-4bf5-9716-8d81f14a89fd --outdir data/out
h5adify download sodb --id "Mouse brain atlas" --outdir data/out
```

## Batch + merge

```bash
h5adify batch --ids geo:GSE229409 cellxgene:e52ed1cc-d59f-4bf5-9716-8d81f14a89fd --outdir data/out --merge-out data/out/merged.h5ad
```

## Override metadata

```bash
h5adify download geo --gse GSE229409 --outdir data/out --set species=human --set tissue=brain --set disease=control
```
