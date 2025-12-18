from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

from ..config import GeneOptions, ObsPolicy


@dataclass
class SearchResult:
    dataset_id: str
    title: str = ""
    source: str = ""
    url: str = ""


class Source(Protocol):
    name: str

    def search(self, query: str, max_results: int = 20) -> List[SearchResult]:
        ...

    def download(
        self,
        *,
        dataset_id: str,
        outdir: str,
        merge_samples: bool = True,
        overrides: Optional[Dict[str, str]] = None,
        obs_policy: ObsPolicy = ObsPolicy(),
        gene_options: Optional[GeneOptions] = None,
    ) -> List[str]:
        ...
