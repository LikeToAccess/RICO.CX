# -*- coding: utf-8 -*-
# filename          : download_engine.py
# description       : A script to download files from the internet.
# author            : Ian Ault
# email             : liketoaccess@protonmail.com
# date              : 12-02-2022
# version           : v2.0
# usage             : python download_engine.py
# notes             :
# license           : MIT
# py version        : 3.11.0 (must run on 3.10 or higher)
#==============================================================================
# IT WORKS, WE DON'T TOUCH THIS FILE.
import os

import requests
from tqdm import tqdm

from download import Download
from settings import *


class DownloadEngine(Download):
	def __init__(self):
		self.downloads = self.get_all()
		self.queue = []
		self.max_retries = 5

	def downloader(self, position: int, resume_position: int | None = None, retry_count: int = 0) -> bool | None:
		"""Download url in ``queue[position]`` to disk with possible resumption.
		Parameters

		args:
			position (int): Position of url.
			resume_position (int): Byte position to resume download from, if any.

		"""
		# Get size of local & remote files
		url = self.queue[position]["url"]
		filename = self.queue[position]["filename"]
		request = requests.head(url, timeout=120, allow_redirects=True)
		remote_file_size = int(request.headers.get("content-length", 0))
		local_file_size = os.path.getsize(filename) if os.path.exists(filename) else 0

		# Append information to resume download at specific byte position to header
		resume_header = ({"Range": f"bytes={resume_position}-"} if resume_position else None)

		try:
			# Establish connection
			request = requests.get(url, stream=True, headers=resume_header, timeout=120, allow_redirects=True)
		except requests.exceptions.ConnectionError:
			return self.download_file(position)
		if request.status_code in {403, 404}:
			if retry_count < self.max_retries:
				print(f"\tWARNING: File not found on server, status code {request.status_code}, retrying ({retry_count + 1}/{self.max_retries})...")
				return self.download_file(position, retry_count=retry_count + 1)
			print("\tERROR: File not found, skipping...")
			return False
			# print("\tERROR: File not found on server.")
			# download_file(position, retry_count+1)
		if request.status_code in {301, 302}:
			if retry_count < self.max_retries:
				print(f"\tWARNING: File not found on server, status code {request.status_code}, retrying ({retry_count + 1}/{self.max_retries})...")
				return self.download_file(position, retry_count=retry_count + 1)
			print("\tERROR: Too many redirects, skipping...")
			return False
		if request.status_code not in {200, 206}:  # 206 is partial content
			print(f"\tERROR: Failed to establish connection, status code {request.status_code}.")
			return False

		# Set configuration
		block_size = 1024
		initial_pos = resume_position if resume_position else 0
		mode = "ab" if resume_position else "wb"
		path = os.path.dirname(filename)
		if not os.path.exists(path):
			os.makedirs(path)

		self.update(filename, download_status="downloading")
		with open(filename, mode) as file:
			with tqdm(total=remote_file_size, unit="B",
					  unit_scale=True, unit_divisor=1024,
					  desc="        "+filename.split("/")[-1].split("\\")[-1],
					  initial=initial_pos,
					  ascii=True, miniters=1) as pbar:
				try:
					# if DEBUG_MODE:
					# 	return "DEBUG_MODE"
					for chunk in request.iter_content(32 * block_size):
						file.write(chunk)
						pbar.update(len(chunk))
				except requests.exceptions.ConnectionError:
					# print("\tConnection error, retrying...")
					return self.download_file(position)

		# Check if download was successful
		if remote_file_size != local_file_size:# and not DEBUG_MODE:
			# print("\tConnection interrupted, retrying...")
			return self.download_file(position)
		print(f"\tDownload complete. ({local_file_size} of {remote_file_size} bytes downloaded)")
		self.update(filename, download_status="finished")
		if self.get(filename).size != remote_file_size:
			self.update(filename, download_size=remote_file_size)
		# Remove the item from the queue after the download is finished
		self.queue.remove({"url": url, "filename": filename})


	def download_file(self, position:int, retry_count:int=0) -> None:
		"""Execute the correct download operation. Depending on the local and
		remote size fo the file, resume the download if the offline file does not
		equal the online file.

		args:
			position (int): Position of url.

		returns:
			bool: True if download was successful, False otherwise.

		"""
		# Establish connection to header of file
		url = self.queue[position]["url"]
		filename = self.queue[position]["filename"]
		# queue.remove({"url": url, "filename": filename})
		# queue.pop(position)
		request = requests.head(url, timeout=120, allow_redirects=True)
		if request.status_code == 404:
			if retry_count < self.max_retries:
				print(f"\tWARNING: File not found on server, status code {request.status_code}, retrying ({retry_count + 1}/{self.max_retries})...")
				return self.downloader(position, retry_count=retry_count + 1)
			print("\tERROR: File not found, skipping...")
			return False
		if request.status_code not in {200, 206}:  # 206 is partial content
			print(f"\tERROR: Failed to establish connection, status code {request.status_code}.")
			return False

		# Get filesize of remote and local file
		remote_file_size = int(request.headers.get("content-length", 0))
		# filename = url.split("?name=")[1].split("&token=ip=")[0] + ".mp4"

		if os.path.exists(filename):
			local_file_size = os.path.getsize(filename)

			if local_file_size > remote_file_size:
				print("\tWARNING: Local file is larger than remote file, deleting local file and starting download from scratch...")
				os.remove(filename)
				return self.downloader(position)
			if remote_file_size != local_file_size:
				for index, item in enumerate(self.queue.copy()):
					print(f"DEBUG: {index} (index)\nDEBUG: {position} (position)")
					if item["filename"] == filename and self.queue[index] is not self.queue[position]:
						self.queue.remove(item)
						print("\tWARNING: Duplicate file found in queue, duplicate file has been removed.")
						return False
				print(f"\tFile is incomplete, resuming download... ({local_file_size} of {remote_file_size} bytes downloaded)")
				return self.downloader(position, local_file_size)
			print("\tFile is complete, download skipped.")
			self.update(filename, download_status="finished")
			if self.get(filename).size != remote_file_size:
				self.update(filename, download_size=remote_file_size)
			self.queue.remove({"url": url, "filename": filename})
			return True
		print("\tFile does not yet exist, starting download...")
		return self.downloader(position)

	def start(self):
		# print(download_engine.queue)
		for index, item in enumerate(self.queue):
			print(f"DEBUG: {index} (index)\nDEBUG: {item} (item)")
			self.update(item["filename"], download_status="initializing")
			self.download_file(index)
		print("\tDownload queue complete.")



