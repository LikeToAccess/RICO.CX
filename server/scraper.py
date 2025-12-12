# -*- coding: utf-8 -*-
# filename          : scraper_tools.py
# description       :
# author            : Rico Alexander
# email             : rico@rico.cx
# date              : 10-24-2023
# version           : v1.0
# usage             : python main.py
# notes             :
# license           : MIT
# py version        : 3.12.0 (must run on 3.10 or higher)
#==============================================================================
import re
import os
import json
from time import sleep
import urllib.parse

# from selenium.common.exceptions import TimeoutException, NoSuchElementException
# from selenium.webdriver.common.by import By

import requests
import feedparser
from selenium.common.exceptions import TimeoutException

from timer import timer
from result import Result
from realdebrid import RealDebrid
# from element_find import find_elements_by_xpath, find_element_by_xpath
from scraper_tools import ScraperTools, TMDbTools, FileBot


tmdb = TMDbTools()
fb = FileBot()
rd = RealDebrid()


# class Goojara(ScraperTools):
# 	"""A scraper for Goojara.to"""

# 	def __init__(self, init: bool = True):
# 		super().__init__(init=init)
# 		self.homepage_url = "https://www.goojara.to/"
# 		self.popular_url = "https://www.goojara.to/watch-trends-popular"
# 		if not init:
# 			return
# 		self.open_link(self.homepage_url)

# 	@staticmethod
# 	def format_title(request: requests.Response, page_url: str) -> dict:
# 		result = find_elements_by_xpath(request.text, "/html/head/title")[0].text
# 		catagories = [
# 			tag.text for tag in find_elements_by_xpath(request.text, "//div[contains(@id, 'wai')]/a")]
# 		if not catagories and result.startswith("Watch ") and result.endswith(" TV Serie"):
# 			catagory = "tv"
# 		else:
# 			match catagories[0]:
# 				case "Movies":
# 					catagory = "movie"
# 				case "Series" | "Serie":
# 					if len(catagories) >= 3:
# 						catagory = "episode"
# 					else:
# 						catagory = "tv"
# 				case _:
# 					catagory = "unknown"
# 		# title = "Watch Saw X (2023)"
# 		tmdb_id = None
# 		video_data = {
# 			"page_url": page_url,
# 			"catagory": catagory,
# 			"quality_tag": "SD"
# 		}

# 		match catagory:
# 			case "movie" | "unknown":
# 				year = result.split(" (")[1].strip(")")
# 				title = result.split(" (")[0].split("Watch ")[1]
# 				tmdb_result = tmdb.search_movie(title)
# 				video_data["year"] = year
# 				if tmdb_result is None:
# 					print(f"Could not find {title} ({year}) on TMDb.")
# 					video_data["readable_title"] = title
# 					title = title +f" ({year})"
# 				else:
# 					tmdb_id = str(tmdb_result["id"])
# 					title = title +f" ({year})"+" {tmdb-"+tmdb_id+"}"
# 					tmdb_details = tmdb.details_movie(int(tmdb_id))
# 					video_data["duration"] = tmdb_details["runtime"] if tmdb_details["runtime"] else "N/A"
# 					video_data["readable_title"] = tmdb_details["title"]
# 					# video_data["poster"] = "https://image.tmdb.org/t/p/w200"+ tmdb_details["poster_path"]
# 				video_data["title"] = f"{title}/{title}"
# 			case "tv":
# 				print(result)
# 				# Watch BEEF (2023) TV Serie
# 				year = result.split(" (")[1].split(")")[0]
# 				title = result.split(" (")[0].split("Watch ")[1]
# 				tmdb_result = tmdb.search_tv_show(title)
# 				if tmdb_result is None:
# 					video_data["readable_title"] = title +" (TV Show)"
# 					video_data["title"] = title+"/"+title
# 					video_data["year"] = year
# 					return video_data
# 				tmdb_id = str(tmdb_result["id"])
# 				title = title +f" ({year})"+" {tmdb-"+tmdb_id+"}"
# 				tmdb_details = tmdb.details_tv(int(tmdb_id))
# 				print(f"DEBUG: {tmdb_details["episode_run_time"]} (tmdb_details['episode_run_time'])")
# 				video_data["duration"] = tmdb_details["episode_run_time"][0] if tmdb_details["episode_run_time"] else "N/A"
# 				video_data["readable_title"] = tmdb_details["name"] +" (TV Show)"
# 				video_data["title"] = f"{title}/{title}"
# 			case "episode":
# 				show_title = catagories[1]  # Rick and Morty S7
# 				episode_title = catagories[2]  # E4: That's Amorte
# 				season_match = re.search(r"( S\d+)", show_title)
# 				episode_match = re.search(r"(E\d+: )", episode_title)
# 				if not season_match:
# 					raise ValueError("Could not find season in show_title.")
# 				if not episode_match:
# 					raise ValueError("Could not find episode in episode_title.")
# 				season = season_match.group(1)
# 				episode = episode_match.group(1)
# 				show_title = show_title.split(season)[0]  # Rick and Morty
# 				episode_title = episode_title.split(episode)[1]  # That's Amorte
# 				season = f"S{season.lstrip("S ").zfill(2)}"  # S07
# 				episode = f"E{episode.strip("E: ").zfill(2)}"  # E04
# 				# title = f"{show_title} {season}{episode}"
# 				tmdb_result = tmdb.search_tv_show(show_title)
# 				if tmdb_result is None:
# 					video_data["readable_title"] = f"{show_title} - {season}{episode} - {episode_title}"
# 					video_data["title"] = f"{show_title}/{show_title} - {season}{episode} - {episode_title}"
# 					return video_data
# 				year = tmdb_result["first_air_date"][:4]
# 				tmdb_id = str(tmdb_result["id"])
# 				title = f"{show_title} ({year})"
# 				video_data["title"] = title+" {tmdb-"+tmdb_id+"}/"+title+f" - {season}{episode} - {episode_title}"
# 				tmdb_details = tmdb.details_tv(int(tmdb_id))
# 				video_data["duration"] = tmdb_details["episode_run_time"][0] if tmdb_details["episode_run_time"] else "N/A"
# 				video_data["readable_title"] = f"{tmdb_details["name"]} - {season}{episode} - {episode_title}"
# 				# print(video_data["duration"])
# 				# print(video_data["poster"])

