# restaurants/tests/test_google_service.py
"""
Unit tests for Google Places API service.
All API calls are mocked - no real API hits.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
from django.test import TestCase
from food.google_api_service import GooglePlacesService
from food.tests.fixtures.google_api_responses import (
    MOCK_EMPTY_RESULTS,
    MOCK_GEOCODE_RESPONSE,
    MOCK_ITALIAN_RESTAURANTS,
    MOCK_JAPANESE_RESTAURANTS,
    MOCK_LOW_QUALITY_RESTAURANTS,
    MOCK_MEXICAN_RESTAURANTS,
    MOCK_REVIEWS,
)


class GooglePlacesServiceBasicTests(TestCase):
    """Test basic Google Places API service functionality"""

    def setUp(self):
        self.service = GooglePlacesService()

    @patch("food.google_api_service.googlemaps.Client")
    def test_service_initialization(self, mock_client):
        """Test that service initializes with Google Maps client"""
        service = GooglePlacesService()
        self.assertIsNotNone(service.client)

    def test_map_cuisine_to_search_term(self):
        """Test cuisine type mapping to Google search terms"""
        self.assertEqual(
            self.service._map_cuisine_to_search_term("italian"), "Italian restaurant"
        )
        self.assertEqual(
            self.service._map_cuisine_to_search_term("mexican"), "Mexican restaurant"
        )

        # Test with weird casing and whitespace
        self.assertEqual(
            self.service._map_cuisine_to_search_term("  iTaLiAn  "),
            "Italian restaurant",
        )


class GooglePlacesAPICallTests(TestCase):
    """Test actual API interaction (mocked)"""

    def setUp(self):
        self.service = GooglePlacesService()

    @patch("food.google_api_service.googlemaps.Client")
    def test_fetch_from_google_places_success(self, mock_client_class):
        """Test successful Google Places API call"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock geocode
        mock_client.geocode.return_value = MOCK_GEOCODE_RESPONSE

        # Mock places_nearby
        mock_client.places_nearby.return_value = MOCK_ITALIAN_RESTAURANTS

        service = GooglePlacesService()
        results = service._fetch_from_google_places(
            location="Paris, France", search_term="Italian restaurant"
        )

        self.assertEqual(len(results), 5)  # All results from mock data
        mock_client.geocode.assert_called_once_with("Paris, France")
        mock_client.places_nearby.assert_called_once()


