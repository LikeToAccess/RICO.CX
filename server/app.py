# -*- coding: utf-8 -*-
# filename          : app.py
# description       : This is the main application file for the flask app
# author            : Ian Ault
# email             : liketoaccess@protonmail.com
# date              : 12-02-2022
# version           : v1.0
# usage             : python app.py
# notes             :
# license           : MIT
# py version        : 3.11.0 (must run on 3.10 or higher)
#==============================================================================
# pylint: disable=import-error
import asyncio
import sqlite3
import json
import time
import os

import requests
from cachetools import TTLCache, LFUCache
from oauthlib.oauth2 import WebApplicationClient
from oauthlib.oauth2.rfc6749.errors import InsecureTransportError
from flask import Flask, redirect, render_template, render_template_string, request, url_for
from flask_login import (  # type: ignore[import-untyped]
	LoginManager,
	current_user,
	login_required,
	login_user,
	logout_user
)

from user import User
from timer import timer
# from file import read_image
# from format import Format
from group import GroupMembership
from scraper import Milkie as Scraper
from database import init_db_command
# from download import Download
from download_engine import DownloadEngine
from realdebrid import RealDebridInfringingError, RealDebridAPIError
from settings import (
	GOOGLE_CLIENT_ID,
	GOOGLE_CLIENT_SECRET,
	GOOGLE_DISCOVERY_URL,
	ROOT_LIBRARY_LOCATION,
	DEBUG_MODE,
)


app = Flask(__name__)
app.secret_key = os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)

server_init_time = time.time()

# Naive database setup
try:
	init_db_command()
	print("DB first-time initialization complete.")
except sqlite3.OperationalError:
	# Assume it's already been created
	pass

# OAuth2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# Web scraping setup
scraper = Scraper()

# Cache setup
#      TTLCache[query, data]
search_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=500, ttl=86400)  # 24 hours
video_url_cache: TTLCache[str, str] = TTLCache(maxsize=100, ttl=6900)  # 1 hour 55 minutes
video_data_cache: LFUCache[str, dict] = LFUCache(maxsize=100)
# popular_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=80, ttl=6900)  # 1 hour 55 minutes


@login_manager.unauthorized_handler
def unauthorized(message: str | None = None):
	return message if message is not None else "You must be logged in to access this content.", 403

# Flask-Login helper to retrieve a user from the database
@login_manager.user_loader
def load_user(user_id):
	return User.get(user_id)

# @app.before_request
# def before_request():
# 	if not request.is_secure:
# 		url = request.url.replace("http://", "https://", 1)
# 		code = 301
# 		# print(f"WARNING: {request.url} is not secure, redirecting to {url}")
# 		print(f"WARNING: {request.url} is not secure")
# 		# return redirect(url, code=code)
# 	print(f"INFO: {request.url} is secure")
# 	# return f"Is already secure {request.url}"

def public_route(decorated_function):
	decorated_function.is_public = True
	return decorated_function

@app.before_request
def check_route_valid():
	if request.endpoint is None:
		return "Invalid endpoint", 404
	return None

@app.before_request
def check_route_access():
	if current_user.is_authenticated:
		# User is banned? Return them to the shadow realm
		if User.get(current_user.id).banned and not request.endpoint.startswith("banned"):
			return redirect(url_for("banned"))
		# User is not part of a group? Send them to the pending page
		if not any([
			GroupMembership.get(current_user.id),
			request.endpoint.startswith("pending"),
			request.endpoint.startswith("static"),
			request.endpoint.startswith("banned"),
			request.endpoint.startswith("logout")
		]):
			return redirect(url_for("pending"))
		return None # Access granted (logged in + not banned + in group)
	if request.endpoint is None:
		# Remove trailing slash
		print("Redirecting to remove trailing slash")
		return redirect(request.url.rstrip("/"))
	if any([
		request.endpoint.startswith("static"),
		request.host_url.startswith("https://127.0.0.1"),
		request.host_url.startswith("http://127.0.0.1"),
		request.host_url.startswith("https://test."),
		getattr(app.view_functions[request.endpoint], "is_public", False)
	]):
		return None # Access granted (public or static route or localhost)
	return redirect(url_for("login"))  # Send to login page (not logged in)

