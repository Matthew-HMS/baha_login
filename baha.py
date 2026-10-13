"""Automated daily sign-in for gamer.com.tw (Bahamut).

Logs in with credentials from the BAHA_ACCOUNT / BAHA_PASSWORD environment
variables, then claims the daily sign-in reward (每日簽到). Designed to run
headless in CI (e.g. GitHub Actions).
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
LOGIN_TIMEOUT = 30
# Cookies do_login.php sets on a successful sign-in.
SESSION_COOKIES = ("BAHAID", "BAHARUNE")
SCREENSHOT_PATH = "failure.png"
HOME_URL = "https://www.gamer.com.tw/"

# Runs in the page (so it carries the session cookies and Bahamut's CSRF
# helper): check today's sign-in, sign in if needed, then re-check. Mirrors
# what signin.js does when you click 每日簽到.
SIGNIN_SCRIPT = """
const done = arguments[arguments.length - 1];
const url = "https://api.gamer.com.tw/user/v1/signin.php";
const status = async () =>
  (await fetch(url + "?action=2", {credentials: "include"})).json();
(async () => {
  let s = await status();
  if (s.error) return done({error: s.error.message});
  const already = s.data.signin == 1;
  if (!already) {
    const csrf = new Bahamut.Csrf();
    csrf.setCookie();
    const body = new FormData();
    body.append("action", 1);
    const r = await (await fetch(url, {
      method: "POST", body, headers: csrf.getFetchHeaders(), credentials: "include",
    })).json();
    if (r.error) return done({error: r.error.message});
    s = await status();
    if (s.error) return done({error: s.error.message});
  }
  done({signin: s.data.signin, days: s.data.days, already});
})().catch(e => done({error: String(e)}));
"""
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


class LoginError(Exception):
    """The login did not produce a signed-in session."""


class SigninError(Exception):
    """The daily sign-in (每日簽到) did not go through."""


def login_error(driver: webdriver.Chrome) -> str:
    """Return the error text login.js shows on the login page, if any."""
    if "login.php" not in driver.current_url:
        return ""
    for alert in driver.find_elements(By.CSS_SELECTOR, ".msgdiv-alert"):
        if alert.is_displayed() and alert.text.strip():
            return alert.text.strip()
    return ""


def verify_logged_in(driver: webdriver.Chrome) -> None:
    """Fail unless the browser holds a signed-in Bahamut session.

    A redirect alone isn't proof: check for the session cookies that
    do_login.php sets on .gamer.com.tw.
    """
    cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
    missing = [name for name in SESSION_COOKIES if not cookies.get(name)]
    if missing:
        raise LoginError(
            f"Missing session cookies {missing}; not signed in"
            f" (cookies present: {sorted(cookies)})"
        )
    log.info("Login verified, signed in as %s", cookies["BAHAID"])


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
    # On failure it stays put and shows the reason in a .msgdiv-alert box.
    try:
        WebDriverWait(driver, LOGIN_TIMEOUT).until(
            lambda d: "login.php" not in d.current_url or login_error(d)
        )
    except TimeoutException:
        raise LoginError("Still on the login page; the submit was likely dropped by reCAPTCHA")
    error = login_error(driver)
    if error:
        raise LoginError(f"Login rejected: {error}")

    # Let the landing page finish loading so the session cookies are in place.
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(5)
    log.info("Redirected to %s", driver.current_url)
    verify_logged_in(driver)


def daily_signin(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    """Claim the daily sign-in reward and fail unless it is recorded."""
    log.info("Opening homepage for daily sign-in")
    driver.get(HOME_URL)
    wait.until(lambda d: d.execute_script(
        "return typeof Bahamut !== 'undefined' && typeof Bahamut.Csrf === 'function'"
    ))
    driver.set_script_timeout(WAIT_TIMEOUT)
    result = driver.execute_async_script(SIGNIN_SCRIPT)
    if result.get("error"):
        raise SigninError(f"Daily sign-in failed: {result['error']}")
    if result.get("signin") != 1:
        raise SigninError(f"Daily sign-in not recorded: {result}")
    log.info(
        "Daily sign-in %s (%s consecutive days)",
        "already done today" if result["already"] else "completed",
        result.get("days"),
    )


def save_screenshot(driver: webdriver.Chrome) -> None:
    """Save what the browser shows, for debugging a failed run."""
    try:
        driver.save_screenshot(SCREENSHOT_PATH)
        log.info("Saved screenshot to %s", SCREENSHOT_PATH)
    except WebDriverException:
        log.warning("Could not save screenshot")


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
        daily_signin(driver, wait)
        return 0
    except (LoginError, SigninError) as e:
        log.error("%s (url: %s)", e, driver.current_url)
        save_screenshot(driver)
        return 1
    except (TimeoutException, WebDriverException):
        log.exception("Automation failed (url: %s)", driver.current_url)
        save_screenshot(driver)
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
