import time
from selenium import webdriver
from selenium.webdriver.common.by import By
import pickle
from selenium.common.exceptions import NoSuchElementException
import os

options = webdriver.ChromeOptions()
options.add_argument('--headless')
driver = webdriver.Chrome(options=options)
driver.get("https://www.gamer.com.tw/")

# Load cookie
cookies = pickle.load(open("baha_cookies.pkl", "rb"))
for cookie in cookies:
    driver.add_cookie(cookie)
driver.refresh()

# quit
time.sleep(10)
driver.quit()