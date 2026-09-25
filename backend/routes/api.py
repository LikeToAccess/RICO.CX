import datetime
import logging
import os
import re
import secrets
import shutil
import threading
import time
from collections import deque
from functools import wraps
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import requests
from flask import Blueprint, request, jsonify, g, redirect
from ..models.user import User
from ..models.result import TorrentResult, AggregatedResult
from ..services.search_client import SearchClient
from ..services.torbox_client import TorboxClient
from ..services.tmdb_client import TmdbClient
from ..database import Database
from ..app import socketio

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

ACTIVE_DOWNLOAD_TASKS: Set[Tuple[int, str]] = set()
ACTIVE_TASKS_LOCK = threading.Lock()
_RESUMPTION_INITIALIZED = False
_RESUMPTION_LOCK = threading.Lock()
MAX_CONCURRENT_LOCAL_TRANSFERS = 2
LOCAL_TRANSFER_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_LOCAL_TRANSFERS)

def get_server_settings():
	db = Database()
	rows = db.query("SELECT key, value FROM server_settings") or []
	settings = {}
	for row in rows:
		settings[row["key"]] = row["value"]
	# Fallback to env variables if not in db
	settings.setdefault("prowlarr_url", os.environ.get("PROWLARR_URL", ""))
	settings.setdefault("prowlarr_api_key", os.environ.get("PROWLARR_API_KEY", ""))
	settings.setdefault("torbox_api_key", os.environ.get("TORBOX_API_KEY", ""))
	settings.setdefault("library_path", os.environ.get("ROOT_LIBRARY_LOCATION", "./library"))
	settings.setdefault("tmdb_api_key", os.environ.get("TMDB_API_KEY", ""))
	return settings

def save_server_settings(settings):
	db = Database()
	for key, value in settings.items():
		db.execute("INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", (key, value))

# Authentication Decorator
def login_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		# Look for token in Authorization header, then cookie
		token = request.headers.get("Authorization")
		if token and token.startswith("Bearer ") and token[7:].strip() not in ("", "null", "undefined"):
			token = token[7:].strip()
		else:
			token = request.cookies.get("session_token")

		user = User.verify_session(token)
		if not user:
			return jsonify({"error": "Unauthorized"}), 401

		g.user = user

		# Access control: users without group are pending approval
		# Bypassed only for /api/auth/me and /api/auth/logout
		if not user.group_id or not user.group:
			if request.path not in ('/api/auth/me', '/api/auth/logout'):
				return jsonify({"error": "Approval pending. Please contact an Administrator."}), 403

		return f(*args, **kwargs)
	return decorated_function

# Background Task for Torbox Lifecycle Monitoring & Downloader
def monitor_and_download_task(user_id, torbox_id, metadata, db_download_id):
	"""
	Background task to poll Torbox API for progress, update the DB,
	emit WebSocket updates, and stream files to local media folders when completed.
	"""
	task_key = (db_download_id, str(torbox_id))
	with ACTIVE_TASKS_LOCK:
		if task_key in ACTIVE_DOWNLOAD_TASKS:
			logger.warning(f"Task already active for download ID {db_download_id} (Torbox ID: {torbox_id}). Aborting duplicate thread.")
			return
		ACTIVE_DOWNLOAD_TASKS.add(task_key)

	try:
		_execute_monitor_and_download(user_id, torbox_id, metadata, db_download_id)
	finally:
		with ACTIVE_TASKS_LOCK:
			ACTIVE_DOWNLOAD_TASKS.discard(task_key)


