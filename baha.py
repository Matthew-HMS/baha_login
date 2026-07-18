"""Automated daily sign-in for gamer.com.tw (Bahamut).

Logs in with credentials from the BAHA_ACCOUNT / BAHA_PASSWORD environment
variables; the daily reward is claimed automatically on sign-in. Designed to
run headless in CI (e.g. GitHub Actions).
"""

import logging
import os
import sys

import random
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

LOGIN_URL = "https://user.gamer.com.tw/login.php"
WAIT_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("baha")


def build_driver() -> webdriver.Chrome:
    """Create a Chrome driver tuned for CI runners.

    Headless by default; set HEADLESS=0 to run a visible browser (useful for
    local testing, where a real window scores better against reCAPTCHA).
    """
    options = webdriver.ChromeOptions()
    if os.getenv("HEADLESS", "1") != "0":
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-agent={USER_AGENT}")
    return webdriver.Chrome(options=options)


def human_type(element, text: str) -> None:
    """Click a field and type into it with small random delays, like a person."""
    element.click()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.18))


def login(driver: webdriver.Chrome, wait: WebDriverWait, account: str, password: str) -> None:
    """Fill in and submit the login form."""
    log.info("Opening login page")
    driver.get(LOGIN_URL)
    # Reloading the login page drops the reCAPTCHA challenge that appears on
    # the first (fresh) visit, letting the form submit without verification.
    driver.refresh()

    # reCAPTCHA Enterprise scores *how* we interact, not just the click. Filling
    # instantly and clicking with no cursor movement scores as a bot and the
    # submit gets silently dropped. So drive the real pointer: move to each
    # field, click it, type with small delays, then move to the button and click.
    email = wait.until(EC.presence_of_element_located((By.NAME, "userid")))
    password_field = driver.find_element(By.NAME, "password")
    human_type(email, account)
    human_type(password_field, password)

    # The 登入 button is an <a> whose click handler is bound by the deferred
    # login.js, which runs only after the page loads. Wait until it's bound so
    # the click can't be a silent no-op.
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    wait.until(lambda d: d.execute_script(
        "return typeof jQuery !== 'undefined'"
        " && jQuery('#btn-login').length > 0"
        " && !!(jQuery._data(jQuery('#btn-login')[0], 'events') || {}).click"
    ))
    log.info("Submitting login form")
    button = driver.find_element(By.ID, "btn-login")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    ActionChains(driver).move_to_element(button).pause(0.4).click().perform()

    # On success login.js sets cookies and redirects away from the login page.
    wait.until(lambda d: "login.php" not in d.current_url)
    log.info("Login successful")

    # Give the daily reward, which claims automatically on sign-in, time to post.
    time.sleep(10)


def main() -> int:
    account = os.getenv("BAHA_ACCOUNT")
    password = os.getenv("BAHA_PASSWORD")
    if not account or not password:
        log.error("BAHA_ACCOUNT and BAHA_PASSWORD must be set")
        return 1

    driver = build_driver()
    try:
        wait = WebDriverWait(driver, WAIT_TIMEOUT)
        login(driver, wait, account, password)
        return 0
    except (TimeoutException, WebDriverException):
        log.exception("Automation failed")
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
