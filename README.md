# nyaa-downloader

Python package to search and download torrents from [nyaa.si](https://nyaa.si).

> **[Documentation en Français](README_FR.md)**

## Installation

```bash
pip install nyaa-downloader
```

On Windows, `libtorrent` (for direct content download) is installed automatically via [`libtorrent-windows-dll`](https://github.com/baseplate-admin/libtorrent-windows-dll).

**Dependencies:** `requests`, `feedparser`, `anitopy`, `libtorrent` (optional on non-Windows, for direct torrent content download)

## Quick Start

```python
from nyaa_downloader import NyaaAnime, Preferences

# Simple search
nyaa = NyaaAnime.search("Jujutsu Kaisen", trusted_only=True)

# Enrich with MAL metadata (seasons, episode counts)
nyaa.enrich_from_mal()

# Get a season
s2 = nyaa.season(2)

# Get episode 1 of season 2
ep1 = s2.get(1)
print(f"Title: {ep1.title}")
print(f"Seeders: {ep1.seeders}")
```

---

## API Reference

### `NyaaAnime`

Main interface for searching anime torrents.

#### `NyaaAnime.search(title, trusted_only=False, category="1_2", max_pages=1, filters=None)`

Search for an anime on Nyaa.

```python
from nyaa_downloader import NyaaAnime, SearchFilters

# Basic search
nyaa = NyaaAnime.search("Sousou no Frieren")

# Search with advanced filters
filters = SearchFilters(
    min_seeders=50,
    resolution="1080p",
    exclude_batches=True
)
nyaa = NyaaAnime.search("Jujutsu Kaisen",
    trusted_only=True,
    max_pages=2,  # More results
    filters=filters
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `title` | `str` | Anime title |
| `trusted_only` | `bool` | Only trusted releases |
| `category` | `str` | Nyaa category (default: `"1_2"` = Anime English) |
| `max_pages` | `int` | Pages to fetch (1 ≈ 75 results) |
| `filters` | `SearchFilters` | Advanced filters |

---

#### `nyaa.enrich_from_mal(mal_id=None)`

Enrich results with MyAnimeList metadata (seasons, episodes).

```python
nyaa = NyaaAnime.search("Jujutsu Kaisen")
nyaa.enrich_from_mal()

print(f"MAL ID: {nyaa.mal_id}")
print(f"Total episodes: {nyaa.total_episodes}")
print(f"Season info: {nyaa._season_episodes_info}")
# Example: {1: (1, 24), 2: (25, 47)} → S1: eps 1-24, S2: eps 25-47
```

---

#### `nyaa.season(season_number)`

Returns results for a given season.

```python
s1 = nyaa.season(1)
s2 = nyaa.season(2)

print(f"S1: {len(s1.episodes)} results")
print(f"S2: {len(s2.episodes)} results")
```

---

#### `nyaa.seasons`

Full mapping `{season_number: SeasonResults}`.

```python
for season_num, season_results in nyaa.seasons.items():
    print(f"Season {season_num}: {len(season_results.episodes)} releases")
```

---

#### `nyaa.to_relative_episode(absolute_ep, season)` / `nyaa.to_absolute_episode(relative_ep, season)`

Convert between absolute and relative episode numbering.

```python
# Jujutsu Kaisen S2 starts at episode 25
nyaa.to_relative_episode(25, 2)  # → 1 (S2E1)
nyaa.to_absolute_episode(1, 2)   # → 25
```

---

#### `nyaa.download_torrent(result, dest_dir="torrents")`

Download the .torrent file.

```python
s2 = nyaa.season(2)
ep1 = s2.get(1)
path = nyaa.download_torrent(ep1, "my_torrents")
```

---

### `SeasonResults`

Results for a given season.

#### `season.get(episode_number, preferences=None)`

Returns the best torrent for an episode.

```python
from nyaa_downloader import Preferences

s2 = nyaa.season(2)

# Best by seeders
ep1 = s2.get(1)

# With preferences
prefs = Preferences(
    preferred_resolution="1080p",
    preferred_release_groups=["SubsPlease", "Erai-raws"],
    min_seeders=10
)
ep1 = s2.get(1, preferences=prefs)
```

---

### `NyaaSearcher`

Low-level client for direct searching.

```python
from nyaa_downloader import NyaaSearcher, SearchFilters

searcher = NyaaSearcher(timeout=60)

# Simple search
results = searcher.search("Frieren", trusted_only=True)

# Paginated search
for page_results in searcher.search_paginated("Jujutsu Kaisen", max_pages=3):
    print(f"Page: {len(page_results)} results")

# Full search
all_results = searcher.search_all("Oshi no ko", max_pages=5)

# With filters
filters = SearchFilters(
    min_seeders=100,
    resolution="1080p",
    exclude_batches=True
)
filtered = searcher.search("Frieren", filters=filters)
```

---

### `SearchFilters`

Advanced search filters.

```python
from nyaa_downloader import SearchFilters
from datetime import datetime

filters = SearchFilters(
    min_seeders=50,              # Minimum seeders
    max_seeders=None,            # Maximum seeders
    min_size_mb=100,             # Minimum size in MB
    max_size_mb=2000,            # Maximum size in MB
    trusted_only=True,           # Trusted only
    batches_only=False,          # Batches only
    exclude_batches=True,        # Exclude batches
    resolution="1080p",          # Preferred resolution
    release_group="SubsPlease",  # Release group
    date_after=datetime(2024, 1, 1),  # After this date
    date_before=None,            # Before this date
)
```

---

### `Preferences`

Preferences for sorting results.

```python
from nyaa_downloader import Preferences

prefs = Preferences(
    preferred_resolution="1080p",           # Preferred resolution
    preferred_release_groups=["SubsPlease"], # Preferred groups
    excluded_release_groups=["HorribleSubs"], # Excluded groups
    min_seeders=10,                         # Minimum seeders
    prefer_trusted=True,                    # Prefer trusted
)

# Score a result
score = prefs.score(result)  # Lower = better

# Sort a list
sorted_results = prefs.sort_results(results)
```

---

### `download_torrent(result, dest_dir, timeout=30, retry_config=None)`

Download a .torrent file.

```python
from nyaa_downloader import download_torrent, RetryConfig

# Simple
path = download_torrent(result, "torrents")

# With custom retry
config = RetryConfig(max_retries=5, base_delay=2.0)
path = download_torrent(result, "torrents", timeout=60, retry_config=config)
```

---

### `TorrentSession` (optional, requires libtorrent)

Direct torrent content download.

```python
from nyaa_downloader import TorrentSession, TorrentConfig, download_torrent_content

# Optimized configuration
config = TorrentConfig(
    connections_limit=300,
    cache_size=1024,  # 16MB cache
    sequential_download=True,  # For streaming
)

# Usage with context manager
with TorrentSession(config) as session:
    handle = session.add_torrent(magnet_link, save_path)

    def on_progress(progress):
        print(f"[{progress.state}] {progress.progress:.1f}% - "
              f"↓{progress.download_rate//1024}KB/s - "
              f"Peers: {progress.num_peers}")

    await session.wait_for_download(handle, on_progress)

# Or directly
await download_torrent_content(magnet_link, "downloads", config)
```

---

### Exceptions

```python
from nyaa_downloader import (
    NyaaError,       # Base exception
    NetworkError,    # Network error (timeout, connection)
    DownloadError,   # Download error
    ParseError,      # RSS parsing error
    RateLimitError,  # API rate limit
    RetryConfig,     # Retry configuration
)

try:
    results = searcher.search("anime")
except NetworkError as e:
    print(f"Network error: {e}")
except ParseError as e:
    print(f"Parse error: {e}")
```

---

## CLI

```bash
# Basic search
nyaa-downloader "Sousou no Frieren"

# Trusted only, download best result
nyaa-downloader "Jujutsu Kaisen" --trusted-only --best

# Limit results
nyaa-downloader "Frieren" --limit 20

# Custom destination folder
nyaa-downloader "Oshi no ko" --dest ./my_torrents
```

---

## Result Structure

### `NyaaResult`

```python
@dataclass
class NyaaResult:
    title: str                    # Full title
    link: str                     # .torrent URL
    magnet: Optional[str]         # Magnet link
    size: str                     # Size (e.g. "1.4 GiB")
    date: str                     # Publication date
    seeders: int                  # Seeder count
    leechers: int                 # Leecher count
    downloads: int                # Total downloads
    trusted: bool                 # Trusted release
    anime_title: Optional[str]    # Parsed anime title
    episode: Optional[str]        # Parsed episode number
    release_group: Optional[str]  # Group (e.g. "SubsPlease")
    resolution: Optional[str]     # Resolution (e.g. "1080p")
    source: Optional[str]         # Source (e.g. "WEB-DL")
    season: Optional[int]         # Detected season
    parsed_episode: ParsedEpisode # Parsed episode object
    is_batch: bool                # Is a batch
```

### `ParsedEpisode`

```python
@dataclass
class ParsedEpisode:
    episode: Optional[int]              # Single episode
    episode_range: Optional[Tuple[int, int]]  # Range (1, 12)
    is_batch: bool                      # Is a batch

    def contains(self, ep: int) -> bool  # Episode is in range
    def episodes(self) -> List[int]      # List of episodes
    def sort_key(self) -> Tuple[int, int]  # For sorting
```

---

## Full Example

```python
from nyaa_downloader import NyaaAnime, Preferences, SearchFilters

# Search with filters
filters = SearchFilters(min_seeders=100, resolution="1080p")
nyaa = NyaaAnime.search("Jujutsu Kaisen",
    trusted_only=True,
    max_pages=2,
    filters=filters
)

# Enrich with MAL
nyaa.enrich_from_mal()
print(f"Detected seasons: {list(nyaa.seasons.keys())}")

# Download preferences
prefs = Preferences(
    preferred_resolution="1080p",
    preferred_release_groups=["SubsPlease"],
)

# Download S2E1
s2 = nyaa.season(2)
ep1 = s2.get(1, preferences=prefs)

if ep1:
    print(f"Choice: {ep1.title}")
    print(f"Group: {ep1.release_group}")
    print(f"Resolution: {ep1.resolution}")
    print(f"Seeders: {ep1.seeders}")

    # Download
    path = nyaa.download_torrent(ep1, "torrents")
    print(f"Downloaded: {path}")
```