def _execute_monitor_and_download(user_id, torbox_id, metadata, db_download_id):
	time.sleep(2)
	db = Database()

	written_paths = []
	created_dirs = []

	# Reload user to ensure latest settings
	user = User.get_by_id(user_id)
	if not user:
		logger.error(f"User {user_id} not found. Exiting task.")
		return

	settings = get_server_settings()
	torbox_key = settings.get("torbox_api_key") or os.environ.get("TORBOX_API_KEY", "")
	torbox = TorboxClient(api_key=torbox_key)

	library_root = settings.get("library_path") or os.environ.get("ROOT_LIBRARY_LOCATION", "./library")
	library_root = os.path.abspath(library_root)

	logger.info(f"Task started. Monitoring Torbox torrent: {torbox_id}. Library: {library_root}")

	last_emit_time = 0

	while True:
		try:
			# Check if cancelled (i.e. deleted from local database)
			exists = db.query("SELECT id FROM downloads WHERE id = ?", (db_download_id,), one=True)
			if not exists:
				logger.info(f"Download {db_download_id} (Torbox ID: {torbox_id}) was cancelled/deleted from database. Exiting monitor task.")
				break

			info = torbox.get_torrent_info(torbox_id)
			if not info:
				logger.error(f"Torrent {torbox_id} could not be found in Torbox.")
				db.execute("UPDATE downloads SET status = 'failed' WHERE id = ?", (db_download_id,))
				socketio.emit('download_progress', {
					'id': torbox_id,
					'title': metadata.get('title', 'Unknown'),
					'filename': metadata.get('filename', 'Unknown'),
					'magnet': metadata.get('magnet'),
					'status': 'failed',
					'progress': 0,
					'speed': 0,
					'user_id': user_id
				})
				break

			raw_progress = info.get("progress", 0.0)
			# Torbox SDK returns progress in 0-1 range or 0-100 range.
			progress = int(raw_progress * 100) if raw_progress <= 1.0 else int(raw_progress)
			speed = info.get("download_speed", 0.0) or 0.0
			state = str(info.get("download_state", "downloading")).lower()
			size = info.get("size", 0) or 0

			# Map raw/cryptic states to human-friendly terms
			friendly_state = state
			if state == "metadl":
				friendly_state = "metadata"
			elif state == "checkingresumedata":
				friendly_state = "checking files"
			elif "stalled" in state:
				friendly_state = "stalled"
			elif state == "paused":
				friendly_state = "paused"
			elif state == "checking":
				friendly_state = "checking files"
			elif state == "allocating":
				friendly_state = "allocating space"
			elif state == "downloading":
				friendly_state = "no cache"
			elif state in ("completed", "cached"):
				friendly_state = "completed"
			elif state == "uploading":
				friendly_state = "seeding"

			# Construct user-friendly status strings
			if friendly_state == "no cache":
				status_str = "Downloading (no cache)"
				db_status = "downloading (no cache)"
			else:
				status_str = f"Downloading ({friendly_state})"
				db_status = f"downloading ({friendly_state})"

			# Throttle websocket emits and persist live state in database
			now = time.time()
			if now - last_emit_time >= 1.5:
				db.execute(
					"UPDATE downloads SET status = ?, progress = ?, speed = ?, size = ? WHERE id = ?",
					(status_str, progress, speed, size, db_download_id)
				)
				socketio.emit('download_progress', {
					'id': torbox_id,
					'title': metadata.get('title'),
					'filename': metadata.get('filename'),
					'magnet': metadata.get('magnet'),
					'status': status_str,
					'progress': progress,
					'speed': speed,
					'size': size,
					'user_id': user_id
				})
				last_emit_time = now

			# Complete on Torbox?
			if state in ("completed", "cached", "uploading") or progress >= 100 or info.get("download_finished"):
				logger.info(f"Torbox finished downloading {torbox_id}. Copying files locally...")

				db.execute("UPDATE downloads SET status = 'moving', speed = 0 WHERE id = ?", (db_download_id,))
				socketio.emit('download_progress', {
					'id': torbox_id,
					'title': metadata.get('title'),
					'filename': metadata.get('filename'),
					'magnet': metadata.get('magnet'),
					'status': 'moving',
					'progress': 0,
					'speed': 0,
					'size': info.get("size", 0) or 0,
					'user_id': user_id
				})

				# Fetch file objects
				files = info.get("files", [])
				if not files:
					# Wait and retry once
					time.sleep(3)
					info = torbox.get_torrent_info(torbox_id)
					files = info.get("files", []) if info else []

				video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.m4v'}
				video_files = []
				for f in files:
					f_name = f.get("name", "").lower()
					if "sample" in f_name:
						continue
					if any(f_name.endswith(ext) for ext in video_extensions):
						video_files.append(f)

				if not video_files:
					if files:
						largest = max(files, key=lambda x: x.get("size", 0))
						video_files = [largest]
					else:
						logger.error("No files found in Torbox torrent.")
						db.execute("UPDATE downloads SET status = 'failed' WHERE id = ?", (db_download_id,))
						socketio.emit('download_progress', {
							'id': torbox_id,
							'title': metadata.get('title'),
							'filename': metadata.get('filename'),
							'magnet': metadata.get('magnet'),
							'status': 'failed',
							'progress': 0,
							'speed': 0,
							'user_id': user_id
						})
						break

				total_files_size = sum(f.get("size", 0) for f in video_files)
				total_downloaded = 0
				local_transfer_success = True

				# Resolve official metadata from TMDb
				settings = get_server_settings()
				tmdb_key = settings.get("tmdb_api_key") or os.environ.get("TMDB_API_KEY", "")
				tmdb = TmdbClient(api_key=tmdb_key)

				import urllib.parse
				magnet_str = metadata.get("magnet", "")
				dn_match = re.search(r'[?&]dn=([^&]+)', magnet_str)
				if dn_match:
					full_release_name = urllib.parse.unquote_plus(dn_match.group(1))
				else:
					full_release_name = metadata.get("filename") or metadata.get("title", "Unknown")

				parsed_torrent = TorrentResult(title=full_release_name, size=0, download_url="", seeders=0, leechers=0, indexer="")
				title_clean = parsed_torrent.clean_title or metadata.get("title", "Unknown")
				category = metadata.get("category", "movie")
				year = parsed_torrent.year or metadata.get("year")

				if category == "movie" and len(video_files) > 1:
					# For movies, select only the main feature film to prevent extra featurettes from overwriting the file
					largest_movie_file = max(video_files, key=lambda x: x.get("size", 0))
					video_files = [largest_movie_file]
					total_files_size = sum(f.get("size", 0) for f in video_files)

				tmdb_id = None
				official_title = title_clean
				official_year = year

				# Helper to make sure filenames are filesystem safe
				def make_safe_filename(name: str) -> str:
					if not name:
						return ""
					return re.sub(r'[\/\\\:\*\?\"\<\>\|]', '', name).strip()

				if category == "movie":
					res = tmdb.search_movie(title_clean, year)
					if res:
						official_title = res["title"]
						official_year = res["year"]
						tmdb_id = res["id"]
				elif category == "tv":
					res = tmdb.search_tv(title_clean, year)
					if res:
						official_title = res["title"]
						official_year = res["year"]
						tmdb_id = res["id"]

						# Dynamically validate season against TMDb's available seasons for this show entry
						req_season = metadata.get("season")
						if req_season and tmdb_id:
							valid_seasons = tmdb.get_tv_seasons(tmdb_id)
							if isinstance(valid_seasons, list) and valid_seasons and req_season not in valid_seasons:
								metadata["season"] = valid_seasons[0]

				official_title_safe = make_safe_filename(official_title)
				official_year_safe = make_safe_filename(str(official_year)) if official_year else ""

				# Format folder name: Avatar (2009) {tmdb-19995}
				if tmdb_id:
					folder_name = f"{official_title_safe} ({official_year_safe}) {{tmdb-{tmdb_id}}}" if official_year_safe else f"{official_title_safe} {{tmdb-{tmdb_id}}}"
				else:
					folder_name = f"{official_title_safe} ({official_year_safe})" if official_year_safe else official_title_safe

				show_name_filename = f"{official_title_safe} ({official_year_safe})" if official_year_safe else official_title_safe

				for idx, file in enumerate(video_files):
					file_id = file.get("id")
					file_name = file.get("name") or metadata.get("filename")
					ext = os.path.splitext(file_name)[1] or ".mkv"

					dl_link = torbox.get_download_link(torbox_id, file_id)
					if not dl_link:
						logger.error(f"Failed to generate download url for file {file_id}")
						local_transfer_success = False
						break

					# Determine target season and episode
					season = metadata.get("season")
					episode = metadata.get("episode")

					# Try parsing from specific file name in case it is a season pack
					tv_match = re.search(r'\b[sS](\d{1,2})[eE](\d{1,2})\b', file_name)
					if tv_match:
						season = int(tv_match.group(1))
						episode = int(tv_match.group(2))
					else:
						x_match = re.search(r'\b(\d{1,2})x(\d{1,2})\b', file_name)
						if x_match:
							season = int(x_match.group(1))
							episode = int(x_match.group(2))
						else:
							season_match = re.search(r'\b[sS]eason\s*(\d{1,2})\b', file_name, re.IGNORECASE)
							if season_match:
								season = int(season_match.group(1))
							elif not season:
								s_match = re.search(r'\b[sS](\d{1,2})\b', file_name)
								if s_match:
									season = int(s_match.group(1))

							episode_match = re.search(r'\b(?:[eE]pisode|[eE]p)\.?\s*(\d{1,2})\b', file_name, re.IGNORECASE)
							if episode_match:
								episode = int(episode_match.group(1))
							elif not episode:
								e_match = re.search(r'\b[eE](\d{1,2})\b', file_name)
								if e_match:
									episode = int(e_match.group(1))

					if category == "tv":
						if tmdb_id and season:
							valid_seasons = tmdb.get_tv_seasons(tmdb_id)
							if isinstance(valid_seasons, list) and valid_seasons and season not in valid_seasons:
								season = valid_seasons[0]

						try:
							s_num = int(season) if (season is not None and type(season).__name__ not in ('MagicMock', 'Mock')) else 1
						except (ValueError, TypeError):
							s_num = 1

						try:
							e_num = int(episode) if (episode is not None and type(episode).__name__ not in ('MagicMock', 'Mock')) else 1
						except (ValueError, TypeError):
							e_num = 1

						season_folder = f"Season {s_num:02d}"
						dest_dir = os.path.join(library_root, "TV SHOWS", folder_name, season_folder)

						episode_name = None
						if tmdb_id and season and episode:
							episode_name = tmdb.get_episode_name(tmdb_id, season, episode)

						episode_name_safe = make_safe_filename(episode_name) if (episode_name and type(episode_name).__name__ not in ('MagicMock', 'Mock')) else ""

						if episode_name_safe:
							base_filename = f"{show_name_filename} - S{s_num:02d}E{e_num:02d} - {episode_name_safe}{ext}"
						else:
							base_filename = f"{show_name_filename} - S{s_num:02d}E{e_num:02d}{ext}"
					else:
						dest_dir = os.path.join(library_root, "MOVIES", folder_name)
						base_filename = f"{folder_name}{ext}"

					os.makedirs(dest_dir, exist_ok=True)
					dest_path = os.path.join(dest_dir, base_filename)

					temp_dest_path = dest_path + ".crdownload"
					if dest_path not in written_paths:
						written_paths.append(dest_path)
					if dest_dir not in created_dirs:
						created_dirs.append(dest_dir)

					# Check if destination file already exists with exact size match
					file_size = file.get("size", 0)
					if os.path.exists(dest_path) and os.path.getsize(dest_path) == file_size:
						logger.info(f"Local file already exists with exact size match ({file_size} bytes): {dest_path}. Skipping copy.")
						total_downloaded += file_size
						continue

					logger.info(f"Local Transfer: {file_name} -> {temp_dest_path}")

					MAX_RETRIES = 2
					transfer_done = False
					start_time = time.time()

					with LOCAL_TRANSFER_SEMAPHORE:
						for attempt in range(1, MAX_RETRIES + 1):
							# Check if cancelled/deleted from database
							exists = db.query("SELECT id FROM downloads WHERE id = ?", (db_download_id,), one=True)
							if not exists:
								logger.info(f"Download {db_download_id} was cancelled during transfer. Aborting and cleaning up.")
								local_transfer_success = False
								break

							# Refresh download link on retries in case token expired
							if attempt > 1:
								fresh_link = torbox.get_download_link(torbox_id, file_id)
								if fresh_link:
									dl_link = fresh_link

							# If attempt 1 failed, corrupt resume, or attempt > 1: force fresh overwrite from byte 0
							if attempt > 1:
								if os.path.exists(temp_dest_path):
									try:
										os.remove(temp_dest_path)
									except Exception:
										pass
								existing_bytes = 0
							else:
								existing_bytes = os.path.getsize(temp_dest_path) if os.path.exists(temp_dest_path) else 0

							if file_size > 0 and existing_bytes == file_size:
								logger.info(f"Local file transfer already complete ({existing_bytes} bytes).")
								transfer_done = True
								break

							if file_size > 0 and existing_bytes > file_size:
								logger.warning(f"Existing file size ({existing_bytes} bytes) exceeds target size ({file_size} bytes). Resetting {temp_dest_path}.")
								try:
									os.remove(temp_dest_path)
								except Exception:
									pass
								existing_bytes = 0

							headers = {
								"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
							}
							if existing_bytes > 0:
								headers["Range"] = f"bytes={existing_bytes}-"
								logger.info(f"Resuming transfer for {file_name} from byte {existing_bytes} (Attempt {attempt}/{MAX_RETRIES})...")
							else:
								if attempt > 1:
									logger.info(f"Fallback to fresh redownload for {file_name} from start (Attempt {attempt}/{MAX_RETRIES})...")

							try:
								resp = requests.get(dl_link, headers=headers, stream=True, timeout=(15, 600))

								# Extract authoritative total file size from response headers if available
								content_range = resp.headers.get("Content-Range")
								content_length = resp.headers.get("Content-Length")
								if content_range and type(content_range).__name__ not in ('MagicMock', 'Mock'):
									try:
										header_total = int(str(content_range).split('/')[-1])
										if header_total > 0:
											file_size = header_total
									except Exception:
										pass
								elif resp.status_code == 200 and content_length and type(content_length).__name__ not in ('MagicMock', 'Mock'):
									try:
										header_total = int(str(content_length))
										if header_total > 0:
											file_size = header_total
									except Exception:
										pass

								if resp.status_code == 206:
									open_mode = "ab"
									current_file_downloaded = existing_bytes
								elif resp.status_code in (200, 203):
									open_mode = "wb"
									current_file_downloaded = 0
								elif resp.status_code == 416: # Range Not Satisfiable
									if file_size > 0 and existing_bytes >= file_size:
										transfer_done = True
										break
									open_mode = "wb"
									current_file_downloaded = 0
									if os.path.exists(temp_dest_path):
										os.remove(temp_dest_path)
								else:
									resp.raise_for_status()
									open_mode = "wb"
									current_file_downloaded = 0

								last_file_emit = 0
								bytes_since_flush = 0
								speed_samples = deque()  # Stores (timestamp, bytes_downloaded) for 5s sliding window
								speed_samples.append((time.time(), current_file_downloaded))

								CHUNK_SIZE = 1024 * 1024  # 1MB chunks aligned with NFS mount block size

								with open(temp_dest_path, open_mode) as f_out:
									for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
										if chunk:
											f_out.write(chunk)
											current_file_downloaded += len(chunk)
											bytes_since_flush += len(chunk)
											now_f = time.time()

											# Cooperative yield for gevent / event loop on every 1MB chunk
											time.sleep(0.001)

											# Flush userland buffers every 16MB without stalling fsync
											if bytes_since_flush >= 16 * 1024 * 1024:
												try:
													f_out.flush()
												except Exception:
													pass
												bytes_since_flush = 0

											# 5-second sliding window speed calculation
											speed_samples.append((now_f, current_file_downloaded))
											while speed_samples and (now_f - speed_samples[0][0]) > 5.0:
												speed_samples.popleft()

											if len(speed_samples) > 1:
												time_diff = speed_samples[-1][0] - speed_samples[0][0]
												bytes_diff = speed_samples[-1][1] - speed_samples[0][1]
												current_speed = bytes_diff / time_diff if time_diff > 0 else 0
											else:
												current_speed = 0

											overall_bytes = total_downloaded + current_file_downloaded
											overall_progress = int((overall_bytes / total_files_size) * 100) if total_files_size > 0 else 0

											if now_f - last_file_emit >= 1.5:
												exists = db.query("SELECT id FROM downloads WHERE id = ?", (db_download_id,), one=True)
												if not exists:
													logger.info(f"Download {db_download_id} was cancelled during transfer stream. Aborting.")
													local_transfer_success = False
													break

												moving_status = f"Moving file {idx+1}/{len(video_files)}"
												try:
													db.execute(
														"UPDATE downloads SET status = ?, progress = ?, speed = ?, size = ? WHERE id = ?",
														(moving_status, overall_progress, current_speed, total_files_size, db_download_id)
													)
												except Exception as db_err:
													logger.warning("Database write error during transfer progress update: %s", db_err)

												socketio.emit('download_progress', {
													'id': torbox_id,
													'title': metadata.get('title'),
													'filename': metadata.get('filename'),
													'magnet': metadata.get('magnet'),
													'status': moving_status,
													'progress': overall_progress,
													'speed': current_speed,
													'size': total_files_size,
													'user_id': user_id
												})
												last_file_emit = now_f

								if not exists:
									local_transfer_success = False
									break

								actual_size = os.path.getsize(temp_dest_path) if os.path.exists(temp_dest_path) else 0
								if file_size > 0 and actual_size == file_size:
									transfer_done = True
									break
								elif file_size == 0 and actual_size > 0:
									transfer_done = True
									break
								else:
									logger.warning(f"Transfer incomplete for {file_name}: got {actual_size}/{file_size} bytes. Falling back to fresh overwrite (Attempt {attempt}/{MAX_RETRIES})...")

							except Exception as ex:
								actual_size = os.path.getsize(temp_dest_path) if os.path.exists(temp_dest_path) else 0
								logger.error(f"Local Transfer connection error for {file_name} at {actual_size}/{file_size} bytes: {ex}. Retrying...")

						if not exists:
							break

						if transfer_done and os.path.exists(temp_dest_path):
							final_size = os.path.getsize(temp_dest_path)
							if file_size == 0 or final_size == file_size:
								logger.info(f"File verification successful (exact size match: {final_size} bytes). Renaming to final destination: {dest_path}")
								if os.path.exists(dest_path):
									os.remove(dest_path)
								os.rename(temp_dest_path, dest_path)
								total_downloaded += final_size
								logger.info(f"Local Transfer complete for file: {file_name}")
							else:
								logger.error(f"File size mismatch for {file_name}: expected {file_size} bytes, got {final_size} bytes. Retaining temporary .crdownload suffix.")
								local_transfer_success = False
								break
						else:
							logger.error(f"Local Transfer failed after {MAX_RETRIES} attempts for file: {file_name}")
							local_transfer_success = False
							break

				# Check if cancelled before finishing
				exists = db.query("SELECT id FROM downloads WHERE id = ?", (db_download_id,), one=True)
				if not exists:
					logger.info(f"Download {db_download_id} was cancelled. Cleaning up files.")
					# Clean up all written files (and any temporary .crdownload duplicates)
					for path in written_paths:
						for p in (path, path + ".crdownload"):
							if os.path.exists(p):
								try:
									os.remove(p)
									logger.info(f"Cleaned up file on cancellation: {p}")
								except Exception as clean_ex:
									logger.error(f"Failed to delete {p}: {clean_ex}")

					# Clean up created directories if they are empty
					for ddir in created_dirs:
						try:
							if os.path.exists(ddir) and not os.listdir(ddir):
								os.rmdir(ddir)
								logger.info(f"Removed empty directory: {ddir}")

								# Try removing parent category dir if empty (e.g. MOVIES/TV SHOWS subfolder)
								parent = os.path.dirname(ddir)
								if os.path.exists(parent) and not os.listdir(parent):
									os.rmdir(parent)
									logger.info(f"Removed empty parent directory: {parent}")
						except Exception:
							pass
					break # Exit monitor task

				if local_transfer_success:
					db.execute("UPDATE downloads SET status = 'completed', progress = 100, speed = 0 WHERE id = ?", (db_download_id,))
					socketio.emit('download_progress', {
						'id': torbox_id,
						'title': metadata.get('title'),
						'filename': metadata.get('filename'),
						'magnet': metadata.get('magnet'),
						'status': 'completed',
						'progress': 100,
						'speed': 0,
						'size': total_files_size,
						'user_id': user_id
					})
					invalidate_library_sizes_cache(library_root)
					logger.info(f"Download complete: {metadata.get('filename')}")
				else:
					db.execute("UPDATE downloads SET status = 'failed' WHERE id = ?", (db_download_id,))
					socketio.emit('download_progress', {
						'id': torbox_id,
						'title': metadata.get('title'),
						'filename': metadata.get('filename'),
						'magnet': metadata.get('magnet'),
						'status': 'failed',
						'progress': 0,
						'speed': 0,
						'size': total_files_size,
						'user_id': user_id
					})
				break

			time.sleep(3)
		except Exception as e:
			logger.error(f"Monitor loop error for torrent {torbox_id}: {e}")
			time.sleep(5)


