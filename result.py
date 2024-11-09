import json


class Result(dict):
	'''A class to hold the results of a search'''

	def __init__(self,
				 scraper_object,
				 title,
				 page_url,
				 release_year=None,
				 description=None,
				 poster_url=None,
				 catagory="unknown"):
		self.scraper_object = scraper_object
		self.title = title
		self.page_url = page_url
		self.release_year = release_year
		self.description = description
		self.poster_url = poster_url
		self.catagory = catagory
		self._video_url = None
		super().__init__(self.__dict__)

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

	def __bool__(self):
		return bool(self.page_url)


def main():
	pass


if __name__ == "__main__":
	main()
