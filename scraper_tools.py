# -*- coding: utf-8 -*-
# filename          : scraper_tools.py
# description       : Helper file for scraping websites and matching filenames to TMDb.
# author            : Rico Alexander
# email             : rico@rico.cx
# date              : 08-01-2025
# version           : v3.0
# usage             : python waitress_serve.py
# notes             : This file should not be run directly.
# license           : MIT
# py version        : 3.12.5 (must run on 3.10 or higher)
#==============================================================================
import os
import subprocess
from time import perf_counter
from collections.abc import Callable

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from tmdbv3api import TMDb, Search, Movie, TV  # type: ignore[import-untyped]

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
		capabilities = DesiredCapabilities.CHROME
		capabilities['goog:loggingPrefs'] = {'performance': 'ALL'}  # type: ignore[assignment]
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

	def resume_video(self):
		self.driver.execute_script(
			"for(v of document.querySelectorAll('video')){v.setAttribute('muted','');v.play()}"
		)

	def pause_video(self):
		self.driver.execute_script(
			"videos = document.querySelectorAll('video'); for(video of videos) {video.pause()}"
		)

	def reload(self):
		self.driver.refresh()

	def current_url(self):
		return self.driver.current_url

	def close(self):
		self.driver.close()

	def refresh(self):
		self.driver.refresh()