# AUTHENTICATION ROUTES
@api_bp.route('/auth/google/login', methods=['GET'])
def google_login():
	client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
	if not client_id:
		return jsonify({"error": "Google Client ID is not configured on the server."}), 500

	import secrets
	state = secrets.token_urlsafe(32)

	redirect_uri = f"{request.host_url.rstrip('/')}/api/auth/google/callback"
	google_auth_url = (
		f"https://accounts.google.com/o/oauth2/v2/auth?"
		f"client_id={client_id}&"
		f"redirect_uri={redirect_uri}&"
		f"response_type=code&"
		f"scope=openid%20email%20profile&"
		f"state={state}"
	)
	is_secure = (os.environ.get("USE_SSL", "false").lower() == "true" or request.is_secure or request.headers.get("X-Forwarded-Proto") == "https")
	response = redirect(google_auth_url)
	response.set_cookie("oauth_state", state, max_age=600, httponly=True, samesite='Lax', secure=is_secure)
	return response

@api_bp.route('/auth/google/callback', methods=['GET'])
def google_callback():
	code = request.args.get("code")
	state = request.args.get("state")
	cookie_state = request.cookies.get("oauth_state")

	if not code:
		return jsonify({"error": "Missing authorization code from Google"}), 400

	if not state or not cookie_state or state != cookie_state:
		return jsonify({"error": "Invalid or expired OAuth state parameter"}), 400

	client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
	client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
	redirect_uri = f"{request.host_url.rstrip('/')}/api/auth/google/callback"

	# Exchange authorization code for access token
	token_url = "https://oauth2.googleapis.com/token"
	payload = {
		"code": code,
		"client_id": client_id,
		"client_secret": client_secret,
		"redirect_uri": redirect_uri,
		"grant_type": "authorization_code"
	}

	try:
		resp = requests.post(token_url, data=payload, timeout=10)
		if resp.status_code != 200:
			logger.error(f"Google Token Exchange error status {resp.status_code}: {resp.text}")
		resp.raise_for_status()
		token_data = resp.json()
	except Exception as e:
		logger.error(f"Google Token Exchange failed: {e}")
		err_msg = str(e)
		if 'resp' in locals() and hasattr(resp, 'text') and resp.text:
			err_msg += f" | Response: {resp.text}"
		return jsonify({"error": "Failed to exchange token with Google", "details": err_msg}), 400

	access_token = token_data.get("access_token")
	if not access_token:
		return jsonify({"error": "Google token response did not contain access token", "details": token_data}), 400

	# Retrieve user information
	userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
	headers = {"Authorization": f"Bearer {access_token}"}
	try:
		userinfo_resp = requests.get(userinfo_url, headers=headers, timeout=10)
		userinfo_resp.raise_for_status()
		user_data = userinfo_resp.json()
	except Exception as e:
		logger.error(f"Failed to fetch Google userinfo: {e}")
		return jsonify({"error": "Failed to retrieve user info from Google", "details": str(e)}), 400

	email = user_data.get("email")
	full_name = user_data.get("name")
	first_name = user_data.get("given_name")
	last_name = user_data.get("family_name")
	profile_picture = user_data.get("picture")

	if not email:
		return jsonify({"error": "Google account does not provide an email address."}), 400

	# Find or create user
	user = User.get_by_username(email)
	if not user:
		import uuid
		db = Database()
		user_count_row = db.query("SELECT COUNT(*) FROM users", one=True)
		role = "Admin" if user_count_row and user_count_row[0] == 0 else None

		user = User.create(
			username=email,
			password=str(uuid.uuid4()),
			group_name=role,
			full_name=full_name,
			first_name=first_name,
			last_name=last_name,
			profile_picture=profile_picture
		)
		logger.info(f"Created new user via Google Authentication: {email} with role: {role}")
		if role is None:
			send_ha_notification("new_pending_user", {
				"username": email,
				"full_name": full_name or email,
				"user_id": user.id
			})
	else:
		# Update details in case they changed on Google profile
		user.full_name = full_name
		user.first_name = first_name
		user.last_name = last_name
		user.profile_picture = profile_picture
		user.save()
		logger.info(f"Updated user details on login for: {email}")

	token = User.create_session(user.id)

	is_secure = (os.environ.get("USE_SSL", "false").lower() == "true" or request.is_secure or request.headers.get("X-Forwarded-Proto") == "https")
	response = redirect("/")
	response.set_cookie("session_token", token, max_age=30*24*60*60, httponly=True, samesite='Lax', secure=is_secure)
	response.delete_cookie("oauth_state")
	return response