@app.route("/")
@app.route("/<video_url>")
@public_route
def index(video_url=None):
	# print(request.args.get("video_url"))
	# print(video_url)
	# print(vars(current_user))
	group = GroupMembership.get(current_user.id) if current_user.is_authenticated else None

	return render_template(
		"pages/home.html",
		user=current_user,
		group=group,
		video_url=video_url
	)

@app.route('/static/js/settings.js')
def serve_settings_js():
    return render_template_string(
        open('static/js/settings.js.template').read(),
        debug_mode=DEBUG_MODE
    )

@app.route("/search")
@app.route("/search/<query>")
def search_results(query=None):
	group = GroupMembership.get(current_user.id) if current_user.is_authenticated else None
	# if not query.strip():
	# 	results = []
	# else:
	# 	results = scraper.search(query)
	# result = cache.get(query)

	return render_template(
		"pages/search.html",
		user=current_user,
		group=group,
		query=query,
		# results=results
	)

# Handle delete, ban, and change_role POST requests to /admin
@app.route("/admin", methods=["POST"])
@login_required
def admin_panel_managment():
	print(GroupMembership.get(current_user.id).role)
	if GroupMembership.get(current_user.id).role not in ["Administrators", "Root"]:
		return unauthorized("You are not authorized to access this page.")

	# Get the user to modify
	user_id = request.form.get("user_id")
	user = User.get(user_id)

	# Get the action to perform
	action = request.form.get("action")

	# Perform the action
	if action == "delete":
		user.delete()
	elif action == "ban":
		user.ban()
	elif action == "unban":
		user.unban()
	elif action == "change_role":
		user.change_role(request.form.get("role"))
	else:
		return "Invalid action.", 400

	return redirect(url_for("admin"))

@app.route("/admin")
@login_required
def admin():
	group = GroupMembership.get(current_user.id)

	if not group and group.role in ["Administrators", "Root"]:
		return unauthorized("You must be an admin to access this content.")

	users = User.get_all()
	groups = GroupMembership.get_all()

	return render_template(
		"pages/admin.html",
		users=users,
		groups=groups
	)

@app.route("/logs")
@login_required
def view_logs():
	"""Renders the live log viewing page."""
	group = GroupMembership.get(current_user.id)

	if not group or group.role not in ["Administrators", "Root"]:
		return unauthorized("Only admins can view logs.")
 
	return render_template("pages/logs.html", user=current_user)

@app.route("/pending")
def pending():
	if not current_user.is_authenticated:
		return redirect(url_for("login"))

	group = GroupMembership.get(current_user.id)
	user = User.get(current_user.id)

	if group:
		return redirect(url_for("index"))

	return render_template(
		"pages/pending.html",
		user=user
	)

@app.route("/banned")
@public_route
def banned():
	if not current_user.is_authenticated:
		print("DEBUG: Not Auth")
		return redirect(url_for("index"))

	user = User.get(current_user.id)
	if user.banned:
		print("DEBUG: Is Banned")
		return render_template(
			"pages/banned.html",
			user=user
		)

	print("DEBUG: Not Banned")
	return redirect(url_for("index"))

# # @timer
# @app.route("/api/v2/search", methods=["GET"])
# async def search_api(query=None):
# 	"""
# 	Search for movies.

# 	Args:
# 		query (str): The query to search for. This can also be a movie URL.

# 	Returns:
# 		200: OK
# 		400: No query provided
# 		404: No results found
# 	"""
# 	# Checks if query or q arguments were provided (q takes priority over query)
# 	query = (next(request.args.get(arg, query) for arg in ["q", "query"]) or "").lower().strip()
# 	if not query: return {"message": "No query provided\nPlease report error code: BANJO"}, 400

