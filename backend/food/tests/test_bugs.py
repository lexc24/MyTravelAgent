"""
Tests for edge cases that could cause REAL BUGS in production.
These scenarios must work correctly to avoid data loss and user frustration.
"""

from unittest.mock import patch

from api.models import Destination, Trip
from django.contrib.auth.models import User
from django.test import TestCase
from food.models import Restaurant, TripRestaurant
from food.restaurant_manager import RestaurantManager
from food.tests.fixtures.test_data import create_mock_restaurant_df


class SelectionPreservationTests(TestCase):
    """
    🚨 CRITICAL: Test that user selections are NEVER lost during regeneration.
    This is the most important bug to prevent!
    """

    def setUp(self):
        self.user = User.objects.create_user("testuser", "test@test.com", "pass")
        self.destination = Destination.objects.create(name="Paris", country="France")
        self.trip = Trip.objects.create(
            user=self.user, title="Paris Vacation", destination=self.destination
        )
        self.manager = RestaurantManager()

    @patch.object(RestaurantManager, "_get_trip_location")
    def test_regenerate_preserves_user_selections(self, mock_location):
        """
        CRITICAL: User selects a restaurant, then regenerates that cuisine.
        The selected restaurant MUST remain in the database.
        """
        mock_location.return_value = "Paris, France"

        # Create initial restaurants
        initial_restaurants = []
        for i in range(4):
            restaurant = Restaurant.objects.create(
                name=f"Initial Italian {i}",
                address=f"{i} Test St",
                cuisine_type="italian",
                google_place_id=f"ChIJ_initial_{i}",
                rating=4.5,
                user_ratings_total=250,
            )
            TripRestaurant.objects.create(
                trip=self.trip,
                restaurant=restaurant,
                cuisine_search_type="italian",
                is_selected=False,
                search_batch=1,
            )
            initial_restaurants.append(restaurant)

        # USER SELECTS ONE RESTAURANT
        selected_restaurant = initial_restaurants[1]
        self.manager.mark_restaurant_selected(
            trip=self.trip, restaurant=selected_restaurant, selected=True
        )

        # Verify it's selected
        trip_rest = TripRestaurant.objects.get(
            trip=self.trip, restaurant=selected_restaurant
        )
        self.assertTrue(trip_rest.is_selected)

        # Now regenerate Italian cuisine
        with patch(
            "food.google_api_service.GooglePlacesService.fetch_restaurants_excluding_previous"
        ) as mock_fetch:
            new_df = create_mock_restaurant_df("italian", count=4, prefix="regen")
            mock_fetch.return_value = new_df

            new_restaurants = self.manager.regenerate_cuisine_restaurants(
                trip=self.trip, cuisine_type="italian"
            )

        # CRITICAL CHECKS:
        # 1. Selected restaurant link MUST still exist
        self.assertTrue(
            TripRestaurant.objects.filter(
                trip=self.trip, restaurant=selected_restaurant, is_selected=True
            ).exists(),
            "🚨 BUG: User's selected restaurant was deleted during regeneration!",
        )

        # 2. Unselected initial restaurants SHOULD be deleted
        unselected_count = TripRestaurant.objects.filter(
            trip=self.trip,
            restaurant__in=[r for r in initial_restaurants if r != selected_restaurant],
            is_selected=False,
        ).count()
        self.assertEqual(
            unselected_count, 0, "Unselected restaurants should be removed"
        )

        # 3. New restaurants should be added
        self.assertEqual(len(new_restaurants), 4)

        # 4. Total Italian restaurants should be 5 (1 selected + 4 new)
        total_italian = TripRestaurant.objects.filter(
            trip=self.trip, cuisine_search_type="italian"
        ).count()
        self.assertEqual(total_italian, 5)

    @patch.object(RestaurantManager, "_get_trip_location")
    def test_regenerate_multiple_times_preserves_all_selections(self, mock_location):
        """
        User selects restaurants, regenerates, selects more, regenerates again.
        ALL selections must be preserved throughout.
        """
        mock_location.return_value = "Paris, France"

        # Initial load
        initial_restaurants = []
        for i in range(4):
            restaurant = Restaurant.objects.create(
                name=f"Initial {i}",
                address="Test",
                cuisine_type="italian",
                google_place_id=f"ChIJ_initial_{i}",
                rating=4.5,
                user_ratings_total=250,
            )
            TripRestaurant.objects.create(
                trip=self.trip,
                restaurant=restaurant,
                cuisine_search_type="italian",
                is_selected=False,
                search_batch=1,
            )
            initial_restaurants.append(restaurant)

        # User selects first restaurant
        selected_restaurant_1 = initial_restaurants[0]
        self.manager.mark_restaurant_selected(self.trip, selected_restaurant_1, True)

        # First regeneration
        with patch(
            "food.google_api_service.GooglePlacesService.fetch_restaurants_excluding_previous"
        ) as mock_fetch:
            df1 = create_mock_restaurant_df("italian", count=4, prefix="regen1")
            mock_fetch.return_value = df1
            regen1_restaurants = self.manager.regenerate_cuisine_restaurants(
                self.trip, "italian"
            )

        # User selects from regenerated batch
        selected_restaurant_2 = regen1_restaurants[1]
        self.manager.mark_restaurant_selected(self.trip, selected_restaurant_2, True)

        # Second regeneration
        with patch(
            "food.google_api_service.GooglePlacesService.fetch_restaurants_excluding_previous"
        ) as mock_fetch:
            df2 = create_mock_restaurant_df("italian", count=4, prefix="regen2")
            mock_fetch.return_value = df2
            regen2_restaurants = self.manager.regenerate_cuisine_restaurants(
                self.trip, "italian"
            )

        # BOTH selected restaurants must still exist
        self.assertTrue(
            TripRestaurant.objects.filter(
                trip=self.trip, restaurant=selected_restaurant_1, is_selected=True
            ).exists(),
            "First selection was lost!",
        )

        self.assertTrue(
            TripRestaurant.objects.filter(
                trip=self.trip, restaurant=selected_restaurant_2, is_selected=True
            ).exists(),
            "Second selection was lost!",
        )

        # Total: 2 selected + 4 new = 6
        total = TripRestaurant.objects.filter(
            trip=self.trip, cuisine_search_type="italian"
        ).count()
        self.assertEqual(total, 6)

    def test_regenerate_different_cuisine_doesnt_affect_other_cuisines(self):
        """
        User has selected Italian restaurants, then regenerates Mexican.
        Italian selections must not be affected.
        """
        # Create Italian restaurants with selections
        italian_restaurant = Restaurant.objects.create(
            name="Selected Italian",
            address="Test",
            cuisine_type="italian",
            google_place_id="ChIJ_italian_selected",
            rating=4.5,
            user_ratings_total=250,
        )
        TripRestaurant.objects.create(
            trip=self.trip,
            restaurant=italian_restaurant,
            cuisine_search_type="italian",
            is_selected=True,
        )

        # Create Mexican restaurants
        for i in range(4):
            restaurant = Restaurant.objects.create(
                name=f"Mexican {i}",
                address="Test",
                cuisine_type="mexican",
                google_place_id=f"ChIJ_mexican_{i}",
                rating=4.5,
                user_ratings_total=250,
            )
            TripRestaurant.objects.create(
                trip=self.trip,
                restaurant=restaurant,
                cuisine_search_type="mexican",
                is_selected=False,
            )

        # Regenerate Mexican
        with patch(
            "food.google_api_service.GooglePlacesService.fetch_restaurants_excluding_previous"
        ) as mock_fetch:
            with patch.object(
                self.manager, "_get_trip_location", return_value="Paris, France"
            ):
                df = create_mock_restaurant_df("mexican", count=4, prefix="regen")
                mock_fetch.return_value = df
                self.manager.regenerate_cuisine_restaurants(self.trip, "mexican")

        # Italian selection must still be there
        self.assertTrue(
            TripRestaurant.objects.filter(
                trip=self.trip, restaurant=italian_restaurant, is_selected=True
            ).exists(),
            "Italian selection was affected by Mexican regeneration!",
        )


