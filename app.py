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
# py version        : 3.11.0 (must run on 3.6 or higher)
#==============================================================================
# pylint: disable=import-error
import base64
import json
import os
import sqlite3

import requests
from flask import Flask, redirect, render_template, request, url_for
from oauthlib.oauth2 import WebApplicationClient
from oauthlib.oauth2.rfc6749.errors import InsecureTransportError
from flask_login import (
	LoginManager,
	current_user,
	login_required,
	login_user,
	logout_user
)

from database import init_db_command
from user import User
from group import Group_Membership
from scraper import Scraper
from settings import (
	GOOGLE_CLIENT_ID,
	GOOGLE_CLIENT_SECRET,
	GOOGLE_DISCOVERY_URL
)


app = Flask(__name__)
app.secret_key = os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)

# Naive database setup
try:
	init_db_command()
except sqlite3.OperationalError:
	# Assume it's already been created
	pass

# OAuth2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# Web scraping setup
scraper = Scraper()


@login_manager.unauthorized_handler
def unauthorized():
	return "You must be logged in to access this content.", 403

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

@app.route("/")
@app.route("/<video_url>")
def index(video_url=None):
	# print(request.args.get("video_url"))
	# print(video_url)
	# print(vars(current_user))
	group = Group_Membership.get(current_user.id) if current_user.is_authenticated else None

	return render_template(
		"pages/home.html",
		current_user=current_user,
		group=group,
		video_url=video_url
	)

@app.route("/api/v1/search/<query>", methods=["GET"])
@app.route("/api/v1/search", methods=["GET"])
@login_required
def search(query=None):
	query = request.args.get("query", query)
	# print(query)
	if query is None:
		return {"message": "No query provided"}, 400
	data = scraper.search(query)
	# data = f"Search for '{query}'"

	if data == 404:
		return {"message": "No results found"}, 404
	return {"message": "OK", "data": data}, 200

@app.route("/api/v1/searchone/<query>", methods=["GET"])
@app.route("/api/v1/searchone", methods=["GET"])
@login_required
def searchone(query=None):
	query = request.args.get("query", query)
	# print(query)
	if query is None:
		return {"message": "No query provided"}, 400
	data = scraper.searchone(query)
	# data = f"Search for '{query}'"

	if data == 404:
		return {"message": "No results found"}, 404
	return {"message": "OK", "data": data}, 200

@app.route("/api/v1/getvideo/<video_url>", methods=["GET"])
@app.route("/api/v1/getvideo", methods=["GET"])
@login_required
def getvideo(video_url=None):
	video_url = request.args.get("video_url", video_url)
	if video_url is None:
		return {"message": "No video_url provided"}, 400
	data = scraper.get_video(video_url)

	if data == 404:
		return {"message": "No results found"}, 404
	if data == 225:
		print("CAPTCHA")
		image_data = base64.b64encode(open("captcha.png", "rb").read()).decode("utf-8")
		image_data = f"data:image/png;base64,{image_data}"
		return {"message": "CAPTCHA", "data": image_data, "video_url": video_url}, 225
	return {"message": "OK", "data": data}, 200

@app.route("/api/v1/captcha", methods=["POST"])
@login_required
def captcha():
	captcha_response = request.args.get("captcha_response")
	video_url = request.args.get("video_url")
	if not captcha_response:
		return {"message": "No captcha_response provided"}, 400
	if not video_url:
		return {"message": "No video_url provided"}, 400
	data = scraper.resolve_captcha(captcha_response)
	if not data:
		image_data = base64.b64encode(open("captcha.png", "rb").read()).decode("utf-8")
		image_data = f"data:image/png;base64,{image_data}"
		return {"message": "CAPTCHA failed", "data": image_data, "video_url": video_url}, 225
	return {"message": "CAPTCHA solved", "video_url": video_url}, 200
	# return {"message": "OK", "data": data}, 200

@app.route("/login")
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
def callback():
	try:
		# Get authorization code Google sent back to you
		code = request.args.get("code")

		# Find out what URL to hit to get tokens that allow you to ask for
		# things on behalf of a user
		google_provider_cfg = get_google_provider_cfg()
		token_endpoint = google_provider_cfg["token_endpoint"]

		# Prepare and send request to get tokens! Yay tokens!
		token_url, headers, body = client.prepare_token_request(
			token_endpoint,
			authorization_response=request.url,
			redirect_url=request.base_url,
			code=code,
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

		# Not a member of any group? Return 403
		if not Group_Membership.get(unique_id):
			return "You are not authorized to access this content.", 403

		# Begin user session by logging the user in
		login_user(user)

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


def get_google_provider_cfg():
	return requests.get(GOOGLE_DISCOVERY_URL, timeout=30).json()


if __name__ == "__main__":
	app.run(ssl_context="adhoc", debug=True)