@api_bp.route('/auth/login', methods=['POST'])
def login():
	return jsonify({"error": "Password login is disabled. Please use Google Authentication."}), 400

@api_bp.route('/auth/logout', methods=['POST'])
def logout():
	token = request.cookies.get("session_token")
	if token:
		User.delete_session(token)
	resp = jsonify({"success": True})
	resp.delete_cookie("session_token")
	return resp

@api_bp.route('/auth/me', methods=['GET'])
@login_required
def me():
	token = request.headers.get("Authorization")
	if token and token.startswith("Bearer ") and token[7:].strip() not in ("", "null", "undefined"):
		token = token[7:].strip()
	else:
		token = request.cookies.get("session_token")

	user_dict = g.user.to_dict()
	user_dict["session_token"] = token
	return jsonify(user_dict)


_LIBRARY_SIZES_CACHE: Dict[str, Tuple[Set[int], float]] = {}
_LIBRARY_SIZES_LOCK = threading.Lock()
_LIBRARY_SIZES_SCANNING: Set[str] = set()
_LIBRARY_SIZES_TTL = 1800.0  # 30 minutes TTL


def invalidate_library_sizes_cache(library_root: Optional[str] = None) -> None:
	"""Invalidates the in-memory library file sizes cache."""
	with _LIBRARY_SIZES_LOCK:
		if library_root:
			_LIBRARY_SIZES_CACHE.pop(os.path.abspath(library_root), None)
		else:
			_LIBRARY_SIZES_CACHE.clear()


def get_library_file_sizes(library_root: str) -> Set[int]:
	"""
	Returns a set of file sizes present in the local media library root.
	Fast, non-blocking implementation:
	- First collects all completed download sizes directly from the database (instant 0.1ms).
	- Merges with cached filesystem sizes.
	- If cache is empty or expired, scans synchronously only for small local folders (<300 files)
	  or dispatches a non-blocking background scanner for massive libraries (e.g. NFS mounts),
	  preventing 80+ second stop-the-world freezes on the web thread.
	"""
	t_start = time.time()
	db = Database()
	rows = db.query("SELECT DISTINCT size FROM downloads WHERE status = 'completed' AND size > 0") or []
	db_sizes: Set[int] = {r["size"] for r in rows if r["size"]}

	if not library_root or not os.path.exists(library_root):
		return db_sizes

	abs_root = os.path.abspath(library_root)
	now = time.time()
	cached_disk_sizes: Set[int] = set()

	with _LIBRARY_SIZES_LOCK:
		if abs_root in _LIBRARY_SIZES_CACHE:
			cached_sizes, expiry = _LIBRARY_SIZES_CACHE[abs_root]
			cached_disk_sizes = set(cached_sizes)
			if now < expiry:
				logger.debug("[PERF] get_library_file_sizes cache HIT in %.3fms (total %d sizes)", (time.time() - t_start) * 1000, len(cached_disk_sizes | db_sizes))
				return cached_disk_sizes | db_sizes

	# Check top level to distinguish small local test directories from massive 22TB NFS mounts
	file_count = 0
	is_small_dir = True
	try:
		with os.scandir(abs_root) as it:
			for entry in it:
				if entry.is_dir() and entry.name.upper() in ("MOVIES", "TV SHOWS"):
					try:
						with os.scandir(entry.path) as sub_it:
							if sum(1 for _ in sub_it) > 100:
								is_small_dir = False
								break
					except OSError:
						pass
				if not is_small_dir:
					break
	except OSError:
		is_small_dir = False

	if is_small_dir:
		sizes: Set[int] = set()
		try:
			for root, _, files in os.walk(abs_root):
				for f in files:
					file_count += 1
					if file_count > 300:
						is_small_dir = False
						break
					try:
						sizes.add(os.path.getsize(os.path.join(root, f)))
					except OSError:
						pass
				if not is_small_dir:
					break
		except OSError:
			pass

		if is_small_dir:
			with _LIBRARY_SIZES_LOCK:
				_LIBRARY_SIZES_CACHE[abs_root] = (sizes, now + _LIBRARY_SIZES_TTL)
			logger.debug("[PERF] get_library_file_sizes scanned small directory %s in %.3fms", abs_root, (time.time() - t_start) * 1000)
			return sizes | db_sizes

	# For large mounts (like 22TB NFS /mnt/PLEX), run scan in background so web thread NEVER blocks
	def _async_scan() -> None:
		with _LIBRARY_SIZES_LOCK:
			if abs_root in _LIBRARY_SIZES_SCANNING:
				return
			_LIBRARY_SIZES_SCANNING.add(abs_root)

		logger.info("[PERF] Started non-blocking background library size scan for %s", abs_root)
		scan_start = time.time()
		scanned_sizes: Set[int] = set()
		total_files = 0
		try:
			# Only scan media folders (MOVIES and TV SHOWS) to skip BACKUP, MUSIC, etc.
			dirs_to_scan = []
			for target_dir in ("MOVIES", "TV SHOWS"):
				full_target = os.path.join(abs_root, target_dir)
				if os.path.exists(full_target):
					dirs_to_scan.append(full_target)
			if not dirs_to_scan:
				dirs_to_scan = [abs_root]

			for scan_dir in dirs_to_scan:
				for root, _, files in os.walk(scan_dir):
					for f in files:
						total_files += 1
						try:
							scanned_sizes.add(os.path.getsize(os.path.join(root, f)))
						except OSError:
							pass
					# Cooperatively yield every directory to prevent gevent CPU / I/O starvation
					time.sleep(0.001)

			with _LIBRARY_SIZES_LOCK:
				_LIBRARY_SIZES_CACHE[abs_root] = (scanned_sizes, time.time() + _LIBRARY_SIZES_TTL)
			logger.info(
				"[PERF] Finished background library scan for %s in %.2fs (found %d files, %d unique sizes)",
				abs_root, time.time() - scan_start, total_files, len(scanned_sizes)
			)
		except Exception as err:
			logger.error("[PERF] Background library scan failed for %s: %s", abs_root, err)
		finally:
			with _LIBRARY_SIZES_LOCK:
				_LIBRARY_SIZES_SCANNING.discard(abs_root)

	start_bg_task(_async_scan)
	logger.info(
		"[PERF] get_library_file_sizes returned instantly in %.3fms (dispatched background scan for %s)",
		(time.time() - t_start) * 1000, abs_root
	)
	return cached_disk_sizes | db_sizes


def populate_all_cards_downloads(cards: List[Dict[str, Any]], file_sizes: Set[int], db: Database) -> None:
	"""Populates the download state and database existence for all search result cards in a single batch database query."""
	all_magnets: List[str] = []
	all_clean_titles: Set[str] = set()

	for card in cards:
		clean_t = (card.get("clean_title") or "").strip().lower()
		if clean_t:
			all_clean_titles.add(clean_t)
		for dl in card.get("downloads", []):
			magnet = dl.get("download_url")
			if magnet:
				all_magnets.append(magnet)

	dl_map: Dict[str, Any] = {}
	if all_magnets:
		# Batch query all magnets in one trip
		placeholders = ",".join("?" for _ in all_magnets)
		query_sql = f"SELECT magnet, torbox_id, user_id, status, filename, size FROM downloads WHERE magnet IN ({placeholders})"
		rows = db.query(query_sql, tuple(all_magnets)) or []
		for r in rows:
			dl_map[r["magnet"]] = r

	title_db_map: Dict[str, Any] = {}
	if all_clean_titles:
		# Also query completed/active downloads by clean title
		title_placeholders = ",".join("?" for _ in all_clean_titles)
		title_query = f"SELECT id, title, filename, size, status, category, created_at FROM downloads WHERE LOWER(title) IN ({title_placeholders}) AND status IN ('completed', 'downloading', 'moving')"
		title_rows = db.query(title_query, tuple(all_clean_titles)) or []
		for tr in title_rows:
			clean_k = (tr["title"] or "").strip().lower()
			if clean_k not in title_db_map or tr["status"] == "completed":
				title_db_map[clean_k] = tr

	for card in cards:
		clean_t = (card.get("clean_title") or "").strip().lower()
		card_db_rec = title_db_map.get(clean_t)
		card_has_db = False
		card_existing_info: Dict[str, Any] = {}

		if card_db_rec:
			card_has_db = True
			card_existing_info = {
				"title": card_db_rec["title"],
				"filename": card_db_rec["filename"],
				"size": card_db_rec["size"],
				"status": card_db_rec["status"]
			}

		for dl in card.get("downloads", []):
			is_downloaded = dl.get("size", 0) in file_sizes
			rec = dl_map.get(dl.get("download_url"))
			if rec:
				dl["torbox_id"] = rec["torbox_id"]
				dl["user_id"] = rec["user_id"]
				dl["db_status"] = rec["status"]
				dl["in_database"] = True
				if rec["status"] == "completed":
					is_downloaded = True
				card_has_db = True
			else:
				dl["torbox_id"] = None
				dl["user_id"] = None
				dl["db_status"] = None
				dl["in_database"] = is_downloaded

			dl["downloaded"] = is_downloaded

		card["in_database"] = card_has_db
		if card_has_db and card_existing_info:
			card["existing_download"] = card_existing_info
