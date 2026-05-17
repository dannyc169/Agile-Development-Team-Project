import os
import time
import uuid

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")


@pytest.fixture()
def base_url():
    return BASE_URL


@pytest.fixture()
def driver():
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1400")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    browser = webdriver.Chrome(options=options)
    browser.set_page_load_timeout(30)
    browser.implicitly_wait(2)

    yield browser

    browser.quit()


@pytest.fixture()
def unique_user_prefix():
    return f"selenium_{int(time.time())}_{uuid.uuid4().hex[:8]}"