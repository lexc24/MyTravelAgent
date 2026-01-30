# restaurants/google_places_service.py
"""
Service for fetching and filtering restaurants using Google Places API.
Replaces the old Yelp-based Food class.
"""

from typing import Dict, List

import googlemaps
import pandas as pd
from django.conf import settings


class GooglePlacesService:
    """
    Handles Google Places API interactions for restaurant discovery.
    Fetches 4 restaurants per cuisine type (12 total for 3 cuisines).
    """

    def __init__(self):
        """Initialize Google Maps client"""
        self.client = googlemaps.Client(key=settings.GOOGLE_PLACES_API_KEY)

    def fetch_restaurants_for_trip(
        self, location: str, cuisine_types: List[str]
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch 4 restaurants for each cuisine type.

        Args:
            location: Destination location (e.g., "Paris, France")
            cuisine_types: List of up to 3 cuisine types (e.g., ["italian", "mexican", "japanese"])

        Returns:
            Dict mapping cuisine_type to DataFrame of restaurants

        Example:
            {
                "italian": DataFrame with 4 Italian restaurants,
                "mexican": DataFrame with 4 Mexican restaurants,
                "japanese": DataFrame with 4 Japanese restaurants
            }
        """
        results = {}

        for cuisine in cuisine_types:
            search_term = self._map_cuisine_to_search_term(cuisine)
            restaurants_df = self._search_restaurants(
                location=location,
                search_term=search_term,
                cuisine_type=cuisine,
                excluded_place_ids=[],  # No exclusions on initial fetch
            )
            results[cuisine] = restaurants_df

        return results

    def fetch_restaurants_excluding_previous(
        self, location: str, cuisine_type: str, excluded_place_ids: List[str]
    ) -> pd.DataFrame:
        """
        Fetch restaurants while excluding previously shown ones.
        Used for regeneration.

        Args:
            location: Destination location
            cuisine_type: Single cuisine type to search
            excluded_place_ids: List of place_ids to exclude

        Returns:
            DataFrame with 4 new restaurants
        """
        search_term = self._map_cuisine_to_search_term(cuisine_type)
        return self._search_restaurants(
            location=location,
            search_term=search_term,
            cuisine_type=cuisine_type,
            excluded_place_ids=excluded_place_ids,
        )

    def _map_cuisine_to_search_term(self, cuisine_type: str) -> str:
        """
        Map user input to Google Places search term.

        Args:
            cuisine_type: User's cuisine selection (e.g., "italian")

        Returns:
            Google Places search term (e.g., "Italian restaurant")
        """
        return f"{cuisine_type.strip().title()} restaurant"

    def _search_restaurants(
        self,
        location: str,
        search_term: str,
        cuisine_type: str,
        excluded_place_ids: List[str],
    ) -> pd.DataFrame:
        """
        Search for restaurants and return filtered, processed DataFrame.

        Args:
            location: Search location
            search_term: Google Places query (e.g., "Italian restaurant")
            cuisine_type: Original cuisine type for tracking
            excluded_place_ids: Place IDs to exclude

        Returns:
            DataFrame with top 4 high-quality restaurants
        """
        # Step 1: Fetch initial results from Google Places
        raw_results = self._fetch_from_google_places(location, search_term)

        # Step 2: Convert to DataFrame
        df = self._normalize_google_response(raw_results, cuisine_type)

        # Step 3: Exclude previously shown restaurants
        if excluded_place_ids:
            df = df[~df["google_place_id"].isin(excluded_place_ids)]

        # Step 4: Apply quality filters
        filtered_df = self._narrow_down(df)

        # Step 5: Return top 4 results
        return filtered_df.head(4)

    def _fetch_from_google_places(self, location: str, search_term: str) -> List[Dict]:
        """
        Query Google Places API using Nearby Search.

        Args:
            location: Location string (e.g., "Paris, France")
            search_term: Search query (e.g., "Italian restaurant")

        Returns:
            List of place dictionaries from Google Places API
        """
        try:
            # Geocode the location to get lat/lng
            geocode_result = self.client.geocode(location)
            if not geocode_result:
                raise ValueError(f"Could not geocode location: {location}")

            lat_lng = geocode_result[0]["geometry"]["location"]

            # Perform Nearby Search
            places_result = self.client.places_nearby(
                location=lat_lng,
                keyword=search_term,
                rank_by="prominence",
                type="restaurant",
                open_now=False,
            )

            return places_result.get("results", [])

        except Exception as e:
            print(f"Error fetching from Google Places: {e}")
            return []

    def _normalize_google_response(
        self, raw_results: List[Dict], cuisine_type: str
    ) -> pd.DataFrame:
        """
        Convert Google Places API response to structured DataFrame.

        Args:
            raw_results: Raw results from Google Places API
            cuisine_type: Cuisine type being searched

        Returns:
            DataFrame with normalized restaurant data
        """
        restaurants = []

        for place in raw_results:
            place_id = place.get("place_id")

            # Generate Google Maps URL from place_id
            maps_url = (
                f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                if place_id
                else ""
            )

            restaurant = {
                "google_place_id": place_id,
                "name": place.get("name"),
                "address": place.get("vicinity", ""),
                "cuisine_type": cuisine_type,
                "rating": place.get("rating"),
                "user_ratings_total": place.get("user_ratings_total", 0),
                "price_level": place.get("price_level"),
                "lat": place.get("geometry", {}).get("location", {}).get("lat"),
                "lng": place.get("geometry", {}).get("location", {}).get("lng"),
                "maps_url": maps_url,
            }
            restaurants.append(restaurant)

        return pd.DataFrame(restaurants)

    def _narrow_down(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter restaurants using stricter thresholds.

        Trust Google's aggregate rating but set high standards:
        - At least 200 reviews (shows consistency)
        - Rating of 4.3+ (top tier)

        Args:
            df: DataFrame with restaurant data

        Returns:
            Filtered DataFrame of high-quality restaurants
        """
        if df.empty:
            return df

        # Remove restaurants with missing critical data
        df = df.dropna(subset=["rating", "user_ratings_total"])

        # Apply quality filters
        filtered_df = df[(df["user_ratings_total"] >= 200) & (df["rating"] >= 4.3)]

        # Sort by rating (descending), then by review count (descending)
        filtered_df = filtered_df.sort_values(
            by=["rating", "user_ratings_total"], ascending=[False, False]
        )

        return filtered_df

    def get_reviews_for_summary(self, place_id: str) -> List[Dict]:
        """
        Fetch only the reviews for AI summary generation.
        Minimal API usage - only gets what we need.

        Args:
            place_id: Google Place ID

        Returns:
            List of review dictionaries with text and rating
        """
        try:
            place_details = self.client.place(
                place_id=place_id, fields=["reviews"]  # Only fetch reviews
            )

            reviews = place_details.get("result", {}).get("reviews", [])

            # Extract only text and rating
            return [
                {"text": review.get("text", ""), "rating": review.get("rating", 0)}
                for review in reviews
            ]

        except Exception as e:
            print(f"Error fetching reviews: {e}")
            return []
