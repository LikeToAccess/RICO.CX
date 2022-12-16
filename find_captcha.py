# -*- coding: utf-8 -*-
# filename          : find_captcha.py
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
import os
import time
from selenium.common.exceptions import *
from selenium.webdriver.common.by import By
from wait_until_element import Wait_Until_Element
from find_element import Find_Element


class Find_Captcha(Find_Element, Wait_Until_Element):
	def check_captcha(self):
		# "Myles" - Myles
		# "Liam" - Liam
		try:
			captcha_image = self.wait_until_element(
				By.XPATH,
				"//*[@id=\"checkcapchamodelyii-captcha-image\"]",
				timeout=1.5
			)
			captcha_input = self.driver.find_element(By.XPATH, "//*[@id=\"checkcapchamodelyii-captcha\"]")
			captcha_submit = self.driver.find_element(By.XPATH, "//*[@id=\"player-captcha\"]/div[3]/div/div")
		except TimeoutException:
			captcha_image, captcha_input, captcha_submit = False, False, False

		return captcha_image, captcha_input, captcha_submit

	def get_captcha_image(self):
		captcha = self.check_captcha()
		if captcha[1]:
			print("\tWARNING: Found captcha!")
			captcha_image, *_ = captcha
			timeout = time.time()
			print("\tWaiting for captcha image to load...")
			while captcha_image.size["width"] == 0 or time.time() - timeout < 5:
				time.sleep(0.1)
			# self.driver.save_screenshot("screenshot.png")
			captcha_image.screenshot("captcha.png")
			print("\tCaptcha image saved.")
			return 225
		return 200

	def resolve_captcha(self, captcha_response):
		captcha = self.check_captcha()
		_captcha_image, captcha_input, captcha_submit = captcha

		if not captcha_input:
			return True

		captcha_input.send_keys(captcha_response)
		captcha_submit.click()

		try:
			self.wait_until_element(By.TAG_NAME, "video", timeout=3)
		except TimeoutException:
			return False

		return bool(self.check_captcha()[1])
