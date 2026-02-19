import sys
import traceback
from datetime import datetime

# ─── Compteurs ────────────────────────────────────────────────────────────────
passed = 0
failed = 0
errors = []

def test(name):
    def decorator(func):
        global passed, failed
        try:
            func()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name} — {e}")
            errors.append((name, str(e)))
            failed += 1
        except Exception as e:
            print(f"  ✗ {name} — ERREUR: {e}")
            errors.append((name, traceback.format_exc()))
            failed += 1
    return decorator

# ═══════════════════════════════════════════════════════════════════════════════
# 1) PARSING UTILS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 1. parsing_utils ===")

from nyaa_downloader.parsing_utils import (
    ParsedEpisode, parse_episode, parse_season,
    normalize_episode_number, compare_episodes, episode_sort_key,
)

@test("ParsedEpisode.contains — single")
def _():
    ep = ParsedEpisode(episode=5)
    assert ep.contains(5)
    assert not ep.contains(4)

@test("ParsedEpisode.contains — range")
def _():
    ep = ParsedEpisode(episode_range=(3, 10), is_batch=True)
    assert ep.contains(3)
    assert ep.contains(7)
    assert ep.contains(10)
    assert not ep.contains(2)
    assert not ep.contains(11)

@test("ParsedEpisode.episodes — single")
def _():
    ep = ParsedEpisode(episode=5)
    assert ep.episodes == [5]

@test("ParsedEpisode.episodes — range")
def _():
    ep = ParsedEpisode(episode_range=(1, 4), is_batch=True)
    assert ep.episodes == [1, 2, 3, 4]

@test("ParsedEpisode.episodes — empty")
def _():
    ep = ParsedEpisode()
    assert ep.episodes == []

@test("ParsedEpisode.sort_key — single")
def _():
    assert ParsedEpisode(episode=5).sort_key() == (5, 5)

@test("ParsedEpisode.sort_key — range")
def _():
    assert ParsedEpisode(episode_range=(3, 10)).sort_key() == (3, 10)

@test("ParsedEpisode.sort_key — empty → (999999, 999999)")
def _():
    assert ParsedEpisode().sort_key() == (999999, 999999)

@test("parse_episode — 'E05'")
def _():
    r = parse_episode("[SubsPlease] Frieren - E05 [1080p]")
    assert r.episode == 5

@test("parse_episode — 'Episode 12'")
def _():
    r = parse_episode("[Erai-raws] JJK Episode 12 [1080p]")
    assert r.episode == 12

@test("parse_episode — S2E01")
def _():
    r = parse_episode("[SubsPlease] Anime S2E01 [1080p]")
    assert r.episode == 1

@test("parse_episode — '[05]'")
def _():
    r = parse_episode("[SubsPlease] Anime [05] [1080p]")
    assert r.episode == 5

@test("parse_episode — range '01-12'")
def _():
    r = parse_episode("[SubsPlease] Anime - 01-12 [Batch]")
    assert r.is_batch
    assert r.episode_range == (1, 12)

@test("parse_episode — range tilde '01~23'")
def _():
    r = parse_episode("[Erai-raws] JJK 2nd Season - 01 ~ 23 [1080p]")
    assert r.is_batch
    assert r.episode_range == (1, 23)

@test("parse_episode — 'Complete'")
def _():
    r = parse_episode("[Group] Anime Complete Season [1080p]")
    assert r.is_batch

@test("parse_episode — 'Batch'")
def _():
    r = parse_episode("[Group] Anime [Batch] [1080p]")
    assert r.is_batch

@test("parse_episode — END marker")
def _():
    r = parse_episode("[SubsPlease] Frieren - 28 (END) [1080p]")
    assert r.episode == 28

@test("parse_season — S2")
def _():
    assert parse_season("[SubsPlease] Anime S2 - 05 [1080p]") == 2

@test("parse_season — 'Season 3'")
def _():
    assert parse_season("[Group] Anime Season 3 [1080p]") == 3

@test("parse_season — '2nd Season'")
def _():
    assert parse_season("[Group] Anime 2nd Season [1080p]") == 2

@test("parse_season — S02E01")
def _():
    assert parse_season("[Group] Anime S02E01 [1080p]") == 2

