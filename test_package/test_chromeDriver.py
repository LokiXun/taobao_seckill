# encoding: utf-8
"""
Function:
@author: LokiXun
@contact: 2682414501@qq.com
"""
from selenium import webdriver

driver = webdriver.Chrome()
url = 'https://www.csdn.net/'
driver.get(url)
driver.maximize_window()