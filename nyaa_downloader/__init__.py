"""
Package `nyaa_downloader`
=========================

Python client to search for torrents on `nyaa.si`
and download the associated `.torrent` files.
"""

from .search import NyaaSearcher, NyaaResult, SearchFilters
from .download import download_torrent
from .anime import NyaaAnime, SeasonResults
from .preferences import Preferences
from .metadata import AnimeMetadata, get_anime_metadata, get_jikan_client, build_season_mapping
from .errors import (
    NyaaError,
    NetworkError,
    DownloadError,
    ParseError,
    RateLimitError,
    RetryConfig,
)

try:
    from .torrent_session import (
        TorrentSession,
        TorrentConfig,
        DownloadProgress,
        download_torrent_content,
        LIBTORRENT_AVAILABLE,
    )
except ImportError:
    LIBTORRENT_AVAILABLE = False
    TorrentSession = None  # type: ignore
    TorrentConfig = None  # type: ignore
    DownloadProgress = None  # type: ignore
    download_torrent_content = None  # type: ignore

__all__ = [
    "NyaaSearcher",
    "NyaaResult",
    "SearchFilters",
    "download_torrent",
    "NyaaAnime",
    "SeasonResults",
    "Preferences",
    "AnimeMetadata",
    "get_anime_metadata",
    "get_jikan_client",
    "NyaaError",
    "NetworkError",
    "DownloadError",
    "ParseError",
    "RateLimitError",
    "RetryConfig",
    "TorrentSession",
    "TorrentConfig",
    "DownloadProgress",
    "download_torrent_content",
    "LIBTORRENT_AVAILABLE",
    "build_season_mapping",
]


