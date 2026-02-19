from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from .search import NyaaResult


RESOLUTION_PRIORITY = {
    "4k": 0,
    "2160p": 0,
    "1080p": 1,
    "720p": 2,
    "480p": 3,
    "360p": 4,
}


@dataclass
class Preferences:
    """
    Preferences for sorting/selecting torrents.
    
    Priority order: resolution > release_group > seeders
    """
    preferred_resolution: Optional[str] = None
    preferred_release_groups: List[str] = field(default_factory=list)
    excluded_release_groups: List[str] = field(default_factory=list)
    min_seeders: int = 0
    prefer_trusted: bool = True

    def _normalize_resolution(self, res: Optional[str]) -> int:
        if not res:
            return 99
        res_lower = res.lower().strip()
        return RESOLUTION_PRIORITY.get(res_lower, 50)

    def score(self, result: NyaaResult) -> tuple:
        """
        Compute a score for a result. Lower score = better.
        
        Returns: tuple for comparison (resolution_score, group_score, trusted_score, seeder_score)
        """
        res_score = self._normalize_resolution(result.resolution)
        
        if self.preferred_resolution:
            preferred_norm = self._normalize_resolution(self.preferred_resolution)
            res_score = abs(res_score - preferred_norm)

        group_score = 10
        if result.release_group:
            group_lower = result.release_group.lower()
            if group_lower in [g.lower() for g in self.excluded_release_groups]:
                return (999, 999, 999, 999)
            if group_lower in [g.lower() for g in self.preferred_release_groups]:
                group_score = 0

        trusted_score = 0 if result.trusted else 1
        if self.prefer_trusted:
            trusted_score = 0 if result.trusted else 5

        seeder_score = -result.seeders

        if result.seeders < self.min_seeders:
            return (999, 999, 999, 999)

        return (res_score, group_score, trusted_score, seeder_score)

    def sort_results(self, results: List[NyaaResult]) -> List[NyaaResult]:
        """Sort results according to preferences."""
        return sorted(results, key=self.score)
