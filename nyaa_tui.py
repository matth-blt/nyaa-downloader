from __future__ import annotations

# pyright: reportAttributeAccessIssue=false

import sys
import os
import asyncio
from typing import Optional, List

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from nyaa_downloader import (
    NyaaAnime,
    NyaaSearcher,
    NyaaResult,
    SeasonResults,
    SearchFilters,
    Preferences,
    get_jikan_client,
    get_anime_metadata,
    TorrentSession,
    DownloadProgress,
    LIBTORRENT_AVAILABLE,
    download_torrent_content,
)
from nyaa_downloader.metadata import JikanClient, AnimeMetadata
from nyaa_downloader.errors import NetworkError, RateLimitError


def open_magnet(magnet_link: str):
    if sys.platform == "win32":
        os.startfile(magnet_link)
    else:
        import subprocess
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, magnet_link])


def format_progress(p: DownloadProgress) -> str:
    rate_mb = p.download_rate / (1024 * 1024)
    eta_str = ""
    if p.eta:
        mins, secs = divmod(p.eta, 60)
        eta_str = f" ETA: {mins:02d}:{secs:02d}"
    return f"[{p.state}] {p.progress:.1f}% - {rate_mb:.2f} MB/s - Peers:{p.num_peers} Seeds:{p.num_seeds}{eta_str}"


