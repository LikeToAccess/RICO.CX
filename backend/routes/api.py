import re
import os
import time
import logging
import requests
import shutil
from functools import wraps
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

            # Throttle websocket emits to avoid flooding the network
            now = time.time()
            if now - last_emit_time > 1:
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

            db.execute(
                "UPDATE downloads SET status = ?, progress = ?, speed = ?, size = ? WHERE id = ?",
                (db_status, progress, speed, size, db_download_id)
            )

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
                            if valid_seasons and req_season not in valid_seasons:
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
                            if valid_seasons and season not in valid_seasons:
                                season = valid_seasons[0]

                        season_folder = f"Season {season:02d}" if season else "Season 01"
                        dest_dir = os.path.join(library_root, "TV SHOWS", folder_name, season_folder)

                        episode_name = None
                        if tmdb_id and season and episode:
                            episode_name = tmdb.get_episode_name(tmdb_id, season, episode)

                        episode_name_safe = make_safe_filename(episode_name) if episode_name else ""

                        if episode_name_safe:
                            base_filename = f"{show_name_filename} - S{season:02d}E{episode:02d} - {episode_name_safe}{ext}"
                        else:
                            base_filename = f"{show_name_filename} - S{season:02d}E{episode:02d}{ext}"
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

                    MAX_RETRIES = 10
                    transfer_done = False
                    start_time = time.time()

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
                                logger.info(f"Retrying transfer for {file_name} from start (Attempt {attempt}/{MAX_RETRIES})...")

                        try:
                            resp = requests.get(dl_link, headers=headers, stream=True, timeout=(15, 600))

                            # Extract authoritative total file size from response headers if available
                            content_range = resp.headers.get("Content-Range")
                            content_length = resp.headers.get("Content-Length")
                            if content_range:
                                try:
                                    header_total = int(content_range.split('/')[-1])
                                    if header_total > 0:
                                        file_size = header_total
                                except Exception:
                                    pass
                            elif resp.status_code == 200 and content_length:
                                try:
                                    header_total = int(content_length)
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
                            with open(temp_dest_path, open_mode) as f_out:
                                for chunk in resp.iter_content(chunk_size=1024*1024):
                                    exists = db.query("SELECT id FROM downloads WHERE id = ?", (db_download_id,), one=True)
                                    if not exists:
                                        logger.info(f"Download {db_download_id} was cancelled during transfer stream. Aborting.")
                                        local_transfer_success = False
                                        break

                                    if chunk:
                                        f_out.write(chunk)
                                        current_file_downloaded += len(chunk)

                                        overall_bytes = total_downloaded + current_file_downloaded
                                        elapsed = time.time() - start_time
                                        current_speed = current_file_downloaded / elapsed if elapsed > 0 else 0
                                        overall_progress = int((overall_bytes / total_files_size) * 100) if total_files_size > 0 else 0

                                        now_f = time.time()
                                        if now_f - last_file_emit > 1:
                                            socketio.emit('download_progress', {
                                                'id': torbox_id,
                                                'title': metadata.get('title'),
                                                'filename': metadata.get('filename'),
                                                'magnet': metadata.get('magnet'),
                                                'status': f"Moving file {idx+1}/{len(video_files)}",
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
                                logger.warning(f"Transfer incomplete for {file_name}: got {actual_size}/{file_size} bytes. Retrying resume in 3s (Attempt {attempt}/{MAX_RETRIES})...")
                                time.sleep(3)

                        except Exception as ex:
                            actual_size = os.path.getsize(temp_dest_path) if os.path.exists(temp_dest_path) else 0
                            logger.error(f"Local Transfer connection error for {file_name} at {actual_size}/{file_size} bytes: {ex}. Retrying resume in 3s (Attempt {attempt}/{MAX_RETRIES})...")
                            time.sleep(3)

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

    redirect_uri = f"{request.host_url.rstrip('/')}/api/auth/google/callback"
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile"
    )
    return redirect(google_auth_url)

@api_bp.route('/auth/google/callback', methods=['GET'])
def google_callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing authorization code from Google"}), 400

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
    else:
        # Update details in case they changed on Google profile
        user.full_name = full_name
        user.first_name = first_name
        user.last_name = last_name
        user.profile_picture = profile_picture
        user.save()
        logger.info(f"Updated user details on login for: {email}")

    token = User.create_session(user.id)

    response = redirect("/")
    response.set_cookie("session_token", token, max_age=30*24*60*60, httponly=True, samesite='Lax')
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


def get_library_file_sizes(library_root):
    sizes = set()
    if not library_root or not os.path.exists(library_root):
        return sizes
    try:
        for root, _, files in os.walk(library_root):
            for f in files:
                try:
                    sizes.add(os.path.getsize(os.path.join(root, f)))
                except Exception:
                    pass
    except Exception:
        pass
    return sizes


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

    def resolve_poster(agg):
        if not tmdb_key:
            return None
        try:
            if agg.is_tv:
                res = tmdb.search_tv(agg.clean_title, agg.year)
            else:
                res = tmdb.search_movie(agg.clean_title, agg.year)
            if res:
                return res.get("poster_url")
        except Exception as e:
            logger.error(f"Failed to fetch TMDb poster for {agg.clean_title}: {e}")
        return None

    def populate_card_downloads(card, file_sizes, db):
        for dl in card["downloads"]:
            dl["downloaded"] = dl["size"] in file_sizes
            row = db.query("SELECT torbox_id, user_id, status FROM downloads WHERE magnet = ?", (dl["download_url"],), one=True)
            if row:
                dl["torbox_id"] = row["torbox_id"]
                dl["user_id"] = row["user_id"]
                dl["db_status"] = row["status"]
            else:
                dl["torbox_id"] = None
                dl["user_id"] = None
                dl["db_status"] = None

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

        # Query Torbox for magnet metadata (like size)
        torbox_key = settings.get("torbox_api_key") or os.environ.get("TORBOX_API_KEY", "")
        torbox = TorboxClient(api_key=torbox_key)
        magnet_info = torbox.get_magnet_info(magnet_url)

        size = 0
        if magnet_info and isinstance(magnet_info, dict):
            if magnet_info.get("size"):
                size = int(magnet_info["size"])
            if magnet_info.get("name") and magnet_info["name"] != "Direct Magnet Link":
                display_name = magnet_info["name"]

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
        agg.poster_url = resolve_poster(agg)

        library_root = settings.get("library_path") or os.environ.get("ROOT_LIBRARY_LOCATION", "./library")
        library_root = os.path.abspath(library_root)
        file_sizes = get_library_file_sizes(library_root)

        card = agg.to_dict()
        db = Database()
        populate_card_downloads(card, file_sizes, db)

        return jsonify({
            "type": "search_results",
            "data": [card]
        })

    prowlarr_url = settings.get("prowlarr_url") or os.environ.get("PROWLARR_URL", "")
    prowlarr_key = settings.get("prowlarr_api_key") or os.environ.get("PROWLARR_API_KEY", "")

    search_client = SearchClient(base_url=prowlarr_url, api_key=prowlarr_key)
    results = search_client.search(query, category=category)
    for r in results:
        r.poster_url = resolve_poster(r)

    library_root = settings.get("library_path") or os.environ.get("ROOT_LIBRARY_LOCATION", "./library")
    library_root = os.path.abspath(library_root)
    file_sizes = get_library_file_sizes(library_root)

    results_data = []
    db = Database()
    for r in results:
        card = r.to_dict()
        populate_card_downloads(card, file_sizes, db)
        results_data.append(card)

    return jsonify({
        "type": "search_results",
        "data": results_data
    })


# DOWNLOAD ENDPOINT
@api_bp.route('/download', methods=['POST'])
@login_required
def download():
    data = request.json or {}
    magnet = data.get('magnet')
    title = data.get('title', 'Unknown Torrent')
    filename = data.get('filename', 'Unknown')
    category = data.get('category', 'movie') # 'movie' or 'tv'
    year = data.get('year')
    season = data.get('season')
    episode = data.get('episode')
    size = data.get('size', 0)

    if not magnet or not isinstance(magnet, str):
        return jsonify({"error": "Missing or invalid magnet link"}), 400

    try:
        size = int(size)
    except (ValueError, TypeError):
        size = 0

    settings = get_server_settings()
    library_root = settings.get("library_path") or os.environ.get("ROOT_LIBRARY_LOCATION", "./library")
    library_root = os.path.abspath(library_root)
    file_sizes = get_library_file_sizes(library_root)

    if size > 0 and size in file_sizes:
        logger.info(f"Preventive skip: File with size {size} already exists in library. Marking completed.")
        db = Database()
        skipped_id = f"skipped_{int(time.time())}"
        db_download_id = db.execute(
            "INSERT INTO downloads (user_id, torbox_id, title, filename, magnet, status, category, size, progress) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (g.user.id, skipped_id, title, filename, magnet, 'completed', category, size, 100)
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
            'user_id': g.user.id
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
            "user_id": g.user.id,
            "username": g.user.username,
            "full_name": g.user.full_name or g.user.username
        })
        return jsonify({
            "success": True,
            "torbox_id": skipped_id,
            "download_id": db_download_id,
            "status": "completed"
        })

    torbox_key = settings.get("torbox_api_key") or os.environ.get("TORBOX_API_KEY", "")
    if not torbox_key:
        return jsonify({"error": "Torbox API Key not configured. Please save it in settings first."}), 400

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
            logger.error(f"Torbox responded successfully but no torrent_id or queued_id could be found in response: {res}")
            return jsonify({"error": "Failed to retrieve torrent ID from Torbox response."}), 500

        logger.info(f"Torrent added to Torbox. Torrent ID: {torrent_id}")

        # Save records in sqlite
        db = Database()
        db_download_id = db.execute(
            "INSERT INTO downloads (user_id, torbox_id, title, filename, magnet, status, category, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (g.user.id, str(torrent_id), title, filename, magnet, 'queued', category, 0)
        )

        # Start background task to monitor
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
            g.user.id,
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
            "size": 0,
            "category": category,
            "created_at": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
            "user_id": g.user.id,
            "username": g.user.username,
            "full_name": g.user.full_name or g.user.username
        })

        return jsonify({
            "success": True,
            "torbox_id": torrent_id,
            "download_id": db_download_id,
            "status": "queued"
        })
    else:
        # Check if we got a structured error response from Torbox
        error_msg = "Failed to add torrent to Torbox"
        if res and isinstance(res, dict):
            detail = res.get("detail") or res.get("error")
            if detail:
                error_msg = detail
        return jsonify({"error": error_msg}), 400


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
               (SELECT SUM(size) FROM downloads WHERE user_id = u.id AND status = 'completed') as total_downloaded_bytes
        FROM users u
        LEFT JOIN groups g ON u.group_id = g.id
        ORDER BY u.created_at DESC
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


