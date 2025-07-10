import os
import requests
import bencodepy
import hashlib

# It's good practice to handle the case where the settings file or key might be missing.
try:
	from settings import REAL_DEBRID_API_KEY
except ImportError:
	REAL_DEBRID_API_KEY = None # Or prompt the user, or read from environment variable

class RealDebridAPIError(Exception):
	"""Custom exception for general Real-Debrid API errors."""
	pass

class RealDebridInfringingError(Exception):
	"""Custom exception for infringing content or service unavailability errors."""
	pass

class RealDebrid:
	"""
	A class for interacting with the Real-Debrid API.
	"""

	def __init__(self, api_key: str = REAL_DEBRID_API_KEY, timeout: int = 10) -> None:
		"""
		Initializes a new RealDebrid instance.

		Args:
			api_key: Your Real-Debrid API key.
			timeout: The request timeout in seconds.
		"""
		if not api_key:
			raise ValueError("Real-Debrid API key is required.")
		self.api_key = api_key
		self.base_url = "https://api.real-debrid.com/rest/1.0"
		self.timeout = timeout
		self.torrent_id: str | None = None

	def _make_request(self, method: str, endpoint: str, data: dict | bytes | None = None, params: dict | None = None) -> dict:
		"""
		Makes an HTTP request to the Real-Debrid API.

		Args:
			method: The HTTP method (e.g., 'GET', 'POST', 'PUT', 'DELETE').
			endpoint: The API endpoint path.
			data: Optional data to send with the request body (dict for form data, bytes for raw file data).
			params: Optional URL parameters for GET requests.

		Returns:
			The JSON response as a dictionary.

		Raises:
			RealDebridAPIError: For API-specific errors.
			RealDebridInfringingError: For infringing torrent errors.
			requests.exceptions.RequestException: If a network request fails.
		"""
		headers = {"Authorization": f"Bearer {self.api_key}"}
		url = f"{self.base_url}/{endpoint}"

		# If data is bytes, it's a file upload. Set the appropriate Content-Type.
		if isinstance(data, bytes):
			headers['Content-Type'] = 'application/x-bittorrent'

		response = requests.request(method, url, headers=headers, params=params, data=data, timeout=self.timeout)

		# Handle successful responses that don't have a body (e.g., HTTP 204 No Content)
		if response.status_code == 204:
			return {}

		# Attempt to parse the JSON response, but don't fail if it's empty or not JSON
		try:
			json_response = response.json()
		except ValueError:
			json_response = {}

		# If the request was successful (2xx status code), return the JSON
		if response.ok:
			return json_response

		# Handle error responses
		error_message = json_response.get("error", "Unknown API error")
		error_code = json_response.get("error_code")

		# Specific error for infringing content or service unavailable
		if error_code == 35 or response.status_code == 503:
			raise RealDebridInfringingError(f"Error code {error_code}: {error_message} (HTTP {response.status_code})")
		else:
			raise RealDebridAPIError(f"Error code {error_code}: {error_message} (HTTP {response.status_code})")

	def add_torrent(self, torrent_source: str, host: str | None = None) -> dict:
		"""
		Adds a torrent to Real-Debrid from a local file path or a URL.
		This corresponds to the 'PUT /torrents/addTorrent' endpoint.

		Args:
			torrent_source: The local path to the .torrent file or a direct URL to it.
			host: Optional hoster domain to use (from /torrents/availableHosts).

		Returns:
			A dictionary containing the new torrent's ID and URI.
		"""
		params = {}
		if host:
			params['host'] = host

		print(f"Adding torrent from source: {torrent_source} with host: {host}")

		torrent_content: bytes
		# Check if the source is a URL or a local file path
		if torrent_source.startswith('http://') or torrent_source.startswith('https://'):
			try:
				response = requests.get(torrent_source, timeout=self.timeout)
				response.raise_for_status()
				torrent_content = response.content
			except requests.exceptions.RequestException as e:
				raise RealDebridAPIError(f"Failed to download torrent from URL: {e}")
		else:
			try:
				with open(torrent_source, 'rb') as f:
					torrent_content = f.read()
			except FileNotFoundError:
				raise RealDebridAPIError(f"Torrent file not found at: {torrent_source}")
			except Exception as e:
				 raise RealDebridAPIError(f"Failed to read torrent file: {e}")

		# The API documentation specifies using PUT to upload the file content.
		return self._make_request("PUT", "torrents/addTorrent", data=torrent_content, params=params)

	@staticmethod
	def get_video_files(files: list[dict]) -> list[dict]:
		"""
		Selects MKV, MP4, and AVI files from a list of files.

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

	# @staticmethod
	# def torrent_to_magnet(torrent_url: str) -> str:
	#     """
	#     Downloads .torrent file content from a URL and converts it to a magnet link.

	#     Args:
	#         torrent_url: The direct URL to the .torrent file.

	#     Returns:
	#         A string containing the magnet link or an error message.
	#     """
	#     try:
	#         response = requests.get(torrent_url, timeout=10)
	#         response.raise_for_status()
	#         torrent_content = response.content
	#         metadata = bencodepy.decode(torrent_content)
	#         info_dictionary = metadata[b'info']
	#         info_bencoded = bencodepy.encode(info_dictionary)
	#         info_hash = hashlib.sha1(info_bencoded).hexdigest()
	#         magnet_link = f"magnet:?xt=urn:btih:{info_hash}"
	#         return magnet_link
	#     except requests.exceptions.RequestException as e:
	#         raise RealDebridAPIError(f"Error fetching URL: {e}")
	#     except Exception as e:
	#         raise RealDebridAPIError(f"Error converting torrent to magnet: {e}")


	@staticmethod
	def largest_video_size(files: list[dict]):
		if not files:
			return 0
		largest_file_size = 0
		for file in files:
			largest_file_size = max(largest_file_size, file["bytes"])
		return largest_file_size

	def _unrestrict_link(self, link: str) -> dict:
		"""
		Unrestricts a hoster link.

		Args:
			link: The link to unrestrict.

		Returns:
			A dictionary containing information about the unrestricted link.
		"""
		data = {"link": link}
		return self._make_request("POST", "unrestrict/link", data=data)

	def select_files(self, files: list, torrent_id: str):
		"""
		Selects files within a torrent to be downloaded.

		Args:
			files: A list of file dictionaries to select.
			torrent_id: The ID of the torrent.
		"""
		file_ids_to_select = [str(f['id']) for f in files]
		if not file_ids_to_select:
			print("No files to select.")
			return

		self._make_request(
			"POST",
			f"torrents/selectFiles/{torrent_id}",
			data={"files": ",".join(file_ids_to_select)}
		)
		print(f"Selected {len(file_ids_to_select)} files for torrent {torrent_id}")


	def add_magnet(self, infohash: str) -> str:
		"""
		Adds a magnet link to Real-Debrid.

		Args:
			infohash: The magnet link to add.

		Returns:
			The ID of the added torrent.
		"""
		data = {"magnet": f"magnet:?xt=urn:btih:{infohash}"}
		response = self._make_request("POST", "torrents/addMagnet", data=data)
		self.torrent_id = response["id"]
		return response["id"]

	def remove_torrent(self, torrent_id: str) -> None:
		"""
		Deletes a torrent from Real-Debrid.

		Args:
			torrent_id: The ID of the torrent to delete.
		"""
		self._make_request("DELETE", f"torrents/delete/{torrent_id}")
		print(f"Successfully deleted torrent {torrent_id}")

	def remove_infohash(self, infohash: str) -> str | None:
		"""
		Deletes a torrent from Real-Debrid using the infohash.

		Args:
			infohash: The infohash of the torrent to delete.
		"""
		torrent_id = self.get_torrent_id(infohash)
		if torrent_id:
			self.remove_torrent(torrent_id)
			return torrent_id
		return None

	def get_torrent_id(self, infohash: str) -> str | None:
		"""
		Gets the ID of a torrent from Real-Debrid using the infohash.

		Args:
			infohash: The infohash of the torrent.

		Returns:
			The ID of the torrent, or None if not found.
		"""
		torrents = self.get_torrents()
		infohash_lower = infohash.lower()
		for torrent in torrents:
			if torrent["hash"].lower() == infohash_lower:
				return torrent["id"]
		return None

	def get_torrent(self, infohash: str) -> dict | None:
		"""
		Gets a torrent from Real-Debrid using the infohash.

		Args:
			infohash: The infohash of the torrent.

		Returns:
			A dictionary containing information about the torrent.
		"""
		torrent_id = self.get_torrent_id(infohash)
		return self.get_torrent_info(torrent_id) if torrent_id else None

	def get_torrents(self) -> list[dict]:
		"""
		Retrieves a list of all torrents on the user's account.

		Returns:
			A list of dictionaries, where each dictionary is a torrent.
		"""
		# The API returns a list directly, no need to wrap it in another list.
		return self._make_request("GET", "torrents")

	def get_torrent_info(self, torrent_id: str) -> dict:
		"""
		Retrieves information about a specific torrent.

		Args:
			torrent_id: The ID of the torrent.

		Returns:
			A dictionary containing the torrent information.
		"""
		return self._make_request("GET", f"torrents/info/{torrent_id}")

	def get_video_file_size(self, infohash: str) -> int:
		"""
		Gets the size of the largest MKV or MP4 file from a magnet link.

		Args:
			infohash: The infohash.

		Returns:
			The size of the largest MKV or MP4 file in bytes.
		"""
		torrent_info = self.get_torrent(infohash)
		if not torrent_info:
			# If torrent doesn't exist, add it
			torrent_id = self.add_magnet(infohash)
			torrent_info = self.get_torrent_info(torrent_id)

		largest_file_size = self.largest_video_size(self.get_video_files(torrent_info["files"]))
		return largest_file_size

	def get_filenames(self, infohash: str) -> list[str]:
		"""
		Gets the filenames of all video files from a magnet link.

		Args:
			infohash: The infohash.

		Returns:
			A list of filenames of all MKV, MP4, and AVI files.
		"""
		torrent_info = self.get_torrent(infohash)
		if not torrent_info:
			torrent_id = self.add_magnet(infohash)
			torrent_info = self.get_torrent_info(torrent_id)

		video_files = self.get_video_files(torrent_info["files"])
		return [os.path.basename(file["path"]) for file in video_files]

	def get_filename(self, infohash: str) -> str:
		"""
		Gets the filename of the largest video file from a magnet link.

		Args:
			infohash: The infohash.

		Returns:
			The filename of the largest video file.
		"""
		torrent_info = self.get_torrent(infohash)
		if not torrent_info:
			torrent_id = self.add_magnet(infohash)
			torrent_info = self.get_torrent_info(torrent_id)
		# print("DEBUG HERE")

		video_files = self.get_video_files(torrent_info["files"])
		if not video_files:
			return "No video files found."

		largest_file = max(video_files, key=lambda x: x["bytes"])
		return os.path.basename(largest_file["path"])

	def get_unrestricted_video_link(self, infohash: str) -> list[str]:
		"""
		The main workflow method: adds a magnet, selects video files,
		and returns the unrestricted download links.

		Args:
			infohash: The infohash of the torrent.

		Returns:
			A list of unrestricted download links for the video files.
		"""
		torrent_info = self.get_torrent(infohash)
		if not torrent_info:
			torrent_id = self.add_magnet(infohash)
			torrent_info = self.get_torrent_info(torrent_id)
		else:
			torrent_id = torrent_info['id']

		# Select all video files for download
		video_files = self.get_video_files(torrent_info["files"])
		self.select_files(video_files, torrent_id)

		# Retrieve the torrent info again to get the download links
		final_torrent_info = self.get_torrent_info(torrent_id)

		# Wait until the torrent is downloaded
		while final_torrent_info['status'] != 'downloaded':
			print(f"Current torrent status: {final_torrent_info['status']} ({final_torrent_info['progress']}%)")
			import time
			time.sleep(5)
			final_torrent_info = self.get_torrent_info(torrent_id)
			
		unrestricted_links = []
		for link in final_torrent_info["links"]:
			unrestricted_links.append(self._unrestrict_link(link)["download"])

		return unrestricted_links