# 		if tmdb_id:
# 			video_data["poster"] = "https://image.tmdb.org/t/p/w200"+ tmdb_details["poster_path"]
# 			video_data["score"]  = f"{tmdb_details["vote_average"]/10:.0%}"

# 		video_data["year"] = year
# 		# video_data["quality"] = "SD"

# 		return video_data

# 	@staticmethod
# 	def parse_results(results):
# 		results_list = []
# 		for result in results:
# 			title = result.xpath("a/div/strong")[0].text.strip()
# 			year = result.xpath("a/div/text()")[0].strip(" ()")
# 			page_url = result.xpath("a")[0].attrib["href"]
# 			catagory = result.xpath("a/div")[0].attrib["class"].split()[0]
# 			match catagory:
# 				case "im":
# 					catagory = "movie"
# 				case "it":
# 					catagory = "tv"
# 				case _:
# 					catagory = "unknown"
# 			# print(f"DEBUG: {page_url} (page_url)")
# 			# if page_url.startswith("//"):
# 			# 	page_url = "https:"+ page_url
# 			results_list.append(
# 				{
# 					"title": f"{title}",
# 					"year": year,
# 					"page_url": page_url,
# 					"catagory": catagory
# 				}
# 			)

# 		return results_list

# 	def search(self, query: str, timeout: int = 10) -> list[dict]:
# 		"""Searches for a movie or show

# 		Args:
# 			query (str): The movie or show to search for
# 			timeout (int, optional): The timeout for the search. Defaults to 10.

# 		Returns:
# 			list[dict]: A list of dictionaries containing the title, year, and page_url
# 		"""
# 		# print(f"Searching for {query}...")
# 		url = "https://www.goojara.to/xhrr.php"
# 		payload = f"q={query}"
# 		headers = {
# 			"content-type": "application/x-www-form-urlencoded",
# 			"cookie":
# 				"aGooz=nmjv7gtkau2kb6qo9recm7efvv; "
# 				"fba21e48=f011d9dc4e14d5459fedce; "
# 				"_4b46=7A54900AABD3A758E8A448514E7D790F71062FA6"
# 		}
# 		request = requests.request(
# 			"POST",
# 			url,
# 			data=payload,
# 			headers=headers,
# 			timeout=timeout)

# 		results = find_elements_by_xpath(request.text, "//ul[@class='mfeed']/li")
# 		results_list = self.parse_results(results)
# 		for index, result in enumerate(results_list):
# 			if result["catagory"] == "tv":
# 				if not result["year"].isnumeric():
# 					result["catagory"] = "episode"
# 					# print(f"DEBUG: {result['year']} (result['year'])")
# 					print(f"DEBUG: {result} (result)")
# 					result["season"], result["episode"] = result["year"].split(".")
# 					del result["year"]
# 			# result["page_url"] = "https://www.goojara.to"+ result["page_url"]
# 			results_list[index] = result