def start_bg_task(target, *args, **kwargs):
    if getattr(socketio, 'server', None) is not None:
        socketio.start_background_task(target, *args, **kwargs)
    else:
        import threading
        t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        t.start()


def init_download_resumption():
    """
    Startup recovery task: Automatically resumes any downloads interrupted by server crash or restart.
    """
    def run_resumption():
        time.sleep(2)  # Wait for Flask & SocketIO startup to stabilize
        db = Database()
        rows = db.query("SELECT * FROM downloads WHERE status NOT IN ('completed')")
        if not rows:
            logger.info("Startup Recovery: No incomplete downloads found.")
            return
        logger.info(f"Startup Recovery: Found {len(rows)} incomplete downloads to evaluate.")
        for r in rows:
            torbox_id = r["torbox_id"]
            if not torbox_id or str(torbox_id).startswith("skipped_"):
                continue
            db_download_id = r["id"]
            user_id = r["user_id"] or 1
            metadata = {
                "title": r["title"],
                "filename": r["filename"],
                "magnet": r["magnet"],
                "category": r["category"]
            }
            logger.info(f"Startup Recovery: Auto-resuming download ID {db_download_id} (Torbox ID: {torbox_id}) - '{r['title']}'")
            db.execute("UPDATE downloads SET status = 'queued' WHERE id = ?", (db_download_id,))
            start_bg_task(
                monitor_and_download_task,
                user_id,
                torbox_id,
                metadata,
                db_download_id
            )

    start_bg_task(run_resumption)

