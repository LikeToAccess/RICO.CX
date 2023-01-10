# -*- coding: utf-8 -*-
# filename          : download.py
# description       : Interact with download_engine and format
# author            : Ian Ault
# email             : liketoaccess@protonmail.com
# date              : 01-10-2023
# version           : v1.0
# usage             : python download.py
# notes             :
# license           : MIT
# py version        : 3.11.1 (must run on 3.6 or higher)
#==============================================================================
import time
import os

from threading import Thread

import download_engine as de
from format import Format


def threaded_download(url, data):
	filename = os.path.abspath(Format(data).format_file_name())
	de.queue.append({"url": url, "filename": filename})
	print("Download queued...")
	print(f"DEBUG: {de.queue}")
	for index in range(len(de.queue)):
		t = Thread(target=de.download_file, args=(index,))
		t.start()

	print("DEBUG: Download finished!")