# 		return results_list

# 	def search_one(self, query: str, timeout: int = 10) -> list[dict]:
# 		"""Returns the first result of the search function

# 		Args:
# 			query (str): The movie or show to search for
# 			timeout (int, optional): The timeout for the search. Defaults to 10.

# 		Returns:
# 			list[dict]: A list of one dictionary containing the title, year, and page_url
# 		"""
# 		results = self.search(query, timeout=timeout)[:1]
# 		return results

# 	@goto_homepage
# 	@timer
# 	def get_video_url(self, page_url: str, timeout: int = 20, retry_count: int = 3) -> str:
# 		"""Gets the video url for a movie or show

# 		Args:
# 			page_url (str): The url of the movie or show
# 			timeout (int, optional): The timeout for the video loading. Defaults to 20.

# 		Returns:
# 			str: The video url

# 		Raises:
# 			TimeoutException: If the video doesn't load within the given timeout and retry_count
# 		"""
# 		self.redirect(page_url)

# 		if retry_count <= 1:
# 			raise TimeoutException("TimeoutException while waiting for iframe in get_video_url.")

# 		try:
# 			video_url = self.wait_until_element_by_xpath(
# 				"//iframe",
# 				timeout=timeout).get_attribute("src")
# 			self.open_link(video_url)
# 		except TimeoutException:
# 			self.reload()
# 			return self.get_video_url(
# 				page_url,
# 				timeout=timeout,
# 				retry_count=retry_count-1)

# 		play_button = self.wait_until_element_by_xpath("//a[@id='prime']")
# 		play_button.click()

# 		while not (video_url := self.wait_until_element_by_xpath(
# 				"//a[contains(text(), 'Download')]").get_attribute("href")):
# 			sleep(1)
# 			if not (retry_count := retry_count - 1):  # Retry count is 0
# 				print("Failed to get video url.")
# 				raise TimeoutException(
# 					"TimeoutException while waiting for video_url in get_video_url.")

# 		# if video_url.startswith("//"):
# 		# 	video_url = "https:"+ video_url

# 		print(f"DEBUG: {video_url} (video_url)")
# 		return video_url

# 	def get_video_data(self, page_url: str, timeout: int = 5) -> dict:
# 		"""Gets the video data for a movie or show

# 		Args:
# 			page_url (str): The url of the movie or show
# 			timeout (int, optional): The timeout for the video loading. Defaults to 5.

# 		Returns:
# 			dict: The video data
# 		"""
# 		# print("Starting...")
# 		print(f"DEBUG: {page_url} (page_url)")
# 		request = requests.get(page_url, timeout=timeout)
# 		video_data = self.format_title(request, page_url)
# 		# print(video_data)
# 		# print(f"Got video data for {video_data['title']}.")

# 		return video_data

# 	def popular(self, timeout: int = 5):
# 		"""Gets the top 80 popular movies and tv episodes

# 		Returns:
# 			list[dict]: A list of dictionaries containing the title, year, and page_url
# 		"""
# 		request = requests.get(self.popular_url, timeout=timeout)
# 		results = find_elements_by_xpath(request.text, "//ul[@class='mfeed']/li")
# 		results_list = self.parse_results(results)

# 		for index, result in enumerate(results_list):
# 			if result["catagory"] == "tv":
# 				result["catagory"] = "episode"
# 				result["season"], result["episode"] = result["year"].split(".")
# 				del result["year"]
# 			result["page_url"] = "https://www.goojara.to"+ result["page_url"]
# 			results_list[index] = result

# 		return results_list

# class GoMovies(ScraperTools):
# 	'''A scraper for GoMovies.sx'''

# 	def __init__(self, init: bool = True):
# 		super().__init__(init=init)
# 		self.homepage_url = "https://gomovies.sx/"
# 		self.popular_url = "https://gomovies.sx/movie"
# 		if not init:
# 			return
# 		self.open_link(self.homepage_url)

# 	@property
# 	def html(self):
# 		return self.find_element_by_xpath("/html").get_attribute("outerHTML")



# class Soaper(ScraperTools):
# 	'''A scraper for Soaper.tv'''

# 	def __init__(self, init: bool = True):
# 		super().__init__(init=init)
# 		self.homepage_url = "https://soaper.tv/"
# 		self.popular_url = "https://soaper.tv/movielist/sort/hot"
# 		if not init:
# 			return
# 		self.open_link(self.homepage_url)