def main():
	"""Download files specified in ``queue``.

	"""
	# print(Download.get("test"))
	download_engine = DownloadEngine()
	# downloads = download_engine.downloads
	# download_engine.create("Test",
	#                        "https://soaper.tv/dev/Apis/tw_m3u8?key=qWKyq9jm1eiAprqAYQ98ijo7LdzPWNslv42r49OWTOPojWNEdZUNLeRzrRJ7tKlRZ1V71aUVw24Wq8BMhQY68bYVzXurAwMrZmQwC2Kvq6Z7JWIom9oLwm4V.m3u8",
	#                        "ANYMOOSE",
	#                        "HD")
	# download_engine.queue.append({"url": "https://soaper.tv/dev/Apis/tw_m3u8?key=qWKyq9jm1eiAprqAYQ98ijo7LdzPWNslv42r49OWTOPojWNEdZUNLeRzrRJ7tKlRZ1V71aUVw24Wq8BMhQY68bYVzXurAwMrZmQwC2Kvq6Z7JWIom9oLwm4V.m3u8", "filename": "Test"})
	# download_engine.start()
	# print(download_engine.queue)
	# Download.create("Guardians of the Galaxy Volume 3", "https://stream-1-1-ip4.loadshare.org/slice/12/VideoID-4zvQaoJr/IBeQKg/zE9XBp/neKcBj/lqRVCI/360?name=guardians-of-the-galaxy-volume-3_360&token=ip=65.128.170.255~st=1690168176~exp=1690182576~acl=/*~hmac=079efad49015ba896907d36524a9f2d354da5f4c7a2fbd8784db51e0d73744c8&source=207", "108802760954752258469")
	# filename = Download.get("Guardians of the Galaxy Volume 3").filename
	# print(filename)
	return download_engine.downloads


if __name__ == "__main__":
	main()