class FinalizationWorkflowTests(TestCase):
    """
    Test that finalization works correctly and doesn't break workflow.
    """

    def setUp(self):
        self.user = User.objects.create_user("testuser", "test@test.com", "pass")
        self.destination = Destination.objects.create(name="Paris", country="France")
        self.trip = Trip.objects.create(
            user=self.user, title="Paris Vacation", destination=self.destination
        )
        self.manager = RestaurantManager()

    def test_finalize_removes_only_unselected(self):
        """
        After finalization, only selected restaurants remain.
        """
        # Create 6 restaurants (3 selected, 3 not)
        selected_restaurants = []
        unselected_restaurants = []

        for i in range(6):
            restaurant = Restaurant.objects.create(
                name=f"Restaurant {i}",
                address="Test",
                cuisine_type="italian",
                google_place_id=f"ChIJ_{i}",
                rating=4.5,
                user_ratings_total=250,
            )

            is_selected = i % 2 == 0  # Select every other one
            TripRestaurant.objects.create(
                trip=self.trip,
                restaurant=restaurant,
                cuisine_search_type="italian",
                is_selected=is_selected,
            )

            if is_selected:
                selected_restaurants.append(restaurant)
            else:
                unselected_restaurants.append(restaurant)

        # Finalize
        final_restaurants = self.manager.finalize_selections(self.trip)

        # Check correct count
        self.assertEqual(len(final_restaurants), 3)

        # All selected should remain
        for restaurant in selected_restaurants:
            self.assertIn(restaurant, final_restaurants)

        # All unselected should be gone
        for restaurant in unselected_restaurants:
            self.assertFalse(
                TripRestaurant.objects.filter(
                    trip=self.trip, restaurant=restaurant
                ).exists()
            )

    def test_finalize_with_no_selections_leaves_nothing(self):
        """
        If user didn't select anything and finalizes, result is empty.
        """
        # Create restaurants but don't select any
        for i in range(4):
            restaurant = Restaurant.objects.create(
                name=f"Restaurant {i}",
                address="Test",
                cuisine_type="italian",
                google_place_id=f"ChIJ_{i}",
                rating=4.5,
                user_ratings_total=250,
            )
            TripRestaurant.objects.create(
                trip=self.trip,
                restaurant=restaurant,
                cuisine_search_type="italian",
                is_selected=False,
            )

        # Finalize
        final_restaurants = self.manager.finalize_selections(self.trip)

        # Should be empty
        self.assertEqual(len(final_restaurants), 0)
        self.assertEqual(TripRestaurant.objects.filter(trip=self.trip).count(), 0)


