from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import List, Optional, Dict

from .download import download_torrent
from .search import NyaaResult, NyaaSearcher, SearchFilters
from .parsing_utils import compare_episodes, normalize_episode_number
from .preferences import Preferences


@dataclass
class SeasonResults:
    """Results for a given season of an anime."""

    season: Optional[int]
    episodes: List[NyaaResult]

    def get(
        self, 
        episode_number: int, 
        preferences: Optional[Preferences] = None,
        relative_numbering: bool = True,
    ) -> Optional[NyaaResult]:
        """
        Return the best result for the requested episode.

        Also supports batches that contain the requested episode.

        :param episode_number: Episode number
        :param preferences: Sorting preferences (optional)
        :param relative_numbering: If True, search for season-relative episode (S2E1).
                                   If False, search using continuous numbering.
        """
        candidates = []
        for r in self.episodes:
            if r.parsed_episode.contains(episode_number):
                candidates.append(r)
            elif r.episode is not None and compare_episodes(r.episode, episode_number):
                candidates.append(r)
        if not candidates:
            return None
        
        if preferences:
            return min(candidates, key=preferences.score)
        return max(candidates, key=lambda r: r.seeders)

    def download_torrent(self, episode_number: int, dest_dir: str | None = None):
        """
        Download the .torrent for the requested episode in this season block.

        :param episode_number: episode number (1, 2, 3, ...)
        :param dest_dir: destination folder, defaults to "torrents".
        :return: path to the downloaded .torrent file, or None if no match.
        """
        dest_dir = dest_dir or "torrents"
        choice = self.get(episode_number)
        if choice is None:
            return None
        return download_torrent(choice, dest_dir)