# 	# Check/Update cache
# 	if not (data := search_cache.get(query)):
# 		data = scraper.search(query)
# 		if not data:
# 			return {"message": "No results found"}, 404
# 		search_cache[query] = data
# 	else:
# 		print(f"Cache Hit: {query}")

# 	async_tasks = []
# 	results = []
# 	for result in data:
# 		cache_hit = video_data_cache.get(result["page_url"])
# 		if cache_hit:
# 			print(f"Cache Hit (video_data): {result['page_url']}")
# 			results.append(cache_hit)
# 		else:
# 			async_tasks.append(asyncio.to_thread(scraper.get_video_data, result["page_url"]))

# 	results += await asyncio.gather(*async_tasks)
# 	for i, result in enumerate(results):
# 		if result["page_url"] not in video_data_cache:
# 			print(f"DEBUG: Adding {result['page_url']} to cache")
# 			video_data_cache[result["page_url"]] = result
# 		results[i].sanatize()  # Sanatize object for JSON serialization

# 	return {"message": "OK", "data": results}, 200


#DEPRICATED for now
# @app.route("/api/v2/searchone", methods=["GET"])
# def searchone_api(query=None):
# 	start = time.time()
# 	query = query if query else request.args.get("q")
# 	# print(query)
# 	if query is None:
# 		print(f"Time taken: {round(time.time() - start, 2)}s.")
# 		return {"message": "No query provided\nPlease report error code: BAGEL"}, 400
# 	data = scraper.search_one(query)
# 	# data = f"Search for '{query}'"

# 	if not data:
# 		print(f"Time taken: {round(time.time() - start, 2)}s.")
# 		return {"message": "No results found"}, 404
# 	print(f"Time taken: {round(time.time() - start, 2)}s.")
# 	return {"message": "OK", "data": data}, 200

@app.route("/api/v2/getvideo", methods=["GET"])
async def getvideo_api(page_url: str | None = None):
	page_url = request.args.get("page_url", page_url)
	if not page_url:
		return {"message": "No page_url provided"}, 400

	# Check cache
	video_data_cache_hit = video_data_cache.get(page_url)
	video_url_cache_hit = video_url_cache.get(page_url)
	if video_data_cache_hit is not None and video_url_cache_hit is not None:
		print(f"Cache Hit (video_data & video_url): {page_url}")
		return {
			"message": "OK",
			"video_url": video_url_cache_hit,
			"video_data": video_data_cache_hit}, 200
	if video_data_cache_hit is not None:
		print(f"Cache Hit (video_data): {page_url}")
		video_url = scraper.get_video_url(page_url)
		video_url_cache[page_url] = video_url
		return {
			"message": "OK",
			"video_url": video_url,
			"video_data": video_data_cache_hit}, 200
	if video_url_cache_hit is not None:
		print(f"Cache Hit (video_url): {page_url}")
		video_data = scraper.get_video_data(page_url)
		video_data_cache[page_url] = video_data
		return {
			"message": "OK",
			"video_url": video_url_cache_hit,
			"video_data": video_data}, 200

	video_data_task = asyncio.create_task(asyncio.to_thread(scraper.get_video_data, page_url))
	video_url_task = asyncio.create_task(asyncio.to_thread(scraper.get_video_url, page_url))
	await asyncio.gather(video_data_task, video_url_task)
	video_data = video_data_task.result()
	video_url = video_url_task.result()
	video_data_cache[page_url] = video_data
	video_url_cache[page_url] = video_url

	return {
		"message": "OK",
		"video_url": video_url,
		"video_data": video_data}, 200

