# -*- coding: utf-8 -*-
# filename          : scraper.py
# description       : Respond to GET requests from websites with MP4 links
# author            : Rico Alexander
# email             : rico@rico.cx
# date              : 10-24-2023
# version           : v2.0
# usage             : python main.py
# notes             :
# license           : MIT
# py version        : 3.12.0 (must run on 3.10 or higher)
#==============================================================================
import os
from time import perf_counter
from collections.abc import Callable

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from tmdbv3api import TMDb, Search  # type: ignore[import-untyped]

from element_find import FindElement
from element_wait_until import WaitUntilElement
from settings import HEADLESS, TMDB_API_KEY


def goto_homepage(function: Callable) -> Callable:
		def wrapper(self, *args, **kwargs):
			result = function(self, *args, **kwargs)
			self.open_link(self.homepage_url)
			return result
		return wrapper


class ScraperTools(WaitUntilElement, FindElement):

	def __init__(self, init: bool = True):
		if not init:
			return
		tic = perf_counter()
		options = Options()
		user_data_dir = os.path.abspath("selenium_data")
		options.add_argument("--autoplay-policy=no-user-gesture-required")
		options.add_argument("log-level=3")
		# options.add_argument("--no-sandbox")
		options.add_experimental_option("prefs", {"download_restrictions": 3})  # Disable downloads
		options.add_argument(f"user-data-dir={user_data_dir}")
		options.add_argument("--ignore-certificate-errors-spki-list")
		for extension in os.listdir("chrome_extensions"):
			options.add_extension(f"chrome_extensions/{extension}")
		if HEADLESS:
			options.add_argument("--headless")
			options.add_argument("--window-size=1920,1080")
			# options.add_argument("--disable-gpu")
			options.add_argument("--mute-audio")
		self.driver = webdriver.Chrome(service=Service(), options=options)
		super().__init__(self.driver)
		toc = perf_counter()
		print(f"Completed init in {toc-tic:.2f}s.")

	def open_link(self, url: str):
		self.driver.get(url)

	def redirect(self, url: str):
		if self.current_url() == url:
			return
		print("Redirecting to correct URL...")
		self.open_link(url)
		print(self.current_url())

	def reload(self):
		self.driver.refresh()

	def current_url(self):
		return self.driver.current_url

	def close(self):
		self.driver.close()

	def refresh(self):
		self.driver.refresh()


class TMDbTools:

	def __init__(self):
		self.tmdb = TMDb()
		self.tmdb.api_key = TMDB_API_KEY
		self.search = Search()

	def search_movies(self, query: str) -> list:
		return self.search.movies(query)["results"]

	def search_movie(self, query: str) -> dict | None:
		results = self.search_movies(query)
		return results[0] if results else None

	def search_tv_shows(self, query: str) -> list | None:
		results = self.search.tv_shows(query)["results"]
		return results

	def search_tv_show(self, query: str) -> dict | None:
		results = self.search_tv_shows(query)
		return results[0] if results else None

	# def get_tv_show_release_year(self, query):
	# 	return self.search_tv_show(query)["first_air_date"][:4]

	# def get_movie_release_year(self, query):
	# 	return self.search_movie(query)["release_date"][:4]
