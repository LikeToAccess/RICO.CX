# -*- coding: utf-8 -*-
# filename          : settings.py
# description       : Different options for parts of the program
# author            : Ian Ault
# email             : rico@rico.cx
# date              : 12-08-2022
# version           : v1.0
# usage             :
# notes             : This file should not be run directly
# license           : MIT
# py version        : 3.11.0
#==============================================================================
# Sets the browser option "--headless", this will prevent the browser from
# opening a GUI window.
# Because of this, the "--disable-gpu" flag is also enabled when HEADLESS is
# set to True.
# The default value is True.
HEADLESS = True

# Sets the IP/Domain Name and port to bind the API to, the API will only be
# accessable from whatever this is set to.
# The default value is "0.0.0.0" (for localhost) and 8080.
HOST = "0.0.0.0"
PORT = 9000

# Enables API serving via Flask instead of Waitress. Also disables downloading
# full media and skips verification checks.
# The default value is False.
DEBUG_MODE = True
USE_RELOADER = False

# External API key for The Movie Database's offical API. The tmdbv3api Python
# library is used to interact with TMDb's API to insert TMDb IDs into the
# filenames.
# The default value is False.
TMDB_API_KEY = "a524c0fd2eaafa0e4288058506baf835"

# Countries whose content is banned from being downloaded. This is a list of
# country codes, for example: ["US", "CA", "GB"].
# The default value is ["PH"].
BANNED_COUNTRIES = ["PH"]

# Root download directory, this will set the download location for all
# media.
# The default value is "../".
ROOT_LIBRARY_LOCATION = "C:/Users/User/Desktop/"
# ROOT_LIBRARY_LOCATION = "/Users/ian/Desktop/"

# Google API credentials, used for Google OAuth2 authentication.
# The default values are False.
GOOGLE_CLIENT_ID = "788220717359-mqsrau2lmb85l94f68febkpb8fnbgj82.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Discord API credentials, used for Discord OAuth2 authentication.
# The default value is False.
DISCORD_BOT_TOKEN = "Nzc2NjgxMzA4MjIyOTE0NTgw.G-yf8a.GtFAFIzGPvjw-tG5kye2dEJcGQCR1Zd_n25Eq4"
