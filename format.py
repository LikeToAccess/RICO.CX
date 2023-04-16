# -*- coding: utf-8 -*-
# filename          : format.py
# description       : Handle formatting filenames and downloading media
# author            : Ian Ault
# email             : liketoaccess@protonmail.com
# date              : 06-25-2022
# version           : v1.0
# usage             : python main.py
# notes             : This file should not be run directly
# license           : MIT
# py version        : 3.10.2 (must run on 3.6 or higher)
#==============================================================================
import re
import os
import json

from time import perf_counter
from tmdbv3api import TMDb, Search

from file import *
from settings import *


if TMDB_API_KEY:
	tmdb = TMDb()
	tmdb.api_key = TMDB_API_KEY
	tmdb.language = "en"
	search = Search()

regions = read_json_file("country_codes.json")


# def filter_bad_characters(data, ):
# 	return re.sub(bad_characters, "", data).encode("ascii", "ignore").decode()

def convert_imdb_to_float(string):
	# Check if the string starts with "IMDb: " and strip it out
	if string.startswith("IMDb: "):
		string = string[6:]

	# Check if the remaining string can be converted to a float or int
	if re.match(r'^\d+\.\d+$', string):
		return float(string)
	elif re.match(r'^\d+$', string):
		return float(string)
	else:
		return string

def contains_only_letters(data):
	matches = re.findall(r"[^a-zA-Z]+", data)
	return not bool(matches)

def find_show_title_from_tv_show(data):
	show_title = re.sub(r"(\s-\sSeason\s\d)(?!.*\s-\sSeason\s\d).*", "", data)
	return show_title

def find_episode_title_from_tv_show(data):
	episode_title = re.sub(r".*(\sEpisode\s\d+\s)(?!.*\sEpisode\s\d+\s)", "", data)
	return episode_title

def find_season_number_from_tv_show(data, regex=r"(\s-\sSeason\s\d)(?!.*\s-\sSeason\s\d)"):
	try:
		season_number = \
			re.findall(
				r"(\d+)$",
				re.findall(
					# r"(.+)(?=\s-\sSeason\s\d)",
					regex,
					data
				)[-1]
			)[0]
	except IndexError:
		return find_season_number_from_tv_show(data, r"(\s-\sSeason\d)(?!.*\s-\sSeason\d)")
	if len(season_number) < 2:
		season_number = "0"+ season_number
	return season_number

def find_episode_number_from_tv_show(data, regex=r"(\sEpisode\s\d+)(?!.*\sEpisode\s\d+)"):
	# print(data)
	try:
		episode_number = \
			re.findall(
				r"(\d+)$",
				re.findall(
					regex,
					data
				)[-1]
			)[0]
	except IndexError:
		return find_episode_number_from_tv_show(data, r"(\sEpisode\d+)(?!.*\sEpisode\d+)")
	if len(episode_number) < 2:
		episode_number = "0"+ episode_number
	return episode_number

# def print_tmdb_results(results):
# 	print("[")
# 	for results_count, result in enumerate(results):
# 		print("  {")
# 		for keys_count, key in enumerate(result):
# 			print(f"    {key}: {result[key]}" + f"{',' if keys_count+1 != len(result) else ''}")
# 		print("  }" + f"{',' if results_count+1 != len(results) else ''}")
# 	print("]")

def make_string_filesystem_safe(string, bad_characters):
	'''
	File system safe title formatting removes reserved and non-ascii characters
	'''
	string = re.sub(f"[{bad_characters}]", "", string).encode("ascii", "ignore").decode()
	return string


