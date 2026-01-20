# tests/e2e/test_login_flow.py

"""
End-to-end tests for user authentication flows.

These tests verify that:
1. Unauthenticated users are redirected to login
2. Users can log in with valid credentials
3. Authentication tokens are properly stored
4. Users are redirected to the home page after login
"""

import os

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Configuration
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
LOGIN_URL = f"{FRONTEND_BASE_URL}/login"
HOME_URL = f"{FRONTEND_BASE_URL}/"

TEST_USERNAME = os.getenv("TEST_USERNAME", "testuser")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "testpass123")


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def driver():
    """Set up and tear down the Chrome WebDriver."""
    options = webdriver.ChromeOptions()
    # Comment out --headless to see the browser during test execution
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,800")

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)
    yield driver
    driver.quit()


# =============================================================================
# TESTS
# =============================================================================


def test_unauthenticated_user_redirected_to_login(driver):
    """
    Verify that unauthenticated users cannot access protected routes.

    When a user without a valid JWT token attempts to access the home page,
    the ProtectedRoute component should redirect them to /login.

    Success criteria:
    - User is redirected from / to /login
    - Login page is displayed
    """
    driver.get(HOME_URL)

    # Wait for React Router to complete the redirect
    WebDriverWait(driver, 10).until(lambda d: "/login" in d.current_url)

    assert (
        "/login" in driver.current_url
    ), "Unauthenticated user should be redirected to login"


def test_can_log_in_with_valid_credentials(driver):
    """
    Verify that users can successfully log in with valid credentials.

    This test covers the complete login flow:
    1. Navigate to login page
    2. Enter valid username and password
    3. Submit the form
    4. Verify redirect to home page
    5. Verify home page content is displayed

    Success criteria:
    - Login form accepts credentials
    - User is redirected to home page after successful login
    - "Your Trips" header is visible on home page
    - User is no longer on /login route
    """
    driver.get(LOGIN_URL)

    # Wait for and fill in the login form
    username_input = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.ID, "username"))
    )
    password_input = driver.find_element(By.ID, "password")

    username_input.clear()
    username_input.send_keys(TEST_USERNAME)

    password_input.clear()
    password_input.send_keys(TEST_PASSWORD)

    # Click the Sign In button
    login_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Sign In')]"))
    )
    login_button.click()

    # Wait for redirect to home page and verify content
    WebDriverWait(driver, 15).until(lambda d: "Your Trips" in d.page_source)

    assert (
        "Your Trips" in driver.page_source
    ), "Home page should display 'Your Trips' header"
    assert "/login" not in driver.current_url, "User should no longer be on login page"