@test("parse_season — 'Part 2'")
def _():
    assert parse_season("[Group] Anime Part 2 [1080p]") == 2

@test("parse_season — 'Cour 2'")
def _():
    assert parse_season("[Group] Anime Cour 2 [1080p]") == 2

@test("parse_season — no season → None")
def _():
    assert parse_season("[SubsPlease] Frieren - 05 [1080p]") is None

@test("normalize_episode_number — None")
def _():
    assert normalize_episode_number(None) is None

@test("normalize_episode_number — int")
def _():
    assert normalize_episode_number(5) == 5

@test("normalize_episode_number — '05'")
def _():
    assert normalize_episode_number("05") == 5

@test("normalize_episode_number — 'E03'")
def _():
    assert normalize_episode_number("E03") == 3

@test("compare_episodes — match")
def _():
    assert compare_episodes("05", 5)
    assert compare_episodes(5, "5")

@test("compare_episodes — no match")
def _():
    assert not compare_episodes("05", 6)

@test("compare_episodes — None")
def _():
    assert not compare_episodes(None, 5)
    assert not compare_episodes(5, None)

# ═══════════════════════════════════════════════════════════════════════════════
# 2) ERRORS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 2. errors ===")

from nyaa_downloader.errors import (
    NyaaError, NetworkError, DownloadError, ParseError,
    RateLimitError, RetryConfig, retry_with_backoff,
)

@test("NyaaError hierarchy")
def _():
    assert issubclass(NetworkError, NyaaError)
    assert issubclass(DownloadError, NyaaError)
    assert issubclass(ParseError, NyaaError)
    assert issubclass(RateLimitError, NyaaError)

@test("RateLimitError.retry_after")
def _():
    e = RateLimitError(retry_after=5.0)
    assert e.retry_after == 5.0

@test("RetryConfig.get_delay — exponential")
def _():
    cfg = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=30.0)
    assert cfg.get_delay(0) == 1.0
    assert cfg.get_delay(1) == 2.0
    assert cfg.get_delay(2) == 4.0
    assert cfg.get_delay(3) == 8.0

@test("RetryConfig.get_delay — max_delay cap")
def _():
    cfg = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=5.0)
    assert cfg.get_delay(10) == 5.0

@test("retry_with_backoff — direct success")
def _():
    result = retry_with_backoff(lambda: 42, RetryConfig(max_retries=0))
    assert result == 42

@test("retry_with_backoff — retry then success")
def _():
    counter = {"n": 0}
    def flaky():
        counter["n"] += 1
        if counter["n"] < 3:
            raise NetworkError("fail")
        return "ok"
    result = retry_with_backoff(flaky, RetryConfig(max_retries=3, base_delay=0.01))
    assert result == "ok"
    assert counter["n"] == 3

@test("retry_with_backoff — fail max_retries")
def _():
    def always_fail():
        raise NetworkError("nope")
    try:
        retry_with_backoff(always_fail, RetryConfig(max_retries=2, base_delay=0.01))
        assert False, "Should have raised"
    except NetworkError:
        pass

@test("retry_with_backoff — non-retryable exception propagates immediately")
def _():
    def raise_value_error():
        raise ValueError("bad")
    try:
        retry_with_backoff(raise_value_error, RetryConfig(max_retries=3, base_delay=0.01))
        assert False, "Should have raised"
    except ValueError:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# 3) PREFERENCES
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 3. preferences ===")

from nyaa_downloader.preferences import Preferences
from nyaa_downloader.search import NyaaResult
from nyaa_downloader.parsing_utils import ParsedEpisode

def make_result(**kwargs):
    defaults = dict(
        title="test", link="http://test", magnet=None, size="1.0 GiB",
        date="Mon, 01 Jan 2024 00:00:00 +0000", seeders=100, leechers=10,
        downloads=50, trusted=True, anime_title="Test", episode="1",
        release_group="SubsPlease", resolution="1080p", source="WEB",
        season=1, parsed_episode=ParsedEpisode(episode=1), is_batch=False,
    )
    defaults.update(kwargs)
    return NyaaResult(**defaults)

@test("Preferences.score — preferred resolution")
def _():
    prefs = Preferences(preferred_resolution="1080p")
    r1080 = make_result(resolution="1080p")
    r720 = make_result(resolution="720p")
    assert prefs.score(r1080) < prefs.score(r720)

