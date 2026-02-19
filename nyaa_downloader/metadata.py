from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict

import requests

from .errors import NetworkError, RateLimitError, RetryConfig, retry_with_backoff


DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_CONFIG = RetryConfig(max_retries=3, base_delay=0.5)


@dataclass
class AnimeMetadata:
    mal_id: int
    title: str
    title_english: Optional[str]
    title_japanese: Optional[str]
    episodes: Optional[int]
    status: str
    year: Optional[int]
    season: Optional[str]
    synopsis: Optional[str]
    relations: List[dict] = field(default_factory=list)


@dataclass  
class SeasonInfo:
    """Info about a specific season."""
    season_number: int
    mal_id: int
    title: str
    start_episode: int
    end_episode: int
    total_episodes: int


class JikanClient:
    BASE_URL = "https://api.jikan.moe/v4"
    
    def __init__(
        self, 
        timeout: int = DEFAULT_TIMEOUT,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.session = requests.Session()
        self._last_req = 0.0
        self.timeout = timeout
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG

    def _rate_limit(self):
        now = time.time()
        elapsed = now - self._last_req
        if elapsed < 0.4:
            time.sleep(0.4 - elapsed)
        self._last_req = time.time()

    def _make_request(self, url: str, params: Optional[dict] = None) -> dict:
        """Make HTTP request with error handling."""
        from requests.exceptions import Timeout, ConnectionError, HTTPError
        
        def _do_request():
            self._rate_limit()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Timeout:
                raise NetworkError(f"Timeout fetching {url}")
            except ConnectionError as e:
                raise NetworkError(f"Connection error: {e}")
            except HTTPError as e:
                if e.response.status_code == 429:
                    retry_after = float(e.response.headers.get('Retry-After', 1.0))
                    raise RateLimitError(retry_after)
                raise NetworkError(f"HTTP {e.response.status_code}")
        
        return retry_with_backoff(_do_request, config=self.retry_config)

    def search_anime(self, query: str, limit: int = 5) -> list[dict]:
        data = self._make_request(f"{self.BASE_URL}/anime", {"q": query, "limit": limit})
        return data.get("data", [])

    def get_anime(self, mal_id: int) -> Optional[dict]:
        data = self._make_request(f"{self.BASE_URL}/anime/{mal_id}")
        return data.get("data")

    def get_relations(self, mal_id: int) -> List[dict]:
        """Get anime relations (sequels, prequels, etc.)."""
        data = self._make_request(f"{self.BASE_URL}/anime/{mal_id}/relations")
        return data.get("data", [])


_jikan_client: Optional[JikanClient] = None


def get_jikan_client() -> JikanClient:
    global _jikan_client
    if _jikan_client is None:
        _jikan_client = JikanClient()
    return _jikan_client


def build_season_mapping(title: str, main_mal_id: Optional[int] = None) -> Dict[int, int]:
    """
    Build an episode_number -> season_number mapping using MAL relations.
    
    :param title: Anime title
    :param main_mal_id: MAL ID of the first season (optional)
    :return: Dict {episode_number: season_number}
    """
    client = get_jikan_client()
    mapping: Dict[int, int] = {}
    
    EXCLUDED_TYPES = ["movie", "special", "ova", "ona", "music", "cm", "pv", "tv_special"]
    
    def is_tv_series(anime_data: dict) -> bool:
        """Check if anime is a TV series (not movie, OVA, etc.)."""
        anime_type = anime_data.get("type", "").lower()
        return anime_type not in EXCLUDED_TYPES and anime_type == "tv"
    
    try:
        if main_mal_id:
            main_anime = client.get_anime(main_mal_id)
            if not main_anime:
                return mapping
        else:
            results = client.search_anime(title, limit=1)
            if not results:
                return mapping
            main_anime = results[0]
        
        main_id = main_anime["mal_id"]
        main_episodes = main_anime.get("episodes") or 0
        
        seasons = [(1, main_id, main_episodes, main_anime.get("title", ""))]
        
        relations = client.get_relations(main_id)
        for rel in relations:
            rel_type = rel.get("relation", "").lower()
            if rel_type in ["sequel", "prequel", "parent story", "side story"]:
                for entry in rel.get("entry", []):
                    if entry.get("type") == "anime":
                        anime_id = entry["mal_id"]
                        try:
                            anime_data = client.get_anime(anime_id)
                            if anime_data and is_tv_series(anime_data):
                                ep_count = anime_data.get("episodes") or 0
                                if ep_count > 0:
                                    if rel_type in ["sequel", "parent story"]:
                                        seasons.append((len(seasons) + 1, anime_id, ep_count, anime_data.get("title", "")))
                                    elif rel_type == "prequel":
                                        prequel_type = anime_data.get("type", "").lower()
                                        if prequel_type == "tv":
                                            seasons.insert(0, (0, anime_id, ep_count, anime_data.get("title", "")))
                        except Exception:
                            pass
        
        seasons.sort(key=lambda x: x[0])
        seasons = [(i + 1, sid, eps, ttl) for i, (_, sid, eps, ttl) in enumerate(seasons)]
        
        current_ep = 1
        for season_num, mal_id, ep_count, season_title in seasons:
            if ep_count > 0:
                for ep in range(current_ep, current_ep + ep_count):
                    mapping[ep] = season_num
                current_ep += ep_count
                
    except Exception:
        pass
    
    return mapping


def get_anime_metadata(title: str, mal_id: Optional[int] = None) -> Optional[AnimeMetadata]:
    """
    Retrieve anime metadata from the Jikan API.
    
    :param title: Anime title to search for
    :param mal_id: Optional MAL ID to skip the search step
    :return: AnimeMetadata or None if not found
    """
    client = get_jikan_client()
    
    try:
        if mal_id:
            data = client.get_anime(mal_id)
        else:
            results = client.search_anime(title, limit=1)
            if not results:
                return None
            data = results[0]
        
        if not data:
            return None
            
        return AnimeMetadata(
            mal_id=data["mal_id"],
            title=data.get("title", ""),
            title_english=data.get("title_english"),
            title_japanese=data.get("title_japanese"),
            episodes=data.get("episodes"),
            status=data.get("status", ""),
            year=data.get("year"),
            season=data.get("season"),
            synopsis=data.get("synopsis"),
        )
    except (NetworkError, RateLimitError):
        return None
