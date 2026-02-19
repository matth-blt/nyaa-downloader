from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .download import download_torrent
from .errors import DownloadError
from .search import NyaaSearcher


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nyaa-downloader",
        description="Search and download torrents from nyaa.si",
    )
    parser.add_argument("query", help="Search term (anime title, etc.)")
    parser.add_argument(
        "-t",
        "--trusted-only",
        action="store_true",
        help="Limit to trusted uploads only",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results to display (default: 10)",
    )
    parser.add_argument(
        "-d",
        "--dest",
        type=Path,
        default=Path("torrents"),
        help="Destination folder for .torrent files (default: ./torrents)",
    )
    parser.add_argument(
        "-b",
        "--best",
        action="store_true",
        help="Automatically download the result with the most seeders",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    searcher = NyaaSearcher()
    results = searcher.search(args.query, trusted_only=args.trusted_only)

    if not results:
        print("No results found.", file=sys.stderr)
        return 1

    # Sort by seeders descending
    results_sorted = sorted(results, key=lambda r: r.seeders, reverse=True)
    to_show = results_sorted[: args.limit]

    for idx, r in enumerate(to_show, start=1):
        trusted_mark = "[T]" if r.trusted else "   "
        print(
            f"{idx:2d}. {trusted_mark} {r.title} "
            f"(S:{r.seeders} L:{r.leechers} D:{r.downloads} Sz:{r.size})"
        )

    if not args.best:
        # If "best" is not requested, stop after displaying results.
        return 0

    best = results_sorted[0]
    print(f"\nDownloading best result: {best.title}")

    try:
        dest = download_torrent(best, args.dest)
    except DownloadError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Torrent file downloaded to: {dest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

