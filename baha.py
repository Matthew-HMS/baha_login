import time
from selenium import webdriver
from selenium.webdriver.common.by import By
import pickle
from selenium.common.exceptions import NoSuchElementException
import os

account = 'matthewhms'
password = 'ho0218ho'

options = webdriver.ChromeOptions()
# options.add_argument('--headless')
driver = webdriver.Chrome(options=options)
driver.get("https://www.gamer.com.tw/")

# Login
driver.get("https://user.gamer.com.tw/login.php")
driver.refresh()
email = driver.find_element(By.XPATH, "//*[@name = 'userid']")
email.send_keys(account)
pword = driver.find_element(By.XPATH, "//*[@name = 'password']")
pword.send_keys(password)
time.sleep(5)
submit = driver.find_element(By.XPATH, "//*[@id = 'btn-login']")
submit.click()

# double reward
time.sleep(2)
driver.get("https://www.gamer.com.tw/")
time.sleep(3)
daily = driver.find_element(By.XPATH, "//*[@id='signin-btn']")
daily.click()
time.sleep(3)
double = driver.find_element(By.XPATH, "//*[@class='popup-dailybox__btn']")
try:
    double.click()
    time.sleep(3)
    confirm = driver.find_element(By.XPATH, "//Button[@type='submit']")
    confirm.click()

except:
    pass

# quit
time.sleep(30)
driver.quit()