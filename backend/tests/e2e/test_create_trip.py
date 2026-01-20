# tests/e2e/test_create_trip_flow.py

"""
End-to-end tests for trip creation flow.

These tests verify that:
1. Users can create new trips from the home page
2. Trip creation navigates to the chat interface
3. The chat interface loads correctly with welcome content
4. Error states are properly handled
"""

import os

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
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
# HELPER FUNCTIONS
# =============================================================================


def login(driver):
    """
    Log in through the UI with test credentials.

    Args:
        driver: Selenium WebDriver instance
    """
    driver.get(LOGIN_URL)

    # Wait for and fill in login form
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

    # Wait until we see the Home page header
    WebDriverWait(driver, 15).until(lambda d: "Your Trips" in d.page_source)


def click_create_trip(driver):
    """
    Click the "Create New Trip" button using available UI elements.

    Tries multiple strategies to accommodate different page states:
    1. E2E-specific header button (preferred)
    2. Empty-state "Create Your First Trip" button

    Args:
        driver: Selenium WebDriver instance

    Raises:
        TimeoutException: If no create-trip button is found
    """
    wait = WebDriverWait(driver, 10)

    # Strategy 1: E2E header button (preferred)
    try:
        e2e_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "[data-testid='e2e-create-trip']")
            )
        )
        e2e_btn.click()
        return
    except TimeoutException:
        pass

    # Strategy 2: Empty-state button (when no trips exist)
    try:
        empty_btn = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[normalize-space()='Create Your First Trip']")
            )
        )
        empty_btn.click()
        return
    except TimeoutException:
        pass

    raise TimeoutException("No create-trip button found (e2e or empty-state)")


# =============================================================================
# TESTS
# =============================================================================


def test_can_create_new_trip_and_navigate_to_chat(driver):
    """
    Verify that users can create a new trip and are navigated to the chat interface.

    This test covers the complete trip creation flow:
    1. Log in to the application
    2. Click the "Create New Trip" button
    3. Verify navigation to /trips/{id}/chat
    4. Verify chat page content loads

    Success criteria:
    - User successfully logs in
    - Create trip button is clickable
    - Navigation to chat page occurs within 20 seconds
    - Chat welcome content or UI elements are visible
    - URL contains both /trips/ and /chat

    Error handling:
    - If navigation fails, captures debug information including:
      * Current URL
      * Page source snippet
      * Presence of error toasts
    """
    login(driver)

    # Verify we're on the home page
    assert "Your Trips" in driver.page_source, "Should be on home page after login"

    # Click the create trip button
    click_create_trip(driver)

    # Wait for navigation to /trips/{id}/chat
    try:
        WebDriverWait(driver, 20).until(
            lambda d: "/trips/" in d.current_url and "/chat" in d.current_url
        )
    except TimeoutException:
        # Capture debug information if navigation fails
        print("\n\n===== DEBUG INFO: NAVIGATION FAILED =====")
        print(f"Current URL: {driver.current_url}")
        print(f"\nPage snippet (first 800 chars):")
        print(driver.page_source[:800])

        # Check for error toasts on the home page
        errors_found = []
        if "Failed to create new trip" in driver.page_source:
            errors_found.append("Failed to create new trip")
        if "Failed to load trips" in driver.page_source:
            errors_found.append("Failed to load trips")

        if errors_found:
            print("\n🔴 Error toast detected on page:")
            for e in errors_found:
                print(f" - {e}")
            print(
                "This indicates a backend API error (POST /api/trips or GET /api/trips) "
                "that prevented navigation from occurring."
            )
        else:
            print(
                "\n⚠️ No known error toast found. Possible causes:\n"
                "  - Click didn't trigger the createNewTrip function\n"
                "  - Different error message than expected\n"
                "  - JavaScript error preventing navigation"
            )

        print("=========================================\n\n")
        raise

    # Verify chat page content has loaded
    WebDriverWait(driver, 20).until(
        lambda d: (
            "Welcome to Your Trip Planning Journey" in d.page_source
            or "Planning Your Trip" in d.page_source
            or "Choose Your Destination" in d.page_source
        )
    )

    # Final assertions
    assert "/trips/" in driver.current_url, "URL should contain /trips/"
    assert "/chat" in driver.current_url, "URL should contain /chat"