class FileBot:

	def __init__(self):
		try:
			if os.listdir("temp"):
				print("Clearing FileBot temp folder...")
				for file in os.listdir("temp"):
					os.remove(f"temp/{file}")
		except FileNotFoundError:
			os.mkdir("temp")
		try:
			subprocess.run(["filebot", "-version"], check=True)
			print("FileBot initialized.")
		except FileNotFoundError as e:
			raise FileNotFoundError("FileBot is not installed. Please install FileBot to use this feature.") from e

	def rename(self, source_dir=".", destination_dir=".", test=False):
		try:
			command = [
				'filebot',
				'-rename', source_dir,
				'--output', destination_dir,
				'--format', "{n} ({y}){{' {tmdb-' + id + '}'}}/{n} ({y}){{' {tmdb-' + id + '}'}}"
			]
			if test: command += ['--action', 'TEST']
			subprocess.run(command, check=True)
			print(f"File/Folder '{source_dir}' renamed successfully.")
		except subprocess.CalledProcessError as e:
			print(f"Error renaming file: {e}")

	def get_names(self, filenames: list[dict[str, str]]):
		print(f"{len(filenames)} files...")
		for index, filename in enumerate(filenames):
			# print(filename)
			extension = filename["filename"].rsplit(".", maxsplit=1)[-1].lower()
			if extension not in ["mkv", "mp4"]:
				filename["filename"] += ".mkv"
				filenames[index] = filename

			with open(f"temp/{filename['filename']}", "w", encoding="utf8") as _:
				pass

		command = [
			"filebot", "-rename",
			"temp/",
			"--output", "/OUTPUT",
			"--format", "{n} ({y}){{' {tmdb-' + id + '}'}}",
			"--action", "test",
			"--log", "info"]
		#                                                                check=True
		result = subprocess.run(command, capture_output=True, text=True, check=False)
		for filename in filenames:
			try:
				os.remove("temp/"+ filename["filename"])
			except FileNotFoundError:
				pass
		# print(result)
		results = result.stdout.split("\n")
		# print(results)
		for index, _result in enumerate(results):
			# print(_result)  # lots of issues can occur here
			if "pattern not found" in _result:  # Print which file had the issue and the specific error
				print(f"ERROR:\n\t{filenames[index]['filename']} - {_result}")
			if _result.startswith("[TEST]"):
				# print(_result)
				# "[TEST] from [/Users/ian/Documents/Python/P084 - RICO.CX/temp/Scum of the Earth [1963 - USA] sexploitation thriller.mkv] to [/OUTPUT/Scum of the Earth! (1963) {tmdb-28175}.mkv]"
				# old, new = _result.split("[TEST] from [")[1].split("] to [")
				old = _result.split("[TEST] from [")[1].split("] to [")[0]
				old = os.path.basename(os.path.normpath(old))
				os.path.basename(_result[_result.find('/temp/')+6:_result.find(']')])
				new = os.path.basename(_result[_result.rfind('/')+1:-1])
				# print(old, "->", new)
				results[index] = new
				for index, filename in enumerate(filenames):
					if filename["filename"] == old:
						filenames[index]["filename"] = new
						filenames[index]["filename_old"] = old
						filenames[index]["title"] = new.rsplit(" (", 1)[0]
						filenames[index]["release_year"] = new.rsplit(" (", 1)[1].split(") ")[0]
						filenames[index]["tmdb_id"] = new.rsplit(") {tmdb-", 1)[1].split("}")[0]
		# for index, filename in enumerate(filenames):
		# 	if filename.get("quality_tag") is not None:
		# 		print(f"DEBUG: {filename['filename']} already has a quality tag of '{filename['quality_tag']}'")
		# 		continue
		# 	if "2160p" in filename["original_title"]:
		# 		filenames[index]["quality_tag"] = "UHD"
		# 	elif "1080p" in filename["original_title"]:
		# 		filenames[index]["quality_tag"] = "FHD"
		# 	elif "720p" in filename["original_title"]:
		# 		filenames[index]["quality_tag"] = "HD"
		# 	elif "480p" in filename["original_title"]:
		# 		filenames[index]["quality_tag"] = "SD"
		# 	elif "360p" in filename["original_title"]:
		# 		filenames[index]["quality_tag"] = "SD"
		# 	elif "dvd" in filename["original_title"].lower():
		# 		filenames[index]["quality_tag"] = "SD"
		# 	else:
		# 		filenames[index]["quality_tag"] = ""

		for index, filename in enumerate(filenames):
			if filename.get("quality_tag") is not None:
				print(f"DEBUG: {filename['filename']} already has a quality tag of '{filename['quality_tag']}'")
			match filename["original_title"]:
				case title if "hdcam" in title.lower() \
				or "camrip" in title.lower() \
				or "hd-ts" in title.lower() \
				or ".ts." in title.lower() \
				or "hdts" in title.lower() \
				or "hd cam" in title.lower() \
				or " ts " in title.lower():
					filenames[index]["quality_tag"] = "CAM"
				case title if "2160p" in title.lower() \
				or " uhd " in title \
				or ".uhd." in title.lower():
					filenames[index]["quality_tag"] = "UHD"
				case title if "1080p" in title.lower():
					filenames[index]["quality_tag"] = "FHD"
				case title if "720p" in title.lower() \
				or "bluray" in title.lower() \
				or "brrip" in title.lower() \
				or "bdrip" in title.lower() \
				or "hdrip" in title.lower() \
				or "webrip" in title.lower() \
				or "web-dl" in title.lower():
					filenames[index]["quality_tag"] = "HD"
				case title if "480p" in title.lower() \
				or "360p" in title.lower() \
				or "dvd" in title.lower():
					filenames[index]["quality_tag"] = "SD"
				case _:
					filenames[index]["quality_tag"] = ""

		for index, filename in enumerate(filenames):
			# if filename.get("title") is not None:
			if filename.get("title") is not None:
				continue
			filenames[index]["title"] = filename["filename"]
			filenames[index]["release_year"] = "1492"
			# filenames[index]["tmdb_id"] = ""

		return filenames

	def get_name(self, filename: str) -> dict[str, str]:
		"""
		This function takes a filename as a string and returns a dictionary
		containing the title, release year, and tmdb_id.

		The filename must contain the name and year of the movie or show.
		"""

		extension = filename.rsplit(".", maxsplit=1)[-1].lower()
		if extension not in ["mkv", "mp4"]:
			filename += ".mkv"  # MKV is the most common extension

		with open(f"temp/{filename}", "w", encoding="utf8") as _:
			pass

		command = [
			"filebot", "-rename",
			"temp/",
			"--output", "/OUTPUT",
			"--format", "{n} ({y}){{' {tmdb-' + id + '}'}}",
			"--action", "test",
			"--log", "info"]
		result = subprocess.run(command, capture_output=True, text=True, check=False)
		os.remove("temp/"+ filename)

		results = result.stdout.split("\n")
		for _result in results:
			if _result.startswith("[TEST]"):
				old, new = _result.split("[TEST] from [")[1].split("] to [")
				old = old.replace(os.getcwd()+"/temp/", "")
				new = new.strip("]").split("/OUTPUT/")[1]

				if old == filename:
					title = new.rsplit(" (", 1)[0]
					release_year = new.rsplit(" (", 1)[1].split(") ")[0]
					tmdb_id = new.rsplit(") {tmdb-", 1)[1].split("}")[0]
					return {
						"filename": new,
						"title": title,
						"release_year": release_year,
						"tmdb_id": tmdb_id
					}

		# If no match is found, return default values
		return {
			"filename": filename,
			"title": filename,
			"release_year": "1492",  # Ricardo sailed the ocean blue! (in his pirate ship)
			"tmdb_id": ""
		}

	# def get_name(self, filename: str):
	# 	extension = filename.rsplit(".", maxsplit=1)[-1].lower()
	# 	if extension not in ["mkv", "mp4"]:
	# 		filename += ".mkv"

	# 	with open(f"temp/{filename}", "w", encoding="utf8") as _:
	# 		pass

	# 	command = [
	# 		"filebot", "-rename",
	# 		f'temp/{filename}',
	# 		"--output", "/OUTPUT",
	# 		"--format", "{n} ({y}){{' {tmdb-' + id + '}'}}",
	# 		"--action", "test",
	# 		"--log", "info"]
	# 	#                                                                check=True
	# 	result = subprocess.run(command, capture_output=True, text=True, check=False)
	# 	os.remove(f"temp/{filename}")
	# 	return result.stdout.strip("\n]").rsplit("[/OUTPUT/", maxsplit=1)[-1]
	# 	# [TEST] from [/Users/ian/Documents/Python/P084 - RICO.CX/temp/Amici per caso (2024) iTALiAN.WEBRiP.x264-Dr4gon.mkv] to [/Accidental Friends (2024) {tmdb-1222510}.mkv]\n

	def add_subtitles(self, source_dir, test=False):
		try:
			command = [
				'filebot',
				'-get-subtitles', source_dir,
				'-lang', 'en',
			]
			if test: command += ['--action', 'TEST']
			subprocess.run(command, check=True)
			print(f"Subtitles added for '{source_dir}'.")
		except subprocess.CalledProcessError as e:
			print(f"Error adding subtitles: {e}")


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

	def details_movie(self, movie_id: int | str) -> dict:
		return Movie().details(int(movie_id))

	def details_tv(self, tv_id: int | str) -> dict:
		return TV().details(int(tv_id))

	# def get_tv_show_release_year(self, query):
	# 	return self.search_tv_show(query)["first_air_date"][:4]

	# def get_movie_release_year(self, query):
	# 	return self.search_movie(query)["release_date"][:4]


def main():
	fb = FileBot()
	result = fb.get_name("Flushed Away (2006).mp4")
	print(result)


if __name__ == "__main__":
	main()