@app.route("/api/v2/popular", methods=["GET"])
async def popular_api():
	"""
	Get popular movies.

	Returns:
		200: OK
	"""
	cache_hit = search_cache.get("_popular")
	if cache_hit is None:
		popular = scraper.popular()
		search_cache["_popular"] = popular
	else:
		popular = cache_hit
		print("Cache Hit: _popular")
	# async_tasks = []
	# results = []
	# for result in popular:
	# 	cache_hit = video_data_cache.get(result["page_url"])
	# 	if cache_hit:
	# 		print(f"Cache Hit (video_data): {result['page_url']}")
	# 		results.append(cache_hit)
	# 	else:
	# 		async_tasks.append(asyncio.to_thread(scraper.get_video_data, result["page_url"]))

	# results += await asyncio.gather(*async_tasks)
	# for result in results:
	# 	if result["page_url"] not in video_data_cache:
	# 		video_data_cache[result["page_url"]] = result
	results = popular

	print(results)
	# return {"message": "OK", "data": [{"testing":"test"}]}, 200
	return {"message": "OK", "data": [result.sanatize() for result in results]}, 200

@app.route("/api/v2/search", methods=["GET"])
def search_api(query=None):
	"""
	Search for movies.

	Args:
		query (str): The query to search for. This can also be a movie URL, infohash, or magnet link.

	Returns:
		200: OK
		400: No query provided
		404: No results found
		502: Failed to connect to the search service
	"""
	query = query if query else request.args.get("q", str())
	query = query.lower().strip()
	if not query:
		return {"message": "No query provided\nPlease report error code: BANJO"}, 400

	if not (results := search_cache.get(query)):
		try:
			results = scraper.search(query)
		except requests.exceptions.ConnectionError as e:
			print(f"Connection error during search: {e}")
			return {"message": "Failed to connect to search service\nPlease report error code: FALCON"}, 502
		if not results:
			return {"message": "No results found"}, 404
		search_cache[query] = results
	else:
		print(f"Cache Hit: {query}")

	return {"message": "OK", "data": [result.sanatize() for result in results]}, 200

