from __future__ import annotations
from ..genes import apply_gene_policy


import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import anndata as ad

from ..metadata import apply_obs_policy
from ..utils import download_file, ensure_dir, get_session, get_timeout
from .base import SearchResult

# BioStudies API is used to search and fetch study metadata for ArrayExpress studies. :contentReference[oaicite:3]{index=3}
_BS_SEARCH = "https://www.ebi.ac.uk/biostudies/api/v1/search"
_BS_STUDY = "https://www.ebi.ac.uk/biostudies/api/v1/studies/{acc}"
_AE_STUDY_PAGE = "https://www.ebi.ac.uk/biostudies/arrayexpress/studies/{acc}"


def _as_https(url: str) -> str:
    u = str(url or "")
    if u.startswith("ftp://"):
        return "https://" + u[len("ftp://") :]
    if u.startswith("//"):
        return "https:" + u
    return u


def _walk(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from _walk(x)


def _extract_file_links(study_json: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Try to extract file links from the BioStudies study JSON.
    This is intentionally permissive because structures vary between studies.
    """
    out: List[Tuple[str, str]] = []

    for node in _walk(study_json):
        if not isinstance(node, dict):
            continue

        # Common patterns across BioStudies payloads
        fname = node.get("fileName") or node.get("filename") or node.get("name")
        furl = node.get("url") or node.get("href") or node.get("downloadUrl") or node.get("download_url")

        if fname and furl and isinstance(fname, str) and isinstance(furl, str):
            out.append((fname, _as_https(furl)))

    # Deduplicate while preserving order
    seen = set()
    uniq: List[Tuple[str, str]] = []
    for fn, fu in out:
        key = (fn, fu)
        if key not in seen:
            uniq.append((fn, fu))
            seen.add(key)
    return uniq


class EMASource:
    """
    "ema" = EBI (ArrayExpress / Expression Atlas ecosystem) via BioStudies API.
    """
    name = "ema"

    def search(self, query: str, max_results: int = 20) -> List[SearchResult]:
        s = get_session()
        params = {
            "query": query,
            "collection": "arrayexpress",
            "pageSize": max_results,
            "page": 1,
        }
        r = s.get(_BS_SEARCH, params=params, timeout=get_timeout())
        r.raise_for_status()
        js = r.json()

        # Response shape may vary; be robust.
        hits = []
        if isinstance(js, dict):
            hits = js.get("hits") or js.get("results") or js.get("data") or []
        elif isinstance(js, list):
            hits = js
        if not isinstance(hits, list):
            hits = []

        out: List[SearchResult] = []
        for h in hits[:max_results]:
            if not isinstance(h, dict):
                continue
            acc = str(h.get("accession") or h.get("id") or "").strip()
            title = str(h.get("title") or h.get("name") or acc).strip()
            if not acc:
                continue
            out.append(
                SearchResult(
                    source=self.name,
                    dataset_id=acc,
                    title=title,
                    url=_AE_STUDY_PAGE.format(acc=acc),
                )
            )
        return out

    def download(
        self,
        dataset_id: str,
        outdir: str | Path,
        policy=None,
        overrides: Optional[Dict[str, str]] = None,
        keep_work: bool = False,
        no_merge_samples: bool = False,
    ) -> DownloadResult:
        """
        Downloads a .h5ad *if the study provides one* as an attached file on BioStudies.
        If no .h5ad is present, this raises with a clear message (so you can add a custom loader).
        """
        if policy is None:
            policy = self.default_policy()
        overrides = dict(overrides or {})
        overrides.setdefault("source", self.name)
        overrides.setdefault("dataset_id", dataset_id)

        outdir = Path(outdir)
        ensure_dir(outdir)

        work = outdir / f"_work_{self.name}_{re.sub(r'[^A-Za-z0-9_.-]+', '_', dataset_id)}"
        ensure_dir(work)

        s = get_session()
        r = s.get(_BS_STUDY.format(acc=dataset_id), params={"collection": "arrayexpress"}, timeout=get_timeout())
        r.raise_for_status()
        study = r.json() if isinstance(r.json(), dict) else {"data": r.json()}

        files = _extract_file_links(study)
        # pick best candidate .h5ad
        h5ads = [(fn, fu) for (fn, fu) in files if str(fn).lower().endswith(".h5ad")]
        if not h5ads:
            raise RuntimeError(
                f"[ema:{dataset_id}] No attached .h5ad found via BioStudies for this study. "
                f"Open the study page and check available files: {_AE_STUDY_PAGE.format(acc=dataset_id)}"
            )

        fn, url = h5ads[0]
        local = work / fn
        download_file(url, local, session=s)

        adata = ad.read_h5ad(local)
        if gene_options is not None:
            apply_gene_policy(
                adata,
                policy=str(gene_options.policy),
                rename_var_names=gene_options.rename_var_names,
                write_var_columns=gene_options.write_var_columns,
                keep_unmapped=gene_options.keep_unmapped,
                species_hint=gene_options.species_hint,
            )
        apply_obs_policy(adata, policy=policy, overrides=overrides)

        out_path = outdir / f"{self.name}__{re.sub(r'[^A-Za-z0-9_.-]+', '_', dataset_id)}.h5ad"
        adata.write_h5ad(out_path)

        if not keep_work:
            shutil.rmtree(work, ignore_errors=True)

        return DownloadResult(
            source=self.name,
            dataset_id=dataset_id,
            out_paths=[out_path],
            workdir=work if keep_work else None,
        )
