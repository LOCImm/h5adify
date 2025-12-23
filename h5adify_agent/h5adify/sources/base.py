from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, runtime_checkable

@dataclass
class SearchResult:
    source: str
    dataset_id: str
    title: str
    description: str = ""
    url: str = ""
    extra: Dict[str, str] | None = None


@runtime_checkable
class Source(Protocol):
    def search(self, query: str, max_results: int = 20) -> List[SearchResult]:
        ...

    def download(
        self,
        dataset_id: str,
        outdir: str,
        merge_samples: bool = True,
        overrides: Optional[Dict[str, str]] = None,
        cleanup: bool = True,
    ) -> List[str]:
        ...
