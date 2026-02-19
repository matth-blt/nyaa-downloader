from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Iterator

import anitopy
import feedparser

from .parsing_utils import parse_episode, parse_season, ParsedEpisode
from .errors import NetworkError, ParseError, RetryConfig, retry_with_backoff


DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_CONFIG = RetryConfig(max_retries=3, base_delay=1.0)
RSS_PAGE_SIZE = 75  # Nyaa RSS returns ~75 items per page


@dataclass
class SearchFilters:
    """Advanced search filters."""
    min_seeders: int = 0
    max_seeders: Optional[int] = None
    min_size_mb: Optional[float] = None
    max_size_mb: Optional[float] = None
    trusted_only: bool = False
    batches_only: bool = False
    exclude_batches: bool = False
    resolution: Optional[str] = None
    release_group: Optional[str] = None
    date_after: Optional[datetime] = None
    date_before: Optional[datetime] = None

    def matches(self, result: NyaaResult) -> bool:
        if result.seeders < self.min_seeders:
            return False
        if self.max_seeders and result.seeders > self.max_seeders:
            return False
        if self.trusted_only and not result.trusted:
            return False
        if self.batches_only and not result.is_batch:
            return False
        if self.exclude_batches and result.is_batch:
            return False
        if self.resolution and result.resolution:
            if self.resolution.lower() not in result.resolution.lower():
                return False
        if self.release_group and result.release_group:
            if self.release_group.lower() not in result.release_group.lower():
                return False
        if self.min_size_mb or self.max_size_mb:
            size_mb = _parse_size_to_mb(result.size)
            if size_mb is not None:
                if self.min_size_mb and size_mb < self.min_size_mb:
                    return False
                if self.max_size_mb and size_mb > self.max_size_mb:
                    return False
        if self.date_after or self.date_before:
            try:
                result_date = datetime.strptime(result.date, "%a, %d %b %Y %H:%M:%S %z")
                if self.date_after and result_date < self.date_after:
                    return False
                if self.date_before and result_date > self.date_before:
                    return False
            except (ValueError, TypeError):
                pass
        return True


def _parse_size_to_mb(size_str: str) -> Optional[float]:
    """Parse size string like '1.4 GiB' to MB."""
    if not size_str or size_str == "?":
        return None
    try:
        parts = size_str.strip().split()
        if len(parts) != 2:
            return None
        value = float(parts[0])
        unit = parts[1].upper()
        multipliers = {
            "B": 1 / (1024 * 1024),
            "KB": 1 / 1024,
            "KIB": 1 / 1024,
            "MB": 1,
            "MIB": 1,
            "GB": 1024,
            "GIB": 1024,
            "TB": 1024 * 1024,
            "TIB": 1024 * 1024,
        }
        for k, v in multipliers.items():
            if unit.startswith(k):
                return value * v
        return None
    except (ValueError, IndexError):
        return None


@dataclass
class NyaaResult:
    """Represents a Nyaa search result."""

    title: str
    link: str  # .torrent download URL
    magnet: Optional[str]  # Magnet link
    size: str
    date: str
    seeders: int
    leechers: int
    downloads: int
    trusted: bool
    anime_title: Optional[str] = None
    episode: Optional[str] = None
    release_group: Optional[str] = None
    resolution: Optional[str] = None
    source: Optional[str] = None
    season: Optional[int] = None
    parsed_episode: ParsedEpisode = field(default_factory=ParsedEpisode)
    is_batch: bool = False


