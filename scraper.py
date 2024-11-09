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
import json
from time import sleep
import urllib.parse

# from selenium.common.exceptions import TimeoutException, NoSuchElementException
# from selenium.webdriver.common.by import By

import requests
from selenium.common.exceptions import TimeoutException

from timer import timer
from result import Result
from element_find import find_elements_by_xpath
from scraper_tools import ScraperTools, TMDbTools, goto_homepage


tmdb = TMDbTools()


class Goojara(ScraperTools):
	"""A scraper for Goojara.to"""

	def __init__(self, init: bool = True):
		super().__init__(init=init)
		self.homepage_url = "https://www.goojara.to/"
		self.popular_url = "https://www.goojara.to/watch-trends-popular"
		if not init:
			return
		self.open_link(self.homepage_url)

	@staticmethod
	def format_title(request: requests.Response, page_url: str) -> dict:
		result = find_elements_by_xpath(request.text, "/html/head/title")[0].text
		catagories = [
			tag.text for tag in find_elements_by_xpath(request.text, "//div[contains(@id, 'wai')]/a")]
		if not catagories and result.startswith("Watch ") and result.endswith(" TV Serie"):
			catagory = "tv"
		else:
			match catagories[0]:
				case "Movies":
					catagory = "movie"
				case "Series" | "Serie":
					if len(catagories) >= 3:
						catagory = "episode"
					else:
						catagory = "tv"
				case _:
					catagory = "unknown"
		# title = "Watch Saw X (2023)"
		tmdb_id = None
		video_data = {
			"page_url": page_url,
			"catagory": catagory,
			"quality_tag": "SD"
		}

		match catagory:
			case "movie" | "unknown":
				year = result.split(" (")[1].strip(")")
				title = result.split(" (")[0].split("Watch ")[1]
				tmdb_result = tmdb.search_movie(title)
				video_data["year"] = year
				if tmdb_result is None:
					print(f"Could not find {title} ({year}) on TMDb.")
					video_data["readable_title"] = title
					title = title +f" ({year})"
				else:
					tmdb_id = str(tmdb_result["id"])
					title = title +f" ({year})"+" {tmdb-"+tmdb_id+"}"
					tmdb_details = tmdb.details_movie(int(tmdb_id))
					video_data["duration"] = tmdb_details["runtime"] if tmdb_details["runtime"] else "N/A"
					video_data["readable_title"] = tmdb_details["title"]
					# video_data["poster"] = "https://image.tmdb.org/t/p/w200"+ tmdb_details["poster_path"]
				video_data["title"] = f"{title}/{title}"
			case "tv":
				print(result)
				# Watch BEEF (2023) TV Serie
				year = result.split(" (")[1].split(")")[0]
				title = result.split(" (")[0].split("Watch ")[1]
				tmdb_result = tmdb.search_tv_show(title)
				if tmdb_result is None:
					video_data["readable_title"] = title +" (TV Show)"
					video_data["title"] = title+"/"+title
					video_data["year"] = year
					return video_data
				tmdb_id = str(tmdb_result["id"])
				title = title +f" ({year})"+" {tmdb-"+tmdb_id+"}"
				tmdb_details = tmdb.details_tv(int(tmdb_id))
				print(f"DEBUG: {tmdb_details["episode_run_time"]} (tmdb_details['episode_run_time'])")
				video_data["duration"] = tmdb_details["episode_run_time"][0] if tmdb_details["episode_run_time"] else "N/A"
				video_data["readable_title"] = tmdb_details["name"] +" (TV Show)"
				video_data["title"] = f"{title}/{title}"
			case "episode":
				show_title = catagories[1]  # Rick and Morty S7
				episode_title = catagories[2]  # E4: That's Amorte
				season_match = re.search(r"( S\d+)", show_title)
				episode_match = re.search(r"(E\d+: )", episode_title)
				if not season_match:
					raise ValueError("Could not find season in show_title.")
				if not episode_match:
					raise ValueError("Could not find episode in episode_title.")
				season = season_match.group(1)
				episode = episode_match.group(1)
				show_title = show_title.split(season)[0]  # Rick and Morty
				episode_title = episode_title.split(episode)[1]  # That's Amorte
				season = f"S{season.lstrip("S ").zfill(2)}"  # S07
				episode = f"E{episode.strip("E: ").zfill(2)}"  # E04
				# title = f"{show_title} {season}{episode}"
				tmdb_result = tmdb.search_tv_show(show_title)
				if tmdb_result is None:
					video_data["readable_title"] = f"{show_title} - {season}{episode} - {episode_title}"
					video_data["title"] = f"{show_title}/{show_title} - {season}{episode} - {episode_title}"
					return video_data
				year = tmdb_result["first_air_date"][:4]
				tmdb_id = str(tmdb_result["id"])
				title = f"{show_title} ({year})"
				video_data["title"] = title+" {tmdb-"+tmdb_id+"}/"+title+f" - {season}{episode} - {episode_title}"
				tmdb_details = tmdb.details_tv(int(tmdb_id))
				video_data["duration"] = tmdb_details["episode_run_time"][0] if tmdb_details["episode_run_time"] else "N/A"
				video_data["readable_title"] = f"{tmdb_details["name"]} - {season}{episode} - {episode_title}"
				# print(video_data["duration"])
				# print(video_data["poster"])

		if tmdb_id:
			video_data["poster"] = "https://image.tmdb.org/t/p/w200"+ tmdb_details["poster_path"]
			video_data["score"]  = f"{tmdb_details["vote_average"]/10:.0%}"

		video_data["year"] = year
		# video_data["quality"] = "SD"

		return video_data

	@staticmethod
	def parse_results(results):
		results_list = []
		for result in results:
			title = result.xpath("a/div/strong")[0].text.strip()
			year = result.xpath("a/div/text()")[0].strip(" ()")
			page_url = result.xpath("a")[0].attrib["href"]
			catagory = result.xpath("a/div")[0].attrib["class"].split()[0]
			match catagory:
				case "im":
					catagory = "movie"
				case "it":
					catagory = "tv"
				case _:
					catagory = "unknown"
			# print(f"DEBUG: {page_url} (page_url)")
			# if page_url.startswith("//"):
			# 	page_url = "https:"+ page_url
			results_list.append(
				{
					"title": f"{title}",
					"year": year,
					"page_url": page_url,
					"catagory": catagory
				}
			)

		return results_list

	def search(self, query: str, timeout: int = 10) -> list[dict]:
		"""Searches for a movie or show

		Args:
			query (str): The movie or show to search for
			timeout (int, optional): The timeout for the search. Defaults to 10.

		Returns:
			list[dict]: A list of dictionaries containing the title, year, and page_url
		"""
		# print(f"Searching for {query}...")
		url = "https://www.goojara.to/xhrr.php"
		payload = f"q={query}"
		headers = {
			"content-type": "application/x-www-form-urlencoded",
			"cookie":
				"aGooz=nmjv7gtkau2kb6qo9recm7efvv; "
				"fba21e48=f011d9dc4e14d5459fedce; "
				"_4b46=7A54900AABD3A758E8A448514E7D790F71062FA6"
		}
		request = requests.request(
			"POST",
			url,
			data=payload,
			headers=headers,
			timeout=timeout)

		results = find_elements_by_xpath(request.text, "//ul[@class='mfeed']/li")
		results_list = self.parse_results(results)
		for index, result in enumerate(results_list):
			if result["catagory"] == "tv":
				if not result["year"].isnumeric():
					result["catagory"] = "episode"
					# print(f"DEBUG: {result['year']} (result['year'])")
					print(f"DEBUG: {result} (result)")
					result["season"], result["episode"] = result["year"].split(".")
					del result["year"]
			# result["page_url"] = "https://www.goojara.to"+ result["page_url"]
			results_list[index] = result

		return results_list

	def search_one(self, query: str, timeout: int = 10) -> list[dict]:
		"""Returns the first result of the search function

		Args:
			query (str): The movie or show to search for
			timeout (int, optional): The timeout for the search. Defaults to 10.

		Returns:
			list[dict]: A list of one dictionary containing the title, year, and page_url
		"""
		results = self.search(query, timeout=timeout)[:1]
		return results

	@goto_homepage
	@timer
	def get_video_url(self, page_url: str, timeout: int = 20, retry_count: int = 3) -> str:
		"""Gets the video url for a movie or show

		Args:
			page_url (str): The url of the movie or show
			timeout (int, optional): The timeout for the video loading. Defaults to 20.

		Returns:
			str: The video url

		Raises:
			TimeoutException: If the video doesn't load within the given timeout and retry_count
		"""
		self.redirect(page_url)

		if retry_count <= 1:
			raise TimeoutException("TimeoutException while waiting for iframe in get_video_url.")

		try:
			video_url = self.wait_until_element_by_xpath(
				"//iframe",
				timeout=timeout).get_attribute("src")
			self.open_link(video_url)
		except TimeoutException:
			self.reload()
			return self.get_video_url(
				page_url,
				timeout=timeout,
				retry_count=retry_count-1)

		play_button = self.wait_until_element_by_xpath("//a[@id='prime']")
		play_button.click()

		while not (video_url := self.wait_until_element_by_xpath(
				"//a[contains(text(), 'Download')]").get_attribute("href")):
			sleep(1)
			if not (retry_count := retry_count - 1):  # Retry count is 0
				print("Failed to get video url.")
				raise TimeoutException(
					"TimeoutException while waiting for video_url in get_video_url.")

		# if video_url.startswith("//"):
		# 	video_url = "https:"+ video_url

		print(f"DEBUG: {video_url} (video_url)")
		return video_url

	def get_video_data(self, page_url: str, timeout: int = 5) -> dict:
		"""Gets the video data for a movie or show

		Args:
			page_url (str): The url of the movie or show
			timeout (int, optional): The timeout for the video loading. Defaults to 5.

		Returns:
			dict: The video data
		"""
		# print("Starting...")
		print(f"DEBUG: {page_url} (page_url)")
		request = requests.get(page_url, timeout=timeout)
		video_data = self.format_title(request, page_url)
		# print(video_data)
		# print(f"Got video data for {video_data['title']}.")

		return video_data

	def popular(self, timeout: int = 5):
		"""Gets the top 80 popular movies and tv episodes

		Returns:
			list[dict]: A list of dictionaries containing the title, year, and page_url
		"""
		request = requests.get(self.popular_url, timeout=timeout)
		results = find_elements_by_xpath(request.text, "//ul[@class='mfeed']/li")
		results_list = self.parse_results(results)

		for index, result in enumerate(results_list):
			if result["catagory"] == "tv":
				result["catagory"] = "episode"
				result["season"], result["episode"] = result["year"].split(".")
				del result["year"]
			result["page_url"] = "https://www.goojara.to"+ result["page_url"]
			results_list[index] = result

		return results_list