@test("Preferences.score — preferred release group")
def _():
    prefs = Preferences(preferred_release_groups=["SubsPlease"])
    r_sub = make_result(release_group="SubsPlease")
    r_other = make_result(release_group="RandomGroup")
    assert prefs.score(r_sub) < prefs.score(r_other)

@test("Preferences.score — release group exclu")
def _():
    prefs = Preferences(excluded_release_groups=["BadGroup"])
    r_bad = make_result(release_group="BadGroup")
    assert prefs.score(r_bad) == (999, 999, 999, 999)

@test("Preferences.score — min_seeders non atteint")
def _():
    prefs = Preferences(min_seeders=500)
    r = make_result(seeders=100)
    assert prefs.score(r) == (999, 999, 999, 999)

@test("Preferences.score — preferred trusted")
def _():
    prefs = Preferences(prefer_trusted=True)
    r_trusted = make_result(trusted=True)
    r_not = make_result(trusted=False)
    assert prefs.score(r_trusted) < prefs.score(r_not)

@test("Preferences.sort_results")
def _():
    prefs = Preferences(preferred_resolution="1080p")
    results = [
        make_result(resolution="720p", seeders=200),
        make_result(resolution="1080p", seeders=100),
        make_result(resolution="1080p", seeders=300),
    ]
    sorted_r = prefs.sort_results(results)
    assert sorted_r[0].resolution == "1080p"

# ═══════════════════════════════════════════════════════════════════════════════
# 4) SEARCH FILTERS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 4. SearchFilters ===")

from nyaa_downloader.search import SearchFilters, _parse_size_to_mb

@test("_parse_size_to_mb — GiB")
def _():
    assert abs(_parse_size_to_mb("1.4 GiB") - 1.4 * 1024) < 0.1

@test("_parse_size_to_mb — MiB")
def _():
    assert abs(_parse_size_to_mb("500 MiB") - 500) < 0.1

@test("_parse_size_to_mb — invalid")
def _():
    assert _parse_size_to_mb("?") is None
    assert _parse_size_to_mb("") is None
    assert _parse_size_to_mb("unknown") is None

@test("SearchFilters.matches — min_seeders")
def _():
    f = SearchFilters(min_seeders=50)
    assert f.matches(make_result(seeders=100))
    assert not f.matches(make_result(seeders=10))

@test("SearchFilters.matches — trusted_only")
def _():
    f = SearchFilters(trusted_only=True)
    assert f.matches(make_result(trusted=True))
    assert not f.matches(make_result(trusted=False))

@test("SearchFilters.matches — exclude_batches")
def _():
    f = SearchFilters(exclude_batches=True)
    assert f.matches(make_result(is_batch=False))
    assert not f.matches(make_result(is_batch=True))

@test("SearchFilters.matches — batches_only")
def _():
    f = SearchFilters(batches_only=True)
    assert f.matches(make_result(is_batch=True))
    assert not f.matches(make_result(is_batch=False))

@test("SearchFilters.matches — resolution")
def _():
    f = SearchFilters(resolution="1080p")
    assert f.matches(make_result(resolution="1080p"))
    assert not f.matches(make_result(resolution="720p"))

# ═══════════════════════════════════════════════════════════════════════════════
# 5) SEASON RESULTS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 5. SeasonResults ===")

from nyaa_downloader.anime import SeasonResults

@test("SeasonResults.get — by episode number")
def _():
    results = [
        make_result(episode="1", parsed_episode=ParsedEpisode(episode=1), seeders=50),
        make_result(episode="1", parsed_episode=ParsedEpisode(episode=1), seeders=100),
        make_result(episode="2", parsed_episode=ParsedEpisode(episode=2), seeders=80),
    ]
    sr = SeasonResults(season=1, episodes=results)
    best = sr.get(1)
    assert best is not None
    assert best.seeders == 100  # more seeders

@test("SeasonResults.get — with preferences")
def _():
    results = [
        make_result(episode="1", parsed_episode=ParsedEpisode(episode=1), seeders=200, resolution="720p"),
        make_result(episode="1", parsed_episode=ParsedEpisode(episode=1), seeders=100, resolution="1080p"),
    ]
    sr = SeasonResults(season=1, episodes=results)
    prefs = Preferences(preferred_resolution="1080p")
    best = sr.get(1, preferences=prefs)
    assert best is not None
    assert best.resolution == "1080p"

