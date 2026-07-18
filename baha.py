"""Automated daily sign-in for gamer.com.tw (Bahamut).

Logs in with credentials from the BAHA_ACCOUNT / BAHA_PASSWORD environment
variables, then claims the daily sign-in and double reward if available.
Designed to run headless in CI (e.g. GitHub Actions).
"""

import logging
import os
import sys

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

LOGIN_URL = "https://user.gamer.com.tw/login.php"
HOME_URL = "https://www.gamer.com.tw/"
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
    """Create a headless Chrome driver tuned for CI runners."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-agent={USER_AGENT}")
    return webdriver.Chrome(options=options)


def login(driver: webdriver.Chrome, wait: WebDriverWait, account: str, password: str) -> None:
    """Fill in and submit the login form."""
    log.info("Opening login page")
    driver.get(LOGIN_URL)

    email = wait.until(EC.presence_of_element_located((By.NAME, "userid")))
    email.send_keys(account)
    driver.find_element(By.NAME, "password").send_keys(password)

    log.info("Submitting login form")
    wait.until(EC.element_to_be_clickable((By.ID, "btn-login"))).click()

    # Wait until we're redirected away from the login page.
    wait.until(lambda d: "login.php" not in d.current_url)
    log.info("Login successful")


def claim_rewards(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    """Claim the daily sign-in and double reward if the buttons are present.

    Any of these steps may be absent (already claimed, no reward today), so
    each click is attempted independently and missing elements are ignored.
    """
    driver.get(HOME_URL)

    steps = [
        ("daily sign-in", (By.ID, "signin-btn")),
        ("double reward", (By.CLASS_NAME, "popup-dailybox__btn")),
        ("confirm", (By.XPATH, "//button[@type='submit']")),
    ]
    for name, locator in steps:
        try:
            wait.until(EC.element_to_be_clickable(locator)).click()
            log.info("Clicked %s", name)
        except TimeoutException:
            log.info("Skipped %s (not available)", name)


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
        claim_rewards(driver, wait)
        return 0
    except (TimeoutException, WebDriverException):
        log.exception("Automation failed")
        try:
            driver.save_screenshot("error.png")
            log.info("Saved screenshot to error.png")
        except WebDriverException:
            pass
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