@app.route("/api/v2/download", methods=["POST"])
@timer
def download_api(
	page_url: str | None = None,
	id: int | None = None) -> tuple[dict, int]:
	"""
	Download video file from a page_url.

	Args:
		page_url (str): The url of the movie or show
		id (int): The id result

	Returns:
		200: The video is already in queue.
		201: The video was downloaded successfully.
		400: No page_url was provided.
		500: Unknown status.
		508: Failed to download the video.

	"""
	page_url = page_url if page_url else request.args.get("page_url")
	result_id = id if id else request.args.get("id")
	if page_url is None:
		return {
			"message": "No page_url provided\nPlease report error code: BANANA",
			"id": result_id}, 400

	if not (video_url := video_url_cache.get(page_url)):
		if not (video_url := scraper.get_video_url(page_url)):
			return {
				"message": "Failed to get video url\nPlease report error code: AVATAR",
				"id": result_id}, 508
		video_url_cache[page_url] = video_url

	try:
		video_data = video_data_cache.get(page_url)
		if not (video_data := video_data_cache.get(page_url)):
			if not (video_data := scraper.get_video_data(page_url)):
				return {
					"message": "Failed to get video data\nPlease report error code: ASTRO",
					"id": result_id}, 508
			video_data_cache[page_url] = video_data
	except RealDebridInfringingError as e:
		print(f"Real-Debrid error: {e}")
		return {
			"message": "Infringing video file, cannot download\nPlease report error code: HAMMER",
			"id": result_id}, 451
	except RealDebridAPIError as e:
		print(f"Real-Debrid error: {e}")
		return {
			"message": "Real-Debrid API key is invalid\nPlease report error code: GUITAR",
			"id": result_id}, 403

	category_mapping = {
		"tv": "TV SHOWS/",
		"movie": "MOVIES/",
		"unknown": "MOVIES/",
		"episode": "TV SHOWS/",
	}

	library_path = category_mapping.get(video_data.get("catagory"), "MOVIES/")  # default is MOVIES/

	# print(f"DEBUG: {video_data} (video_data)")  # video_data is wrong here (FIXED?)

	full_filename = os.path.join(
		ROOT_LIBRARY_LOCATION,
		library_path,
		video_data["filename"].rsplit(".", 1)[0],
		video_data["filename"] +".crdownload")  # : filtering should be unnecessary
	filename = os.path.join(
		library_path,
		video_data["filename"].rsplit(".", 1)[0],
		video_data["filename"])

	download_engine = DownloadEngine()
	downloads = download_engine.downloads
	# Check if the video is already in the queue
	if downloads is not None:
		for download in downloads:
			if filename in download.filename:
				# The download was started but never finished due to a server restart
				if download.status in ["downloading", "initializing"] and download.last_updated < server_init_time:
					print(f"DEBUG: {filename} was started but never finished, resuming...")
					download.delete()
					break
				match download.status:
					case "downloading":
						print("DEBUG: Already in queue")
						return {
							"message": "Already in queue",
							"video_data": video_data.sanatize(),
							"id": result_id}, 200
					case "initializing":
						print("DEBUG: Download is initializing")
						return {
							"message": "Download is initializing",
							"video_data": video_data.sanatize(),
							"id": result_id}, 200
					case "finished":
						if os.path.exists(os.path.join(ROOT_LIBRARY_LOCATION, download.filename.rsplit(".crdownload", 1)[0])):
							print("DEBUG: Already downloaded")
							return {
								"message": "Already downloaded",
								"video_data": video_data.sanatize(),
								"id": result_id}, 200
						print(f"DEBUG: download.filename: {download.filename}")
						print(f"DEBUG: filename: {filename}")
						print("DEBUG: Download was finished but file is missing, retrying...")
						download.delete()
					case "failed":
						print(f"DEBUG: {filename} failed to download, retrying...")
						download.delete()
					case "not_started":
						print(f"DEBUG: {filename} was queued but never started ({download.last_updated}), retrying...")
						download.delete()
					case _:
						print(f"DEBUG: {download.status} is not a valid known status for {filename}")
						return {
							"message": f"{download.status} is not a valid known status\nPlease report error code: EAGLE",
							"id": result_id}, 500
				break
	user_id = current_user.id if current_user.is_authenticated else "ANYMOOSE"  # -kyrakyrakyrakyra
	if download_engine.get(filename) and os.path.exists(full_filename):
		print("DEBUG: Already downloaded.")
		return {
			"message": "Already downloaded",
			"video_data": video_data.sanatize(),
			"id": result_id}, 200
	download_engine.create(
		filename.replace(ROOT_LIBRARY_LOCATION, "").strip("/\\"),
		video_url,
		user_id,
		download_quality=video_data.get("quality_tag")
	)
	download_engine.queue.append({"url": video_url, "filename": filename.replace(ROOT_LIBRARY_LOCATION, "").strip("/\\")})
	download_engine.start()
	try:
		if os.path.exists(filename):
			print("DEBUG: Already downloaded, but database is out of sync.")
			return {
				"message": "Already downloaded",
				"video_data": video_data.sanatize(),
				"id": result_id}, 200
		# os.rename(filename, filename.rsplit(".crdownload", 1)[0])  # TODO: This should be moved to download_engine.py
	except FileNotFoundError:
		pass

	return {
		"message": "OK",
		"video_data": video_data.sanatize(),
		"video_url": video_url,
		"id": result_id}, 201

# @app.route("/api/v1/download", methods=["POST"])
# def download_api_old(page_url=None):
# 	"""
# 	Download a video from a result.

# 	Args:
# 		page_url (str): The url of the movie or show

# 	Returns:
# 		200: The video is already in queue.
# 		201: The video was downloaded successfully.
# 		400: No url or result was provided.
# 		508: Failed to download the video.

# 	"""
# 	page_url = request.args.get("page_url", page_url)

