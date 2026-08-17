import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

# Try importing SDK
try:
	from torbox_api import TorboxApi  # type: ignore[import-not-found,import-untyped]
	from torbox_api.models import CreateTorrentRequest  # type: ignore[import-not-found,import-untyped]
	SDK_AVAILABLE = True
except ImportError:
	SDK_AVAILABLE = False
	logger.warning("torbox-api SDK not found. Falling back to REST API operations.")


class TorboxClient:
	"""
	Client for interacting with the Torbox Debrid API (SDK & REST API fallback).
	"""
	def __init__(self, api_key: Optional[str] = None) -> None:
		self.api_key = api_key or os.environ.get("TORBOX_API_KEY", "")
		self.base_url = "https://api.torbox.app/v1/api"
		self.sdk: Optional[Any] = None

		if SDK_AVAILABLE and self.api_key:
			try:
				self.sdk = TorboxApi(
					access_token=self.api_key,
					base_url="https://api.torbox.app",
					timeout=15000
				)
			except Exception as exc:  # pylint: disable=broad-exception-caught
				logger.error("Failed to initialize Torbox SDK: %s", exc)
				self.sdk = None

	def add_magnet(self, magnet_link: str) -> Optional[Dict[str, Any]]:
		"""Adds a magnet link or a torrent URL to Torbox and returns the added torrent info."""
		if not self.api_key:
			logger.error("Torbox API Key not set.")
			return None

		is_url = magnet_link.startswith("http://") or magnet_link.startswith("https://")
		file_payload: Optional[Tuple[str, bytes, str]] = None

		if is_url:
			try:
				from ..database import Database  # pylint: disable=import-outside-toplevel
				logger.info("Detected HTTP/HTTPS torrent URL: %s. Downloading torrent file...", magnet_link)

				headers = {
					"User-Agent": (
						"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
						"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
					)
				}
				try:
					db = Database()
					row = db.query("SELECT value FROM server_settings WHERE key = 'prowlarr_api_key'", one=True)
					prowlarr_key = row[0] if row else None
					if prowlarr_key:
						headers["X-Api-Key"] = prowlarr_key
				except Exception as db_err:  # pylint: disable=broad-exception-caught
					logger.debug("Could not load Prowlarr key from database: %s", db_err)

				current_url = magnet_link
				redirect_count = 0
				max_redirects = 5
				resp: Optional[requests.Response] = None

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
						current_url = location
						redirect_count += 1
					else:
						resp.raise_for_status()
						break

				if is_url and resp is not None:
					if resp.text.strip().startswith("magnet:"):
						magnet_link = resp.text.strip()
						is_url = False
					else:
						content = resp.content
						filename = "torrent.torrent"
						cd_header = resp.headers.get("Content-Disposition")
						if cd_header:
							fn_match = re.findall(r'filename=["\']?([^"\']+)["\']?', cd_header)
							if fn_match:
								filename = fn_match[0]
						file_payload = (filename, content, "application/x-bittorrent")
			except Exception as exc:  # pylint: disable=broad-exception-caught
				logger.error("Failed to download torrent file from URL: %s", exc)
				return None

		if self.sdk and not is_url:
			try:
				request_body = CreateTorrentRequest(magnet=magnet_link)
				response = self.sdk.torrents.create_torrent(api_version="v1", request_body=request_body)
				if response:
					res_dict: Dict[str, Any] = {}
					if hasattr(response, 'data') and response.data:
						res_data = response.data
						res_dict = {
							"torrent_id": getattr(res_data, 'torrent_id', None) or getattr(res_data, 'id', None),
							"hash": getattr(res_data, 'hash', None),
							"name": getattr(res_data, 'name', None)
						}
						if not res_dict["torrent_id"] and hasattr(res_data, '_id'):
							res_dict["torrent_id"] = getattr(res_data, '_id')
						return {"success": True, "data": res_dict}
					if hasattr(response, 'success') and response.success:
						return {"success": True, "data": getattr(response, '__dict__', {})}
			except Exception as exc:  # pylint: disable=broad-exception-caught
				logger.error("Torbox SDK add_magnet error: %s. Trying REST fallback.", exc)

		url = f"{self.base_url}/torrents/createtorrent"
		headers = {
			"Authorization": f"Bearer {self.api_key}"
		}
		data: Dict[str, Any] = {
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

		resp_obj: Optional[requests.Response] = None
		try:
			logger.info("Submitting torrent to Torbox (REST)... is_file=%s", bool(files))
			resp_obj = requests.post(url, headers=headers, data=data, files=files, timeout=20)
			resp_obj.raise_for_status()
			res_json = resp_obj.json()
			return res_json if isinstance(res_json, dict) else None
		except Exception as exc:  # pylint: disable=broad-exception-caught
			if resp_obj is not None and hasattr(resp_obj, 'text'):
				logger.error("Torbox REST add_magnet failed: %s. Response: %s", exc, resp_obj.text)
				try:
					err_json = resp_obj.json()
					if isinstance(err_json, dict):
						return err_json
				except Exception:  # pylint: disable=broad-exception-caught
					pass
			else:
				logger.error("Torbox REST add_magnet failed: %s", exc)
			return None

	def get_torrents(self, _torrent_id: Optional[str] = None) -> List[Dict[str, Any]]:
		"""Gets user torrents list."""
		if not self.api_key:
			return []

		if self.sdk:
			try:
				kwargs = {
					"bypass_cache": "true"
				}
				response = self.sdk.torrents.get_torrent_list(api_version="v1", **kwargs)

				if response and hasattr(response, 'data') and response.data:
					res_data = response.data
					if isinstance(res_data, list):
						return [self._map_sdk_torrent(t) for t in res_data]
					return [self._map_sdk_torrent(res_data)]
			except Exception as exc:  # pylint: disable=broad-exception-caught
				logger.error("Torbox SDK get_torrents error: %s. Trying REST fallback.", exc)

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
			if isinstance(res_json, dict) and res_json.get("success") and "data" in res_json:
				raw_data = res_json["data"]
				if isinstance(raw_data, list):
					return [item for item in raw_data if isinstance(item, dict)]
				if isinstance(raw_data, dict):
					return [raw_data]
			return []
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("Torbox REST get_torrents failed: %s", exc)
			return []

	def get_torrent_info(self, torrent_id: str) -> Optional[Dict[str, Any]]:
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
					return bool(response.success)
			except Exception as exc:  # pylint: disable=broad-exception-caught
				logger.error("Torbox SDK control_torrent error: %s. Trying REST fallback.", exc)

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
			return bool(res_json.get("success", False)) if isinstance(res_json, dict) else False
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("Torbox REST control_torrent failed: %s", exc)
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
					return str(response.data)
			except Exception as exc:  # pylint: disable=broad-exception-caught
				logger.error("Torbox SDK get_download_link error: %s. Trying REST fallback.", exc)

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
			if isinstance(res_json, dict) and res_json.get("success"):
				dl_data = res_json.get("data")
				return str(dl_data) if dl_data else None
			return None
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.error("Torbox REST get_download_link failed: %s", exc)
			return None

	def get_magnet_info(self, magnet_link: str) -> Optional[Dict[str, Any]]:
		"""Queries Torbox /torrents/checkcached to get metadata (size, name) quickly if cached."""
		if not self.api_key:
			return None

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

		cache_url = f"{self.base_url}/torrents/checkcached"
		headers = {
			"Authorization": f"Bearer {self.api_key}"
		}
		try:
			resp = requests.get(cache_url, headers=headers, params={"hash": info_hash}, timeout=3)
			resp.raise_for_status()
			res_json = resp.json()
			if isinstance(res_json, dict) and res_json.get("success") and "data" in res_json:
				raw_data = res_json["data"]
				if isinstance(raw_data, dict):
					for key, val in raw_data.items():
						if key.lower() == info_hash.lower() and isinstance(val, dict):
							return {
								"name": val.get("name") or val.get("title"),
								"size": val.get("size", 0)
							}
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.warning("Torbox checkcached failed: %s", exc)

		return None

	def _map_sdk_torrent(self, t: Any) -> Dict[str, Any]:
		"""Helper to convert SDK model to a standard dict matching the API response."""
		sdk_files = getattr(t, 'files', []) or []
		mapped_files: List[Dict[str, Any]] = []
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
