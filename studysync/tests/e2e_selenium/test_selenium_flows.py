import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


WAIT_SECONDS = 10


def wait_for(driver, condition):
    return WebDriverWait(driver, WAIT_SECONDS).until(condition)


def go(driver, base_url, path):
    driver.get(f"{base_url}{path}")


def fill_and_submit_login(driver, base_url, username, password):
    go(driver, base_url, "/login")
    wait_for(driver, EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
    driver.find_element(By.NAME, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()


def fill_and_submit_register(driver, base_url, username, password):
    go(driver, base_url, "/register")
    wait_for(driver, EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
    driver.find_element(By.NAME, "email").send_keys("")
    driver.find_element(By.NAME, "password").send_keys(password)
    driver.find_element(By.NAME, "confirm_password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()


def open_user_menu_and_logout(driver):
    wait_for(driver, EC.element_to_be_clickable((By.ID, "openUserModalBtn"))).click()
    wait_for(driver, EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Logout']"))).click()


@pytest.mark.e2e
def test_login_page_opens(driver, base_url):
    go(driver, base_url, "/login")

    wait_for(driver, EC.presence_of_element_located((By.NAME, "username")))
    assert "Sign In" in driver.title


@pytest.mark.e2e
def test_register_succeeds(driver, base_url, unique_user_prefix):
    username = f"{unique_user_prefix}_reg"
    fill_and_submit_register(driver, base_url, username, "Password123!")

    wait_for(driver, EC.url_contains("/dashboard"))
    assert username in driver.page_source


@pytest.mark.e2e
def test_login_succeeds(driver, base_url, unique_user_prefix):
    username = f"{unique_user_prefix}_login"
    fill_and_submit_register(driver, base_url, username, "Password123!")
    open_user_menu_and_logout(driver)

    wait_for(driver, EC.url_contains("/login"))

    fill_and_submit_login(driver, base_url, username, "Password123!")
    wait_for(driver, EC.url_contains("/dashboard"))
    assert "Dashboard" in driver.page_source


@pytest.mark.e2e
def test_create_team_succeeds(driver, base_url, unique_user_prefix):
    username = f"{unique_user_prefix}_team"
    team_name = f"Team {unique_user_prefix}"

    fill_and_submit_register(driver, base_url, username, "Password123!")
    go(driver, base_url, "/teams/create")

    wait_for(driver, EC.presence_of_element_located((By.NAME, "name"))).send_keys(team_name)
    driver.find_element(By.NAME, "description").send_keys("Created from Selenium test")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    wait_for(driver, EC.url_matches(r'.*/teams/\d+'))
    assert team_name in driver.page_source


@pytest.mark.e2e
def test_logout_forces_login_required(driver, base_url, unique_user_prefix):
    username = f"{unique_user_prefix}_logout"

    fill_and_submit_register(driver, base_url, username, "Password123!")
    open_user_menu_and_logout(driver)

    wait_for(driver, EC.url_contains("/login"))

    go(driver, base_url, "/dashboard")
    wait_for(driver, EC.url_contains("/login"))
    assert "Sign In" in driver.title