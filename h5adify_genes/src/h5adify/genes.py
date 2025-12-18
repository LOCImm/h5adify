from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, Union

import re
import os
import warnings

import numpy as np

try:
    import anndata as ad
except Exception:  # pragma: no cover
    ad = None  # type: ignore

from .utils import get_session


_ENS_LOOKUP = "https://rest.ensembl.org/lookup/id"
_ENS_HOMOLOGY = "https://rest.ensembl.org/homology/id/{gene_id}"

# Heuristic species inference from Ensembl stable ID prefix
_ENSEMBL_PREFIX_SPECIES = {
    "ENSG": "human",
    "ENSMUSG": "mouse",
    "ENSRNOG": "rat",
    "ENSBTAG": "cow",
    "ENSPTRG": "chimpanzee",
    "ENSMMUG": "macaque",
    "ENSCJAG": "marmoset",
    "ENSDARG": "zebrafish",
    "ENSGALG": "chicken",
}


@dataclass
class GeneSummary:
    id_style: str  # symbol | ensembl | mixed | unknown
    ensembl_rate: float
    symbol_rate: float
    sample_prefix: str = ""
    inferred_species: str = ""  # from Ensembl prefixes (best-effort)
    target: str = ""           # e.g., HUGO
    policy_applied: str = ""   # e.g., detect|hugo|symbol
    unmapped: int = 0
    mapped: int = 0


def _is_ensembl_id(x: str) -> bool:
    # Covers ENSG..., ENSMUSG..., etc, optionally with version suffix .\d+
    return bool(re.match(r"^ENS[A-Z]{0,6}G\d+(?:\.\d+)?$", x))


def _is_symbol_like(x: str) -> bool:
    # Loose: letters/digits/underscore/hyphen, no spaces, not Ensembl
    if not x or len(x) > 50:
        return False
    if _is_ensembl_id(x):
        return False
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9_\-\.]*$", x))


def detect_gene_style(var_names: Iterable[str], max_check: int = 2000) -> GeneSummary:
    names = list(var_names)
    if not names:
        return GeneSummary(id_style="unknown", ensembl_rate=0.0, symbol_rate=0.0)

    # Sample for speed
    if len(names) > max_check:
        idx = np.linspace(0, len(names) - 1, max_check).astype(int)
        sample = [names[i] for i in idx]
    else:
        sample = names

    ensembl = sum(1 for g in sample if _is_ensembl_id(str(g)))
    symbol = sum(1 for g in sample if _is_symbol_like(str(g)))
    total = len(sample)
    ensembl_rate = ensembl / total if total else 0.0
    symbol_rate = symbol / total if total else 0.0

    if ensembl_rate >= 0.9:
        style = "ensembl"
    elif symbol_rate >= 0.9:
        style = "symbol"
    elif ensembl_rate + symbol_rate >= 0.5:
        style = "mixed"
    else:
        style = "unknown"

    # infer species from prefix frequency among Ensembl-like IDs
    prefixes: Dict[str, int] = {}
    for g in sample:
        s = str(g)
        if _is_ensembl_id(s):
            p = s.split("G", 1)[0] + "G"  # keep the 'G' suffix
            prefixes[p] = prefixes.get(p, 0) + 1
    sample_prefix = ""
    inferred_species = ""
    if prefixes:
        sample_prefix = max(prefixes.items(), key=lambda kv: kv[1])[0]
        # normalize to known keys
        for k, sp in _ENSEMBL_PREFIX_SPECIES.items():
            if sample_prefix.startswith(k):
                inferred_species = sp
                break

    return GeneSummary(
        id_style=style,
        ensembl_rate=float(ensembl_rate),
        symbol_rate=float(symbol_rate),
        sample_prefix=sample_prefix,
        inferred_species=inferred_species,
    )