class NyaaSearcher:
    """Client for searching torrents on nyaa.si via RSS feed."""

    RSS_URL = "https://nyaa.si/?page=rss&q={query}&c={category}&f={filter}&p={page}"

    def __init__(
        self, 
        timeout: int = DEFAULT_TIMEOUT,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.timeout = timeout
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG

    def _fetch_feed(self, url: str):
        """Fetch and parse RSS feed with error handling."""
        import requests
        from requests.exceptions import Timeout, ConnectionError as ReqConnectionError, HTTPError
        
        def _do_fetch():
            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return feedparser.parse(resp.content)
            except Timeout:
                raise NetworkError(f"Timeout fetching {url}")
            except ReqConnectionError as e:
                raise NetworkError(f"Connection error: {e}")
            except HTTPError as e:
                raise NetworkError(f"HTTP {e.response.status_code}")
        
        return retry_with_backoff(_do_fetch, config=self.retry_config)

    def _validate_feed(self, feed) -> None:
        """Validate RSS feed structure."""
        if hasattr(feed, 'bozo') and feed.bozo:
            if feed.bozo_exception:
                raise ParseError(f"Invalid RSS feed: {feed.bozo_exception}")

    def _parse_entry(self, entry) -> Optional[NyaaResult]:
        """Parse a single RSS entry into NyaaResult."""
        if not hasattr(entry, 'title') or not hasattr(entry, 'link'):
            return None
            
        parsed: dict = anitopy.parse(entry.title) or {}

        info_hash = entry.get("nyaa_infohash")
        magnet: Optional[str] = None
        if info_hash:
            magnet = (
                f"magnet:?xt=urn:btih:{info_hash}"
                f"&dn={urllib.parse.quote(entry.title)}"
                "&tr=http%3A%2F%2Fnyaa.tracker.wf%3A7777%2Fannounce"
                "&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce"
                "&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce"
                "&tr=udp%3A%2F%2Fexodus.desync.com%3A6969%2Fannounce"
                "&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce"
            )

        seeders = int(entry.get("nyaa_seeders", 0))
        leechers = int(entry.get("nyaa_leechers", 0))
        downloads = int(entry.get("nyaa_downloads", 0))
        size = entry.get("nyaa_size", "?")
        trusted = entry.get("nyaa_trusted", "No") == "Yes"

        parsed_ep = parse_episode(entry.title)
        season = parse_season(entry.title)
        anitopy_season = parsed.get("season")
        if season is None and anitopy_season is not None:
            try:
                season = int(str(anitopy_season))
            except (ValueError, TypeError):
                pass

        return NyaaResult(
            title=entry.title,
            link=entry.link,
            magnet=magnet,
            size=size,
            date=entry.published,
            seeders=seeders,
            leechers=leechers,
            downloads=downloads,
            trusted=trusted,
            anime_title=parsed.get("anime_title"),
            episode=parsed.get("episode_number"),
            release_group=parsed.get("release_group"),
            resolution=parsed.get("video_resolution"),
            source=parsed.get("source"),
            season=season,
            parsed_episode=parsed_ep,
            is_batch=parsed_ep.is_batch,
        )

    def search(
        self,
        query: str,
        trusted_only: bool = False,
        category: str = "1_2",
        filters: Optional[SearchFilters] = None,
    ) -> List[NyaaResult]:
        """
        Search Nyaa and return a list of parsed results.

        :param query: search term (anime title, release group, etc.).
        :param trusted_only: if True, only return "trusted" uploads.
        :param category: Nyaa category code (default: 1_2 = Anime English-sub).
        :param filters: optional advanced filters.
        :raises NetworkError: on network issues.
        :raises ParseError: if the RSS feed is invalid.
        """
        encoded_query = urllib.parse.quote(query)
        filter_code = "2" if trusted_only else "0"
        url = self.RSS_URL.format(
            query=encoded_query, 
            category=category, 
            filter=filter_code,
            page=1
        )

        feed = self._fetch_feed(url)
        self._validate_feed(feed)
        results: List[NyaaResult] = []

        for entry in getattr(feed, "entries", []):
            result = self._parse_entry(entry)
            if result:
                if filters is None or filters.matches(result):
                    results.append(result)

        return results

    def search_paginated(
        self,
        query: str,
        max_pages: int = 3,
        trusted_only: bool = False,
        category: str = "1_2",
        filters: Optional[SearchFilters] = None,
    ) -> Iterator[List[NyaaResult]]:
        """
        Paginated search on Nyaa.

        :param query: search term.
        :param max_pages: maximum number of pages to fetch.
        :param trusted_only: if True, only return "trusted" uploads.
        :param category: Nyaa category code.
        :param filters: optional advanced filters.
        :yields: List of results for each page.
        """
        encoded_query = urllib.parse.quote(query)
        filter_code = "2" if trusted_only else "0"

        for page in range(1, max_pages + 1):
            url = self.RSS_URL.format(
                query=encoded_query,
                category=category,
                filter=filter_code,
                page=page
            )
            
            feed = self._fetch_feed(url)
            self._validate_feed(feed)
            
            page_results: List[NyaaResult] = []
            entries = getattr(feed, "entries", [])
            
            if not entries:
                break
            
            for entry in entries:
                result = self._parse_entry(entry)
                if result:
                    if filters is None or filters.matches(result):
                        page_results.append(result)
            
            yield page_results
            
            if len(entries) < RSS_PAGE_SIZE:
                break

    def search_all(
        self,
        query: str,
        max_pages: int = 5,
        trusted_only: bool = False,
        category: str = "1_2",
        filters: Optional[SearchFilters] = None,
    ) -> List[NyaaResult]:
        """
        Search all available pages.

        :param query: search term.
        :param max_pages: maximum number of pages to fetch.
        :param trusted_only: if True, only return "trusted" uploads.
        :param category: Nyaa category code.
        :param filters: optional advanced filters.
        :return: All combined results.
        """
        all_results: List[NyaaResult] = []
        for page_results in self.search_paginated(
            query, max_pages, trusted_only, category, filters
        ):
            all_results.extend(page_results)
        return all_results