# 	if result is not None:
# 		result = json.loads(requests.utils.unquote(result))
# 		print(f"DEBUG: {result} (result)")
# 		# print(f"DEBUG: {url} (url)")
# 	elif url is not None:
# 		print("\tWARNING: No result provided, getting data from page_url...")
# 		result = cache.get(url)
# 		if result is None:
# 			result = scraper.find_data_from_url(url)
# 			cache[url] = result
# 	else:
# 		print("\tERROR: No result provided for direct download link.")
# 		# return {"message": "No result provided for direct download link\nPlease report error code: BANANA"}, 400
# 	video_url = scraper.get_video(result["page_url"])
# 	if video_url == 225:
# 		print("CAPTCHA")
# 		image_data = read_image("captcha.png")
# 		return {"message": "CAPTCHA", "data": image_data, "page_url": result["page_url"]}, 225
# 	retry_count = 0
# 	while not video_url:
# 		video_url = scraper.get_video(result["page_url"])
# 		retry_count += 1
# 		if retry_count > 5:
# 			print("\tERROR: Failed to get video url.")
# 			return {"message": "Failed to get video url\nPlease report error code: AVATAR"}, 508

# 	filename = Format(result).format_filename()

# 	download_engine = DownloadEngine()
# 	downloads = download_engine.downloads
# 	# Check if the video is already in the queue
# 	if downloads is not None:
# 		for download in downloads:
# 			if filename not in download.filename:
# 				continue
# 			# The download was started but never finished due to a server restart
# 			if download.status in ["downloading", "initializing"] and download.last_updated < server_init_time:
# 				print(f"DEBUG: {filename} was started but never finished, resuming...")
# 				download.delete()
# 				break
# 			match download.status:
# 				case "downloading":
# 					print("DEBUG: Already in queue")
# 					return {"message": "Already in queue", "result": result}, 200
# 				case "initializing":
# 					print("DEBUG: Download is initializing")
# 					return {"message": "Download is initializing", "result": result}, 200
# 				case "finished":
# 					if os.path.exists(download.filename):
# 						print("DEBUG: Already downloaded")
# 						return {"message": "Already downloaded", "result": result}, 200
# 					print("DEBUG: Download was finished but file is missing, retrying...")
# 					download.delete()
# 				case "failed":
# 					print(f"DEBUG: {filename} failed to download, retrying...")
# 					download.delete()
# 				case "not_started":
# 					print(f"DEBUG: {filename} was queued but never started ({download.last_updated}), retrying...")
# 					download.delete()
# 				case _:
# 					print(f"DEBUG: {download.status} is not a valid known status for {filename}")
# 					return {"message": f"{download.status} is not a valid known status\nPlease report error code: EAGLE"}, 500
# 			break
# 	user_id = current_user.id if current_user.is_authenticated else "ANYMOOSE"
# 	download_engine.create(filename, video_url, user_id, download_quality=result["data"]["quality_tag"])
# 	download_engine.queue.append({"url": video_url, "filename": filename})
# 	download_engine.start()

# 	# Check if the video is already in the queue
# 	# for item in download_engine.queue:
# 	# 	if item["filename"] == filename:
# 	# 		print("DEBUG: Already in queue")
# 	# 		return {"message": "Already in queue"}, 200

# 	# # Add the item to the queue
# 	# download_engine.queue.append({"url": video_url, "filename": filename})
# 	# print("Download queued...")
# 	# print(f"DEBUG: {download_engine.queue}")
# 	# download_succeed = download_engine.download_file(-1)
# 	# if not download_succeed:
# 	# 	print("\tERROR: Failed to download the video.")
# 	# 	return {"message": "Failed to download the video\nPlease report error code: APPLE"}, 508

# 	# print("DEBUG: Download finished!")
# 	# # Remove the item from the queue after the download is finished
# 	# # download_engine.queue.remove({"url": url, "filename": filename})
# 	return {"message": "Created", "result": result}, 201

