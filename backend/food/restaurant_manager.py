# restaurants/restaurant_manager.py
"""
Manages restaurant fetching, storage, and lifecycle for trips.
FIXED: Preserves user selections during regeneration.
"""

from typing import Dict, List

from api.models import Trip
from django.db import models, transaction

from .google_api_service import GooglePlacesService
from .models import Restaurant, TripRestaurant


class RestaurantManager:
    """
    High-level service for managing restaurant discovery workflow.
    """

    def __init__(self):
        self.places_service = GooglePlacesService()

    @transaction.atomic
    def fetch_and_load_restaurants(
        self, trip: Trip, cuisine_types: List[str]
    ) -> Dict[str, List[Restaurant]]:
        """
        Fetch 4 restaurants per cuisine (12 total) and load into database.
        Links them to the trip with is_selected=False.

        Args:
            trip: Trip instance
            cuisine_types: List of 3 cuisine types (e.g., ["italian", "mexican", "japanese"])

        Returns:
            Dict mapping cuisine_type to list of Restaurant objects
        """
        if len(cuisine_types) != 3:
            raise ValueError("Must provide exactly 3 cuisine types")

        # Get destination location from trip
        destination = self._get_trip_location(trip)

        # Fetch restaurants from Google Places (no exclusions on initial fetch)
        restaurants_by_cuisine = self.places_service.fetch_restaurants_for_trip(
            location=destination, cuisine_types=cuisine_types
        )

        # Save to database and link to trip
        saved_restaurants = {}

        for cuisine_type, df in restaurants_by_cuisine.items():
            cuisine_restaurants = []

            for _, row in df.iterrows():
                restaurant = self._save_or_update_restaurant(row)

                # Link to trip (not selected by default)
                TripRestaurant.objects.create(
                    trip=trip,
                    restaurant=restaurant,
                    cuisine_search_type=cuisine_type,
                    is_selected=False,
                    search_batch=1,
                )

                cuisine_restaurants.append(restaurant)

            saved_restaurants[cuisine_type] = cuisine_restaurants

        return saved_restaurants

    @transaction.atomic
    def regenerate_cuisine_restaurants(
        self, trip: Trip, cuisine_type: str
    ) -> List[Restaurant]:
        """
        Delete old UNSELECTED results for this cuisine and fetch 4 new ones.
        PRESERVES user selections - selected restaurants are kept.
        Excludes previously shown restaurants.

        Args:
            trip: Trip instance
            cuisine_type: Which cuisine to regenerate (e.g., "italian")

        Returns:
            List of new Restaurant objects
        """
        # Get all place_ids previously shown for this trip and cuisine
        excluded_place_ids = list(
            TripRestaurant.objects.filter(
                trip=trip, cuisine_search_type=cuisine_type
            ).values_list("restaurant__google_place_id", flat=True)
        )

        # Delete only UNSELECTED associations for this cuisine
        # CRITICAL: Keep selected restaurants!
        TripRestaurant.objects.filter(
            trip=trip,
            cuisine_search_type=cuisine_type,
            is_selected=False,  # Only delete unselected ones
        ).delete()

        # Get destination location
        destination = self._get_trip_location(trip)

        # Fetch new restaurants excluding previously shown ones
        df = self.places_service.fetch_restaurants_excluding_previous(
            location=destination,
            cuisine_type=cuisine_type,
            excluded_place_ids=excluded_place_ids,
        )

        # Get the latest batch number for this cuisine
        latest_batch = (
            TripRestaurant.objects.filter(
                trip=trip, cuisine_search_type=cuisine_type
            ).aggregate(models.Max("search_batch"))["search_batch__max"]
            or 0
        )

        new_batch = latest_batch + 1

        # Save new restaurants and link to trip
        new_restaurants = []

        if not df.empty:
            for _, row in df.iterrows():
                restaurant = self._save_or_update_restaurant(row)

                TripRestaurant.objects.create(
                    trip=trip,
                    restaurant=restaurant,
                    cuisine_search_type=cuisine_type,
                    is_selected=False,
                    search_batch=new_batch,
                )

                new_restaurants.append(restaurant)

        return new_restaurants

    @transaction.atomic
    def finalize_selections(self, trip: Trip) -> List[Restaurant]:
        """
        Delete all restaurants where is_selected=False for this trip.
        Keep only user's chosen restaurants.

        Args:
            trip: Trip instance

        Returns:
            List of selected Restaurant objects
        """
        # Get all selected restaurants for this trip
        selected_restaurants = Restaurant.objects.filter(
            trip_associations__trip=trip, trip_associations__is_selected=True
        ).distinct()

        # Delete associations for non-selected restaurants
        TripRestaurant.objects.filter(trip=trip, is_selected=False).delete()

        # Optionally: Clean up orphaned Restaurant objects
        self._cleanup_orphaned_restaurants()

        return list(selected_restaurants)

    def mark_restaurant_selected(
        self, trip: Trip, restaurant: Restaurant, selected: bool = True
    ):
        """
        Mark a restaurant as selected or unselected by the user.

        Args:
            trip: Trip instance
            restaurant: Restaurant instance
            selected: Whether to mark as selected (default True)
        """
        TripRestaurant.objects.filter(trip=trip, restaurant=restaurant).update(
            is_selected=selected
        )

    def get_selected_restaurants(self, trip: Trip) -> List[Restaurant]:
        """
        Get all restaurants the user has selected for this trip.

        Args:
            trip: Trip instance

        Returns:
            List of selected Restaurant objects
        """
        return list(
            Restaurant.objects.filter(
                trip_associations__trip=trip, trip_associations__is_selected=True
            ).distinct()
        )

    def get_unselected_restaurants_by_cuisine(
        self, trip: Trip, cuisine_type: str
    ) -> List[Restaurant]:
        """
        Get unselected restaurants for a specific cuisine.
        Useful for displaying current options to user.

        Args:
            trip: Trip instance
            cuisine_type: Cuisine type (e.g., "italian")

        Returns:
            List of unselected Restaurant objects
        """
        return list(
            Restaurant.objects.filter(
                trip_associations__trip=trip,
                trip_associations__cuisine_search_type=cuisine_type,
                trip_associations__is_selected=False,
            )
        )

    def _save_or_update_restaurant(self, row) -> Restaurant:
        """
        Create or update Restaurant from DataFrame row.

        Args:
            row: Pandas Series with restaurant data

        Returns:
            Restaurant instance
        """
        restaurant, created = Restaurant.objects.update_or_create(
            google_place_id=row["google_place_id"],
            defaults={
                "name": row["name"],
                "address": row["address"],
                "cuisine_type": row["cuisine_type"],
                "rating": row["rating"],
                "user_ratings_total": row["user_ratings_total"],
                "price_level": row["price_level"],
                "latitude": row["lat"],
                "longitude": row["lng"],
                "maps_url": row["maps_url"],
            },
        )

        return restaurant

    def _get_trip_location(self, trip: Trip) -> str:
        """
        Extract location string from trip's destination.

        Args:
            trip: Trip instance

        Returns:
            Location string for Google Places API
        """
        if trip.destination:
            return f"{trip.destination.name}, {trip.destination.country}"
        else:
            raise ValueError(f"Trip {trip.id} has no destination set")

    def _cleanup_orphaned_restaurants(self):
        """
        Delete Restaurant objects that aren't associated with any trip.
        Run this periodically to keep database clean.
        """
        Restaurant.objects.filter(trip_associations__isnull=True).delete()
