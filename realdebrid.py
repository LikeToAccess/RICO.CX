import os
import requests

from settings import REAL_DEBRID_API_KEY  # Import API key from the settings file


class RealDebrid:
	"""
	A class for interacting with the Real-Debrid API.
	"""

	def __init__(self, api_key: str = REAL_DEBRID_API_KEY, timeout: int = 10) -> None:
		"""
		Initializes a new RealDebrid instance.

		Args:
			api_key: Your Real-Debrid API key.
		"""
		self.api_key = api_key
		self.base_url = "https://api.real-debrid.com/rest/1.0"
		self.timeout = timeout
		self.torrent_id: str | None = None

	def _make_request(self, method: str, endpoint: str, data: dict | None = None) -> dict:
		"""
		Makes an HTTP request to the Real-Debrid API.

		Args:
			method: The HTTP method (e.g., 'GET', 'POST').
			endpoint: The API endpoint path.
			data: Optional data to send with the request.

		Returns:
			The JSON response as a dictionary.

		Raises:
			requests.exceptions.RequestException: If the request fails.
		"""
		headers = {"Authorization": f"Bearer {self.api_key}"}
		url = f"{self.base_url}/{endpoint}"
		response = requests.request(method, url, headers=headers, data=data, timeout=self.timeout)
		print(response.status_code)
		if response.status_code == 403:
			raise Exception("Real-Debrid API key is invalid.")
		if response.status_code == 503:
			raise Exception("Error, likely infringing torrent.")
		response.raise_for_status()
		return response.json() if response.text else {}

	@staticmethod
	def get_video_files(files: list[dict]) -> list[dict]:
		"""
		Selects MKV and MP4 files from a list of files.

		Args:
			files: A list of file dictionaries.

		Returns:
			A list of selected file dictionaries.
		"""
		video_extensions = (".mkv", ".mp4", ".avi")
		selected_files = []
		for file in files:
			if file["path"].lower().endswith(video_extensions):
				selected_files.append(file)

		return selected_files

	@staticmethod
	def largest_video_size(files: list[dict]):
		largest_file_size = 0
		for file in files:
			largest_file_size = max(largest_file_size, file["bytes"])

		return largest_file_size

	def _unrestrict_link(self, link: str) -> dict:
		"""
		Unrestricts a link, handling both hoster links and Real-Debrid torrent links.

		Args:
			link: The link to unrestrict. Can be a supported hoster link or a 
				  Real-Debrid torrent link.

		Returns:
			A dictionary containing information about the unrestricted link.
		"""
		# if link.startswith("https://real-debrid.com/torrents/"):
		# 	# Handle Real-Debrid torrent links
		# 	torrent_id = link.split("/")[-1]
		# 	response = self._make_request("POST", f"torrents/unrestrictLink/{torrent_id}")
		# else:
		# 	Handle supported hoster links
		data = {"link": link}
		response = self._make_request("POST", "unrestrict/link", data=data)

		return response

	def select_files(self, files: list, infohash: str):
		if self.torrent_id is None:
			self.torrent_id = self.add_magnet(infohash)
			print(f"DEBUG: running add_magnet with torrent_id: {self.torrent_id}")

		torrent_info = self.get_torrent_info(self.torrent_id)
		for remote_file in torrent_info["files"]:
			for index, file in enumerate(files):
				# print(f"DEBUG: {remote_file['path']} == {file["path"]}")
				if remote_file["path"] == file["path"]:
					files[index]["selected"] = 1
		# print(",".join([str(file["id"]) for file in files if file.get("selected") == 1]))
		self._make_request("POST",
			f"torrents/selectFiles/{self.torrent_id}",
			data={"files": ",".join([str(file["id"]) for file in files if file.get("selected") == 1])})

	def add_magnet(self, infohash: str) -> str:
		"""
		Adds a magnet link to Real-Debrid.

		Args:
			infohash: The magnet link to add.

		Returns:
			The ID of the added torrent.
		"""
		# print(f"DEBUG: running add_magnet with infohash: {infohash}")
		data = {"magnet": "magnet:?xt=urn:btih:"+ infohash}
		response = self._make_request("POST", "torrents/addMagnet", data=data)
		self.torrent_id = response["id"]
		return response["id"]

	def remove_torrent(self, torrent_id: str) -> None:
		"""
		Deletes a torrent from Real-Debrid.

		Args:
			torrent_id: The ID of the torrent to delete.
		"""
		# print(f"DEBUG: running delete_torrent with torrent_id: {torrent_id}")
		self._make_request("DELETE", f"torrents/delete/{torrent_id}")

	def remove_infohash(self, infohash: str) -> str | None:
		"""
		Deletes a torrent from Real-Debrid using the infohash.

		Args:
			infohash: The infohash of the torrent to delete.
		"""
		# print(f"DEBUG: running delete_infohash with infohash: {infohash}")
		self.torrent_id = self.get_torrent_id(infohash)
		if self.torrent_id is None: return None
		self.remove_torrent(self.torrent_id)
		return self.torrent_id

	def get_torrent_id(self, infohash: str) -> str | None:
		"""
		Gets the ID of a torrent from Real-Debrid using the infohash.

		Args:
			infohash: The infohash of the torrent.

		Returns:
			The ID of the torrent.
		"""
		# print(f"DEBUG: running get_torrent_id with infohash: {infohash}")
		torrents = self.get_torrents()
		torrent = next((torrent for torrent in torrents if torrent["hash"] == infohash), None)
		return torrent["id"] if torrent else None

	def get_torrent(self, infohash: str) -> dict | None:
		"""
		Gets a torrent from Real-Debrid using the infohash.

		Args:
			infohash: The infohash of the torrent.

		Returns:
			A dictionary containing information about the torrent.
		"""
		# print(f"DEBUG: running get_torrent with infohash: {infohash}")
		self.torrent_id = self.get_torrent_id(infohash)
		return self.get_torrent_info(self.torrent_id) if self.torrent_id else None

	def get_torrents(self) -> list[dict]:
		"""
		Retrieves a list of all torrents.

		Returns:
			A list of dictionaries containing information about each torrent.
		"""
		# print(f"DEBUG: running get_torrents")
		request = self._make_request("GET", "torrents")
		print(request)
		return [request]

	def get_torrent_info(self, torrent_id: str) -> dict:
		"""
		Retrieves information about a torrent.

		Args:
			torrent_id: The ID of the torrent.

		Returns:
			A dictionary containing the torrent information.
		"""
		# print(f"DEBUG: running get_torrent_info with torrent_id: {torrent_id}")
		return self._make_request("GET", f"torrents/info/{torrent_id}")

	def get_video_file_size(self, infohash: str) -> int:
		"""
		Gets the size of the largest MKV or MP4 file from a magnet link.

		Args:
			infohash: The infohash.

		Returns:
			The size of the largest MKV or MP4 file in bytes.

		"""
		# print(f"DEBUG: running get_video_file_size with infohash: {infohash}")
		if self.torrent_id is None:
			self.torrent_id = self.add_magnet(infohash)
			print(f"DEBUG: running add_magnet with torrent_id: {self.torrent_id}")
		torrent_id = self.torrent_id
		torrent_info = self.get_torrent_info(torrent_id)
		largest_file_size = self.largest_video_size(self.get_video_files(torrent_info["files"]))

		return largest_file_size

	def get_filenames(self, infohash: str) -> list[str]:
		"""
		Gets the filenames of all MKV and MP4 files from a magnet link.

		Args:
			infohash: The infohash.

		Returns:
			A list of filenames of all MKV and MP4 files, including extensions.
		"""
		# print(f"DEBUG: running get_filenames with infohash: {infohash}")
		if self.torrent_id is None:
			self.torrent_id = self.add_magnet(infohash)
			print(f"DEBUG: running add_magnet with torrent_id: {self.torrent_id}")
		torrent_id = self.torrent_id
		torrent_info = self.get_torrent_info(torrent_id)
		video_files = self.get_video_files(torrent_info["files"])

		return [os.path.basename(file["path"]) for file in video_files]

	def get_filename(self, infohash: str) -> str:
		"""
		Gets the filename of the largest MKV or MP4 file from a magnet link.

		Args:
			infohash: The infohash.

		Returns:
			The filename of the largest MKV or MP4 file, including extension.
		"""
		# print(f"DEBUG: running get_filename with infohash: {infohash}")
		if self.torrent_id is None:
			self.torrent_id = self.add_magnet(infohash)
			print(f"DEBUG: running add_magnet with torrent_id: {self.torrent_id}")
		torrent_id = self.torrent_id
		torrent_info = self.get_torrent_info(torrent_id)
		video_files = self.get_video_files(torrent_info["files"])

		largest_file = max(video_files, key=lambda x: x["bytes"])
		return os.path.basename(largest_file["path"])

	def get_unrestricted_video_link(self, infohash):
		# print(f"DEBUG: running get_unrestricted_video_link with infohash: {infohash}")
		if self.torrent_id is None:
			self.torrent_id = self.add_magnet(infohash)
			print(f"DEBUG: running add_magnet in get_unrestricted_video_link with torrent_id: {self.torrent_id}")

		files = self.get_video_files(self.get_torrent_info(self.torrent_id)["files"])
		self.select_files(files, infohash)
		torrent_info = self.get_torrent_info(self.torrent_id)
		unrestricted_links = []
		for link in torrent_info["links"]:
			unrestricted_links.append(self._unrestrict_link(link)["download"])

		# print(f"DEBUG: {unrestricted_links}")
		return unrestricted_links


def main():
	# Example usage
	rd = RealDebrid(REAL_DEBRID_API_KEY)  # Use the imported API key
	infohash = "1956E238E5D115A29DB662A8BC5D407757C7717B"

	# try:
	# 	total_size = rd.get_video_file_size(infohash)
	# 	print(f"Total size of video file: {total_size} bytes")
	# except requests.exceptions.RequestException as e:
	# 	print(f"Error: {e}")

	# Test the add_magnet and select files methods
	print(rd.get_unrestricted_video_link(infohash))
	print(rd.get_filename(infohash))



if __name__ == "__main__":
	main()
