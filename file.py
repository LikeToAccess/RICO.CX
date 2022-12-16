# -*- coding: utf-8 -*-
# filename          : file.py
# description       : Functions to help read/write files
# author            : Ian Ault
# email             : liketoaccess@protonmail.com
# date              : 05-19-2022
# version           : v1.0
# usage             : python main.py
# notes             : This file should not be run directly
# license           : MIT
# py version        : 3.10.2
#==============================================================================
import os
import json


def rename_file(source, filename):
	try:
		os.rename(source, filename)
	except FileExistsError:
		remove_file(filename)
		rename_file(source, filename)

def remove_file(filename):
	try:
		os.remove(filename)
		return True
	except OSError:
		return False

def read_file(filename, encoding="utf8"):
	if not os.path.exists(filename): return filename
	with open(filename, "r", encoding=encoding) as file:
		data = file.read()

	return data

def write_file(filename, data, encoding="utf8"):
	with open(filename, "w", encoding=encoding) as file:
		file.write(data)

def read_json_file(filename, encoding="utf8"):
	if not os.path.exists(filename): return []
	with open(filename, "r", encoding=encoding) as file:
		data = json.load(file)

	return data

def write_json_file(filename, data, encoding="utf8"):
	"""Write json object to file

	Args:
		filename (str): File name
		data (dict): Data to write to file
		encoding (str, optional): Encoding. Defaults to "utf8".

	"""
	with open(filename, "w", encoding=encoding) as file:
		json.dump(data, file, indent=4, sort_keys=True)

	return json.dumps(data, indent=4, sort_keys=True)

def append_json_file(filename, data, encoding="utf8"):
	existing_data = read_json_file(filename, encoding=encoding)
	existing_data.append(data)
	write_json_file(filename, existing_data, encoding=encoding)
