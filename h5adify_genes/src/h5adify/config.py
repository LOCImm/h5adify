from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ObsMode(str, Enum):
    loose = "loose"
    strict = "strict"


@dataclass
class ObsPolicy:
    """Controls how strictly we enforce standardized obs keys."""
    mode: ObsMode = ObsMode.loose

    def __str__(self) -> str:
        return str(self.mode.value)


class GenePolicy(str, Enum):
    detect = "detect"   # detect + annotate only
    symbol = "symbol"   # best-effort annotate symbol fields
    ensembl = "ensembl" # best-effort annotate ensembl fields
    hugo = "hugo"       # map to human gene symbols when possible


@dataclass
class GeneOptions:
    policy: GenePolicy = GenePolicy.detect
    rename_var_names: bool = False
    write_var_columns: bool = True
    keep_unmapped: bool = True
    species_hint: str = ""