def _chunked(xs: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def map_ensembl_to_symbol(ids: List[str], timeout: Optional[float] = None) -> Dict[str, str]:
    """Batch-map Ensembl stable IDs -> display_name (gene symbol) using Ensembl REST.

    Best-effort: on failure returns an empty mapping.
    """
    if not ids:
        return {}
    session = get_session()
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    out: Dict[str, str] = {}
    # Ensembl REST POST lookup/id supports up to a few thousand IDs; chunk conservatively.
    for chunk in _chunked(ids, 1000):
        try:
            r = session.post(_ENS_LOOKUP, headers=headers, json={"ids": chunk}, timeout=timeout or 60)
            r.raise_for_status()
            js = r.json()
            if isinstance(js, dict):
                for k, v in js.items():
                    if isinstance(v, dict):
                        sym = v.get("display_name") or v.get("name")
                        if sym:
                            out[str(k)] = str(sym)
        except Exception as e:
            warnings.warn(f"Ensembl lookup/id failed (kept original IDs): {e}")
            return {}
    return out


def map_to_hugo_human(
    ids: List[str],
    source_species: str = "",
    timeout: Optional[float] = None,
    max_map: Optional[int] = None,
) -> Dict[str, str]:
    """Map (non-human) Ensembl gene IDs -> *human* gene symbols (HUGO-like) via Ensembl homology.

    This is potentially slow. We cap total IDs mapped via max_map (env H5ADIFY_GENE_MAXMAP).
    """
    if not ids:
        return {}
    if max_map is None:
        try:
            max_map = int(os.environ.get("H5ADIFY_GENE_MAXMAP", "5000"))
        except Exception:
            max_map = 5000

    if len(ids) > max_map:
        warnings.warn(
            f"Refusing to map {len(ids)} genes to human (cap={max_map}). " 
            "Use H5ADIFY_GENE_MAXMAP to increase, or choose --gene-policy symbol/ensembl/detect."
        )
        return {}

    session = get_session()
    out: Dict[str, str] = {}

    def _one(gid: str) -> Tuple[str, str]:
        url = _ENS_HOMOLOGY.format(gene_id=gid)
        params = {
            "target_species": "human",
            "type": "orthologues",
            "format": "condensed",
        }
        headers = {"Accept": "application/json"}
        r = session.get(url, params=params, headers=headers, timeout=timeout or 60)
        r.raise_for_status()
        js = r.json()
        # Data model: {"data": [{"id":..., "homologies": [...] }]}
        data = js.get("data", []) if isinstance(js, dict) else []
        if not data:
            return gid, ""
        homs = data[0].get("homologies", []) if isinstance(data[0], dict) else []
        if not homs:
            return gid, ""

        # Prefer one2one orthologs
        def _score(h: dict) -> Tuple[int, float]:
            desc = str(h.get("description", ""))
            one2one = 1 if "one2one" in desc else 0
            pid = float(h.get("target", {}).get("perc_id", 0.0) or 0.0)
            return (one2one, pid)

        best = max((h for h in homs if isinstance(h, dict)), key=_score, default=None)
        if not best:
            return gid, ""
        tgt = best.get("target", {}) if isinstance(best.get("target"), dict) else {}
        # target may have display_id or id; we want display_id (symbol) if present
        sym = tgt.get("display_id") or tgt.get("display_name") or ""
        return gid, str(sym) if sym else ""

    # limited parallelism to avoid hammering API
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_one, gid): gid for gid in ids}
        for fut in concurrent.futures.as_completed(futs):
            gid, sym = fut.result()
            if sym:
                out[gid] = sym
    return out


