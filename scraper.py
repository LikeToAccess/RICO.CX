# -*- coding: utf-8 -*-
# filename          : scraper.py
# description       : Respond to GET requests from websites with MP4 links
# author            : Ian Ault
# email             : liketoaccess@protonmail.com
# date              : 04-25-2022
# version           : v1.0
# usage             : python main.py
# notes             :
# license           : MIT
# py version        : 3.10.2 (must run on 3.6 or higher)
#==============================================================================
import os
import time
import platform
import jmespath
from selenium import webdriver
from selenium.common.exceptions import *
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from file import *
from settings import *
from find_captcha import Find_Captcha


OS = platform.system()
page_extension = "-online-for-free.html"


class Scraper(Find_Captcha):
	def __init__(self):
		init_timestamp = time.time()
		options = Options()
		user_data_dir = os.path.abspath("selenium_data")
		options.add_argument("autoplay-policy=no-user-gesture-required")
		options.add_argument("log-level=3")
		options.add_argument(f"user-data-dir={user_data_dir}")
		options.add_argument("--ignore-certificate-errors-spki-list")
		if HEADLESS:
			options.add_argument("--headless")
			options.add_argument("window-size=1920,1080")
			# options.add_argument("--disable-gpu")
			options.add_argument("--mute-audio")
		self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
		super().__init__(self.driver)
		print(f"Completed init in {round(time.time()-init_timestamp,2)}s.")

	def open_link(self, url):
		self.driver.get(url)

	def current_url(self):
		return self.driver.current_url

	def close(self):
		self.driver.close()

	def refresh(self):
		self.driver.refresh()

	def find_video_source(self):
		pass
		#//*[@id="_skqeqEJBSrS"]/div[2]/video

	def current_page_is_404(self):
		try:
			if self.find_element_by_xpath("//*[@id='_sKnoHaKJFse']/div[1]/h1/p[1]").text == "404":
				return True
		except NoSuchElementException:
			pass

		try:
			if self.find_element_by_xpath('//*[@id="oppsBlock"]/span') \
			.get_attribute("innerHTML").strip() == "Oh!":
				return True
		except NoSuchElementException:
			pass

		return False

	def resume_video(self):
		self.driver.execute_script(
			"for(v of document.querySelectorAll('video')){v.setAttribute('muted','');v.play()}"
		)

	def pause_video(self):
		self.driver.execute_script(
			"videos = document.querySelectorAll('video'); for(video of videos) {video.pause()}"
		)

	def get_first_page_link_from_search(self, search_results):
		print(search_results)
		return search_results[0]["url"] if not isinstance(search_results, int) else search_results

	def find_subtitles_source(self):
		sequence = "/html/body/main/div/div/section/div[5]/div/script[2]"
		element = self.wait_until_element_by_xpath(sequence)
		# print(element.get_attribute("innerHTML").rsplit("window.subtitles = ", 1)[1])
		subtitle_data = json.loads(
			element.get_attribute("innerHTML").rsplit("window.subtitles = ", 1)[1]
		)
		keys = ["src", "srclang"]
		values = [jmespath.search(f"[*].{key}", subtitle_data) for key in keys]
		values = list(zip(values[1],values[0]))

		subtitles = []
		for value in values:
			if value[0] == "en":
				subtitles.append({"lang":value[0], "src":value[1]})

		return subtitles

	def find_data_from_url(self, url):
		print("Adding media via direct link...")
		# movie = bool(
		# 	self.find_element_by_xpath(
		# 		"/html/body/main/div/div/section/section/ul/li[2]/div/a"
		# 	).text == "MOVIES"
		# )
		movie = "/watch-film/" in url and "/watch-tv-show/" not in url

		if movie: url += "-online-for-free.html" if not url.endswith("-online-for-free.html") else ""
		if self.current_url() != url: self.open_link(url)

		base_element = self.find_element_by_xpath("//*[@class='_sxfctqTgvOf _sYsfmtEcNNg']")
		title = base_element.find_element(By.XPATH, value="div[2]/div[1]/div[1]/h1").text
		poster_url = base_element.find_element(By.XPATH, value="div[1]/div[1]/img")

		data = {
			"title": base_element.find_element(
				By.XPATH, value="div[2]/div[1]/div[1]/h1"
			),
			"release_year": base_element.find_element(
				By.XPATH, value="div[2]/div[2]/div[2]/div/div[1]/span[2]/a"
			),
			"imdb_score": base_element.find_element(
				By.XPATH, value="div[2]/div[2]/div[2]/div/div[2]/span[2]/span"
			),
			"duration": base_element.find_element(
				By.XPATH, value="div[2]/div[2]/div[2]/div/div[4]/span[2]"
			),
			"release_country": base_element.find_element(
				By.XPATH, value="div[2]/div[2]/div[1]/div[4]/span/a"
			),
			"genre": base_element.find_element(
				By.XPATH, value="div[2]/div[2]/div[1]/div[2]/span"
			),
			"description_preview": base_element.find_element(
			By.XPATH, value="div[2]/div[1]/div[2]/span[2]"
			),  # Limit is 151 characters
			"quality_tag": base_element.find_element(
				By.XPATH, value="div[2]/div[2]/div[2]/div/div[3]/span[2]"
			),
			"user_rating": base_element.find_element(
				By.XPATH, value="div[2]/div[1]/div[1]/div[1]/fieldset"
			),
			"key": "0",
		}

		data["title"] = data["title"].text
		data["release_year"] = data["release_year"].text
		data["imdb_score"] = data["imdb_score"].text
		data["duration"] = data["duration"].text
		data["release_country"] = data["release_country"].text
		data["user_rating"] = data["user_rating"].get_attribute("data-rating")
		data["description_preview"] = data["description_preview"].text
		data["genre"] = data["genre"].text.replace("Genre:", "").strip()
		data["quality_tag"] = data["quality_tag"].get_attribute("class").split()[1]

		if data["quality_tag"] == "_swRnbEfUMBJ":
			data["quality_tag"] = "HD"
		elif data["quality_tag"] == "_sNhWjzrWjwZ":
			data["quality_tag"] = "SD"
		elif data["quality_tag"] == "_sfqZXxzgiEC":
			data["quality_tag"] = "CAM"
		if title != data["title"]:
			print("\tWARNING: Titles do not match!")
			print(f"\t\tGot:      '{data['title']}'")
			print(f"\t\tExpected: '{title}'")
		if poster_url.get_attribute("src").endswith("dist/image/default_poster.jpg"):
			poster_url = poster_url.get_attribute("data-src")
		else:
			poster_url = poster_url.get_attribute("src")
		data["description_preview"] = data["description_preview"] \
			.strip(". ")       \
			.rsplit(" ", 1)[0] \
			.strip(".") +"..." \

		data = {
			"title":      title,
			"poster_url": poster_url,
			"url":        url,
			"data":       data,
		}

		return [data]

	def searchone(self, query):
		return self.search(query, top_result_only=True)

	def search(self, search_term, top_result_only=False):
		# https://gomovies-online.cam/watch-tv-show/mr-robot-season-4/cYqlqU9U/t5f85jpg/h2586jt3-online-for-free.html
		if search_term.startswith("https://"):
			url = search_term
			if not url.endswith("-online-for-free.html"):
				if "/watch-film/" in url and "/watch-tv-show/" not in url:
					url += page_extension
				else:
					print("WARNING: 'search_term' should be a direct link to video page!")
					print(f"\tGot: '{search_term}'")
					return 404

			self.open_link(url)
			# self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
			return self.find_data_from_url(url)

		print("Waiting for search results...")
		search_timestamp = time.time()
		self.open_link(f"https://gomovies-online.cam/search/{search_term}")

		if self.current_page_is_404():
			print("\tERROR: Page error 404!")
			return 404

		try:
			results = self.find_elements_by_xpath("//*[@class='item_hd']") + \
					  self.find_elements_by_xpath("//*[@class='item_sd']") + \
					  self.find_elements_by_xpath("//*[@class='item_cam']") + \
					  self.find_elements_by_xpath("//*[@class='item_series']") \
					  if top_result_only < 1 else [
					  	  self.find_element_by_xpaths(
					  	  	  "//*[@class='item_hd']",
					  	  	  "//*[@class='item_sd']",
					  	  	  "//*[@class='item_cam']",
					  	  	  "//*[@class='item_series']",
					  	  )
					  ]
		except NoSuchElementException:
			return 404

		results_data = []
		for result in results:
			if not result: return 404
			# Title
			title = result.text
			# Poster
			poster_url = result.find_element(by=By.XPATH, value="div/div/img")
			# URL
			url = result.get_attribute("href")
			# Other Data
			_data_element = result.find_element(by=By.XPATH, value="..")

			search_data = {
				"title":               _data_element.get_attribute("data-filmname"),
				"release_year":        _data_element.get_attribute("data-year"),
				"imdb_score":          _data_element.get_attribute("data-imdb"),
				"duration":            _data_element.get_attribute("data-duration"),
				"release_country":     _data_element.get_attribute("data-country"),
				"genre":               _data_element.get_attribute("data-genre"),
				"description_preview": _data_element.get_attribute("data-descript"),  # Limit is 151 characters
				"key":                 _data_element.get_attribute("data-key"),
				"quality_tag":         _data_element.get_attribute("data-quality"),
				"user_rating":         _data_element.get_attribute("data-rating"),
			}

			search_data["description_preview"], search_data["quality_tag"] = (
				search_data["description_preview"].strip(". ").rsplit(" ", 1)[0].strip(".") + "...",
				search_data["quality_tag"].replace("itemAbsolute_", "").upper()
			)

			if title != search_data["title"]:
				print("\tWARNING: Titles do not match!")
				print(f"\t\tGot:      '{search_data['title']}'")
				print(f"\t\tExpected: '{title}'")

			if poster_url.get_attribute("src").endswith("dist/image/default_poster.jpg"):
				# print("DEBUG")
				poster_url = poster_url.get_attribute("data-src")
			else:
				poster_url = poster_url.get_attribute("src")
				# print(poster_url)

			results_data.append(
				{
					"title":      title,
					"poster_url": poster_url,
					"url":        url,
					"data":       search_data,
				}
			)

		print(f"Completed search in {round(time.time()-search_timestamp,2)}s,", end=" ")
		print(f"found {len(results_data)} {'result' if len(results_data) == 1 else 'results'}.")

		return results_data

	def convert_data_from_page_link(self, current_page_url, timeout=60):
		print(f"\tWaiting for video to load... (up to {timeout} seconds)")
		current_page_url += page_extension if not current_page_url.endswith(page_extension) else ""
		self.open_link(current_page_url)
		print("\tChecking for captchas...")
		if self.get_captcha_image() == 225:
			return 225  # Made up status 225 to be the "Captcha" response code (BAD)
		print("\tNo captchas.")
		# self.resolve_captcha()

		original_video_url = self.wait_until_element(
			By.TAG_NAME, "video", timeout=timeout
		).get_attribute("src")
		print("\tVideo loaded.")

		print("\tSleeping...")
		time.sleep(0.5)
		# TODO: Instead of sleeping, this time could be used to get meta data about the movie

		try:
			print(f"\tWaiting for video resolution list... (up to {timeout} seconds)")
			best_quality = self.wait_until_element_by_xpath(
				"//*[@class='changeClassLabel jw-reset jw-settings-content-item']",
				timeout
			).get_attribute("innerHTML").split("p (")[0]
			print("\tVideo resolution list found.")
		except TimeoutException:
			# TODO: Fallback to old way of verifying resolutions if the above way fails.
			print("\tWARNING: Could not find a resoltion higher than 360p!")
			best_quality = "360"

		self.pause_video()
		print("\tVideo paused.")

		return original_video_url, best_quality

	def get_video(self, url, timeout=30):
		if self.current_url() != url:
			self.open_link(url)

		data = self.convert_data_from_page_link(self.current_url(), timeout=timeout)

		if isinstance(data, int):
			return data
		return self.convert_link(data[0], data[1])[0]


	def convert_link(self, video_url, best_quality):
		print("\tWaiting for subtitles...")
		subtitles = self.find_subtitles_source()
		if subtitles:
			print(f"\tFound {len(subtitles)} English {'subtitle' if len(subtitles) == 1 else 'subtitles'}.")
		else:
			print("\tNo English subtitles available.")

		modified_video_url = video_url \
			.replace("/360?name=", f"/{best_quality}?name=") \
			.replace("_360&token=ip=", f"_{best_quality}&token=ip=")

		print(f"\tVideo link converted to {best_quality}p.")

		return [modified_video_url]

	def get_video_url_from_page_link(self, page_link, timeout=30):
		if page_link == 404: return page_link
		print("Waiting for page to load...")
		get_video_url_timestamp = time.time()
		self.open_link(page_link)
		current_page_url = self.current_url()

		if self.current_page_is_404():
			print("\tERROR: Page error 404!")
			return [], 404, [], page_link

		if self.find_element_by_xpath(
			"/html/body/main/div/div/section/section/ul/li[2]/div/a"
		).text == "MOVIES":
			print("\tMedia is detected as 'MOVIE'.")
			data = self.convert_data_from_page_link(current_page_url, timeout=timeout)
			if isinstance(data, int):
				return [], data, [], page_link
			video_url, best_quality = data
		else:
			if current_page_url.endswith("-online-for-free.html"):
				print("\tMedia is detected as 'TV SHOW: EPISODE'.")
				data = self.convert_data_from_page_link(current_page_url, timeout=timeout)
				if data == 225:
					return [], 225, [current_page_url], page_link
				if isinstance(data, int):
					return [], data, [], page_link
				video_url, best_quality = data
			else:
				print("\tMedia is detected as 'TV SHOW: SEASON'.")
				print("\tWaiting for season page to load...")
				self.open_link(current_page_url)
				# TODO: Make seasons work
				urls = self.find_elements_by_xpath("//*[@class=\"_sXFMWEIryHd \"]")
				episode_urls = []
				season_urls = []
				for url in urls:
					url = url.get_attribute("href")
					if url.endswith("-online-for-free.html"):
						episode_urls.append(url)
					else:
						season_urls.append(url)

				results = []
				remaining_episode_urls = episode_urls[:]  # Make a copy of episode_urls not point to episode_urls
				for episode_url in episode_urls:
					result, http_status_code, *_, page_link = self.get_video_url_from_page_link(episode_url)
					if http_status_code == 225:
						print("\tPausing for captcha solve...")
						return results, 225, remaining_episode_urls, page_link
					remaining_episode_urls.remove(episode_url)
					results += result
					# data = self.convert_data_from_page_link(episode_url, timeout=timeout)
					# if isinstance(data, int):
					# 	return [], data
					# video_url, best_quality = data
					# print(data)
				print(
					f"\tCompleted all scraping for season in {round(time.time()-get_video_url_timestamp,2)}s."
				)
				return results, 200, episode_urls, page_link

				# DEBUG
				# print(
				# 	"Episode URLs:\n\t"+ "\n\t".join(episode_urls) +"\nSeason URLs:\n\t"+"\n\t".join(season_urls)
				# )

		results = self.convert_link(video_url, best_quality)  # TODO: Need to pass through page_link!
		print(f"\tCompleted scraping in {round(time.time()-get_video_url_timestamp,2)}s.")
		return results, 200, [video_url], page_link

	def run(self):
		while True:
			url = self.get_video_url_from_page_link(
				self.get_first_page_link_from_search(
					self.search(
						input("\nEnter movie title:\n> "),
						top_result_only=True
					)
				)
			)

			if url == 404:
				print("ERROR: Page error 404!")
				continue

			print(url[0])
			# print(url)

		wait_for_input()


def wait_for_input():
	print()
	if OS == "Windows":  # Only works on Windows
		os.system("pause")
	else:                # Works for MacOS and Linux
		print("Press any key to continue...", end="", flush=True)
		os.system("read -n1 -r")

def main():
	scraper = Scraper()
	# scraper.run()
	print(scraper.find_data_from_url("https://gomovies-online.cam/watch-tv-show/rick-and-morty-season-6/dFl1ohVT/6SfvSx4p-online-for-free.html"))
	# scraper.close()


if __name__ == "__main__":
	main()
