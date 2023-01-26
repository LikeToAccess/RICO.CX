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
import base64


def read_image(filename: str, encoding: str="utf8") -> str:
	"""Read image file and return base64 encoded string

	Args:
		filename (str): File name of image
		encoding (str, optional): Encoding type. Defaults to "utf8".

	Returns:
		str: Base64 encoded string

	"""
	with open(filename, "rb") as file:
		image_data = file.read()
	image_data = base64.b64encode(image_data).decode(encoding)
	image_data = f"data:image/png;base64,{image_data}"

	return image_data

def rename_file(source: str, filename: str) -> None:
	try:
		os.rename(source, filename)
	except FileExistsError:
		remove_file(filename)
		rename_file(source, filename)

def remove_file(filename: str) -> bool:
	try:
		os.remove(filename)
		return True
	except OSError:
		return False

def read_file(filename: str, encoding: str="utf8") -> str:
	if not os.path.exists(filename): return filename
	with open(filename, "r", encoding=encoding) as file:
		data = file.read()

	return data

def write_file(filename: str, data: str, encoding: str="utf8") -> None:
	with open(filename, "w", encoding=encoding) as file:
		file.write(data)

def read_json_file(filename: str, encoding: str="utf8") -> dict:
	"""Read json object from file

	Args:
		filename (str): filename
		encoding (str, optional): encoding. Defaults to "utf8".

	Returns:
		dict: json object

	"""
	if not os.path.exists(filename): return []
	with open(filename, "r", encoding=encoding) as file:
		data = json.load(file)

	return data

def write_json_file(filename: str, data: dict, encoding: str="utf8") -> str:
	"""Write json object to file

	Args:
		filename (str): File name
		data (dict): Data to write to file
		encoding (str, optional): Encoding. Defaults to "utf8".

	Returns:
		str: Formatted json string

	"""
	with open(filename, "w", encoding=encoding) as file:
		json.dump(data, file, indent=4, sort_keys=True)

	return json.dumps(data, indent=4, sort_keys=True)

def append_json_file(filename: str, data: dict, encoding: str="utf8") -> str:
	"""Append json object to file

	Args:
		filename (str): File name
		data (dict): Data to write to file
		encoding (str, optional): Encoding. Defaults to "utf8".

	Returns:
		str: Formatted json string

	"""
	existing_data = read_json_file(filename, encoding=encoding)
	existing_data.append(data)
	return write_json_file(filename, existing_data, encoding=encoding)
