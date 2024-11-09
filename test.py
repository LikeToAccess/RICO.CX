import requests
import os


class File(str):
	def __new__(cls, file_path, *args, **kwargs):
		"""
		Creates a new FileTypeChecker instance and sets its string value to the file path.

		Args:
			file_path: The path to the file.
			*args, **kwargs: Additional arguments passed to the str constructor.
		"""
		obj = str.__new__(cls, file_path, *args, **kwargs)
		obj.file_path = file_path
		return obj

	@property
	def file_type(self):
		"""
		Determines the file type based on its header (magic bytes).

		Returns:
			The file type as a string (e.g., 'MP4', 'M3U8', 'Unknown')
		"""
		try:
			with open(self.file_path, 'rb') as f:
				header = f.read(11)  # Adjust the number of bytes read if needed for other formats

				if header[:4] == b'\x00\x00\x00\x18' and header[4:8] == b'ftyp':
					return 'mp4'
				if header.startswith(b'#EXTM3U'):
					return 'm3u8'
				if header[:4] == b'\x1a\x45\xdf\xa3':  # Matroska (MKV) magic bytes
					return 'mkv'
				return 'unkown'

		except FileNotFoundError:
			return '404'

	@property
	def file_size(self):
		"""
		Gets the size of the file in bytes.

		Returns:
			The file size in bytes or -1 if the file is not found.
		"""
		try:
			return os.path.getsize(self.file_path)
		except FileNotFoundError:
			return -1


def download_m3u8_video(m3u8_url, output_filename):
	"""
	Downloads a video from an m3u8 URL and saves it to the specified filename.

	Args:
		m3u8_url: The URL of the m3u8 file.
		output_filename: The filename to save the downloaded video as.
	"""
	m3u8_url = File(m3u8_url)

	# Check if local file or URL
	if m3u8_url.file_type == 'm3u8':
		with open(m3u8_url, 'r') as file:
			m3u8_content = file.read()
	else:
		# Fetch the m3u8 content
		response = requests.get(m3u8_url, timeout=10)
		response.raise_for_status()  # Raise an exception for bad status codes

		m3u8_content = response.text

	# Extract the video URLs from the m3u8 content
	video_urls = [line.strip() for line in m3u8_content.splitlines() if not (line.startswith("#") or not line)]
	video_urls = ["https://soaper.tv" if url.startswith("/") else ""+ url for url in video_urls]
	print(f"DEBUG: {video_urls} (video_urls)")

	# Choose the desired video quality (you might need to modify this based on your preferences)
	selected_video_url = video_urls[-1]  # Select the last URL (assuming it's the highest quality)
	print(f"DEBUG: {selected_video_url} (selected_video_url)")

	# Download the video segments and combine them
	with open(output_filename, "wb") as f:
		for segment_url in video_urls:
			segment_response = requests.get(segment_url, timeout=10)
			segment_response.raise_for_status()
			f.write(segment_response.content)

	output_filename = File(output_filename)
	print(f"DEBUG: {output_filename.file_type} (output_filename.file_type)")

	# Rename file to include the file type
	os.rename(output_filename, f"{output_filename}.{output_filename.file_type.lower()}")
	output_filename = File(f"{output_filename}.{output_filename.file_type.lower()}")

	print(f"Video downloaded successfully and saved as {output_filename}")
	print(f"File type: {output_filename.file_type}")
	print(f"File size: {output_filename.file_size / 1024**2:.2} MB")


def main():
	# Replace with your actual m3u8 URL
	# m3u8_url = "https://soaper.tv/dev/Apis/tw_m3u8?key=5Z3XOEaxNNHOwWR33BnZiZOeK9qvQzfjBWzwpVnWiBZd1N4YvPhAmndOLdyNFNRa2EqoE6hjBxKvJY5MtP987172XpHnE0xnjbxYHbWvr95oVEuElN9epNv4sZ94.m3u8"
	m3u8_url = "Desktop/MOVIES/Oppenheimer.m3u8"

	# Replace with your desired output filename
	output_filename = "downloaded_video"

	download_m3u8_video(m3u8_url, output_filename)


if __name__ == "__main__":
	main()
