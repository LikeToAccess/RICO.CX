# -*- coding: utf-8 -*-
# filename          : download.py
# description       : 
# author            : Ian Ault
# email             : liketoaccess@protonmail.com
# date              : 07-22-2023
# version           : v1.0
# usage             : python download.py
# notes             :
# license           : MIT
# py version        : 3.11.1 (must run on 3.10 or higher)
#==============================================================================
import time

from database import get_db


class Download:
	def __init__(self, download_filename, download_url, download_size, download_quality, last_updated, user_id, download_status="not_started"):
		self.filename = download_filename
		self.url = download_url
		self.size = download_size
		self.quality = download_quality
		self.last_updated = last_updated
		self.status = download_status
		self.user_id = user_id

	@staticmethod
	def get(download_filename):
		db = get_db()
		download = db.execute(
			"SELECT * FROM downloads WHERE download_filename = ?", (download_filename,)
		).fetchone()
		if not download:
			return None

		download = Download(
			download_filename=download[0],
			download_url=download[1],
			download_size=download[2],
			download_quality=download[3],
			last_updated=download[4],
			download_status=download[6],
			user_id=download[5]
		)

		return download

	@staticmethod
	def get_all():
		db = get_db()
		downloads = db.execute(
			"SELECT * FROM downloads ORDER BY last_updated ASC"
		).fetchall()
		if not downloads:
			return None

		download_list = []
		for download in downloads:
			download_list.append(
				Download(
					download_filename=download[0],
					download_url=download[1],
					download_size=download[2],
					download_quality=download[3],
					last_updated=download[4],
					download_status=download[6],
					user_id=download[5]
				)
			)

		return download_list

	@staticmethod
	def create(download_filename, download_url, user_id, download_quality=None):
		db = get_db()
		db.execute(
			"INSERT INTO downloads (download_filename, download_url, download_size, download_quality, last_updated, user_id, download_status) "
			"VALUES (?, ?, ?, ?, ?, ?, ?)",
			(download_filename, download_url, None, download_quality, time.time(), user_id, "not_started")
		)
		db.commit()

	@staticmethod
	def update(download_filename, download_size=None, download_quality=None, user_id=None, download_status=None):
		download = Download.get(download_filename)
		if not download:
			return

		download_size = download_size if download_size else download.size
		download_quality = download_quality if download_quality else download.quality
		user_id = user_id if user_id else download.user_id
		download_status = download_status if download_status else download.status

		db = get_db()
		db.execute(
			"UPDATE downloads SET download_size = ?, download_quality = ?, last_updated = ?, user_id = ?, download_status = ? WHERE download_filename = ?",
			(download_size, download_quality, time.time(), user_id, download_status, download_filename)
		)
		db.commit()

	def delete(self):
		db = get_db()
		db.execute(
			"DELETE FROM downloads WHERE download_filename = ?", (self.filename,)
		)
		db.commit()