@patch("food.google_api_service.googlemaps.Client")
def test_fetch_from_google_places_geocode_failure(self, mock_client_class):
    """Test handling of geocode failure"""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    # Mock geocode failure (empty result)
    mock_client.geocode.return_value = []

    service = GooglePlacesService()

    # The method catches ValueError internally and returns empty list
    results = service._fetch_from_google_places(
        location="Invalid Location", search_term="Italian restaurant"
    )

    # Should return empty list on geocode failure
    self.assertEqual(results, [])

    @patch("food.google_api_service.googlemaps.Client")
    def test_fetch_from_google_places_api_error(self, mock_client_class):
        """Test handling of API errors"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock API exception
        mock_client.geocode.side_effect = Exception("API Error")

        service = GooglePlacesService()
        results = service._fetch_from_google_places(
            location="Paris, France", search_term="Italian restaurant"
        )

        # Should return empty list on error
        self.assertEqual(results, [])


class DataNormalizationTests(TestCase):
    """Test converting API responses to DataFrames"""

    def setUp(self):
        self.service = GooglePlacesService()

    def test_normalize_google_response(self):
        """Test converting Google API response to DataFrame"""
        raw_results = MOCK_ITALIAN_RESTAURANTS["results"][:2]

        df = self.service._normalize_google_response(raw_results, "italian")

        # Check DataFrame structure
        self.assertEqual(len(df), 2)
        self.assertIn("google_place_id", df.columns)
        self.assertIn("name", df.columns)
        self.assertIn("address", df.columns)
        self.assertIn("cuisine_type", df.columns)
        self.assertIn("rating", df.columns)
        self.assertIn("maps_url", df.columns)

        # Check first restaurant data
        first_row = df.iloc[0]
        self.assertEqual(first_row["name"], "Trattoria Bella")
        self.assertEqual(first_row["cuisine_type"], "italian")
        self.assertEqual(first_row["rating"], 4.5)
        self.assertIn("place_id:ChIJ_italian_1", first_row["maps_url"])


def test_normalize_google_response_empty(self):
    """Test normalizing empty API response"""
    df = self.service._normalize_google_response([], "italian")

    # Should return empty DataFrame
    self.assertTrue(df.empty)
    self.assertEqual(len(df), 0)


class QualityFilteringTests(TestCase):
    """Test restaurant quality filtering logic"""

    def setUp(self):
        self.service = GooglePlacesService()

    def test_narrow_down_quality_filters(self):
        """Test that quality filters remove low-quality restaurants"""
        raw_results = MOCK_ITALIAN_RESTAURANTS["results"]
        df = self.service._normalize_google_response(raw_results, "italian")

        filtered_df = self.service._narrow_down(df)

        # Low quality restaurant should be filtered out
        self.assertNotIn(
            "ChIJ_italian_lowquality", filtered_df["google_place_id"].tolist()
        )

        # All remaining should meet quality thresholds
        for _, row in filtered_df.iterrows():
            self.assertGreaterEqual(row["user_ratings_total"], 200)
            self.assertGreaterEqual(row["rating"], 4.3)

    def test_narrow_down_sorting(self):
        """Test that results are sorted by rating then review count"""
        raw_results = MOCK_ITALIAN_RESTAURANTS["results"][:4]
        df = self.service._normalize_google_response(raw_results, "italian")

        filtered_df = self.service._narrow_down(df)

        # Should be sorted by rating (descending)
        ratings = filtered_df["rating"].tolist()
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_all_restaurants_filtered_out(self):
        """Test when all restaurants are below quality threshold"""
        raw_results = MOCK_LOW_QUALITY_RESTAURANTS["results"]
        df = self.service._normalize_google_response(raw_results, "italian")

        filtered_df = self.service._narrow_down(df)

        # Should return empty DataFrame
        self.assertTrue(filtered_df.empty)


class ReviewFetchingTests(TestCase):
    """Test fetching reviews for AI summaries"""

    def setUp(self):
        self.service = GooglePlacesService()

    @patch("food.google_api_service.googlemaps.Client")
    def test_get_reviews_for_summary(self, mock_client_class):
        """Test fetching reviews for AI summary generation"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock place details with reviews
        mock_client.place.return_value = MOCK_REVIEWS

        service = GooglePlacesService()
        reviews = service.get_reviews_for_summary("ChIJ_test_123")

        self.assertEqual(len(reviews), 3)
        self.assertIn("text", reviews[0])
        self.assertIn("rating", reviews[0])
        self.assertEqual(reviews[0]["rating"], 5)

        # Verify API was called with correct parameters
        mock_client.place.assert_called_once_with(
            place_id="ChIJ_test_123", fields=["reviews"]
        )

    @patch("food.google_api_service.googlemaps.Client")
    def test_get_reviews_for_summary_no_reviews(self, mock_client_class):
        """Test handling when place has no reviews"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock place details with no reviews
        mock_client.place.return_value = {"result": {}}

        service = GooglePlacesService()
        reviews = service.get_reviews_for_summary("ChIJ_test_123")

        self.assertEqual(reviews, [])

    @patch("food.google_api_service.googlemaps.Client")
    def test_get_reviews_api_error(self, mock_client_class):
        """Test handling of API error when fetching reviews"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock API exception
        mock_client.place.side_effect = Exception("API Error")

        service = GooglePlacesService()
        reviews = service.get_reviews_for_summary("ChIJ_test_123")

        # Should return empty list on error
        self.assertEqual(reviews, [])