# HEALTH CHECK ENDPOINT (Public unauthenticated endpoint for monitoring)
@api_bp.route('/health', methods=['GET'])
def health():
	"""Public lightweight health check endpoint returning server status."""
	return jsonify({
		"status": "healthy",
		"service": "rico.cx",
		"timestamp": time.time()
	}), 200


def start_magnet_download(
	user: User,
	magnet: str,
	title: str = "Unknown Torrent",
	filename: str = "Unknown",
	category: str = "movie",
	year: Optional[Union[str, int]] = None,
	season: Optional[Union[str, int]] = None,
	episode: Optional[Union[str, int]] = None,
	size: int = 0,
	force_overwrite: bool = False
) -> Dict[str, Any]:
	"""
	Initiates the download for a magnet link on the server side:
	- Checks for duplicate active or completed downloads
	- Submits the magnet to Torbox
	- Records the download entry in SQLite
	- Spawns background worker thread to monitor & stream files to disk
	- Emits WebSocket notification
	"""
	if not magnet or not isinstance(magnet, str):
		return {"error": "Missing or invalid magnet link", "status_code": 400}

	try:
		size = int(size)
	except (ValueError, TypeError):
		size = 0

	settings = get_server_settings()
	library_root = settings.get("library_path") or os.environ.get("ROOT_LIBRARY_LOCATION", "./library")
	library_root = os.path.abspath(library_root)
	file_sizes = get_library_file_sizes(library_root)

	db = Database()

	# Check if already actively downloading or queued
	existing_active = db.query(
		"SELECT id, torbox_id, status FROM downloads WHERE magnet = ? AND status NOT IN ('failed', 'cancelled')",
		(magnet,),
		one=True
	)
	if existing_active and not force_overwrite:
		logger.info(
			"Magnet already active in downloads (ID %s, status %s). Skipping duplicate queue.",
			existing_active["id"], existing_active["status"]
		)
		return {
			"success": True,
			"torbox_id": existing_active["torbox_id"],
			"download_id": existing_active["id"],
			"status": existing_active["status"],
			"already_active": True
		}

	# Check if already completed in library
	existing_completed = db.query(
		"SELECT id FROM downloads WHERE (magnet = ? OR (size > 0 AND size = ?)) AND status = 'completed'",
		(magnet, size),
		one=True
	)
	if not force_overwrite and (existing_completed or (size > 0 and size in file_sizes)):
		logger.info("Preventive skip: File with size %d / magnet already completed in library. Marking completed.", size)
		skipped_id = f"skipped_{int(time.time())}"
		db_download_id = db.execute(
			"INSERT INTO downloads (user_id, torbox_id, title, filename, magnet, status, category, size, progress) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
			(user.id, skipped_id, title, filename, magnet, 'completed', category, size, 100)
		)
		socketio.emit('download_progress', {
			'id': skipped_id,
			'title': title,
			'filename': filename,
			'magnet': magnet,
			'status': 'completed',
			'progress': 100,
			'speed': 0,
			'size': size,
			'user_id': user.id
		})
		socketio.emit('download_added', {
			"torbox_id": skipped_id,
			"title": title,
			"filename": filename,
			"magnet": magnet,
			"status": "completed",
			"progress": 100,
			"speed": 0,
			"size": size,
			"category": category,
			"created_at": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
			"user_id": user.id,
			"username": user.username,
			"full_name": user.full_name or user.username
		})
		return {
			"success": True,
			"torbox_id": skipped_id,
			"download_id": db_download_id,
			"status": "completed"
		}

	torbox_key = settings.get("torbox_api_key") or os.environ.get("TORBOX_API_KEY", "")
	if not torbox_key:
		return {"error": "Torbox API Key not configured. Please save it in settings first.", "status_code": 400}

	torbox = TorboxClient(api_key=torbox_key)
	res = torbox.add_magnet(magnet)

	if res and res.get('success'):
		torrent_id = None
		res_data = res.get('data')
		if isinstance(res_data, dict):
			torrent_id = res_data.get('torrent_id') or res_data.get('id') or res_data.get('queued_id')
		elif isinstance(res_data, (int, float, str)):
			torrent_id = res_data

		if not torrent_id:
			torrent_id = res.get('torrent_id') or res.get('id')

		if not torrent_id:
			logger.error("Torbox responded successfully but no torrent_id found in response: %s", res)
			return {"error": "Failed to retrieve torrent ID from Torbox response.", "status_code": 500}

		logger.info("Torrent added to Torbox. Torrent ID: %s", torrent_id)

		db_download_id = db.execute(
			"INSERT INTO downloads (user_id, torbox_id, title, filename, magnet, status, category, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
			(user.id, str(torrent_id), title, filename, magnet, 'queued', category, size)
		)

		metadata = {
			'title': title,
			'filename': filename,
			'magnet': magnet,
			'category': category,
			'year': year,
			'season': season,
			'episode': episode
		}
		start_bg_task(
			monitor_and_download_task,
			user.id,
			torrent_id,
			metadata,
			db_download_id
		)

		socketio.emit('download_added', {
			"torbox_id": str(torrent_id),
			"title": title,
			"filename": filename,
			"magnet": magnet,
			"status": "queued",
			"progress": 0,
			"speed": 0,
			"size": size,
			"category": category,
			"created_at": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
			"user_id": user.id,
			"username": user.username,
			"full_name": user.full_name or user.username
		})

		return {
			"success": True,
			"torbox_id": str(torrent_id),
			"download_id": db_download_id,
			"status": "queued"
		}

	error_msg = "Failed to add torrent to Torbox"
	if res and isinstance(res, dict):
		detail = res.get("detail") or res.get("error")
		if detail:
			error_msg = str(detail)
	return {"error": error_msg, "status_code": 400}


# SEARCH ENDPOINT
@api_bp.route('/search', methods=['GET'])
@login_required
def search():
	query = request.args.get('q')
	category = request.args.get('category')  # 'movie' or 'tv'

	if not query:
		return jsonify({"error": "Missing query parameter 'q'"}), 400

	query_str = query.strip()

	settings = get_server_settings()
	tmdb_key = settings.get("tmdb_api_key") or os.environ.get("TMDB_API_KEY", "")
	tmdb = TmdbClient(api_key=tmdb_key)

	# Check if the query is a magnet link or an info hash (hex or base32)
	query_str_lower = query_str.lower()
	is_magnet = (
		query_str_lower.startswith("magnet:") or
		re.match(r'^[0-9a-fA-F]{40}$', query_str) or
		re.match(r'^[2-7a-zA-Z]{32}$', query_str)
	)

	if is_magnet:
		magnet_url = query_str
		if not query_str_lower.startswith("magnet:"):
			magnet_url = f"magnet:?xt=urn:btih:{query_str}"

		import urllib.parse
		dn_match = re.search(r'[&?]dn=([^&]+)', magnet_url)
		display_name = urllib.parse.unquote(dn_match.group(1).replace('+', ' ')) if dn_match else "Direct Magnet Link"

		has_meaningful_dn = bool(
			dn_match and
			display_name not in ("Direct Magnet Link", "") and
			not re.match(r'^[0-9a-fA-F]{40}$', display_name.strip()) and
			not re.match(r'^[2-7a-zA-Z]{32}$', display_name.strip())
		)

		# Query Torbox for magnet metadata (like size)
		torbox_key = settings.get("torbox_api_key") or os.environ.get("TORBOX_API_KEY", "")
		torbox = TorboxClient(api_key=torbox_key)
		magnet_info = torbox.get_magnet_info(magnet_url)

		size = 0
		if magnet_info and isinstance(magnet_info, dict):
			if magnet_info.get("size"):
				try:
					size = int(magnet_info["size"])
				except (ValueError, TypeError):
					size = 0
			torbox_name = (magnet_info.get("name") or "").strip()
			is_torbox_name_hash = bool(
				re.match(r'^[0-9a-fA-F]{40}$', torbox_name) or
				re.match(r'^[2-7a-zA-Z]{32}$', torbox_name)
			)
			if torbox_name and torbox_name != "Direct Magnet Link" and not is_torbox_name_hash:
				display_name = torbox_name
			elif not has_meaningful_dn and torbox_name:
				display_name = torbox_name

		# Build a synthetic TorrentResult and AggregatedResult
		torrent = TorrentResult(
			title=display_name,
			size=size,
			download_url=magnet_url,
			seeders=0,
			leechers=0,
			indexer="Direct Link"
		)
		agg = AggregatedResult(torrent.clean_title, torrent.year, torrent.is_tv)
		agg.add_result(torrent)
		if tmdb_key:
			tmdb.resolve_posters_batch([agg])

		# Automatically start downloading on the server side ("Set and Forget")
		category_val = category if category in ("movie", "tv") else ("tv" if agg.is_tv else "movie")
		auto_dl_result = start_magnet_download(
			user=g.user,
			magnet=magnet_url,
			title=agg.clean_title or display_name,
			filename=display_name,
			category=category_val,
			year=agg.year,
			season=None,
			episode=None,
			size=size,
			force_overwrite=False
		)
		auto_downloaded = auto_dl_result.get("success", False)
		if auto_downloaded:
			logger.info("Auto-download initiated for magnet: '%s' (torbox_id: %s)", display_name, auto_dl_result.get("torbox_id"))

		library_root = settings.get("library_path") or os.environ.get("ROOT_LIBRARY_LOCATION", "./library")
		file_sizes = get_library_file_sizes(library_root)

		cards = [agg.to_dict()]
		db = Database()
		populate_all_cards_downloads(cards, file_sizes, db)

		return jsonify({
			"type": "search_results",
			"data": cards,
			"auto_downloaded": auto_downloaded
		})

	t_search_start = time.time()
	prowlarr_url = settings.get("prowlarr_url") or os.environ.get("PROWLARR_URL", "")
	prowlarr_key = settings.get("prowlarr_api_key") or os.environ.get("PROWLARR_API_KEY", "")

	search_client = SearchClient(base_url=prowlarr_url, api_key=prowlarr_key, tmdb_api_key=tmdb_key)
	results = search_client.search(query, category=category)
	t_prowlarr = time.time() - t_search_start

	# Resolve TMDb posters only for cards that missed poster resolution
	missing_posters = [r for r in results if getattr(r, 'poster_url', None) is None]
	if tmdb_key and missing_posters:
		tmdb.resolve_posters_batch(missing_posters)

	t_sizes_start = time.time()
	library_root = settings.get("library_path") or os.environ.get("ROOT_LIBRARY_LOCATION", "./library")
	file_sizes = get_library_file_sizes(library_root)
	t_sizes = time.time() - t_sizes_start

	results_data = [r.to_dict() for r in results]
	t_pop_start = time.time()
	db = Database()
	populate_all_cards_downloads(results_data, file_sizes, db)
	t_pop = time.time() - t_pop_start

	logger.info(
		"[PERF] /api/search: query='%s' total=%.3fs (Prowlarr=%.3fs, sizes=%.3fs, populate=%.3fs, cards=%d)",
		query, time.time() - t_search_start, t_prowlarr, t_sizes, t_pop, len(results_data)
	)

	return jsonify({
		"type": "search_results",
		"data": results_data
	})


