from __future__ import annotations

from pathlib import Path
from typing import Union, Optional

import requests
from requests.exceptions import Timeout, ConnectionError, HTTPError

from .search import NyaaResult
from .errors import DownloadError, NetworkError, RateLimitError, RetryConfig, retry_with_backoff


PathLike = Union[str, Path]

DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_CONFIG = RetryConfig(max_retries=3, base_delay=1.0)


def _do_download(url: str, timeout: int) -> bytes:
    """Perform the actual HTTP download."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except Timeout as e:
        raise NetworkError(f"Request timeout for {url}") from e
    except ConnectionError as e:
        raise NetworkError(f"Connection failed for {url}: {e}") from e
    except HTTPError as e:
        if e.response.status_code >= 500:
            raise NetworkError(f"Server error {e.response.status_code} for {url}") from e
        raise DownloadError(f"HTTP {e.response.status_code} for {url}") from e
    except requests.RequestException as e:
        raise NetworkError(f"Request failed for {url}: {e}") from e


def download_torrent(
    result: NyaaResult, 
    dest_dir: PathLike,
    timeout: int = DEFAULT_TIMEOUT,
    retry_config: Optional[RetryConfig] = None,
) -> Path:
    """
    Download the .torrent file associated with a Nyaa result.

    :param result: NyaaResult instance whose `link` field points to the .torrent.
    :param dest_dir: destination folder (str or Path).
    :param timeout: HTTP timeout in seconds.
    :param retry_config: retry configuration (None = default 3 retries).
    :return: path to the downloaded .torrent file.
    :raises DownloadError: on HTTP or I/O failure.
    :raises NetworkError: on network issues.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in " .-_[]" else "_" for c in result.title)
    filename = safe_name + ".torrent"
    dest_path = dest_dir / filename

    config = retry_config or DEFAULT_RETRY_CONFIG
    
    try:
        content = retry_with_backoff(
            lambda: _do_download(result.link, timeout),
            config=config,
        )
    except (NetworkError, RateLimitError) as e:
        raise DownloadError(f"Failed to download {result.link}: {e}") from e

    try:
        dest_path.write_bytes(content)
    except OSError as e:
        raise DownloadError(f"Cannot write file {dest_path}: {e}") from e

    return dest_path