class GoMovies(ScraperTools):
	'''A scraper for GoMovies.sx'''

	def __init__(self, init: bool = True):
		super().__init__(init=init)
		self.homepage_url = "https://gomovies.sx/"
		self.popular_url = "https://gomovies.sx/movie"
		if not init:
			return
		self.open_link(self.homepage_url)

	@property
	def html(self):
		return self.find_element_by_xpath("/html").get_attribute("outerHTML")



class Soaper(ScraperTools):
	'''A scraper for Soaper.tv'''

	def __init__(self, init: bool = True):
		super().__init__(init=init)
		self.homepage_url = "https://soaper.tv/"
		self.popular_url = "https://soaper.tv/movielist/sort/hot"
		if not init:
			return
		self.open_link(self.homepage_url)

	@property
	def html(self):
		return self.find_element_by_xpath("/html").get_attribute("outerHTML")

	@property
	def m3u8_link(self):
		logs = self.driver.get_log('performance')

		# Process the logs and look for the M3U8 URL
		m3u8_url = ""
		for log in logs:
			log_json = json.loads(log['message'])
			message = log_json['message']
			if message['method'] == 'Network.responseReceived':
				url = message['params']['response']['url']
				if '.m3u8' in url:
					m3u8_url = url
					break
		return m3u8_url

	def get_video_url(self, page_url: str) -> str:
		self.redirect(page_url)

		# Wait for the video to load
		self.wait_until_element_by_xpath("//video")
		self.resume_video()
		sleep(1)

		self.wait_until_element_by_xpath("//video[@src]").get_attribute("src")
		self.pause_video()
		# sleep(5)
		return self.m3u8_link

	def get_video_data(self, page_url: str, timeout: int = 5) -> Result:
		"""Gets the video data for a movie or show

		Args:
			page_url (str): The url of the movie or show
			timeout (int, optional): The timeout for the video loading. Defaults to 5.

		Returns:
			Result: The video data
		"""
		request = requests.get(page_url, timeout=timeout)
		info_block = find_elements_by_xpath(request.text, '//div[contains(@class, "col-sm-12 col-md-7 col-lg-7")]')[0]
		title = info_block.xpath("div/div/h4")[0].text
		# year = info_block.xpath("p[6]")[0].text
		year = "1111"
		description = info_block.xpath("p[6]")[0].text.strip("\n")
		# print(f"DEBUG: Year is {year}")
		# rating = info_block.xpath("div[2]/p[3]")[0].text.split(" from ")[0]
		image = info_block.xpath("div/div/div/img")[0].attrib["src"]
		catagory = page_url.split(self.homepage_url)[1].split("_")[0]
		video_data = Result(
			scraper_object=self,
			title=title,
			release_year=year,
			description=description,
			page_url=page_url,
			poster_url=urllib.parse.urljoin(self.homepage_url, image),
			catagory=catagory,
		)
		print(bool(video_data))
		print(video_data)
		return video_data

	@timer
	def search(self, query: str, timeout: int = 10) -> list[dict]:
		# print(f"Searching for {query}...")
		# https://soaper.tv/search.html?keyword=split
		# https://soaper.tv/movie_5Wk53Mxg1m.html
		url = "https://soaper.tv/search.html?keyword="+ query
		request = requests.get(url, timeout=timeout)
		results = find_elements_by_xpath(
			request.text,
			'//div[contains(@class, "col-lg-2 col-md-3 col-sm-4 col-xs-6 no-padding")]')
		# Title and Link: /div/div[2]/h5/a
		# Year: /div/div[1]/div
		# Image: /div/div[1]/a/img
		# Catagory: ../../../../../../../div
		for index, result in enumerate(results):
			title = result.xpath("div/div[2]/h5/a")[0].text
			link = result.xpath("div/div[2]/h5/a")[0].attrib["href"]
			# year = "0000"
			year = result.xpath("div/div[1]/div")[0].text
			print(f"DEBUG: Year is {year}")
			image = result.xpath("div/div[1]/a/img")[0].attrib["src"]
			catagory = result.xpath("../../../../../../../div")[0].text.split("Related ")[1].rstrip("s")
			# results[index] = {
			# 	"title": title,
			# 	"release_year": year,
			# 	"page_url": urllib.parse.urljoin(self.homepage_url, link),
			# 	"poster_url": urllib.parse.urljoin(self.homepage_url, image),
			# 	"catagory": catagory.lower(),
			# }
			results[index] = Result(
			    scraper_object=self,
				title=title,
				release_year=year,
				page_url=urllib.parse.urljoin(self.homepage_url, link),
				poster_url=urllib.parse.urljoin(self.homepage_url, image),
				catagory=catagory.lower(),
			)
		return results

	def popular(self):
		# https://soaper.tv/movielist/sort/hot
		request = requests.get(self.popular_url)