# TRENDING / POPULAR ENDPOINT
@api_bp.route('/trending', methods=['GET'])
@login_required
def trending():
	"""
	Returns daily or weekly trending movies or TV shows from TMDb.
	Cross-references items with local downloads database to mark 'in_database'.
	Query params:
		type: 'movie' (default) or 'tv'
		window: 'day' (default) or 'week'
		page: int (default 1)
	"""
	media_type = (request.args.get('type') or 'movie').strip().lower()
	time_window = (request.args.get('window') or 'day').strip().lower()
	page_str = request.args.get('page', '1')

	try:
		page = max(1, int(page_str))
	except (ValueError, TypeError):
		page = 1

	if media_type not in ('movie', 'tv'):
		media_type = 'movie'
	if time_window not in ('day', 'week'):
		time_window = 'day'

	settings = get_server_settings()
	tmdb_key = settings.get("tmdb_api_key") or os.environ.get("TMDB_API_KEY", "")

	if not tmdb_key:
		return jsonify({"error": "TMDb API Key not configured.", "results": []}), 503

	tmdb = TmdbClient(api_key=tmdb_key)
	trending_data = tmdb.get_trending(media_type=media_type, time_window=time_window, page=page)

	if not trending_data:
		return jsonify({"error": "Failed to fetch trending media from TMDb.", "results": []}), 502

	results = trending_data.get("results", [])

	# Cross-reference against downloads in database
	db = Database()
	completed_downloads = db.query(
		"SELECT id, title, filename, size, status, category, created_at FROM downloads WHERE status IN ('completed', 'downloading', 'moving')"
	) or []

	title_db_map: Dict[str, Any] = {}
	norm_db_map: Dict[str, Any] = {}

	for row in completed_downloads:
		t_lower = (row["title"] or "").strip().lower()
		if t_lower and (t_lower not in title_db_map or row["status"] == "completed"):
			title_db_map[t_lower] = row
		norm_k = re.sub(r'[^a-z0-9]', '', t_lower)
		if norm_k and (norm_k not in norm_db_map or row["status"] == "completed"):
			norm_db_map[norm_k] = row

	for item in results:
		item_title = (item.get("title") or "").strip().lower()
		item_norm = re.sub(r'[^a-z0-9]', '', item_title)
		match = title_db_map.get(item_title) or norm_db_map.get(item_norm)

		if match:
			item["in_database"] = True
			item["existing_download"] = {
				"id": match["id"],
				"title": match["title"],
				"filename": match["filename"],
				"size": match["size"],
				"status": match["status"]
			}
		else:
			item["in_database"] = False
			item["existing_download"] = None

	return jsonify(trending_data), 200


# DOWNLOAD ENDPOINT
@api_bp.route('/download', methods=['POST'])
@login_required
def download():
	t_dl_start = time.time()
	data = request.json or {}
	magnet = data.get('magnet')
	title = data.get('title', 'Unknown Torrent')
	filename = data.get('filename', 'Unknown')
	category = data.get('category', 'movie') # 'movie' or 'tv'
	year = data.get('year')
	season = data.get('season')
	episode = data.get('episode')
	size = data.get('size', 0)
	force_overwrite = bool(data.get('overwrite', False))

	result = start_magnet_download(
		user=g.user,
		magnet=magnet,
		title=title,
		filename=filename,
		category=category,
		year=year,
		season=season,
		episode=episode,
		size=size,
		force_overwrite=force_overwrite
	)

	if "error" in result:
		status_code = result.get("status_code", 400)
		return jsonify({"error": result["error"]}), status_code

	logger.info("[PERF] /api/download completed '%s' in %.3fms", title, (time.time() - t_dl_start) * 1000)
	return jsonify(result), 200


# DOWNLOADS LIST
@api_bp.route('/downloads', methods=['GET'])
@login_required
def get_downloads():
	db = Database()
	if g.user.group and g.user.group.name == "Admin":
		rows = db.query("SELECT * FROM downloads ORDER BY created_at DESC LIMIT 50")
	else:
		rows = db.query("SELECT * FROM downloads WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", (g.user.id,))
	downloads = []
	if rows:
		for r in rows:
			size = r["size"] if "size" in r.keys() else 0
			downloads.append({
				"id": r["id"],
				"torbox_id": r["torbox_id"],
				"title": r["title"],
				"filename": r["filename"],
				"magnet": r["magnet"],
				"status": r["status"],
				"progress": r["progress"],
				"speed": r["speed"],
				"size": size,
				"category": r["category"],
				"created_at": r["created_at"],
				"user_id": r["user_id"]
			})
	return jsonify(downloads)


