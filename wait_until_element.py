# -*- coding: utf-8 -*-
# filename          : wait_until_element.py
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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class Wait_Until_Element:
	def __init__(self, driver):
		self.driver = driver

	def wait_until_element(self, selector, locator, timeout=10):
		wait = WebDriverWait(self.driver, timeout)
		element = wait.until(
			EC.presence_of_element_located(
				(
					selector, locator
				)
			)
		)
		return element

	def wait_until_elements(self, selector, locator, timeout=10):
		wait = WebDriverWait(self.driver, timeout)
		elements = wait.until(
			EC.presence_of_all_elements_located(
				(
					selector, locator
				)
			)
		)
		return elements

	def wait_until_element_by_xpath(self, sequence, timeout=10):
		return self.wait_until_element(By.XPATH, sequence, timeout=timeout)

	def wait_until_elements_by_xpath(self, sequence, timeout=10):
		return self.wait_until_elements(By.XPATH, sequence, timeout=timeout)