# 	@property
# 	def html(self):
# 		return self.find_element_by_xpath("/html").get_attribute("outerHTML")

# 	@property
# 	def m3u8_link(self):
# 		logs = self.driver.get_log('performance')

# 		# Process the logs and look for the M3U8 URL
# 		m3u8_url = ""
# 		for log in logs:
# 			log_json = json.loads(log['message'])
# 			message = log_json['message']
# 			if message['method'] == 'Network.responseReceived':
# 				url = message['params']['response']['url']
# 				if '.m3u8' in url:
# 					m3u8_url = url
# 					break
# 		return m3u8_url

# 	def get_video_url(self, page_url: str) -> str:
# 		self.redirect(page_url)

# 		# Wait for the video to load
# 		self.wait_until_element_by_xpath("//video")
# 		self.resume_video()
# 		sleep(1)

# 		self.wait_until_element_by_xpath("//video[@src]").get_attribute("src")
# 		self.pause_video()
# 		# sleep(5)
# 		return self.m3u8_link

# 	def get_video_data(self, page_url: str, timeout: int = 5) -> Result:
# 		"""Gets the video data for a movie or show

# 		Args:
# 			page_url (str): The url of the movie or show
# 			timeout (int, optional): The timeout for the video loading. Defaults to 5.

# 		Returns:
# 			Result: The video data
# 		"""
# 		request = requests.get(page_url, timeout=timeout)
# 		info_block = find_elements_by_xpath(request.text, '//div[contains(@class, "col-sm-12 col-md-7 col-lg-7")]')[0]
# 		title = info_block.xpath("div/div/h4")[0].text
# 		# year = info_block.xpath("p[6]")[0].text
# 		year = "1111"
# 		description = info_block.xpath("p[6]")[0].text.strip("\n")
# 		# print(f"DEBUG: Year is {year}")
# 		# rating = info_block.xpath("div[2]/p[3]")[0].text.split(" from ")[0]
# 		image = info_block.xpath("div/div/div/img")[0].attrib["src"]
# 		catagory = page_url.split(self.homepage_url)[1].split("_")[0]
# 		video_data = Result(
# 			scraper_object=self,
# 			title=title,
# 			release_year=year,
# 			description=description,
# 			page_url=page_url,
# 			poster_url=urllib.parse.urljoin(self.homepage_url, image),
# 			catagory=catagory,
# 		)
# 		print(bool(video_data))
# 		print(video_data)
# 		return video_data

# 	@timer
# 	def search(self, query: str, timeout: int = 10) -> list[dict]:
# 		# print(f"Searching for {query}...")
# 		# https://soaper.tv/search.html?keyword=split
# 		# https://soaper.tv/movie_5Wk53Mxg1m.html
# 		url = "https://soaper.tv/search.html?keyword="+ query
# 		request = requests.get(url, timeout=timeout)
# 		results = find_elements_by_xpath(
# 			request.text,
# 			'//div[contains(@class, "col-lg-2 col-md-3 col-sm-4 col-xs-6 no-padding")]')
# 		# Title and Link: /div/div[2]/h5/a
# 		# Year: /div/div[1]/div
# 		# Image: /div/div[1]/a/img
# 		# Catagory: ../../../../../../../div
# 		for index, result in enumerate(results):
# 			title = result.xpath("div/div[2]/h5/a")[0].text
# 			link = result.xpath("div/div[2]/h5/a")[0].attrib["href"]
# 			# year = "0000"
# 			year = result.xpath("div/div[1]/div")[0].text
# 			print(f"DEBUG: Year is {year}")
# 			image = result.xpath("div/div[1]/a/img")[0].attrib["src"]
# 			catagory = result.xpath("../../../../../../../div")[0].text.split("Related ")[1].rstrip("s")
# 			# results[index] = {
# 			# 	"title": title,
# 			# 	"release_year": year,
# 			# 	"page_url": urllib.parse.urljoin(self.homepage_url, link),
# 			# 	"poster_url": urllib.parse.urljoin(self.homepage_url, image),
# 			# 	"catagory": catagory.lower(),
# 			# }
# 			results[index] = Result(
# 			    scraper_object=self,
# 				title=title,
# 				release_year=year,
# 				page_url=urllib.parse.urljoin(self.homepage_url, link),
# 				poster_url=urllib.parse.urljoin(self.homepage_url, image),
# 				catagory=catagory.lower(),
# 			)
# 		return results

