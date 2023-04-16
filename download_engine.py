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
# py version        : 3.11.0 (must run on 3.6 or higher)
#==============================================================================
import os
import time

import requests
from tqdm import tqdm

from settings import *


queue = []
max_retries = 5


def downloader(position: int, resume_position: int = None, retry_count: int = 0) -> None:
	"""Download url in ``queue[position]`` to disk with possible resumption.
	Parameters

	args:
		position (int): Position of url.
		resume_position (int): Byte position to resume download from, if any.

	"""
	# Get size of local & remote files
	url = queue[position]["url"]
	filename = queue[position]["filename"]
	request = requests.head(url, timeout=120)
	remote_file_size = int(request.headers.get("content-length", 0))
	local_file_size = os.path.getsize(filename) if os.path.exists(filename) else 0

	# Append information to resume download at specific byte position to header
	resume_header = ({"Range": f"bytes={resume_position}-"} if resume_position else None)

	try:
		# Establish connection
		request = requests.get(url, stream=True, headers=resume_header, timeout=120)
	except requests.exceptions.ConnectionError:
		download_file(position)
		return
	if request.status_code == 404:
		if retry_count < max_retries:
			print(f"\tWARNING: File not found on server, status code {request.status_code}, retrying ({retry_count + 1}/{max_retries})...")
			download_file(position, retry_count=retry_count + 1)
			return
		print("\tERROR: File not found, skipping...")
		return
		# print("\tERROR: File not found on server.")
		# download_file(position, retry_count+1)
	if request.status_code not in {200, 206}:  # 206 is partial content
		print(f"\tERROR: Failed to establish connection, status code {request.status_code}.")
		return

	# Set configuration
	block_size = 1024
	initial_pos = resume_position if resume_position else 0
	mode = "ab" if resume_position else "wb"
	path = os.path.dirname(filename)
	if not os.path.exists(path):
		os.makedirs(path)

	with open(filename, mode) as file:
		with tqdm(total=remote_file_size, unit="B",
				  unit_scale=True, unit_divisor=1024,
				  desc="        "+filename.split("/")[-1].split("\\")[-1],
				  initial=initial_pos,
				  ascii=True, miniters=1) as pbar:
			try:
				if DEBUG_MODE:
					return
				for chunk in request.iter_content(32 * block_size):
					file.write(chunk)
					pbar.update(len(chunk))
			except requests.exceptions.ConnectionError:
				# print("\tConnection error, retrying...")
				download_file(position)
				return

	# Check if download was successful
	if remote_file_size != local_file_size and not DEBUG_MODE:
		# print("\tConnection interrupted, retrying...")
		download_file(position)
		return
	print(f"\tDownload complete. ({local_file_size} of {remote_file_size} bytes downloaded)")
	# Remove the item from the queue after the download is finished
	queue.remove({"url": url, "filename": filename})


def download_file(position: int, retry_count: int = 0) -> None:
	"""Execute the correct download operation. Depending on the local and
	remote size fo the file, resume the download if the offline file does not
	equal the online file.

	args:
		position (int): Position of url.

	returns:
		bool: True if download was successful, False otherwise.

	"""
	# Establish connection to header of file
	url = queue[position]["url"]
	filename = queue[position]["filename"]
	# queue.remove({"url": url, "filename": filename})
	# queue.pop(position)
	request = requests.head(url, timeout=120)
	if request.status_code == 404:
		if retry_count < max_retries:
			print(f"\tWARNING: File not found on server, status code {request.status_code}, retrying ({retry_count + 1}/{max_retries})...")
			downloader(position, retry_count=retry_count + 1)
			return
		print("\tERROR: File not found, skipping...")
		return
	if request.status_code not in {200, 206}:  # 206 is partial content
		print(f"\tERROR: Failed to establish connection, status code {request.status_code}.")
		return

	# Get filesize of remote and local file
	remote_file_size = int(request.headers.get("content-length", 0))
	# filename = url.split("?name=")[1].split("&token=ip=")[0] + ".mp4"

	if os.path.exists(filename):
		local_file_size = os.path.getsize(filename)

		if local_file_size > remote_file_size:
			print("\tWARNING: Local file is larger than remote file, deleting local file and starting download from scratch...")
			os.remove(filename)
			downloader(position)
			return
		if remote_file_size != local_file_size:
			print(f"\tFile is incomplete, resuming download... ({local_file_size} of {remote_file_size} bytes downloaded)")
			downloader(position, local_file_size)
			return
		print("\tFile is complete, download skipped.")
		queue.remove({"url": url, "filename": filename})
	else:
		print("\tFile does not yet exist, starting download...")
		downloader(position)
		return


def main():
	"""Download files specified in ``queue``.

	"""
	print("Starting download of required files...")
	START_TIME = time.time()
	for position in range(len(queue)):
		download_file(position)

	print(f"Finished download of {len(queue)} file{'s' if len(queue) != 1 else ''} in {time.time() - START_TIME:.2f} seconds.")

if __name__ == "__main__":
	main()