class NyaaCLI:
    def __init__(self):
        self.jikan = get_jikan_client()
        self.preferences = Preferences(
            preferred_resolution="1080p",
            prefer_trusted=True,
        )
        self._current_anime: Optional[NyaaAnime] = None
        self._current_metadata: Optional[AnimeMetadata] = None

    def start(self):
        print("\n=== Nyaa Downloader ===\n")
        while True:
            query = inquirer.text(message="Search Anime (or 'q' to quit):").execute()
            if query.lower() in ("q", "quit", "exit"):
                break
            if not query.strip():
                continue
            self.handle_search(query)

    def handle_search(self, query: str):
        print("Searching MyAnimeList via Jikan...")
        try:
            results = self.jikan.search_anime(query, limit=10)
        except (NetworkError, RateLimitError) as e:
            print(f"Error searching anime: {e}")
            return

        if not results:
            print("No anime found.")
            return

        choices = []
        for anime in results:
            anime_type = anime.get("type", "?")
            year = anime.get("year") or anime.get("aired", {}).get("prop", {}).get("from", {}).get("year", "?")
            title = anime.get("title", "Unknown")
            mal_id = anime.get("mal_id")
            choices.append(Choice((mal_id, title), name=f"{title} ({anime_type}, {year})"))

        choices.append(Separator())
        choices.append(Choice("back", name="< Back"))

        selected = inquirer.select(
            message="Select Anime:",
            choices=choices,
        ).execute()

        if selected == "back":
            return

        mal_id, title = selected
        self.handle_anime_selection(mal_id, title)

    def handle_anime_selection(self, mal_id: int, title: str):
        action = inquirer.select(
            message=f"Selected: {title}",
            choices=[
                Choice("search", name="Search Nyaa for this title"),
                Choice("relations", name="View Related Seasons/Sequels"),
                Choice("metadata", name="View Metadata"),
                Choice("back", name="< Back")
            ]
        ).execute()

        if action == "back":
            return
        elif action == "search":
            self.handle_nyaa_search(mal_id, title)
        elif action == "relations":
            self.handle_relations(mal_id, title)
        elif action == "metadata":
            self.show_metadata(mal_id, title)
            self.handle_anime_selection(mal_id, title)

    def show_metadata(self, mal_id: int, title: str):
        print(f"\nFetching metadata for '{title}'...")
        try:
            metadata = get_anime_metadata(title, mal_id)
        except (NetworkError, RateLimitError) as e:
            print(f"Error: {e}")
            return

        if not metadata:
            print("No metadata found.")
            return

        self._current_metadata = metadata
        print(f"\n--- {metadata.title} ---")
        if metadata.title_english:
            print(f"English: {metadata.title_english}")
        if metadata.title_japanese:
            print(f"Japanese: {metadata.title_japanese}")
        print(f"Episodes: {metadata.episodes or '?'}")
        print(f"Status: {metadata.status}")
        print(f"Year: {metadata.year or '?'}")
        if metadata.synopsis:
            print(f"\n{metadata.synopsis[:300]}...")
        print()

    def handle_relations(self, mal_id: int, title: str):
        print("Fetching relations...")
        try:
            relations = self.jikan.get_relations(mal_id)
        except (NetworkError, RateLimitError) as e:
            print(f"Error fetching relations: {e}")
            return

        if not relations:
            print("No related anime found.")
            return

        EXCLUDED_TYPES = ["movie", "special", "ova", "ona", "music"]
        interesting = ["Sequel", "Prequel", "Parent story", "Side story", "Alternative version"]

        choices = []
        for rel in relations:
            rel_type = rel.get("relation", "")
            for entry in rel.get("entry", []):
                if entry.get("type") == "anime":
                    anime_type = entry.get("type", "?")
                    rel_mal_id = entry.get("mal_id")
                    rel_title = entry.get("title", "Unknown")
                    choices.append(
                        Choice((rel_mal_id, rel_title), name=f"[{rel_type}] {rel_title} ({anime_type})")
                    )

        if not choices:
            print("No related TV series found.")
            return

        choices.append(Separator())
        choices.append(Choice("back", name="< Back"))

        selected = inquirer.select(
            message=f"Relations for {title}:",
            choices=choices,
        ).execute()

        if selected == "back":
            return

        rel_mal_id, rel_title = selected
        self.handle_anime_selection(rel_mal_id, rel_title)

    def handle_nyaa_search(self, mal_id: int, title: str):
        use_mal_title = inquirer.confirm(
            message=f"Use '{title}' as search query?",
            default=True
        ).execute()

        search_title = title if use_mal_title else inquirer.text(message="Enter search query:").execute()

        trusted = inquirer.confirm(message="Trusted groups only?", default=True).execute()

        print(f"\nSearching Nyaa for '{search_title}'...")
        
        filters = SearchFilters(trusted_only=trusted) if trusted else None
        
        try:
            self._current_anime = NyaaAnime.search(
                search_title,
                trusted_only=trusted,
                max_pages=2,
                filters=filters,
            )
            self._current_anime.enrich_from_mal(mal_id)
        except NetworkError as e:
            print(f"Error: {e}")
            return

        if not self._current_anime.results:
            print("No results found on Nyaa.")
            return

        self._show_season_menu()

    def _show_season_menu(self):
        if not self._current_anime:
            return

        seasons = self._current_anime.seasons
        if not seasons:
            print("No results to display.")
            return

        choices = []
        sorted_seasons = sorted([s for s in seasons.keys() if s is not None])
        
        for season_num in sorted_seasons:
            season_data = seasons[season_num]
            ep_count = len(season_data.episodes)
            batch_count = sum(1 for r in season_data.episodes if r.is_batch)
            name = f"Season {season_num} ({ep_count} releases, {batch_count} batches)"
            choices.append(Choice(season_num, name=name))

        if None in seasons:
            season_data = seasons[None]
            name = f"Unknown Season ({len(season_data.episodes)} releases)"
            choices.append(Choice(None, name=name))

        choices.append(Separator())
        choices.append(Choice("all", name="Show all results"))
        choices.append(Choice("back", name="< Back"))

        selected = inquirer.select(
            message="Select Season:",
            choices=choices,
        ).execute()

        if selected == "back":
            return

        if selected == "all":
            self._show_results(self._current_anime.results)
        else:
            self._show_season_episodes(selected)

    def _show_season_episodes(self, season_num: Optional[int]):
        if not self._current_anime:
            return

        season_data = self._current_anime.season(season_num)
        episodes: dict[str, List[NyaaResult]] = {}
        batches: List[NyaaResult] = []
        others: List[NyaaResult] = []

        for res in season_data.episodes:
            if res.is_batch:
                batches.append(res)
            elif res.parsed_episode.episode is not None:
                ep_key = f"{res.parsed_episode.episode:02d}"
                episodes.setdefault(ep_key, []).append(res)
            elif res.episode:
                try:
                    ep_num = int(res.episode)
                    ep_key = f"{ep_num:02d}"
                    episodes.setdefault(ep_key, []).append(res)
                except (ValueError, TypeError):
                    others.append(res)
            else:
                others.append(res)

        choices = []
        sorted_eps = sorted(episodes.keys())
        for ep in sorted_eps:
            count = len(episodes[ep])
            choices.append(Choice(ep, name=f"Episode {int(ep)} ({count} releases)"))

        if batches:
            choices.append(Choice("batches", name=f"Batches ({len(batches)} releases)"))
        if others:
            choices.append(Choice("others", name=f"Other ({len(others)} releases)"))

        choices.append(Separator())
        choices.append(Choice("back", name="< Back"))

        selected = inquirer.select(
            message=f"Season {season_num} - Select Episode:",
            choices=choices,
        ).execute()

        if selected == "back":
            self._show_season_menu()
            return

        if selected == "batches":
            self._show_results(batches)
        elif selected == "others":
            self._show_results(others)
        else:
            self._show_results(episodes[selected])

    def _show_results(self, results: List[NyaaResult]):
        sorted_results = self.preferences.sort_results(results)

        choices = []
        for res in sorted_results:
            group = res.release_group or "?"
            res_str = res.resolution or "?"
            trusted_mark = "[T]" if res.trusted else "   "
            batch_mark = "[B]" if res.is_batch else "   "
            name = f"{trusted_mark}{batch_mark} [{group}] {res_str} ({res.size}) | S:{res.seeders} L:{res.leechers}"
            choices.append(Choice(res, name=name))

        choices.append(Separator())
        choices.append(Choice("back", name="< Back"))

        selected = inquirer.select(
            message="Select Release:",
            choices=choices
        ).execute()

        if selected == "back":
            return

        self._handle_download(selected)

    def _handle_download(self, result: NyaaResult | dict):
        if isinstance(result, dict):
            result = NyaaResult(**result)
        
        choices = [
            Choice("magnet", name="Open Magnet Link (Default Client)"),
        ]
        
        if LIBTORRENT_AVAILABLE:
            choices.append(Choice("direct", name="Direct Download (Libtorrent)"))
        
        choices.append(Choice("info", name="Show Info"))
        choices.append(Choice("back", name="< Cancel"))

        action = inquirer.select(
            message=f"Action for: {result.title[:60]}...",
            choices=choices
        ).execute()

        if action == "back":
            return
        elif action == "magnet":
            magnet = result.magnet or result.link
            print(f"Opening magnet...")
            open_magnet(magnet)
        elif action == "direct":
            self._direct_download(result)
        elif action == "info":
            print(f"\n--- Release Info ---")
            print(f"Title: {result.title}")
            print(f"Group: {result.release_group or 'Unknown'}")
            print(f"Resolution: {result.resolution or 'Unknown'}")
            print(f"Size: {result.size}")
            print(f"Seeders: {result.seeders} | Leechers: {result.leechers}")
            print(f"Downloads: {result.downloads}")
            print(f"Trusted: {result.trusted}")
            print(f"Date: {result.date}")
            if result.episode:
                print(f"Episode: {result.episode}")
            if result.season:
                print(f"Season: {result.season}")
            print()
            self._handle_download(result)

    def _direct_download(self, result: NyaaResult):
        if not LIBTORRENT_AVAILABLE:
            print("Libtorrent not available. Install with: pip install libtorrent")
            return

        save_path = inquirer.text(
            message="Save to directory:",
            default="./downloads"
        ).execute()

        source = result.magnet or result.link
        if not source:
            print("No download source available.")
            return

        print(f"\nStarting download to {save_path}...")

        def progress_callback(p: DownloadProgress):
            print(f"\r{format_progress(p)}", end="", flush=True)

        try:
            asyncio.run(
                download_torrent_content(
                    source,
                    save_path,
                    progress_callback=progress_callback,
                )
            )
            print(f"\n\nDownload complete: {save_path}")
        except Exception as e:
            print(f"\nDownload error: {e}")


def main():
    try:
        cli = NyaaCLI()
        cli.start()
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