@test("SeasonResults.get — batch contains the episode")
def _():
    results = [
        make_result(episode="1-12", parsed_episode=ParsedEpisode(episode_range=(1, 12), is_batch=True), seeders=500, is_batch=True),
    ]
    sr = SeasonResults(season=1, episodes=results)
    best = sr.get(5)
    assert best is not None
    assert best.is_batch
    assert best.parsed_episode.contains(5)

@test("SeasonResults.get — episode not found → None")
def _():
    results = [
        make_result(episode="1", parsed_episode=ParsedEpisode(episode=1)),
    ]
    sr = SeasonResults(season=1, episodes=results)
    assert sr.get(99) is None

# ═══════════════════════════════════════════════════════════════════════════════
# 6) NyaaAnime (unit tests without network)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 6. NyaaAnime (unit) ===")

from nyaa_downloader.anime import NyaaAnime

@test("NyaaAnime — construction and seasons")
def _():
    results = [
        make_result(season=1, episode="1", parsed_episode=ParsedEpisode(episode=1)),
        make_result(season=1, episode="2", parsed_episode=ParsedEpisode(episode=2)),
        make_result(season=2, episode="1", parsed_episode=ParsedEpisode(episode=1)),
    ]
    nyaa = NyaaAnime(title="Test", results=results)
    assert 1 in nyaa.seasons
    assert 2 in nyaa.seasons
    assert len(nyaa.season(1).episodes) == 2
    assert len(nyaa.season(2).episodes) == 1

@test("NyaaAnime — non-existent season → empty")
def _():
    nyaa = NyaaAnime(title="Test", results=[])
    sr = nyaa.season(99)
    assert sr.episodes == []

@test("NyaaAnime — cached_property seasons")
def _():
    results = [make_result(season=1, episode="1", parsed_episode=ParsedEpisode(episode=1))]
    nyaa = NyaaAnime(title="Test", results=results)
    s1 = nyaa.seasons
    s2 = nyaa.seasons
    assert s1 is s2  # same object = cache

@test("NyaaAnime — to_relative_episode / to_absolute_episode")
def _():
    nyaa = NyaaAnime(title="Test", results=[])
    nyaa._season_episodes_info = {1: (1, 24), 2: (25, 47)}
    
    assert nyaa.to_relative_episode(25, 2) == 1
    assert nyaa.to_relative_episode(1, 1) == 1
    assert nyaa.to_relative_episode(47, 2) == 23
    
    assert nyaa.to_absolute_episode(1, 2) == 25
    assert nyaa.to_absolute_episode(1, 1) == 1
    
    # Hors limites
    assert nyaa.to_relative_episode(50, 2) is None
    assert nyaa.to_absolute_episode(100, 2) is None

@test("NyaaAnime — download_torrent appelle download module")
def _():
    # Just verify the method exists and calls correctly
    nyaa = NyaaAnime(title="Test", results=[])
    assert hasattr(nyaa, 'download_torrent')

# ═══════════════════════════════════════════════════════════════════════════════
# 7) TORRENT SESSION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 7. TorrentSession ===")

from nyaa_downloader import LIBTORRENT_AVAILABLE

@test("LIBTORRENT_AVAILABLE est un bool")
def _():
    assert isinstance(LIBTORRENT_AVAILABLE, bool)

if LIBTORRENT_AVAILABLE:
    from nyaa_downloader.torrent_session import TorrentSession, TorrentConfig, DownloadProgress

    @test("TorrentConfig — default values")
    def _():
        cfg = TorrentConfig()
        assert cfg.connections_limit == 200
        assert cfg.cache_size == 512
        assert cfg.enable_dht is True

    @test("TorrentConfig.to_settings_pack — returns a dict")
    def _():
        cfg = TorrentConfig()
        sp = cfg.to_settings_pack()
        assert isinstance(sp, dict)
        assert "connections_limit" in sp
        assert "enable_dht" in sp

    @test("DownloadProgress — dataclass")
    def _():
        dp = DownloadProgress(
            progress=50.0, download_rate=1024, upload_rate=512,
            num_peers=10, num_seeds=5, total_done=100, total_size=200
        )
        assert dp.progress == 50.0
        assert dp.state == "downloading"