class Null(ScraperTools):

	@timer
	def search(self, query: str, timeout: int = 10) -> list[dict]:
		del query, timeout
		return [{"title": "Flushed Away", "year": "2006", "page_url": "http://wikipedia/org/wiki/cheese"}]

	def search_one(self, query: str, timeout: int = 10) -> list[dict]:
		return self.search(query, timeout=timeout)[:1]

	@timer
	def get_movie(self, page_url: str, timeout: int = 20) -> str:
		del page_url, timeout
		return "https://wikipedia/org/wiki/cheese"


# class Scraper(Goojara, Null):
# 	def __init__(self):
# 		super(ScraperTools).__init__(self)

class X1337(ScraperTools):

	@timer
	def search(self, query: str, timeout: int = 10) -> list[dict]:
		request = requests.get("https://1337x.to/sub/54/0/")
		results = find_elements_by_xpath(request.text, '//td/a[contains(@href, "/torrent/")]')
		return results


def main():
	print("Starting scraper...")
	scraper = Soaper()
	# scraper.open_link("https://soaper.tv/movie_3d8kdr0gY9.html")
	# print(scraper.html)
	# print(scraper.get_video_url("https://soaper.tv/movie_5Wk53Mxg1m.html"))
	results = scraper.search("independence day")
	# print(json.dumps(results, indent=2))
	# print(len(results))
	# scraper.get_video_url(results[0]["page_url"])
	print(results[0])
	print(results[0].video_url)
	print(results[0])
	scraper.close()
	print("Scraper closed.")


if __name__ == "__main__":
	main()