# 	def popular(self):
# 		# https://soaper.tv/movielist/sort/hot
# 		request = requests.get(self.popular_url)


# class Null(ScraperTools):

# 	@timer
# 	def search(self, query: str, timeout: int = 10) -> list[dict]:
# 		del query, timeout
# 		return [{"title": "Flushed Away", "year": "2006", "page_url": "http://wikipedia/org/wiki/cheese"}]

# 	def search_one(self, query: str, timeout: int = 10) -> list[dict]:
# 		return self.search(query, timeout=timeout)[:1]

# 	@timer
# 	def get_movie(self, page_url: str, timeout: int = 20) -> str:
# 		del page_url, timeout
# 		return "https://wikipedia/org/wiki/cheese"


# class Scraper(Goojara, Null):
# 	def __init__(self):
# 		super(ScraperTools).__init__(self)

# class X1337(ScraperTools):
# class X1337:

# 	def __init__(self):
# 		self.homepage_url = "https://1337x.to"
# 		self.popular_url = "https://1337x.to/sub/54/0/"
# 		self.search_url = "https://1337x.to/search/"  # searches require a user agent
# 		self.search_url_movies = "https://1337x.to/category-search/{}/Movies/"
# 		self.search_url_tv = "https://1337x.to/category-search/{}}/TV/"
# 		self.headers = {"User-Agent": "Mozilla/5.0"}
# 		# self.search_results = []

# 	def _get_results_from_request(self, request: requests.Response) -> list[Result]:
# 		"""
# 		Convenience function to convert the request into a list of Result objects

# 		Args:
# 			request (requests.Response): The request object

# 		Returns:
# 			list[Result]: A list of Result objects
# 		"""
# 		# print(request.url)
# 		results = find_elements_by_xpath(request.text, '//td/a[contains(@href, "/torrent/")]')
# 		results = Result.remove.codecs(results)
# 		results = Result.remove.bad_characters(results)
# 		results = fb.get_names([{
# 				"filename":result.text,
# 				"filename_old":result.text,
# 				"page_url":self.homepage_url+result.get("href")
# 			} for result in results])
# 		# print(results)
# 		for index, result in enumerate(results):
# 			if result.get("tmdb_id") is None:
# 				continue
# 			result_data = tmdb.details_movie(result["tmdb_id"])
# 			# print(result_data)
# 			if result_data.get("poster_path") is not None:
# 				results[index]["poster_url"] = "https://image.tmdb.org/t/p/w200"+ result_data['poster_path']
# 			if result_data.get("runtime") is not None:
# 				results[index]["duration"] = result_data["runtime"]
# 			if result_data.get("vote_average") is not None:
# 				results[index]["score"] = f"{result_data['vote_average']/10:.0%}"

# 		# result_count = len(results)
# 		# results = Result.filter_codecs(results)
# 		# results_removed = result_count - len(results)
# 		# print(f"\tINFO: {results_removed}x HEVC/H.265 item", end="s " if results_removed != 1 else " ")
# 		# print("filtered from results.")
# 		return [Result(scraper_object=self, **result) for result in results]

# 	@timer
# 	def search(self, query: str, timeout: int = 10, catagory="movie") -> list[Result]:
# 		"""
# 		Searches for a movie or show

# 		Args:
# 			query (str): The movie or show to search for
# 			timeout (int, optional): The timeout for the search. Defaults to 10.

# 		Returns:
# 			list[dict]: A list of dictionaries containing the title, year, and page_url
# 		"""
# 		# print(f"Searching for {query}...")
# 		match catagory:
# 			case "movie":
# 				url = self.search_url_movies.format(urllib.parse.quote_plus(query)) +"1/"  # 1/ is the page number
# 			case "tv":
# 				url = self.search_url_tv.format(urllib.parse.quote_plus(query)) +"1/"  # 1/ is the page number
# 			case _:  # default
# 				url = self.search_url + urllib.parse.quote_plus(query) +"/1/"  # /1/ is the page number
# 		# try:
# 		# 	request = requests.get(url, headers=self.headers, timeout=timeout)
# 		# except requests.exceptions.ConnectionError as e:
# 		# 	print(f"ERROR: Connection error while searching for '{query}' on host '{self.homepage_url}': {e}")
# 		# 	return []
# 		# print(f"DEBUG: {url} (url)")
# 		request = requests.get(url, headers=self.headers, timeout=timeout)
# 		# print(f"DEBUG: {request.text} (request.text)")
# 		results = self._get_results_from_request(request)

