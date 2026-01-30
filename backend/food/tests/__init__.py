"""
Test suite for restaurant discovery system.

Structure:
- test_models.py: Restaurant and TripRestaurant model tests
- test_google_service.py: Google Places API service tests (all mocked)
- test_critical_bugs.py: Critical edge cases that could cause production bugs
- fixtures/: Mock data for consistent, fast tests

Run all tests:
    python manage.py test restaurants

Run specific test file:
    python manage.py test restaurants.tests.test_models
    python manage.py test restaurants.tests.test_critical_bugs

Run with coverage:
    coverage run --source='restaurants' manage.py test restaurants
    coverage report
"""