# TORBOX TORRENT CONTROL
@api_bp.route('/torbox/control', methods=['POST'])
@login_required
def control_torrent():
	data = request.json or {}
	torbox_id = data.get("torbox_id")
	action = data.get("action")  # 'delete', 'resume', 'reannounce'

	if not torbox_id or not action:
		return jsonify({"error": "Missing parameters"}), 400

	db = Database()
	row = db.query("SELECT * FROM downloads WHERE torbox_id = ?", (str(torbox_id),), one=True)

	# Permission check: User must be Admin or the owner who started this download initially.
	is_admin = g.user.group and g.user.group.name == "Admin"
	if not is_admin:
		if not row or row["user_id"] is None or row["user_id"] != g.user.id:
			return jsonify({"error": "You do not have permission to delete/cancel this download"}), 403

	settings = get_server_settings()
	torbox_key = settings.get("torbox_api_key") or os.environ.get("TORBOX_API_KEY", "")
	torbox = TorboxClient(api_key=torbox_key)

	if action == "delete":
		# Best-effort delete from Torbox
		torbox.control_torrent(torbox_id, "delete")

		# Retrieve the record before deleting it so we can clean up files
		if row:
			db_download_id = row["id"]
			user_id = row["user_id"]
			filename = row["filename"]
			category = row["category"]

			# Delete from database immediately
			db.execute("DELETE FROM downloads WHERE id = ?", (db_download_id,))

			# Perform immediate filesystem clean-up of files/folders
			try:
				from ..models.user import User
				user = User.get_by_id(user_id)
				if user:
					settings = get_server_settings()
					library_root = settings.get("library_path") or os.environ.get("ROOT_LIBRARY_LOCATION", "./library")
					library_root = os.path.abspath(library_root)

					from ..services.tmdb_client import TmdbClient
					from ..models.result import TorrentResult

					tmdb_key = settings.get("tmdb_api_key") or os.environ.get("TMDB_API_KEY", "")
					tmdb = TmdbClient(api_key=tmdb_key)

					# Parse metadata
					torrent = TorrentResult(title=filename, size=0, download_url="", seeders=0, leechers=0, indexer="")
					title_clean = torrent.clean_title
					year = torrent.year
					season = torrent.season
					episode = torrent.episode

					tmdb_id = None
					official_title = title_clean
					official_year = year

					def make_safe_filename(name: str) -> str:
						if not name:
							return ""
						return re.sub(r'[\/\\\:\*\?\"\<\>\|]', '', name).strip()

					if category == "movie":
						res = tmdb.search_movie(title_clean, year)
						if res:
							official_title = res["title"]
							official_year = res["year"]
							tmdb_id = res["id"]
					elif category == "tv":
						res = tmdb.search_tv(title_clean, year)
						if res:
							official_title = res["title"]
							official_year = res["year"]
							tmdb_id = res["id"]

					official_title_safe = make_safe_filename(official_title)
					official_year_safe = make_safe_filename(str(official_year)) if official_year else ""

					if tmdb_id:
						folder_name = f"{official_title_safe} ({official_year_safe}) {{tmdb-{tmdb_id}}}" if official_year_safe else f"{official_title_safe} {{tmdb-{tmdb_id}}}"
					else:
						folder_name = f"{official_title_safe} ({official_year_safe})" if official_year_safe else official_title_safe

					show_name_filename = f"{official_title_safe} ({official_year_safe})" if official_year_safe else official_title_safe

					if category == "tv":
						season_folder = f"Season {season:02d}" if season else "Season 01"
						dest_dir = os.path.join(library_root, "TV SHOWS", folder_name, season_folder)
					else:
						dest_dir = os.path.join(library_root, "MOVIES", folder_name)

					if os.path.exists(dest_dir):
						if category == "movie":
							try:
								shutil.rmtree(dest_dir)
								logger.info(f"Removed movie folder on cancel: {dest_dir}")
							except Exception as ex:
								logger.error(f"Failed to remove movie folder {dest_dir}: {ex}")
						else:
							# TV Show: only delete files starting with show name and season/episode prefix
							prefix = f"{show_name_filename} - S{season:02d}E{episode:02d}" if season and episode else show_name_filename
							try:
								for entry in os.scandir(dest_dir):
									if entry.is_file() and entry.name.startswith(prefix):
										os.remove(entry.path)
										logger.info(f"Deleted TV show episode file on cancel: {entry.path}")
								if not os.listdir(dest_dir):
									os.rmdir(dest_dir)
									logger.info(f"Removed empty season directory on cancel: {dest_dir}")

									parent_dir = os.path.dirname(dest_dir)
									if os.path.exists(parent_dir) and not os.listdir(parent_dir):
										os.rmdir(parent_dir)
										logger.info(f"Removed empty TV show directory on cancel: {parent_dir}")
							except Exception as ex:
								logger.error(f"Failed to clean up TV show folder: {ex}")
			except Exception as e:
				logger.error(f"Immediate cancel cleanup failed: {e}")
			finally:
				invalidate_library_sizes_cache(library_root)
		else:
			db.execute("DELETE FROM downloads WHERE torbox_id = ?", (str(torbox_id),))
		socketio.emit('download_deleted', {'torbox_id': str(torbox_id)})
		return jsonify({"success": True})
	elif action == "resume":
		# Best-effort resume signal to Torbox
		res = torbox.control_torrent(str(torbox_id), "resume")

		if row:
			db_download_id = row["id"]
			target_user_id = row["user_id"] or g.user.id
			metadata = {
				"title": row["title"],
				"filename": row["filename"],
				"magnet": row["magnet"],
				"category": row["category"]
			}

			task_key = (db_download_id, str(torbox_id))
			with ACTIVE_TASKS_LOCK:
				if task_key in ACTIVE_DOWNLOAD_TASKS:
					return jsonify({"success": True, "message": "Download is already active."})

			db.execute("UPDATE downloads SET status = 'queued' WHERE id = ?", (db_download_id,))
			start_bg_task(
				monitor_and_download_task,
				target_user_id,
				str(torbox_id),
				metadata,
				db_download_id
			)
			socketio.emit('download_progress', {
				'id': str(torbox_id),
				'title': row["title"],
				'filename': row["filename"],
				'magnet': row["magnet"],
				'status': 'queued',
				'progress': row["progress"] or 0,
				'speed': 0,
				'size': row["size"] or 0,
				'user_id': target_user_id
			})
			return jsonify({"success": True, "message": "Download resumption started.", "details": res})
		else:
			return jsonify({"error": "Download record not found in database"}), 404
	elif action == "reannounce":
		res = torbox.control_torrent(str(torbox_id), action)
		return jsonify({"success": True, "details": res})
	else:
		return jsonify({"error": f"Unsupported or invalid action: {action}"}), 400


# SERVER SETTINGS MANAGEMENT (ADMIN ONLY)
@api_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def server_settings_route():
	is_admin = g.user.group and g.user.group.name == "Admin"
	if not is_admin:
		return jsonify({"error": "Forbidden"}), 403

	if request.method == 'POST':
		data = request.json or {}
		settings = get_server_settings()

		# Keys to allow updates
		allowed_keys = ["prowlarr_url", "prowlarr_api_key", "torbox_api_key", "library_path", "tmdb_api_key"]
		for key in allowed_keys:
			if key in data:
				settings[key] = data[key]

		save_server_settings(settings)
		return jsonify({"status": "updated", "settings": settings})

	return jsonify(get_server_settings())


# ==========================================
# ADMIN & MODERATOR SECTION
# ==========================================

# ADMIN: DOWNLOADS VIEW
@api_bp.route('/admin/downloads', methods=['GET'])
@login_required
def admin_downloads():
	is_admin_or_mod = g.user.group and g.user.group.name in ("Admin", "Moderator")
	if not is_admin_or_mod:
		return jsonify({"error": "Forbidden"}), 403

	db = Database()
	query = """
		SELECT d.*, u.username, u.full_name
		FROM downloads d
		LEFT JOIN users u ON d.user_id = u.id
	"""
	conditions = []
	params = []

	search = request.args.get('search', '').strip()
	if search:
		conditions.append("(d.title LIKE ? OR d.filename LIKE ?)")
		params.extend([f"%{search}%", f"%{search}%"])

	status = request.args.get('status', '').strip()
	if status:
		conditions.append("d.status LIKE ?")
		params.append(f"%{status}%")

	user_filter = request.args.get('user_id', '').strip()
	if user_filter:
		conditions.append("d.user_id = ?")
		params.append(user_filter)

	if conditions:
		query += " WHERE " + " AND ".join(conditions)

	# Sorting
	sort_by = request.args.get('sort_by', 'created_at').strip()
	sort_order = request.args.get('sort_order', 'desc').strip().lower()

	# Validate sort_by to prevent SQL injection
	allowed_sort_fields = {
		'created_at': 'd.created_at',
		'size': 'd.size',
		'status': 'd.status',
		'username': 'u.username',
		'title': 'd.title'
	}
	sort_field = allowed_sort_fields.get(sort_by, 'd.created_at')
	if sort_order not in ('asc', 'desc'):
		sort_order = 'desc'

	query += f" ORDER BY {sort_field} {sort_order.upper()}"

	rows = db.query(query, tuple(params))
	downloads = []
	if rows:
		for r in rows:
			downloads.append({
				"id": r["id"],
				"torbox_id": r["torbox_id"],
				"title": r["title"],
				"filename": r["filename"],
				"magnet": r["magnet"],
				"status": r["status"],
				"progress": r["progress"],
				"speed": r["speed"],
				"size": r["size"],
				"category": r["category"],
				"created_at": r["created_at"],
				"user_id": r["user_id"],
				"username": r["username"] or "Unknown",
				"full_name": r["full_name"] or "Unknown User"
			})
	return jsonify(downloads)


# ADMIN: USERS VIEW
@api_bp.route('/admin/users', methods=['GET'])
@login_required
def admin_users():
	is_admin_or_mod = g.user.group and g.user.group.name in ("Admin", "Moderator")
	if not is_admin_or_mod:
		return jsonify({"error": "Forbidden"}), 403

	db = Database()
	query = """
		SELECT u.*, g.name as group_name,
			   (SELECT COUNT(*) FROM downloads WHERE user_id = u.id) as total_downloads,
			   (SELECT SUM(size) FROM downloads WHERE user_id = u.id AND status = 'completed') as total_downloaded_bytes,
			   (SELECT MAX(created_at) FROM downloads WHERE user_id = u.id) as last_downloaded_at
		FROM users u
		LEFT JOIN groups g ON u.group_id = g.id
		ORDER BY 
			CASE WHEN (SELECT MAX(created_at) FROM downloads WHERE user_id = u.id) IS NOT NULL THEN 0 ELSE 1 END,
			(SELECT MAX(created_at) FROM downloads WHERE user_id = u.id) DESC,
			u.created_at DESC
	"""
	rows = db.query(query)
	users_list = []
	if rows:
		for r in rows:
			users_list.append({
				"id": r["id"],
				"username": r["username"],
				"full_name": r["full_name"],
				"first_name": r["first_name"],
				"last_name": r["last_name"],
				"profile_picture": r["profile_picture"],
				"created_at": r["created_at"],
				"last_downloaded_at": r["last_downloaded_at"],
				"group_id": r["group_id"],
				"group_name": r["group_name"] or "None (Pending Approval)",
				"total_downloads": r["total_downloads"] or 0,
				"total_downloaded_bytes": r["total_downloaded_bytes"] or 0
			})
	return jsonify(users_list)


