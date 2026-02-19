# nyaa-downloader

Package Python pour rechercher et télécharger des torrents depuis [nyaa.si](https://nyaa.si).

## Installation

```bash
pip install nyaa-downloader
```

**Dépendances:** `requests`, `feedparser`, `anitopy`, `libtorrent` (optionnel, pour téléchargement direct)

## Quick Start

```python
from nyaa_downloader import NyaaAnime, Preferences

# Recherche simple
nyaa = NyaaAnime.search("Jujutsu Kaisen", trusted_only=True)

# Enrichir avec les métadonnées MAL (saisons, nombre d'épisodes)
nyaa.enrich_from_mal()

# Récupérer une saison
s2 = nyaa.saison(2)

# Récupérer l'épisode 1 de la saison 2
ep1 = s2.get(1)
print(f"Titre: {ep1.title}")
print(f"Seeders: {ep1.seeders}")
```

---

## API Reference

### `NyaaAnime`

Interface principale pour rechercher un anime.

#### `NyaaAnime.search(title, trusted_only=False, category="1_2", max_pages=1, filters=None)`

Recherche un anime sur Nyaa.

```python
from nyaa_downloader import NyaaAnime, SearchFilters

# Recherche basique
nyaa = NyaaAnime.search("Sousou no Frieren")

# Recherche avec filtres avancés
filters = SearchFilters(
    min_seeders=50,
    resolution="1080p",
    exclude_batches=True
)
nyaa = NyaaAnime.search("Jujutsu Kaisen", 
    trusted_only=True, 
    max_pages=2,  # Plus de résultats
    filters=filters
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `title` | `str` | Titre de l'anime |
| `trusted_only` | `bool` | Seulement les releases trusted |
| `category` | `str` | Catégorie Nyaa (défaut: "1_2" = Anime English) |
| `max_pages` | `int` | Pages à récupérer (1 ≈ 75 résultats) |
| `filters` | `SearchFilters` | Filtres avancés |

---

#### `nyaa.enrich_from_mal(mal_id=None)`

Enrichit avec les métadonnées MyAnimeList (saisons, épisodes).

```python
nyaa = NyaaAnime.search("Jujutsu Kaisen")
nyaa.enrich_from_mal()

print(f"MAL ID: {nyaa.mal_id}")
print(f"Total episodes: {nyaa.total_episodes}")
print(f"Saison info: {nyaa._season_episodes_info}")
# Exemple: {1: (1, 24), 2: (25, 47)} → S1: eps 1-24, S2: eps 25-47
```

---

#### `nyaa.saison(season_number)`

Retourne les résultats pour une saison.

```python
s1 = nyaa.saison(1)
s2 = nyaa.saison(2)

print(f"S1: {len(s1.episodes)} résultats")
print(f"S2: {len(s2.episodes)} résultats")
```

---

#### `nyaa.saisons`

Mapping complet `{season_number: SeasonResults}`.

```python
for season_num, season_results in nyaa.saisons.items():
    print(f"Saison {season_num}: {len(season_results.episodes)} releases")
```

---

#### `nyaa.to_relative_episode(absolute_ep, season)` / `nyaa.to_absolute_episode(relative_ep, season)`

Conversion entre numérotation absolue et relative.

```python
# Jujutsu Kaisen S2 commence à l'épisode 25
nyaa.to_relative_episode(25, 2)  # → 1 (S2E1)
nyaa.to_absolute_episode(1, 2)   # → 25
```

---

#### `nyaa.download_torrent(result, dest_dir="torrents")`

Télécharge le fichier .torrent.

```python
s2 = nyaa.saison(2)
ep1 = s2.get(1)
path = nyaa.download_torrent(ep1, "my_torrents")
```

---

### `SeasonResults`

Résultats pour une saison donnée.

#### `season.get(episode_number, preferences=None)`

Retourne le meilleur torrent pour un épisode.

```python
from nyaa_downloader import Preferences

s2 = nyaa.saison(2)

# Meilleur par seeders
ep1 = s2.get(1)

# Avec préférences
prefs = Preferences(
    preferred_resolution="1080p",
    preferred_release_groups=["SubsPlease", "Erai-raws"],
    min_seeders=10
)
ep1 = s2.get(1, preferences=prefs)
```

---

### `NyaaSearcher`

Client bas-niveau pour rechercher directement.

```python
from nyaa_downloader import NyaaSearcher, SearchFilters

searcher = NyaaSearcher(timeout=60)

# Recherche simple
results = searcher.search("Frieren", trusted_only=True)

# Recherche paginée
for page_results in searcher.search_paginated("Jujutsu Kaisen", max_pages=3):
    print(f"Page: {len(page_results)} résultats")

# Recherche complète
all_results = searcher.search_all("Oshi no ko", max_pages=5)

# Avec filtres
filters = SearchFilters(
    min_seeders=100,
    resolution="1080p",
    exclude_batches=True
)
filtered = searcher.search("Frieren", filters=filters)
```

---

### `SearchFilters`

Filtres avancés pour la recherche.

```python
from nyaa_downloader import SearchFilters
from datetime import datetime

filters = SearchFilters(
    min_seeders=50,              # Minimum de seeders
    max_seeders=None,            # Maximum de seeders
    min_size_mb=100,             # Taille minimum
    max_size_mb=2000,            # Taille maximum
    trusted_only=True,           # Seulement trusted
    batches_only=False,          # Seulement les batches
    exclude_batches=True,        # Exclure les batches
    resolution="1080p",          # Résolution préférée
    release_group="SubsPlease",  # Release group
    date_after=datetime(2024, 1, 1),  # Après cette date
    date_before=None,            # Avant cette date
)
```

---

### `Preferences`

Préférences pour le tri des résultats.

```python
from nyaa_downloader import Preferences

prefs = Preferences(
    preferred_resolution="1080p",           # Résolution préférée
    preferred_release_groups=["SubsPlease"], # Groups préférés
    excluded_release_groups=["HorribleSubs"], # Groups exclus
    min_seeders=10,                         # Minimum seeders
    prefer_trusted=True,                    # Préférer trusted
)

# Scorer un résultat
score = prefs.score(result)  # Plus bas = meilleur

# Trier une liste
sorted_results = prefs.sort_results(results)
```

---

### `download_torrent(result, dest_dir, timeout=30, retry_config=None)`

Télécharge un fichier .torrent.

```python
from nyaa_downloader import download_torrent, RetryConfig

# Simple
path = download_torrent(result, "torrents")

# Avec retry personnalisé
config = RetryConfig(max_retries=5, base_delay=2.0)
path = download_torrent(result, "torrents", timeout=60, retry_config=config)
```

---

### `TorrentSession` (optionnel, nécessite libtorrent)

Téléchargement direct du contenu torrent.

```python
from nyaa_downloader import TorrentSession, TorrentConfig, download_torrent_content

# Configuration optimisée
config = TorrentConfig(
    connections_limit=300,
    cache_size=1024,  # 16MB cache
    sequential_download=True,  # Pour streaming
)

# Usage avec context manager
with TorrentSession(config) as session:
    handle = session.add_torrent(magnet_link, save_path)
    
    def on_progress(progress):
        print(f"[{progress.state}] {progress.progress:.1f}% - "
              f"↓{progress.download_rate//1024}KB/s - "
              f"Peers: {progress.num_peers}")
    
    await session.wait_for_download(handle, on_progress)

# Ou directement
await download_torrent_content(magnet_link, "downloads", config)
```

---

### Exceptions

```python
from nyaa_downloader import (
    NyaaError,       # Exception de base
    NetworkError,    # Erreur réseau (timeout, connection)
    DownloadError,   # Erreur téléchargement
    ParseError,      # Erreur parsing RSS
    RateLimitError,  # Rate limit API
    RetryConfig,     # Configuration retry
)

try:
    results = searcher.search("anime")
except NetworkError as e:
    print(f"Erreur réseau: {e}")
except ParseError as e:
    print(f"Erreur parsing: {e}")
```

---

## CLI

```bash
# Recherche basique
nyaa-downloader "Sousou no Frieren"

# Seulement trusted, télécharger le meilleur
nyaa-downloader "Jujutsu Kaisen" --trusted-only --best

# Limiter les résultats
nyaa-downloader "Frieren" --limit 20

# Dossier de destination
nyaa-downloader "Oshi no ko" --dest ./my_torrents
```

---

## Structure des résultats

### `NyaaResult`

```python
@dataclass
class NyaaResult:
    title: str                    # Titre complet
    link: str                     # URL .torrent
    magnet: Optional[str]         # Lien magnet
    size: str                     # Taille (ex: "1.4 GiB")
    date: str                     # Date publication
    seeders: int                  # Nombre de seeders
    leechers: int                 # Nombre de leechers
    downloads: int                # Total téléchargements
    trusted: bool                 # Release trusted
    anime_title: Optional[str]    # Titre anime parsé
    episode: Optional[str]        # Numéro épisode parsé
    release_group: Optional[str]  # Groupe (ex: "SubsPlease")
    resolution: Optional[str]     # Résolution (ex: "1080p")
    source: Optional[str]         # Source (ex: "WEB-DL")
    season: Optional[int]         # Saison détectée
    parsed_episode: ParsedEpisode # Objet episode parsé
    is_batch: bool                # Est un batch
```

### `ParsedEpisode`

```python
@dataclass
class ParsedEpisode:
    episode: Optional[int]              # Épisode unique
    episode_range: Optional[Tuple[int, int]]  # Range (1, 12)
    is_batch: bool                      # Est un batch
    
    def contains(self, ep: int) -> bool  # L'épisode est dans le range
    def episodes(self) -> List[int]      # Liste des épisodes
    def sort_key(self) -> Tuple[int, int]  # Pour tri
```

---

## Exemple complet

```python
from nyaa_downloader import NyaaAnime, Preferences, SearchFilters

# Recherche avec filtres
filters = SearchFilters(min_seeders=100, resolution="1080p")
nyaa = NyaaAnime.search("Jujutsu Kaisen", 
    trusted_only=True, 
    max_pages=2,
    filters=filters
)

# Enrichir avec MAL
nyaa.enrich_from_mal()
print(f"Saisons détectées: {list(nyaa.saisons.keys())}")

# Préférences de téléchargement
prefs = Preferences(
    preferred_resolution="1080p",
    preferred_release_groups=["SubsPlease"],
)

# Télécharger S2E1
s2 = nyaa.saison(2)
ep1 = s2.get(1, preferences=prefs)

if ep1:
    print(f"Choix: {ep1.title}")
    print(f"Group: {ep1.release_group}")
    print(f"Resolution: {ep1.resolution}")
    print(f"Seeders: {ep1.seeders}")
    
    # Télécharger
    path = nyaa.download_torrent(ep1, "torrents")
    print(f"Téléchargé: {path}")
```