@app.route("/login")
@public_route
def login():
	# Find out what URL to hit for Google login
	google_provider_cfg = get_google_provider_cfg()
	authorization_endpoint = google_provider_cfg["authorization_endpoint"]

	# Use library to construct the request for login and provide
	# scopes that let you retrieve user's profile from Google
	request_uri = client.prepare_request_uri(
		authorization_endpoint,
		redirect_uri=request.base_url.replace("http://", "https://", 1) + "/callback",
		scope=["openid", "email", "profile"],
	)
	return redirect(request_uri)


@app.route("/login/callback")
@public_route
def callback():
	try:
		# Find out what URL to hit to get tokens that allow you to ask for
		# things on behalf of a user
		google_provider_cfg = get_google_provider_cfg()

		# Prepare and send request to get tokens.
		token_url, headers, body = client.prepare_token_request(
			google_provider_cfg["token_endpoint"],
			authorization_response=request.url,
			redirect_url=request.base_url,
			code=request.args.get("code"),
		)
		token_response = requests.post(
			token_url,
			headers=headers,
			data=body,
			auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
			timeout=30,
		)

		# Parse the tokens!
		client.parse_request_body_response(json.dumps(token_response.json()))

		# Now that we have tokens (yay) let's find and hit URL
		# from Google that gives you user's profile information,
		# including their Google Profile Image and Email
		userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
		uri, headers, body = client.add_token(userinfo_endpoint)
		userinfo_response = requests.get(uri, headers=headers, data=body, timeout=30)

		# We want to make sure their email is verified.
		# The user authenticated with Google, authorized our
		# app, and now we've verified their email through Google!
		if userinfo_response.json().get("email_verified"):
			print(userinfo_response.json())
			unique_id = userinfo_response.json()["sub"]
			email = userinfo_response.json()["email"]
			picture = userinfo_response.json()["picture"]
			first_name = userinfo_response.json()["given_name"]
			last_name = userinfo_response.json().get("family_name", "")
		else:
			return "User email not available or not verified by Google.", 400

		# Create user object with the information provided by Google
		user = User(
			user_id=unique_id,
			first_name=first_name,
			last_name=last_name,
			email=email,
			profile_pic=picture
		)

		# Doesn't exist? Add to database
		if not User.get(unique_id):
			User.create(unique_id, first_name, last_name, email, picture)

		# Begin user session by logging the user in
		login_user(user, remember=True)

		# User is banned? Return banned page
		if user.banned:
			return redirect(url_for("banned"))

		# Not a member of any group? Return waiting page
		if not GroupMembership.get(unique_id):
			return redirect(url_for("pending"))
			# return render_template(
			# 	"pages/pending_approval.html",
			# 	current_user=current_user
			# )


		# Send user back to homepage
		return redirect(url_for("index"))
	except InsecureTransportError as e:
		print(e)
		# app.logger.error(e)
		return f"Something went wrong {e}", 400


@app.route("/logout")
@login_required
def logout():
	logout_user()
	return redirect(url_for("index"))

# @app.route("/test")
# def test():
# 	return {"message": "OK"}, 200

@app.route("/test/<filename>")
@app.route("/test")
@public_route
def test(filename=None):
	filename = request.args.get("filename", filename)
	download_engine = DownloadEngine()
	if filename is None:
		downloads = download_engine.downloads
		return {"message": download.filename for download in downloads}, 200
	download = download_engine.get(filename)
	if download is None:
		return {"message": "Not found"}, 404
	return {
		# "message": "Okay",
		"filename": download.filename,
		"status": download.status,
	}, 200

def get_google_provider_cfg():
	return requests.get(GOOGLE_DISCOVERY_URL, timeout=30).json()


if __name__ == "__main__":
	app.run(ssl_context="adhoc", debug=True, host="0.0.0.0", port=9000)