def main():
	# Example usage
	if not REAL_DEBRID_API_KEY:
		print("Error: REAL_DEBRID_API_KEY not found in settings.py")
		return

	rd = RealDebrid(REAL_DEBRID_API_KEY)
	
	# --- Example for add_torrent with a local file ---
	# Create a dummy torrent file for testing since we can't provide a real one.
	# In a real scenario, you would have an actual .torrent file.
	dummy_file_path = "my_test_torrent.torrent"
	try:
		with open(dummy_file_path, "w") as f:
			f.write("this is not a real torrent file")
		
		print(f"--- Testing add_torrent with local file: {dummy_file_path} ---")
		# This will fail with a 'Torrent file invalid' error from the API, which is expected.
		try:
			response = rd.add_torrent(dummy_file_path)
			print("Successfully added torrent from file:", response)
		except RealDebridAPIError as e:
			print(f"Caught expected error for invalid torrent file: {e}")
		finally:
			os.remove(dummy_file_path) # Clean up the dummy file
			
	except Exception as e:
		print(f"An error occurred during the local file test: {e}")


	# --- Example for add_magnet and getting links ---
	infohash = "1956E238E5D115A29DB662A8BC5D407757C7717B" # Example infohash
	print(f"\n--- Testing full workflow with infohash: {infohash} ---")
	try:
		# Get unrestricted links
		links = rd.get_unrestricted_video_link(infohash)
		print("Unrestricted links:", links)

		# Get the main filename
		filename = rd.get_filename(infohash)
		print("Main filename:", filename)

	except (RealDebridAPIError, RealDebridInfringingError, requests.exceptions.RequestException) as e:
		print(f"An error occurred: {e}")
	finally:
		# Clean up by deleting the torrent from Real-Debrid
		print(f"Cleaning up torrent with infohash {infohash}...")
		rd.remove_infohash(infohash)


if __name__ == "__main__":
	main()