# 		return results

# 	@timer
# 	def popular(self, timeout: int = 10) -> list[Result]:
# 		"""
# 		Gets the top 80 popular movies and tv episodes

# 		Args:
# 			timeout (int, optional): The timeout for the search. Defaults to 10.

# 		Returns:
# 			list[dict]: A list of dictionaries containing the title, year, and page_url
# 		"""
# 		request = requests.get(self.popular_url, timeout=timeout)
# 		results = self._get_results_from_request(request)

# 		return results

# 	def get_video_data(self, page_url):
# 		# video_data = Result(
# 		# 	scraper_object=self,
# 		# 	title="Flushed Away",
# 		# 	release_year="2006",
# 		# 	description="Flushed Away!",
# 		# 	page_url=page_url,
# 		# 	poster_url="https://en.wikipedia.org/wiki/Cheese",
# 		# 	catagory="Drama",
# 		# )

# 		# TODO: need to get the Filename from the page_url
# 		request = requests.get(page_url, timeout=10)
# 		# XPATH: //div[contains(@id, "mCSB_1_container")]/h3/a
# 		# title = find_element_by_xpath(
# 		# 	request.text, '//div[contains(@id, "mCSB_1_container")]/h3/a').text
# 		infohash = find_element_by_xpath(
# 			request.text, '//div[contains(@class, "infohash-box")]/p/span').text

# 		torrent_id = rd.add_magnet(infohash)
# 		filename = rd.get_filename(torrent_id)
# 		rd.remove_torrent(torrent_id)

# 		result = fb.get_name(filename)
# 		if not result.get("tmdb_id"):
# 			print(f"WARNING: Could not find {filename} on TMDb.")
# 			print(f"DEBUG: {result} (result)")
# 			return result
# 		print(f"DEBUG: {result["tmdb_id"]} (tmdb_id)")
# 		result_data = tmdb.details_movie(result["tmdb_id"])
# 		if result_data.get("poster_path") is not None:
# 			result["poster_url"] = "https://image.tmdb.org/t/p/w200"+ result_data['poster_path']
# 		if result_data.get("runtime") is not None:
# 			result["duration"] = result_data["runtime"]

# 		video_data = Result(
# 			scraper_object=self,
# 			page_url=page_url,
# 			**result)
# 		print(f"DEBUG: {video_data} (video_data) (type={type(video_data)})")

# 		return video_data

# 	def get_video_url(self, page_url: str, timeout: int = 10):
# 		"""Gets magnet link from page_url"""
# 		request = requests.get(page_url, timeout=timeout)
# 		infohash = find_element_by_xpath(
# 			request.text, '//div[contains(@class, "infohash-box")]/p/span').text
# 		magnet_url = "magnet:?xt=urn:btih:"+ infohash
# 		print(f"DEBUG: {magnet_url}")
# 		return magnet_url