class Format:
	def __init__(self, result):
		# print(page_url)
		# print(result)
		if isinstance(result, str):
			result = json.loads(result)  # Convert str to dict
			print("\tLoaded result as JSON.")
		data = result["data"]
		page_url = result["page_url"]
		print(f"DEBUG: {page_url} (page_url)")
		title = result["title"]
		release_country = data["release_country"]
		self.release_year = data["release_year"]
		# self.imdb_score = data["imdb_score"]
		# self.duration = data["duration"]
		# self.genre = data["genre"]
		# self.description_preview = data["description_preview"]
		# self.key = data["key"]
		# self.quality_tag = data["quality_tag"]
		# self.user_rating = data["user_rating"]
		if "/watch-film/" in page_url and "/watch-tv-show/" not in page_url:
			self.type = "MOVIE"
		elif "/watch-tv-show/" in page_url and "/watch-film/" not in page_url:
			is_episode = page_url.endswith("-online-for-free.html")  # True/False
			self.type = "TV SHOW", is_episode
		else:
			self.type = "MISC"

		if ", " in release_country:
			release_country = release_country.split(", ")[0]

		self.region = regions[release_country]
		self.bad_characters = "<>:\"/\\|?*"
		self.safe_title = make_string_filesystem_safe(title, self.bad_characters)

	def movie(self):
		query = {
			"query": self.safe_title,
			"primary_release_year": self.release_year,
			"region": self.region,
		}

		tmdb_id = None
		while TMDB_API_KEY:
			tmdb_results = search.movies(query)
			count = len(tmdb_results)
			print(f"\tFound {count} {'result' if count == 1 else 'results'} for TMDb lookup.")
			if not tmdb_results:
				print(f"\tWARNING: No TMDb results for query: '{query}'.")
				break
			tmdb_top = tmdb_results[0]
			tmdb_top_title = make_string_filesystem_safe(tmdb_top["original_title"], self.bad_characters)
			if tmdb_top_title != self.safe_title:
				print(
					f"\tWARNING: TMDb result, '{tmdb_top_title}'",
					f"is not an exact match for title, '{self.safe_title}' (this will be ignored)."
				)
				# tmdb_results = []
			tmdb_id = str(tmdb_top["id"]) if tmdb_results else None
			tmdb_release_date_year = re.sub(r"-\d{2}-\d{2}", "", tmdb_top["release_date"])
			if tmdb_release_date_year != self.release_year:
				print(
					f"\tWARNING: TMDb release date, '{tmdb_release_date_year}'",
					f"is not an exact match for release, '{self.release_year}' (this will be ignored)."
				)
			break

		self.safe_title = (
			self.safe_title if re.match(
				r"^.*?\([^\d]*(\d+)[^\d]*\).*$", self.safe_title
			) else f"{self.safe_title} ({self.release_year})"
		)

		self.safe_title = self.safe_title + (" {tmdb-"+ tmdb_id +"}" if tmdb_id else "")
		file_path = os.path.join(ROOT_LIBRARY_LOCATION, f"MOVIES/{self.safe_title}/{self.safe_title}.mp4")

		return file_path

	def tv_show(self, is_episode):
		show_title = find_show_title_from_tv_show(self.safe_title)
		query = {
			"query": show_title,
			# "first_air_date_year": self.release_year,  # Needs initial release of show, not the current
		}

		tmdb_id = None
		while TMDB_API_KEY:
			tmdb_results = search.tv_shows(query)
			# print_tmdb_results(tmdb_results)
			count = len(tmdb_results)
			print(f"\tFound {count} {'result' if count == 1 else 'results'} for TMDb lookup.")
			if not tmdb_results:
				print(f"\tWARNING: No TMDb results for query: {query}")
				break
			tmdb_top = tmdb_results[0]
			tmdb_top_title = make_string_filesystem_safe(tmdb_top["name"], self.bad_characters)
			if tmdb_top_title != show_title:
				print(
					f"\tWARNING: TMDb result, '{tmdb_top_title}'",
					f"is not an exact match for title, '{show_title}' (TMDb ID will not be used)."
				)
				tmdb_results = []
			tmdb_id = str(tmdb_top["id"]) if tmdb_results else None
			tmdb_first_air_date_year = re.sub(r"-\d{2}-\d{2}", "", tmdb_top["first_air_date"])

			show_title = (
				show_title if re.match(
					r"^.*?\([^\d]*(\d{4})[^\d]*\).*$", show_title
				) else f"{show_title} ({tmdb_first_air_date_year})"
			)
			break

		season_number = find_season_number_from_tv_show(self.safe_title)
		show_title = show_title.replace("-", "")
		file_path = os.path.join(
			ROOT_LIBRARY_LOCATION,
			f"TV Shows/{show_title +(' {tmdb-'+ tmdb_id +'}' if tmdb_id else '')}/Season {season_number}"
		)
		# print(file_path)

		if is_episode:
			episode_number = find_episode_number_from_tv_show(self.safe_title)
			episode_title = find_episode_title_from_tv_show(self.safe_title)
			file_path = os.path.join(
				file_path,
				f"{show_title} - s{season_number}e{episode_number} - {episode_title}.mp4"
			).replace("\\","/")
		# print(file_path)

		return file_path

	def format_filename(self):
		if TMDB_API_KEY:
			print("Waiting for TMDb lookup...")
			t1_start = perf_counter()

		match self.type:
			case "MOVIE":
				file_path = self.movie()
			case "TV SHOW", is_episode:
				file_path = self.tv_show(is_episode)
			case _:
				print("\tERROR: \"file_path\" is undefined!")

		if TMDB_API_KEY:
			t1_stop = perf_counter()
			print(f"\tCompleted lookup in {round(t1_stop-t1_start,2)}s.")
		return file_path

	def run(self):
		print(f"DEBUG: {self.format_filename()}")


def main():
	file_name = Format({'title': 'Flushed Away', 'page_url': 'https://gomovies-online.cam/watch-film/flushed-away/6N8p178f', 'poster_url': 'https://static.gomovies-online.cam/dist/img/UI8PAe7IzXTeCQl4aF9SqFxc5YsWt9wHRD2UgAy3culxFUdWsD5ckp32IfKlMqWNZmsCMpsk2sffXG_NWWAfaWQkhVjoB4hR32MXmEumXW0.jpg', 'data': {'title': 'Flushed Away', 'release_year': '2006', 'imdb_score': 'IMDb: 6.6', 'duration': '85 min', 'release_country': 'United States, United Kingdom', 'genre': 'Comedy, Adventure, Animation', 'description_preview': 'After an ignoble landing in Ratropolis, a pampered rodent\xa0that gets flushed down the toilet from his penthouse apartment\xa0enlists the help of a...', 'key': '0', 'quality_tag': 'HD', 'user_rating': '5.000000'}})
	file_name.run()


if __name__ == "__main__":
	main()