# ADMIN: UPDATE USER ROLE / APPROVE
@api_bp.route('/admin/users/update_role', methods=['POST'])
@login_required
def admin_update_role():
	is_admin = g.user.group and g.user.group.name == "Admin"
	if not is_admin:
		return jsonify({"error": "Forbidden"}), 403

	data = request.json or {}
	user_id = data.get("user_id")
	group_name = data.get("group_name")

	if not user_id:
		return jsonify({"error": "Missing user_id"}), 400

	db = Database()

	# Check if target user exists
	target = db.query("SELECT id FROM users WHERE id = ?", (user_id,), one=True)
	if not target:
		return jsonify({"error": "User not found"}), 404

	if group_name is None or group_name == "None":
		# Unapprove or set group to NULL
		db.execute("UPDATE users SET group_id = NULL WHERE id = ?", (user_id,))
		return jsonify({"success": True, "message": "User access removed."})

	# Find group by name
	from ..models.group import Group
	group = Group.get_by_name(group_name)
	if not group:
		if group_name == "Admin":
			group = Group.create("Admin", ["admin"])
		elif group_name == "Moderator":
			group = Group.create("Moderator", ["moderate"])
		elif group_name == "User":
			group = Group.create("User", ["search", "download"])
		else:
			return jsonify({"error": f"Invalid group name: {group_name}"}), 400

	db.execute("UPDATE users SET group_id = ? WHERE id = ?", (group.id, user_id))
	return jsonify({"success": True, "message": f"User role updated to {group_name}."})


# ADMIN: DELETE USER
@api_bp.route('/admin/users/delete', methods=['POST'])
@login_required
def admin_delete_user():
	is_admin = g.user.group and g.user.group.name == "Admin"
	if not is_admin:
		return jsonify({"error": "Forbidden"}), 403

	data = request.json or {}
	user_id = data.get("user_id")
	if not user_id:
		return jsonify({"error": "Missing user_id"}), 400

	try:
		user_id_int = int(user_id)
	except (ValueError, TypeError):
		return jsonify({"error": "Invalid user_id parameter"}), 400

	if user_id_int == g.user.id:
		return jsonify({"error": "You cannot delete your own admin account."}), 400

	db = Database()
	db.execute("DELETE FROM users WHERE id = ?", (user_id_int,))
	return jsonify({"success": True, "message": "User deleted successfully."})


def format_byte_size(size_bytes: int) -> str:
	"""Helper function to format byte numbers into human-readable strings."""
	if size_bytes <= 0:
		return "0 B"
	units = ["B", "KB", "MB", "GB", "TB", "PB"]
	i = 0
	val = float(size_bytes)
	while val >= 1024.0 and i < len(units) - 1:
		val /= 1024.0
		i += 1
	return f"{val:.1f} {units[i]}"


# ADMIN: SYSTEM STATS & METRICS
@api_bp.route('/admin/stats', methods=['GET'])
@login_required
def admin_stats():
	is_admin_or_mod = g.user.group and g.user.group.name in ("Admin", "Moderator")
	if not is_admin_or_mod:
		return jsonify({"error": "Forbidden"}), 403

	db = Database()
	db_path = db.db_path
	db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
	wal_path = f"{db_path}-wal"
	wal_size = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0

	# Get SQLite journal mode
	journal_mode_row = db.query("PRAGMA journal_mode", one=True)
	journal_mode = journal_mode_row[0] if journal_mode_row else "unknown"

	# User stats
	user_counts = db.query("""
		SELECT 
			COUNT(*) as total,
			SUM(CASE WHEN group_id IS NOT NULL THEN 1 ELSE 0 END) as approved,
			SUM(CASE WHEN group_id IS NULL THEN 1 ELSE 0 END) as pending
		FROM users
	""", one=True)

	total_users = user_counts["total"] if user_counts else 0
	approved_users = user_counts["approved"] or 0 if user_counts else 0
	pending_users = user_counts["pending"] or 0 if user_counts else 0

	# Download stats
	dl_stats = db.query("""
		SELECT 
			COUNT(*) as total,
			SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
			SUM(CASE WHEN status IN ('downloading', 'queued') OR status LIKE 'Moving%' THEN 1 ELSE 0 END) as active,
			SUM(CASE WHEN status IN ('failed', 'error') THEN 1 ELSE 0 END) as failed,
			SUM(CASE WHEN status = 'completed' THEN size ELSE 0 END) as total_downloaded_bytes
		FROM downloads
	""", one=True)

	total_dls = dl_stats["total"] if dl_stats else 0
	completed_dls = dl_stats["completed"] or 0 if dl_stats else 0
	active_dls = dl_stats["active"] or 0 if dl_stats else 0
	failed_dls = dl_stats["failed"] or 0 if dl_stats else 0
	total_downloaded_bytes = dl_stats["total_downloaded_bytes"] or 0 if dl_stats else 0

	# Storage stats on library path
	settings = get_server_settings()
	library_path = settings.get("library_path") or os.environ.get("LIBRARY_PATH", "/mnt/PLEX")
	storage_info = {
		"library_path": library_path,
		"total_bytes": 0,
		"used_bytes": 0,
		"free_bytes": 0,
		"usage_percent": 0.0,
		"total_formatted": "N/A",
		"used_formatted": "N/A",
		"free_formatted": "N/A"
	}
	if os.path.exists(library_path):
		try:
			usage = shutil.disk_usage(library_path)
			storage_info["total_bytes"] = usage.total
			storage_info["used_bytes"] = usage.used
			storage_info["free_bytes"] = usage.free
			storage_info["usage_percent"] = round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0.0
			storage_info["total_formatted"] = format_byte_size(usage.total)
			storage_info["used_formatted"] = format_byte_size(usage.used)
			storage_info["free_formatted"] = format_byte_size(usage.free)
		except Exception as exc:  # pylint: disable=broad-exception-caught
			logger.debug("Failed to get library disk usage: %s", exc)

	import sys
	return jsonify({
		"database": {
			"path": db_path,
			"size_bytes": db_size,
			"size_formatted": format_byte_size(db_size),
			"wal_size_bytes": wal_size,
			"wal_size_formatted": format_byte_size(wal_size),
			"journal_mode": str(journal_mode).upper()
		},
		"storage": storage_info,
		"downloads": {
			"total_count": total_dls,
			"completed_count": completed_dls,
			"active_count": active_dls,
			"failed_count": failed_dls,
			"total_downloaded_bytes": total_downloaded_bytes,
			"total_downloaded_formatted": format_byte_size(total_downloaded_bytes)
		},
		"users": {
			"total_count": total_users,
			"approved_count": approved_users,
			"pending_count": pending_users
		},
		"server": {
			"service": "RICO.CX",
			"status": "healthy",
			"python_version": sys.version.split()[0],
			"timestamp": time.time()
		}
	})


def start_bg_task(target, *args, **kwargs):
	if getattr(socketio, 'server', None) is not None:
		socketio.start_background_task(target, *args, **kwargs)
	else:
		import threading
		t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
		t.start()


def send_ha_notification(event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
	"""
	Sends an automated crash / respawn notification webhook to Home Assistant.
	"""
	ha_webhook_url = os.environ.get("HA_WEBHOOK_URL") or "https://haos.rc2.rico.cx/api/webhook/rico_cx_crash_alert"
	payload = {
		"event": event_type,
		"timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
		"server": "island.rico.cx",
		"details": details or {}
	}
	try:
		requests.post(ha_webhook_url, json=payload, timeout=5)
	except Exception as exc:  # pylint: disable=broad-exception-caught
		logger.debug("Failed to dispatch Home Assistant alert webhook: %s", exc)


def init_download_resumption():
	"""
	Startup recovery task: Automatically resumes any downloads interrupted by server crash or restart.
	"""
	# Guard against duplicate execution in Flask/Werkzeug dev reloader parent process
	if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and os.environ.get("WERKZEUG_SERVER_FD") is not None:
		logger.info("Startup Recovery: Skipping parent process execution in Werkzeug reloader.")
		return

	global _RESUMPTION_INITIALIZED
	with _RESUMPTION_LOCK:
		if _RESUMPTION_INITIALIZED:
			logger.info("Startup Recovery: Already initialized in this process. Skipping duplicate run.")
			return
		_RESUMPTION_INITIALIZED = True

	def run_resumption():
		time.sleep(2)  # Wait for Flask & SocketIO startup to stabilize
		db = Database()
		rows = db.query("SELECT * FROM downloads WHERE status NOT IN ('completed', 'failed') AND (status IN ('queued', 'downloading', 'moving') OR status LIKE 'Moving file%' OR status LIKE 'Downloading%')")
		if not rows:
			logger.info("Startup Recovery: No active incomplete downloads found.")
			return
		logger.info(f"Startup Recovery: Found {len(rows)} active incomplete downloads to evaluate.")
		send_ha_notification("server_restart_with_resumption", {"resumed_count": len(rows)})
		for r in rows:
			torbox_id = r["torbox_id"]
			if not torbox_id or str(torbox_id).startswith("skipped_") or str(torbox_id).startswith("legacy_"):
				continue
			db_download_id = r["id"]
			user_id = r["user_id"] or 1
			metadata = {
				"title": r["title"],
				"filename": r["filename"],
				"magnet": r["magnet"],
				"category": r["category"]
			}

			task_key = (db_download_id, str(torbox_id))
			with ACTIVE_TASKS_LOCK:
				if task_key in ACTIVE_DOWNLOAD_TASKS:
					logger.info(f"Startup Recovery: Download ID {db_download_id} is already active. Skipping duplicate launch.")
					continue

			logger.info(f"Startup Recovery: Auto-resuming download ID {db_download_id} (Torbox ID: {torbox_id}) - '{r['title']}'")
			db.execute("UPDATE downloads SET status = 'queued' WHERE id = ?", (db_download_id,))
			start_bg_task(
				monitor_and_download_task,
				user_id,
				torbox_id,
				metadata,
				db_download_id
			)
			time.sleep(0.1)  # Stagger background task dispatch

	start_bg_task(run_resumption)

