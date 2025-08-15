import json

from lxml.html import HtmlElement


class Result(dict):
	'''A class to hold the results of a search'''

	def __init__(self,
				 scraper_object,
				 title,
				 page_url,
				 filename=None,
				 release_year=None,
				 description=None,
				 poster_url="/img/missing_poster.svg",
				 duration=0,
				 catagory="unknown",
				 **kwargs):
		self.scraper_object = scraper_object
		self.title = title
		self.page_url = page_url
		self.filename = title if filename is None else filename
		self.release_year = release_year
		self.description = description
		self.poster_url = poster_url
		self.catagory = catagory
		self.duration = duration
		self._video_url = None
		for key, value in kwargs.items():
			setattr(self, key, value)
		super().__init__(self.__dict__)

	class remove:
		def __init__(self, results: list):
			self.results = results
			self.results = self.codecs(self.results)
			self.results = self.bad_characters(self.results)

		@staticmethod
		def codecs(results: list) -> list:
			"""
			Filters out results with unwanted video codecs in the title.

			Args:
				results (list[Result]): The list of results

			Returns:
				list[Result]: The filtered list of results
			"""
			unwanted_codecs = ["x265", "h.265", "h265", "hevc", "av1"]  # Add more codecs as needed
			unwanted_other = ["hindi"]

			filtered_results = []
			for result in results:
				match result:
					case HtmlElement():
						title = result.text_content().lower()
					case dict() | Result():
						title = result.get("filename_old", str()).lower()
					case str() | _:
						title = result.lower()
				# print(f"DEBUG: {title} (title)")
				if not any(codec in title for codec in unwanted_codecs+unwanted_other):
					filtered_results.append(result)

			# Print number of results filtered:
			number_removed = len(results) - len(filtered_results)
			print(f"\tINFO: {number_removed} HEVC/H.265/AV1 item", end="s " if number_removed != 1 else " ")
			print("filtered from results.")
			return filtered_results

		@staticmethod
		def bad_characters(titles: str | list) -> list:
			"""Removes bad characters from a title"""
			if not isinstance(titles, list):
				titles = [titles]
			for title in titles:
				bad_characters = ["/", "\\", "\"", ":"]
				for char in bad_characters:
					title = title.replace(char, "").encode("ascii", "ignore").decode("ascii").strip()

			return titles

	def __str__(self):
		dict_copy = self.__dict__.copy()
		dict_copy.pop("scraper_object")
		for key, value in self.__dict__.items():
			if value is None:
				dict_copy.pop(key)
			elif key.startswith("_"):
				dict_copy.pop(key)
				dict_copy[key.lstrip("_")] = value
		return json.dumps(dict_copy, indent=4)

	@property
	def video_url(self):
		if not self._video_url:
			self._video_url = self.scraper_object.get_video_url(self.page_url)
		return self._video_url

	@video_url.setter
	def video_url(self, value):
		self._video_url = value

	def sanatize(self):
		"""Safely removes the scraper object from the result"""
		try:
			del self.scraper_object
		except AttributeError:
			pass

		# Update the underlying dictionary since it's a dict subclass
		self.pop("scraper_object", None)
		return self.__dict__

	def __bool__(self):
		return bool(self.page_url)


def main():
	pass


if __name__ == "__main__":
	main()
