import os
import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try importing SDK
try:
    from torbox_api import TorboxApi
    from torbox_api.models import CreateTorrentRequest
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning("torbox-api SDK not found. Falling back to REST API operations.")

class TorboxClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("TORBOX_API_KEY", "")
        self.base_url = "https://api.torbox.app/v1/api"
        
        if SDK_AVAILABLE and self.api_key:
            try:
                self.sdk = TorboxApi(
                    access_token=self.api_key,
                    base_url="https://api.torbox.app",
                    timeout=15000
                )
            except Exception as e:
                logger.error(f"Failed to initialize Torbox SDK: {e}")
                self.sdk = None
        else:
            self.sdk = None

    def add_magnet(self, magnet_link: str) -> Optional[dict]:
        """Adds a magnet link or a torrent URL to Torbox and returns the added torrent info."""
        if not self.api_key:
            logger.error("Torbox API Key not set.")
            return None

        # Check if this is a web URL pointing to a torrent file instead of a magnet link
        is_url = magnet_link.startswith("http://") or magnet_link.startswith("https://")
        
        file_payload = None
        if is_url:
            try:
                import re
                from ..database import Database
                logger.info(f"Detected HTTP/HTTPS torrent URL: {magnet_link}. Downloading torrent file...")
                
                # Fetch Prowlarr API Key directly from DB to authenticate the download if it's a Prowlarr redirect
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                }
                try:
                    db = Database()
                    row = db.execute("SELECT value FROM server_settings WHERE key = 'prowlarr_api_key'").fetchone()
                    prowlarr_key = row[0] if row else None
                    if prowlarr_key:
                        headers["X-Api-Key"] = prowlarr_key
                except Exception as db_err:
                    logger.debug(f"Could not load Prowlarr key from database: {db_err}")

                current_url = magnet_link
                redirect_count = 0
                max_redirects = 5
                resp = None
                
                while redirect_count < max_redirects:
                    resp = requests.get(current_url, headers=headers, timeout=15, allow_redirects=False)
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("Location")
                        if not location:
                            break
                        if location.startswith("magnet:"):
                            magnet_link = location
                            is_url = False
                            break
                        else:
                            current_url = location
                            redirect_count += 1
                    else:
                        resp.raise_for_status()
                        break
                
                if is_url and resp:
                    # Check if final content itself is a magnet link
                    if resp.text.strip().startswith("magnet:"):
                        magnet_link = resp.text.strip()
                        is_url = False
                    else:
                        # It's a torrent file!
                        content = resp.content
                        filename = "torrent.torrent"
                        cd = resp.headers.get("Content-Disposition")
                        if cd:
                            fn_match = re.findall(r'filename=["\']?([^"\']+)["\']?', cd)
                            if fn_match:
                                filename = fn_match[0]
                        file_payload = (filename, content, "application/x-bittorrent")
            except Exception as e:
                logger.error(f"Failed to download torrent file from URL: {e}")
                return None

        # Try using SDK first (SDK doesn't support file upload, so skip if it is a file)
        if self.sdk and not is_url:
            try:
                request_body = CreateTorrentRequest(magnet=magnet_link)
                response = self.sdk.torrents.create_torrent(api_version="v1", request_body=request_body)
                if response:
                    # Parse SDK response object
                    res_dict = {}
                    if hasattr(response, 'data') and response.data:
                        data = response.data
                        res_dict = {
                            "torrent_id": getattr(data, 'torrent_id', None) or getattr(data, 'id', None),
                            "hash": getattr(data, 'hash', None),
                            "name": getattr(data, 'name', None)
                        }
                        if not res_dict["torrent_id"] and hasattr(data, '_id'):
                            res_dict["torrent_id"] = data._id
                        return {"success": True, "data": res_dict}
                    elif hasattr(response, 'success') and response.success:
                        return {"success": True, "data": response.__dict__}
            except Exception as e:
                logger.error(f"Torbox SDK add_magnet error: {e}. Trying REST fallback.")

        # REST API Fallback
        url = f"{self.base_url}/torrents/createtorrent"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Prepare form parameters
        data = {
            "seed": "1",
            "allow_zip": "true"
        }
        
        files = None
        if is_url and file_payload:
            files = {
                "file": file_payload
            }
        else:
            data["magnet"] = magnet_link

        try:
            # Torbox expects form data / multipart for this endpoint
            logger.info(f"Submitting torrent to Torbox (REST)... is_file={bool(files)}")
            resp = requests.post(url, headers=headers, data=data, files=files, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if 'resp' in locals() and hasattr(resp, 'text'):
                logger.error(f"Torbox REST add_magnet failed: {e}. Response: {resp.text}")
                try:
                    err_json = resp.json()
                    if isinstance(err_json, dict):
                        return err_json
                except Exception:
                    pass
            else:
                logger.error(f"Torbox REST add_magnet failed: {e}")
            return None

    def get_torrents(self, torrent_id: str = None) -> List[dict]:
        """Gets user torrents list."""
        if not self.api_key:
            return []

        # We do NOT pass the torrent_id (id_) to the SDK or the REST API because of a major
        # serialization bug in the official torbox-api SDK when querying a single torrent by ID.
        # Instead, we query the full list with bypass_cache and filter client-side.
        if self.sdk:
            try:
                kwargs = {
                    "bypass_cache": "true"
                }
                response = self.sdk.torrents.get_torrent_list(api_version="v1", **kwargs)
                
                if response and hasattr(response, 'data') and response.data:
                    data = response.data
                    if isinstance(data, list):
                        return [self._map_sdk_torrent(t) for t in data]
                    else:
                        return [self._map_sdk_torrent(data)]
            except Exception as e:
                logger.error(f"Torbox SDK get_torrents error: {e}. Trying REST fallback.")

        # REST API Fallback
        url = f"{self.base_url}/torrents/mylist"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        params = {
            "bypass_cache": "true",
            "bypassCache": "true"
        }
            
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            res_json = resp.json()
            if res_json.get("success") and "data" in res_json:
                data = res_json["data"]
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return [data]
            return []
        except Exception as e:
            logger.error(f"Torbox REST get_torrents failed: {e}")
            return []

    def get_torrent_info(self, torrent_id: str) -> Optional[dict]:
        """Gets detailed torrent info by ID."""
        torrents = self.get_torrents(torrent_id)
        if torrents:
            for t in torrents:
                t_id = t.get("id") or t.get("torrent_id")
                if t_id and str(t_id) == str(torrent_id):
                    return t
        return None

    def control_torrent(self, torrent_id: str, action: str) -> bool:
        """Controls a torrent. Action can be 'reannounce', 'delete', 'resume'."""
        if not self.api_key:
            return False

        if self.sdk:
            try:
                body = {
                    "torrent_id": torrent_id,
                    "operation": action
                }
                response = self.sdk.torrents.control_torrent(api_version="v1", request_body=body)
                if response and hasattr(response, 'success'):
                    return response.success
            except Exception as e:
                logger.error(f"Torbox SDK control_torrent error: {e}. Trying REST fallback.")

        url = f"{self.base_url}/torrents/controltorrent"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "torrent_id": torrent_id,
            "operation": action
        }
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=15)
            resp.raise_for_status()
            res_json = resp.json()
            return res_json.get("success", False)
        except Exception as e:
            logger.error(f"Torbox REST control_torrent failed: {e}")
            return False

    def get_download_link(self, torrent_id: str, file_id: str) -> Optional[str]:
        """Gets the direct download link for a file within a torrent."""
        if not self.api_key:
            return None

        if self.sdk:
            try:
                response = self.sdk.torrents.request_download_link(
                    api_version="v1",
                    token=self.api_key,
                    torrent_id=str(torrent_id),
                    file_id=str(file_id)
                )
                if response and hasattr(response, 'data') and response.data:
                    return response.data
            except Exception as e:
                logger.error(f"Torbox SDK get_download_link error: {e}. Trying REST fallback.")

        # REST API Fallback
        url = f"{self.base_url}/torrents/requestdl"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        params = {
            "token": self.api_key,
            "torrent_id": torrent_id,
            "file_id": file_id
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            res_json = resp.json()
            if res_json.get("success"):
                return res_json.get("data")
            return None
        except Exception as e:
            logger.error(f"Torbox REST get_download_link failed: {e}")
            return None

    def get_magnet_info(self, magnet_link: str) -> Optional[dict]:
        """Queries Torbox /torrents/checkcached to get metadata (size, name) quickly if cached."""
        if not self.api_key:
            return None
        import re
        info_hash = None
        magnet_link_lower = magnet_link.lower()
        if magnet_link_lower.startswith("magnet:"):
            match = re.search(r'urn:btih:([a-zA-Z0-9]+)', magnet_link, re.IGNORECASE)
            if match:
                info_hash = match.group(1).lower()
        else:
            info_hash = magnet_link.lower()
            
        if not info_hash:
            logger.error("Torbox get_magnet_info: Could not extract info hash from magnet link")
            return None

        # Try GET checkcached (instant, <300ms)
        cache_url = f"{self.base_url}/torrents/checkcached"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        try:
            resp = requests.get(cache_url, headers=headers, params={"hash": info_hash}, timeout=3)
            resp.raise_for_status()
            res_json = resp.json()
            if res_json.get("success") and "data" in res_json:
                data = res_json["data"]
                if isinstance(data, dict):
                    for key, val in data.items():
                        if key.lower() == info_hash.lower() and isinstance(val, dict):
                            return {
                                "name": val.get("name") or val.get("title"),
                                "size": val.get("size", 0)
                            }
        except Exception as e:
            logger.warning(f"Torbox checkcached failed: {e}")

        return None

    def _map_sdk_torrent(self, t) -> dict:
        """Helper to convert SDK model to a standard dict matching the API response."""
        sdk_files = getattr(t, 'files', []) or []
        mapped_files = []
        for f in sdk_files:
            if f is not None:
                fid = getattr(f, 'id_', None)
                if fid is None:
                    fid = getattr(f, 'id', None)
                mapped_files.append({
                    "id": fid,
                    "name": getattr(f, 'name', None) or getattr(f, 'short_name', None),
                    "size": getattr(f, 'size', 0)
                })
                
        tid = getattr(t, 'id_', None)
        if tid is None:
            tid = getattr(t, 'id', None)
            
        return {
            "id": tid,
            "name": getattr(t, 'name', None),
            "progress": getattr(t, 'progress', 0.0),
            "active": getattr(t, 'active', False),
            "download_speed": getattr(t, 'download_speed', 0) or getattr(t, 'downloadSpeed', 0),
            "download_finished": getattr(t, 'download_finished', False) or getattr(t, 'downloadFinished', False),
            "download_state": getattr(t, 'download_state', "unknown") or getattr(t, 'downloadState', "unknown"),
            "size": getattr(t, 'size', 0),
            "hash": getattr(t, 'hash', None),
            "files": mapped_files
        }
