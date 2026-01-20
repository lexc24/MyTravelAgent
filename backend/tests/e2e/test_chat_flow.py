# tests/e2e/test_chat_flow.py

"""
End-to-end tests for the chat flow in the trip planning application.

These tests verify that users can:
1. Create a new trip and land on the chat page
2. Send messages in the chat interface
3. Interact with the AI-powered destination discovery system
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


def get_chat_textarea(driver):
    """
    Wait for the chat TextArea to appear and return it.

    This is the primary signal that the chat UI has loaded.
    Uses multiple strategies to handle Carbon Design System rendering.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        WebElement: The chat textarea element

    Raises:
        TimeoutException: If textarea cannot be found with any strategy
    """
    wait = WebDriverWait(driver, 30)

    # Strategy 1: Find by placeholder text
    try:
        text_area = wait.until(
            EC.visibility_of_element_located(
                (
                    By.XPATH,
                    "//textarea[contains(@placeholder, 'Describe your ideal vacation')"
                    " or contains(@placeholder, 'Type your answer')"
                    " or contains(@placeholder, 'Ask about the destinations')]",
                )
            )
        )
        return text_area
    except TimeoutException:
        pass

    # Strategy 2: Find by Carbon Design System class
    try:
        text_area = wait.until(
            EC.visibility_of_element_located(
                (By.XPATH, "//textarea[contains(@class, 'cds--text-area')]")
            )
        )
        return text_area
    except TimeoutException:
        pass

    # Strategy 3: Find any visible, enabled textarea
    try:
        textareas = driver.find_elements(By.TAG_NAME, "textarea")
        for ta in textareas:
            if ta.is_displayed() and ta.is_enabled():
                return ta
    except:
        pass

    # Strategy 4: Use JavaScript as last resort
    try:
        text_area = driver.execute_script(
            """
            const textareas = document.querySelectorAll('textarea');
            for (let ta of textareas) {
                if (ta.offsetParent !== null) {
                    return ta;
                }
            }
            return null;
        """
        )
        if text_area:
            return text_area
    except:
        pass

    raise TimeoutException("Could not find chat textarea with any strategy")


def send_message_in_chat(driver, message):
    """
    Type a message in the chat textarea and send it.

    Uses JavaScript to click the send button to avoid issues with
    Carbon Design System's icon-only button rendering.

    Args:
        driver: Selenium WebDriver instance
        message: The message text to send

    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    import time

    text_area = get_chat_textarea(driver)
    text_area.clear()
    text_area.send_keys(message)

    # Brief pause to ensure React state updates
    time.sleep(0.5)

    # Use JavaScript to find and click the enabled send button
    send_button = driver.execute_script(
        """
        const buttons = document.querySelectorAll('button.cds--btn--primary');
        for (let btn of buttons) {
            if (!btn.disabled && btn.offsetParent !== null) {
                return btn;
            }
        }
        return null;
    """
    )

    if send_button:
        driver.execute_script("arguments[0].click();", send_button)
        return True

    return False


def login_and_create_trip(driver):
    """
    Complete login and trip creation flow.

    This is a common setup for chat-related tests.

    Args:
        driver: Selenium WebDriver instance
    """
    login(driver)
    click_create_trip(driver)


# =============================================================================
# TESTS
# =============================================================================


def test_chat_page_loads_for_new_trip(driver):
    """
    Verify that creating a new trip navigates to the chat page
    and displays the chat interface correctly.

    Success criteria:
    - URL contains /trips/{id}/chat
    - Welcome content or chat UI is visible
    - Chat textarea is present and functional
    """
    login_and_create_trip(driver)

    # Wait for navigation to chat page
    WebDriverWait(driver, 20).until(
        lambda d: "/trips/" in d.current_url and "/chat" in d.current_url
    )

    # Wait for React to render key page elements
    WebDriverWait(driver, 30).until(
        lambda d: (
            "Welcome to Your Trip Planning Journey" in d.page_source
            or "Describe your ideal vacation" in d.page_source
            or "Planning Your Trip" in d.page_source
        )
    )

    # Verify chat textarea is present
    text_area = get_chat_textarea(driver)
    assert text_area is not None, "Chat textarea should be present"

    # Verify we're on the correct route
    assert "/trips/" in driver.current_url
    assert "/chat" in driver.current_url


def test_user_can_send_message_in_chat(driver):
    """
    Verify that users can send messages in the chat interface
    and see them appear in the conversation.

    Success criteria:
    - User can type a message in the textarea
    - User can click the send button
    - Message appears in the chat history
    """
    login_and_create_trip(driver)

    # Define test message
    test_message = "I want a warm beach vacation in July."

    # Send the message
    success = send_message_in_chat(driver, test_message)
    assert success, "Failed to send message"

    # Wait for message to appear in chat history
    # (Increased timeout for API response + rendering)
    WebDriverWait(driver, 60).until(lambda d: test_message in d.page_source)

    assert test_message in driver.page_source, "Message should appear in chat"