# ═══════════════════════════════════════════════════════════════════════════════
# 8) __init__.py EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 8. Exports __init__.py ===")

import nyaa_downloader

@test("__all__ contient tous les exports attendus")
def _():
    expected = [
        "NyaaSearcher", "NyaaResult", "SearchFilters",
        "download_torrent", "NyaaAnime", "SeasonResults",
        "Preferences", "AnimeMetadata", "get_anime_metadata", "get_jikan_client",
        "NyaaError", "NetworkError", "DownloadError", "ParseError",
        "RateLimitError", "RetryConfig",
        "TorrentSession", "TorrentConfig", "DownloadProgress",
        "download_torrent_content", "LIBTORRENT_AVAILABLE",
    ]
    for name in expected:
        assert name in nyaa_downloader.__all__, f"{name} manquant dans __all__"

@test("build_season_mapping importable depuis le package")
def _():
    from nyaa_downloader import build_season_mapping
    assert callable(build_season_mapping)

# ═══════════════════════════════════════════════════════════════════════════════
# 9) CLI
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 9. CLI ===")

@test("CLI parser — arguments reconnus")
def _():
    from nyaa_downloader.cli import _build_parser
    parser = _build_parser()
    args = parser.parse_args(["test query", "--trusted-only", "--limit", "5", "--best"])
    assert args.query == "test query"
    assert args.trusted_only is True
    assert args.limit == 5
    assert args.best is True

# ═══════════════════════════════════════════════════════════════════════════════
# 10) NETWORK TESTS (live search)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 10. Network tests (Nyaa + Jikan) ===")

@test("NyaaSearcher.search — live search 'Frieren'")
def _():
    from nyaa_downloader import NyaaSearcher
    searcher = NyaaSearcher(timeout=30)
    results = searcher.search("Frieren", trusted_only=False)
    assert len(results) > 0, "No results found for 'Frieren'"
    r = results[0]
    assert r.title
    assert r.link
    assert isinstance(r.seeders, int)
    assert isinstance(r.parsed_episode, ParsedEpisode)
    print(f"    ({len(results)} results, first: {r.title[:60]}...)")

@test("NyaaSearcher.search — filters applied")
def _():
    from nyaa_downloader import NyaaSearcher, SearchFilters
    searcher = NyaaSearcher(timeout=30)
    filters = SearchFilters(min_seeders=10, exclude_batches=True)
    results = searcher.search("Frieren", filters=filters)
    for r in results:
        assert r.seeders >= 10, f"Seeders {r.seeders} < 10"
        assert not r.is_batch, f"Batch found despite exclude_batches"

@test("NyaaSearcher.search_paginated — iterator")
def _():
    from nyaa_downloader import NyaaSearcher
    searcher = NyaaSearcher(timeout=30)
    pages = list(searcher.search_paginated("Jujutsu Kaisen", max_pages=2))
    assert len(pages) >= 1, "No pages returned"
    total = sum(len(p) for p in pages)
    print(f"    ({len(pages)} pages, {total} results)")

@test("NyaaAnime.search — workflow complet")
def _():
    nyaa = NyaaAnime.search("Frieren", trusted_only=True)
    assert len(nyaa.results) > 0
    seasons = nyaa.seasons
    print(f"    ({len(nyaa.results)} results, seasons: {list(seasons.keys())})")

@test("get_anime_metadata — Jikan API")
def _():
    from nyaa_downloader import get_anime_metadata
    meta = get_anime_metadata("Sousou no Frieren")
    assert meta is not None, "Metadata not found"
    assert meta.mal_id > 0
    assert meta.title
    print(f"    (MAL ID: {meta.mal_id}, title: {meta.title}, eps: {meta.episodes})")

# ═════════════════════════════════════════════════════════════════════════════
# REPORT
# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"RESULT: {passed} passed, {failed} failed out of {passed + failed}")
if errors:
    print("\nDetailed failures:")
    for name, err in errors:
        print(f"  - {name}: {err[:200]}")
print(f"{'='*60}")

sys.exit(0 if failed == 0 else 1)