class Milkie:
	# WORKING HTTP REQUEST EXAMPLE from INSOMNIA
	# TODO: current HTTP requests are returning a 401 error when trying to use the API
	# import requests

	# url = "https://milkie.cc/api/v1/torrents"

	# querystring = {"query":"f1 2025","oby":"created_at","odir":"desc","categories":"1","pi":"0","ps":"50"}

	# payload = ""
	# headers = {
	# 	"accept": "application/json, text/plain, */*",
	# 	"accept-language": "en-US,en;q=0.9,es;q=0.8",
	# 	"authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzA3NjI0NzQsImlhdCI6MTc2NTU3ODQ3NCwic3ViIjoiNTg4NTYifQ.QePsnSmLf_PIyGNjXWS2kmv-EZkvSccei7ESTwcRFQw",
	# 	"dnt": "1",
	# 	"priority": "u=1, i",
	# 	"referer": "https://milkie.cc/browse?query=f1%202025&oby=created_at&odir=desc&categories=1&pi=0&ps=50",
	# 	"sec-ch-ua": ""Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"",
	# 	"sec-ch-ua-mobile": "?0",
	# 	"sec-ch-ua-platform": ""macOS"",
	# 	"sec-fetch-dest": "empty",
	# 	"sec-fetch-mode": "cors",
	# 	"sec-fetch-site": "same-origin",
	# 	"user-agent": "Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.2.9) Gecko/20100915 Gentoo Firefox/3.6.9"
	# }

	# response = requests.request("GET", url, data=payload, headers=headers, params=querystring)

	# print(response.text)
	def __init__(self):
		origin = "https://milkie.cc"
		# Updated to use JSON API for consistency with _get_results_from_request
		self.popular_url = origin +"/api/v1/torrents?oby=d&odir=desc&categories=1&pi=0&ps=10" 
		self.search_url = origin +"/api/v1/torrents?oby=d&odir=desc&categories=1&pi=0&ps=10&query="
		self.search_url_rss = origin +"/api/v1/rss?categories=1&key=splUBeBWfU0rUPRKJf&query="
		self.browse_url = origin +"/browse/"
		
		# Headers from the working example
		self.headers = {
			"accept": "application/json, text/plain, */*",
			"accept-language": "en-US,en;q=0.9,es;q=0.8",
			"authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzA3NjI0NzQsImlhdCI6MTc2NTU3ODQ3NCwic3ViIjoiNTg4NTYifQ.QePsnSmLf_PIyGNjXWS2kmv-EZkvSccei7ESTwcRFQw",
			"dnt": "1",
			"priority": "u=1, i",
			"referer": "https://milkie.cc/browse",
			"sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
			"sec-ch-ua-mobile": "?0",
			"sec-ch-ua-platform": '"macOS"',
			"sec-fetch-dest": "empty",
			"sec-fetch-mode": "cors",
			"sec-fetch-site": "same-origin",
			"user-agent": "Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.2.9) Gecko/20100915 Gentoo Firefox/3.6.9"
		}

	def popular(self, timeout: int = 10) -> list[Result]:
		"""
		Gets the top 80 popular movies and tv episodes

		Args:
			timeout (int, optional): The timeout for the search. Defaults to 10.

		Returns:
			list[Result]: A list of Result objects
		"""
		url = self.popular_url
		request = requests.get(url, headers=self.headers, timeout=timeout)
		print(f"DEBUG: {url} (url)")
		results = self._get_results_from_request(request)

		return results

	def search(self, query: str, timeout: int = 10) -> list[Result]:
		url = self.search_url + urllib.parse.quote(query)
		# Update referer for search specifically (optional but good practice based on example)
		headers = self.headers.copy()
		headers["referer"] = f"https://milkie.cc/browse?query={urllib.parse.quote(query)}&oby=created_at&odir=desc&categories=1&pi=0&ps=50"
		
		request = requests.get(url, headers=headers, timeout=timeout)
		print(f"DEBUG: {url} (url)")
		# print(f"DEBUG: {request.text} (request.text)")
		
		results = self._get_results_from_request(request)

		return results

	def _get_results_from_request(self, request: requests.Response) -> list[Result]:
		"""
		Convenience function to convert the request into a list of Result objects

		Args:
			request (requests.Response): The request object

		Returns:
			list[Result]: A list of Result objects
		"""
		try:
			json_results = request.json().get("torrents", [])
			# print(f"DEBUG: {json_results} (json_results)")
		except ValueError as e:
			print(f"ERROR: Could not parse JSON from response: {e}")
			return []

		results = [result["releaseName"] for result in json_results]
		print(results)
		results = Result.remove.codecs(results)
		results = Result.remove.bad_characters(results)
		results = fb.get_names([{
				"filename":result,
				"filename_old":result,
				"page_url":self.browse_url + str(result_data["id"])
			} for result, result_data in zip(results, json_results)])

		for index, result in enumerate(results):
			if result.get("tmdb_id") is None or result.get("tmdb_id") == "":
				continue
			try:
				result_data = tmdb.details_movie(result["tmdb_id"])
				# print(result_data)
				if result_data.get("poster_path") is not None:
					results[index]["poster_url"] = "https://image.tmdb.org/t/p/w200"+ result_data['poster_path']
				if result_data.get("runtime") is not None:
					results[index]["duration"] = result_data["runtime"]
				if result_data.get("vote_average") is not None:
					results[index]["score"] = f"{result_data['vote_average']/10:.0%}"
			except (ValueError, TypeError) as e:
				print(f"WARNING: Could not get TMDb details for '{result.get('title', 'Unknown')}' with ID '{result.get('tmdb_id')}': {e}")
				continue

		return [Result(scraper_object=self, **result) for result in results]

	def _get_results_from_request_rss(self, request: requests.Response) -> list[Result]:
		"""
		Convenience function to convert the request into a list of Result objects

		Args:
			request (requests.Response): The request object

		Returns:
			list[Result]: A list of Result objects
		"""
		rss_results = feedparser.parse(request.text).entries
		results = [result.title for result in rss_results]
		print(results)
		results = Result.remove.codecs(results)
		results = Result.remove.bad_characters(results)
		results = fb.get_names([{
				"filename":result,
				"filename_old":result,
				"page_url":rss_result.link
			} for result, rss_result in zip(results, rss_results)])

		for index, result in enumerate(results):
			if result.get("tmdb_id") is None or result.get("tmdb_id") == "":
				continue
			try:
				result_data = tmdb.details_movie(result["tmdb_id"])
				# print(result_data)
				if result_data.get("poster_path") is not None:
					results[index]["poster_url"] = "https://image.tmdb.org/t/p/w200"+ result_data['poster_path']
				if result_data.get("runtime") is not None:
					results[index]["duration"] = result_data["runtime"]
				if result_data.get("vote_average") is not None:
					results[index]["score"] = f"{result_data['vote_average']/10:.0%}"
			except (ValueError, TypeError) as e:
				print(f"WARNING: Could not get TMDb details for '{result.get('title', 'Unknown')}' with ID '{result.get('tmdb_id')}': {e}")
				continue

		return [Result(scraper_object=self, **result) for result in results]

	def _get_magnet_from_page_url(self, page_url: str) -> str:
		"""
		Extracts the magnet link from the Milkie API using the ID from the page_url.
		page_url example: https://milkie.cc/browse/HtXkpXyJlX7H
		"""
		try:
			# Extract ID from URL
			torrent_id_milkie = page_url.split("/")[-1]
			api_url = f"https://milkie.cc/api/v1/torrents/{torrent_id_milkie}"
			
			# Use existing headers
			request = requests.get(api_url, headers=self.headers, timeout=10)
			request.raise_for_status()
			
			data = request.json()
			infohash = data.get("torrent", {}).get("infoHash")
			
			if not infohash:
				raise ValueError(f"No infoHash found for {page_url}")
				
			return f"magnet:?xt=urn:btih:{infohash}"
		except Exception as e:
			print(f"ERROR: Failed to get magnet from {page_url}: {e}")
			raise e

	def get_video_data(self, page_url: str) -> Result:
		# Get magnet link first
		magnet_link = self._get_magnet_from_page_url(page_url)
		# Add magnet instead of torrent URL
		torrent_id = rd.add_magnet(magnet_link.split("btih:")[-1])
		
		try:
			filename = rd.get_torrent_info(torrent_id)["filename"]
		finally:
			# Ensure we clean up even if getting info fails
			rd.remove_torrent(torrent_id)

		file_info_dict = {"filename": filename, "page_url": page_url}
		result = fb.get_name(file_info_dict)

		if not result.get("tmdb_id") or result.get("tmdb_id") == "":
			print(f"WARNING: Could not find {filename} on TMDb.")
			print(f"DEBUG: {result} (result)")
			return Result(scraper_object=self, **result) # Pass **result directly

		print(f"DEBUG: {result['tmdb_id']} (tmdb_id)")
		try:
			result_data = tmdb.details_movie(result["tmdb_id"])
			if result_data.get("poster_path"):
				result["poster_url"] = "https://image.tmdb.org/t/p/w200" + result_data['poster_path']
			if result_data.get("runtime"):
				result["duration"] = result_data["runtime"]
		except (ValueError, TypeError) as e:
			print(f"WARNING: Could not get TMDb details for '{result.get('title', 'Unknown')}' with ID '{result.get('tmdb_id')}': {e}")

		# --- THIS IS THE FIX ---
		# Removed the redundant 'page_url=page_url' argument
		video_data = Result(
			scraper_object=self,
			**result)
			
		print(f"DEBUG: {video_data} (video_data) (type={type(video_data)})")

		return video_data

	def get_video_url(self, page_url: str) -> str:
		magnet_link = self._get_magnet_from_page_url(page_url)
		# We already have the magnet link, no need to add/remove torrent just to get it back
		# But we might need to verify it works or follows the pattern? 
		# The original code added/removed to get infohash, but we typically already have infohash here.
		
		# Original logic:
		# torrent_id = rd.add_torrent(page_url)["id"]
		# infohash = rd.get_torrent_info(torrent_id)["hash"]
		# rd.remove_torrent(torrent_id)
		# magnet_url = f"magnet:?xt=urn:btih:{infohash}"
		
		print(f"DEBUG: {magnet_link} (magnet_url)")
		return magnet_link


def main():
	print("Starting scraper...")
	scraper = Milkie()
	results = scraper.search("lego movie")
	print(f"Found {len(results)} results:")
	for result in results:
		print(result)
	# scraper.close()
	print("Scraper closed.")


if __name__ == "__main__":
	main()
