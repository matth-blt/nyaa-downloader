from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)

try:
    import libtorrent as lt
    LIBTORRENT_AVAILABLE = True
except ImportError:
    LIBTORRENT_AVAILABLE = False
    lt = None


@dataclass
class TorrentConfig:
    """Optimized configuration for libtorrent."""
    connections_limit: int = 200
    active_downloads: int = 4
    active_seeds: int = 4
    active_limit: int = 8
    cache_size: int = 512  # 512 * 16KB = 8MB cache
    cache_expiry: int = 300
    max_peerlist_size: int = 4000
    min_announce_interval: int = 300
    send_buffer_watermark: int = 500 * 1024
    recv_socket_buffer_size: int = 500 * 1024
    
    enable_utp: bool = True
    enable_tcp: bool = True
    enable_dht: bool = True
    enable_lsd: bool = True
    enable_upnp: bool = True
    enable_natpmp: bool = True
    
    sequential_download: bool = False
    download_rate_limit: int = 0  # 0 = unlimited
    upload_rate_limit: int = 0
    
    listen_interfaces: str = "0.0.0.0:6881"

    def to_settings_pack(self) -> dict:
        return {
            "connections_limit": self.connections_limit,
            "active_downloads": self.active_downloads,
            "active_seeds": self.active_seeds,
            "active_limit": self.active_limit,
            "cache_size": self.cache_size,
            "cache_expiry": self.cache_expiry,
            "max_peerlist_size": self.max_peerlist_size,
            "min_announce_interval": self.min_announce_interval,
            "send_buffer_watermark": self.send_buffer_watermark,
            "recv_socket_buffer_size": self.recv_socket_buffer_size,
            "enable_outgoing_utp": self.enable_utp,
            "enable_incoming_utp": self.enable_utp,
            "enable_outgoing_tcp": self.enable_tcp,
            "enable_incoming_tcp": self.enable_tcp,
            "enable_dht": self.enable_dht,
            "enable_lsd": self.enable_lsd,
            "enable_upnp": self.enable_upnp,
            "enable_natpmp": self.enable_natpmp,
            "download_rate_limit": self.download_rate_limit,
            "upload_rate_limit": self.upload_rate_limit,
            "listen_interfaces": self.listen_interfaces,
        }


@dataclass
class DownloadProgress:
    """Progress info for torrent download."""
    progress: float
    download_rate: int
    upload_rate: int
    num_peers: int
    num_seeds: int
    total_done: int
    total_size: int
    eta: Optional[int] = None
    state: str = "downloading"