def apply_gene_policy(
    adata,
    policy: str = "detect",
    *,
    rename_var_names: bool = True,
    write_var_columns: bool = True,
    keep_unmapped: bool = True,
    target: str = "hugo",
    species_hint: str = "",
) -> GeneSummary:
    """Annotate (and optionally rename) genes in an AnnData according to a policy.

    Policies:
      - detect: only detect + annotate (no renaming)
      - symbol: ensure var contains gene_symbol (best-effort) but no cross-species mapping
      - ensembl: ensure var contains gene_ensembl (best-effort)
      - hugo: if non-human Ensembl IDs, attempt to map to human symbols (HUGO-like)
    """
    # normalize policy (accept Enum-like string reprs)
    policy = str(policy).split(".")[-1].strip().lower()

    if adata is None:
        raise ValueError("AnnData is required")

    summary = detect_gene_style(list(adata.var_names))
    summary.policy_applied = policy

    # best-effort species hint
    inferred = summary.inferred_species
    if not species_hint:
        species_hint = inferred

    # Store detection always
    if write_var_columns:
        if "gene_id" not in adata.var.columns:
            adata.var["gene_id"] = adata.var_names.astype(str)
        adata.var["gene_id_style"] = summary.id_style
        adata.var["gene_ensembl_like"] = [bool(_is_ensembl_id(str(x))) for x in adata.var_names]
        adata.var["gene_symbol_like"] = [bool(_is_symbol_like(str(x))) for x in adata.var_names]

    # Nothing else to do
    if policy == "detect" or summary.id_style == "unknown":
        _write_uns(adata, summary, target=target)
        return summary

    # If symbols already, for symbol policy we just mark
    if summary.id_style in ("symbol", "mixed") and policy in ("symbol",):
        summary.target = "symbol"
        _write_uns(adata, summary, target=summary.target)
        return summary

    # Ensembl -> symbol (same species)
    if summary.id_style in ("ensembl", "mixed") and policy in ("symbol", "hugo"):
        # collect ensembl ids (strip version)
        ens_ids = []
        ens_norm = []
        for g in adata.var_names.astype(str):
            if _is_ensembl_id(g):
                base = g.split(".", 1)[0]
                ens_ids.append(base)
                ens_norm.append(base)
            else:
                ens_norm.append("")
        # map
        mapped = {}
        unmapped = 0

        # If hugo and non-human, try homology; else lookup/id for display_name in same species
        if policy == "hugo" and species_hint and species_hint != "human":
            mapped = map_to_hugo_human(ens_ids, source_species=species_hint) or {}
            summary.target = "hugo"
        else:
            mapped = map_ensembl_to_symbol(ens_ids) or {}
            summary.target = "symbol"

        new_names = []
        for orig, base in zip(adata.var_names.astype(str), ens_norm):
            if base and base in mapped and mapped[base]:
                new_names.append(mapped[base])
                summary.mapped += 1
            else:
                unmapped += 1 if base else 0
                new_names.append(orig if keep_unmapped else "")
        summary.unmapped = unmapped

        if write_var_columns:
            adata.var["gene_symbol"] = [
                mapped.get(g.split(".", 1)[0], "") if _is_ensembl_id(str(g)) else (str(g) if _is_symbol_like(str(g)) else "")
                for g in adata.var_names.astype(str)
            ]
            adata.var["gene_ensembl"] = [
                g.split(".", 1)[0] if _is_ensembl_id(str(g)) else ""
                for g in adata.var_names.astype(str)
            ]
            adata.var["gene_target"] = summary.target

        if rename_var_names:
            try:
                adata.var_names = np.array(new_names, dtype=str)
            except Exception:
                # fallback: don't rename
                warnings.warn("Failed to rename var_names; kept original.")

        _write_uns(adata, summary, target=summary.target)
        return summary

    # Fallback: just annotate
    _write_uns(adata, summary, target=target)
    return summary


def _write_uns(adata, summary: GeneSummary, target: str = "") -> None:
    adata.uns.setdefault("h5adify", {})
    adata.uns["h5adify"].setdefault("genes", {})
    adata.uns["h5adify"]["genes"].update(
        {
            "id_style": summary.id_style,
            "ensembl_rate": summary.ensembl_rate,
            "symbol_rate": summary.symbol_rate,
            "sample_prefix": summary.sample_prefix,
            "inferred_species": summary.inferred_species,
            "policy": summary.policy_applied,
            "target": target or summary.target,
            "mapped": summary.mapped,
            "unmapped": summary.unmapped,
        }
    )


def genes_info_from_adata(adata) -> Dict[str, object]:
    """Return a JSON-serializable gene info dict, using stored uns if present."""
    info = {}
    try:
        info = dict(adata.uns.get("h5adify", {}).get("genes", {}) or {})
    except Exception:
        info = {}
    if not info:
        s = detect_gene_style(list(adata.var_names))
        info = {
            "id_style": s.id_style,
            "ensembl_rate": s.ensembl_rate,
            "symbol_rate": s.symbol_rate,
            "sample_prefix": s.sample_prefix,
            "inferred_species": s.inferred_species,
        }
    return info
