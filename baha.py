import time
from selenium import webdriver
from selenium.webdriver.common.by import By
import pickle
from selenium.common.exceptions import NoSuchElementException
import os

account = os.getenv("BAHA_ACCOUNT")
password = os.getenv("BAHA_PASSWORD")

options = webdriver.ChromeOptions()
options.add_argument('--headless')
driver = webdriver.Chrome(options=options)
driver.get("https://www.gamer.com.tw/")

# Load cookie
cookies = pickle.load(open("baha_cookies.pkl", "rb"))
for cookie in cookies:
    driver.add_cookie(cookie)
driver.refresh()

# check login
try:
    driver.find_element(By.XPATH, "//a[@href='https://user.gamer.com.tw/login.php']")
    login = False
    print("not login")
except NoSuchElementException:
    login = True

if login:
    print("login")
else:
    driver.get("https://user.gamer.com.tw/login.php")
    driver.refresh()
    email = driver.find_element(By.XPATH, "//*[@name = 'userid']")
    email.send_keys(account)
    pword = driver.find_element(By.XPATH, "//*[@name = 'password']")
    pword.send_keys(password)
    time.sleep(5)
    submit = driver.find_element(By.XPATH, "//*[@id = 'btn-login']")
    submit.click()

    # save cookie
    time.sleep(5)
    pickle.dump(driver.get_cookies(), open("baha_cookies.pkl", "wb"))


# quit
time.sleep(10)
driver.quit()