class TorrentSession:
    """
    Optimized libtorrent session for performant downloads.
    
    Example:
        session = TorrentSession()
        session.start()
        
        handle = session.add_torrent(magnet_link, save_path)
        await session.wait_for_download(handle, progress_callback=callback)
        
        session.stop()
    """
    
    DEFAULT_CONFIG = TorrentConfig()
    
    def __init__(self, config: Optional[TorrentConfig] = None):
        if not LIBTORRENT_AVAILABLE:
            raise ImportError(
                "libtorrent not installed. Install with: pip install libtorrent"
            )
        
        self.config = config or self.DEFAULT_CONFIG
        self._session: Optional[Any] = None
        self._running = False
    
    def start(self) -> None:
        """Start the libtorrent session."""
        if self._running:
            return

        sp = lt.session_params()
        settings = sp.settings
        for key, value in self.config.to_settings_pack().items():
            settings[key] = value
        sp.settings = settings

        self._session = lt.session(sp)
        
        if self.config.enable_dht:
            self._session.add_dht_router("router.bittorrent.com", 6881)
            self._session.add_dht_router("router.utorrent.com", 6881)
            self._session.add_dht_router("dht.transmissionbt.com", 6881)
        
        self._running = True
        logger.info("TorrentSession started")
    
    def stop(self) -> None:
        """Stop the libtorrent session."""
        if self._session:
            self._session.pause()
            self._session = None
        self._running = False
        logger.info("TorrentSession stopped")
    
    def add_torrent(
        self, 
        source: str, 
        save_path: str | Path,
        sequential: bool = False,
    ) -> Any:
        """
        Add a torrent from magnet link or torrent file.
        
        :param source: Magnet link or path to .torrent file
        :param save_path: Directory to save files
        :param sequential: Download pieces sequentially (good for streaming)
        :return: Torrent handle
        """
        if not self._running:
            self.start()
        
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        
        if source.startswith("magnet:"):
            atp = lt.parse_magnet_uri(source)
            atp.save_path = str(save_path)
        else:
            atp = lt.add_torrent_params()
            atp.ti = lt.torrent_info(source)
            atp.save_path = str(save_path)
        
        handle = self._session.add_torrent(atp)
        
        if sequential or self.config.sequential_download:
            handle.set_sequential_download(True)
        
        handle.set_max_connections(self.config.connections_limit)
        
        return handle
    
    def remove_torrent(self, handle: Any, delete_files: bool = False) -> None:
        """Remove a torrent from the session."""
        if self._session and handle:
            self._session.remove_torrent(handle, delete_files)
    
    def get_progress(self, handle: Any) -> DownloadProgress:
        """Get download progress for a torrent handle."""
        status = handle.status()
        
        progress = status.progress * 100
        download_rate = status.download_rate
        upload_rate = status.upload_rate
        num_peers = status.num_peers
        num_seeds = status.num_seeds
        total_done = status.total_done
        total_size = status.total_wanted
        
        eta = None
        if download_rate > 0:
            remaining = total_size - total_done
            eta = int(remaining / download_rate)
        
        state_map = {
            lt.torrent_status.queued_for_checking: "queued",
            lt.torrent_status.checking_files: "checking",
            lt.torrent_status.downloading_metadata: "metadata",
            lt.torrent_status.downloading: "downloading",
            lt.torrent_status.finished: "finished",
            lt.torrent_status.seeding: "seeding",
            lt.torrent_status.allocating: "allocating",
            lt.torrent_status.checking_resume_data: "checking_resume",
        }
        state = state_map.get(status.state, "unknown")
        
        return DownloadProgress(
            progress=progress,
            download_rate=download_rate,
            upload_rate=upload_rate,
            num_peers=num_peers,
            num_seeds=num_seeds,
            total_done=total_done,
            total_size=total_size,
            eta=eta,
            state=state,
        )
    
    async def wait_for_download(
        self,
        handle: Any,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        poll_interval: float = 1.0,
    ) -> bool:
        """
        Wait for torrent download to complete.
        
        :param handle: Torrent handle
        :param progress_callback: Called with progress updates
        :param poll_interval: Seconds between progress checks
        :return: True if download completed successfully
        """
        while True:
            if not handle.is_valid():
                return False
            
            status = handle.status()
            progress = self.get_progress(handle)
            
            if progress_callback:
                progress_callback(progress)
            
            if status.is_finished or status.is_seeding:
                return True
            
            if status.paused and not status.auto_managed:
                return False
            
            await asyncio.sleep(poll_interval)
    
    def __enter__(self) -> "TorrentSession":
        self.start()
        return self
    
    def __exit__(self, *args) -> None:
        self.stop()


async def download_torrent_content(
    source: str,
    save_path: str | Path,
    config: Optional[TorrentConfig] = None,
    progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
) -> Path:
    """
    Download torrent content asynchronously.
    
    :param source: Magnet link or .torrent file path
    :param save_path: Directory to save files
    :param config: Torrent configuration
    :param progress_callback: Progress update callback
    :return: Path to downloaded files
    """
    with TorrentSession(config) as session:
        handle = session.add_torrent(source, save_path)
        
        def default_callback(p: DownloadProgress) -> None:
            if progress_callback:
                progress_callback(p)
            else:
                logger.info(
                    f"[{p.state}] {p.progress:.1f}% - "
                    f"↓{p.download_rate/1024:.0f}KB/s "
                    f"↑{p.upload_rate/1024:.0f}KB/s "
                    f"Peers:{p.num_peers} Seeds:{p.num_seeds}"
                )
        
        await session.wait_for_download(handle, default_callback)
        return Path(save_path)
