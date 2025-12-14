from h5adify import download, batch_download

geo_out = download("geo", gse="GSE229409", outdir="data/out", merge_samples=True)
print("GEO:", geo_out)

cxg_out = download("cellxgene", id="e52ed1cc-d59f-4bf5-9716-8d81f14a89fd", outdir="data/out")
print("CELLxGENE:", cxg_out)

produced = batch_download(
    ids=["geo:GSE229409", "cellxgene:e52ed1cc-d59f-4bf5-9716-8d81f14a89fd"],
    outdir="data/out",
    merge_out="data/out/merged_all.h5ad",
)
print("BATCH:", produced)
