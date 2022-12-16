# -*- coding: utf-8 -*-
# filename          : find_element.py
# description       : Class containing methods for finding elements
# author            : Ian Ault
# email             : liketoaccess@protonmail.com
# date              : 05-19-2022
# version           : v1.0
# usage             : python main.py
# notes             : This file should not be run directly
# license           : MIT
# py version        : 3.10.2
#==============================================================================
from selenium.common.exceptions import *
from selenium.webdriver.common.by import By


class Find_Element:
	def __init__(self, driver):
		self.driver = driver

	def find_element(self, selector, sequence):
		try:
			return self.driver.find_element(selector, sequence)
		except NoSuchElementException as exc:
			raise NoSuchElementException(self.driver.current_url) from exc


	def find_elements(self, selector, sequence):
		return self.driver.find_elements(selector, sequence)

	def find_element_by_xpath(self, sequence):
		return self.find_element(By.XPATH, sequence)

	def find_elements_by_xpath(self, sequence):
		return self.find_elements(By.XPATH, sequence)

	def find_element_by_xpaths(self, *xpaths):
		for xpath in xpaths:
			try:
				data = self.find_element_by_xpath(xpath)
			except NoSuchElementException:
				continue
			if data:
				return data

		return False