class MultiUserIsolationTests(TestCase):
    """
    Test that multiple users don't interfere with each other.
    """

    def setUp(self):
        self.user1 = User.objects.create_user("user1", "user1@test.com", "pass")
        self.user2 = User.objects.create_user("user2", "user2@test.com", "pass")
        self.destination = Destination.objects.create(name="Paris", country="France")
        self.trip1 = Trip.objects.create(
            user=self.user1, title="User 1 Trip", destination=self.destination
        )
        self.trip2 = Trip.objects.create(
            user=self.user2, title="User 2 Trip", destination=self.destination
        )
        self.manager = RestaurantManager()

    def test_user_deletion_doesnt_affect_shared_restaurants(self):
        """
        If two users have the same restaurant, deleting one user's trip
        doesn't delete the restaurant.
        """
        # Create shared restaurant
        shared_restaurant = Restaurant.objects.create(
            name="Shared Restaurant",
            address="Test",
            cuisine_type="italian",
            google_place_id="ChIJ_shared",
            rating=4.5,
            user_ratings_total=250,
        )

        # Link to both trips
        TripRestaurant.objects.create(
            trip=self.trip1, restaurant=shared_restaurant, cuisine_search_type="italian"
        )
        TripRestaurant.objects.create(
            trip=self.trip2, restaurant=shared_restaurant, cuisine_search_type="italian"
        )

        # User 1 deletes their trip
        self.trip1.delete()

        # Restaurant should still exist
        self.assertTrue(
            Restaurant.objects.filter(google_place_id="ChIJ_shared").exists(),
            "Shared restaurant was deleted when it shouldn't be!",
        )

        # User 2's link should still exist
        self.assertTrue(
            TripRestaurant.objects.filter(
                trip=self.trip2, restaurant=shared_restaurant
            ).exists()
        )


class EmptyResultsHandlingTests(TestCase):
    """
    Test handling when API returns no results or all are filtered.
    """

    def setUp(self):
        self.user = User.objects.create_user("testuser", "test@test.com", "pass")
        self.destination = Destination.objects.create(name="Paris", country="France")
        self.trip = Trip.objects.create(
            user=self.user, title="Test Trip", destination=self.destination
        )
        self.manager = RestaurantManager()

    @patch(
        "food.google_api_service.GooglePlacesService.fetch_restaurants_excluding_previous"
    )
    @patch.object(RestaurantManager, "_get_trip_location")
    def test_regenerate_with_no_new_results(self, mock_location, mock_fetch):
        """
        If regeneration returns no results (all filtered or exhausted),
        handle gracefully.
        """
        mock_location.return_value = "Paris, France"

        # Create initial restaurants
        for i in range(4):
            restaurant = Restaurant.objects.create(
                name=f"Restaurant {i}",
                address="Test",
                cuisine_type="italian",
                google_place_id=f"ChIJ_{i}",
                rating=4.5,
                user_ratings_total=250,
            )
            TripRestaurant.objects.create(
                trip=self.trip,
                restaurant=restaurant,
                cuisine_search_type="italian",
                is_selected=False,
            )

        # Mock empty results
        import pandas as pd

        mock_fetch.return_value = pd.DataFrame()

        # Regenerate
        new_restaurants = self.manager.regenerate_cuisine_restaurants(
            self.trip, "italian"
        )

        # Should handle gracefully - return empty list
        self.assertEqual(len(new_restaurants), 0)

        # Should still delete old unselected ones
        self.assertEqual(
            TripRestaurant.objects.filter(
                trip=self.trip, cuisine_search_type="italian"
            ).count(),
            0,
        )