class NyaaAnime:
    """
    High-level interface for searching anime on Nyaa
    and navigating by season/episodes.

    Example:

        nyaa = NyaaAnime.search("Sousou no Frieren")
        nyaa.enrich_from_mal()
        s2 = nyaa.season(2)
        choice = s2.get(1)  # episode 1 of season 2 (relative)
        nyaa.download_torrent(choice)
    """

    def __init__(self, title: str, results: List[NyaaResult]):
        self.title = title
        self.results = results
        self._mal_id: Optional[int] = None
        self._total_episodes: Optional[int] = None
        self._season_mapping: Dict[int, int] = {}
        self._episode_ranges: List[tuple] = []
        self._season_episodes_info: Dict[int, tuple] = {}  # {season: (start_ep, end_ep)}

    @classmethod
    def search(
        cls,
        title: str,
        trusted_only: bool = False,
        category: str = "1_2",
        max_pages: int = 1,
        filters: Optional[SearchFilters] = None,
    ) -> "NyaaAnime":
        """
        Search for a given title and return a `NyaaAnime` wrapper.

        :param title: Anime title
        :param trusted_only: Only trusted releases
        :param category: Nyaa category
        :param max_pages: Number of pages to fetch (1 = ~75 results)
        :param filters: Advanced filters
        """
        searcher = NyaaSearcher()
        if max_pages > 1:
            results = searcher.search_all(
                title, 
                max_pages=max_pages,
                trusted_only=trusted_only, 
                category=category,
                filters=filters,
            )
        else:
            results = searcher.search(
                title, 
                trusted_only=trusted_only, 
                category=category,
                filters=filters,
            )
        return cls(title=title, results=results)

    @property
    def mal_id(self) -> Optional[int]:
        return self._mal_id

    @property
    def total_episodes(self) -> Optional[int]:
        return self._total_episodes

    def enrich_from_mal(self, mal_id: Optional[int] = None) -> "NyaaAnime":
        """
        Enrich metadata from the MyAnimeList API via Jikan.

        :param mal_id: Optional MAL ID. If None, searches automatically.
        :return: self for chaining
        """
        from .metadata import get_anime_metadata, build_season_mapping
        metadata = get_anime_metadata(self.title, mal_id)
        if metadata:
            self._mal_id = metadata.mal_id
            self._total_episodes = metadata.episodes
        
        self._season_mapping = build_season_mapping(self.title, mal_id)
        self._build_episode_ranges()
        return self

    def _build_episode_ranges(self) -> None:
        """Build episode ranges per season."""
        season_episodes: Dict[Optional[int], List[int]] = {}
        orphan_episodes: List[int] = []
        
        for r in self.results:
            if r.season is not None:
                ep_num = normalize_episode_number(r.episode)
                if ep_num is not None:
                    if r.season not in season_episodes:
                        season_episodes[r.season] = []
                    season_episodes[r.season].append(ep_num)
                
                if r.parsed_episode.episode_range:
                    if r.season not in season_episodes:
                        season_episodes[r.season] = []
                    for ep in r.parsed_episode.episodes:
                        season_episodes[r.season].append(ep)
            else:
                ep_num = normalize_episode_number(r.episode)
                if ep_num is None and r.parsed_episode.episode:
                    ep_num = r.parsed_episode.episode
                if ep_num is not None:
                    orphan_episodes.append(ep_num)
        
        ranges = []
        for season, episodes in season_episodes.items():
            if season is not None and episodes:
                min_ep = min(episodes)
                max_ep = max(episodes)
                ranges.append((season, min_ep, max_ep))
        
        ranges.sort(key=lambda x: x[0])
        
        if orphan_episodes and ranges:
            orphan_min = min(orphan_episodes)
            orphan_max = max(orphan_episodes)
            last_season = max(r[0] for r in ranges)
            known_max = max(r[2] for r in ranges if r[0] == last_season)
            if orphan_min > known_max:
                for i, r in enumerate(ranges):
                    if r[0] == last_season:
                        ranges[i] = (r[0], r[1], orphan_max)
                        break
        
        ranges.sort(key=lambda x: x[1])
        
        if not ranges:
            for ep_num, season in self._season_mapping.items():
                if season not in [r[0] for r in ranges]:
                    ranges.append((season, ep_num, ep_num))
                else:
                    for i, (s, min_ep, max_ep) in enumerate(ranges):
                        if s == season:
                            ranges[i] = (s, min(min_ep, ep_num), max(max_ep, ep_num))
                            break
            ranges.sort(key=lambda x: x[1])
        
        self._episode_ranges = ranges
        
        self._season_episodes_info = {}
        current_ep = 1
        sorted_seasons = sorted(set(self._season_mapping.values()))
        for season in sorted_seasons:
            season_eps = [ep for ep, s in self._season_mapping.items() if s == season]
            if season_eps:
                start = min(season_eps)
                end = max(season_eps)
                self._season_episodes_info[season] = (start, end)

    def _infer_season(self, result: NyaaResult) -> Optional[int]:
        """Infer season from episode number if not detected in title."""
        if result.season is not None:
            return result.season
        
        ep_num = normalize_episode_number(result.episode)
        if ep_num is None and result.parsed_episode.episode:
            ep_num = result.parsed_episode.episode
        
        if ep_num is None:
            return None
        
        if ep_num in self._season_mapping:
            return self._season_mapping[ep_num]
        
        for season, min_ep, max_ep in self._episode_ranges:
            if min_ep <= ep_num <= max_ep:
                return season
        
        if self._episode_ranges:
            sorted_ranges = sorted(self._episode_ranges, key=lambda x: x[1])
            if ep_num < sorted_ranges[0][1]:
                return sorted_ranges[0][0]
            if ep_num > sorted_ranges[-1][2]:
                return sorted_ranges[-1][0]
        
        return None
    
    def to_relative_episode(self, absolute_ep: int, season: int) -> Optional[int]:
        """
        Convert an absolute episode number to a season-relative number.

        :param absolute_ep: Absolute episode number (e.g. 25 for S2E1 of JJK)
        :param season: Season number
        :return: Season-relative episode number, or None
        """
        if season in self._season_episodes_info:
            start, end = self._season_episodes_info[season]
            if start <= absolute_ep <= end:
                return absolute_ep - start + 1
        return None
    
    def to_absolute_episode(self, relative_ep: int, season: int) -> Optional[int]:
        """
        Convert a season-relative episode number to an absolute number.

        :param relative_ep: Season-relative episode number (e.g. 1 for S2E1)
        :param season: Season number
        :return: Absolute episode number, or None
        """
        if season in self._season_episodes_info:
            start, end = self._season_episodes_info[season]
            absolute = start + relative_ep - 1
            if absolute <= end:
                return absolute
        return None

    def _group_by_season(self) -> dict[Optional[int], List[NyaaResult]]:
        groups: dict[Optional[int], List[NyaaResult]] = {}
        for r in self.results:
            season_int = self._infer_season(r)
            groups.setdefault(season_int, []).append(r)
        return groups

    @cached_property
    def seasons(self) -> dict[Optional[int], SeasonResults]:
        """Return a mapping {season_number -> SeasonResults}."""
        grouped = self._group_by_season()
        return {
            season: SeasonResults(season=season, episodes=sorted(group, key=lambda r: r.parsed_episode.sort_key()))
            for season, group in grouped.items()
        }

    def season(self, season_number: Optional[int] = None) -> SeasonResults:
        """
        Return results for a given season.

        - if `season_number` is None: group everything without a season.
        - otherwise: return the corresponding key.
        """
        if season_number not in self.seasons:
            return SeasonResults(season=season_number, episodes=[])
        return self.seasons[season_number]

    def download_torrent(self, result: NyaaResult, dest_dir: str | None = None):
        """
        Download the .torrent for a given result.

        :param result: NyaaResult object to download.
        :param dest_dir: destination folder, defaults to "torrents".
        """
        dest_dir = dest_dir or "torrents"
        return download_torrent(result, dest_dir)

