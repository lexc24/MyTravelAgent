# restaurants/tests/test_models.py
"""
Unit tests for Restaurant and TripRestaurant models.
Uses fixtures for fast, consistent test data.
"""

from decimal import Decimal

from api.models import Destination, Trip
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from food.models import Restaurant, TripRestaurant


class RestaurantModelTests(TestCase):
    """Test Restaurant model"""

    def test_restaurant_creation(self):
        """Test creating a restaurant with all fields"""
        restaurant = Restaurant.objects.create(
            name="Test Restaurant",
            address="123 Test St, Test City",
            cuisine_type="italian",
            rating=4.5,
            user_ratings_total=250,
            price_level=2,
            latitude=48.8566,
            longitude=2.3522,
            google_place_id="ChIJ_test_123",
            maps_url="https://maps.google.com/?cid=123",
        )

        self.assertIsNotNone(restaurant)
        self.assertEqual(restaurant.name, "Test Restaurant")
        self.assertEqual(restaurant.cuisine_type, "italian")
        self.assertEqual(restaurant.rating, Decimal("4.5"))
        self.assertEqual(restaurant.google_place_id, "ChIJ_test_123")

    def test_restaurant_string_representation(self):
        """Test __str__ method"""
        restaurant = Restaurant.objects.create(
            name="Pasta Palace",
            cuisine_type="italian",
            address="Test Address",
            google_place_id="ChIJ_test_456",
        )

        self.assertEqual(str(restaurant), "Pasta Palace - italian")

    def test_restaurant_unique_place_id(self):
        """Test that google_place_id must be unique"""
        Restaurant.objects.create(
            name="First Restaurant",
            address="123 St",
            cuisine_type="italian",
            google_place_id="ChIJ_duplicate",
        )

        with self.assertRaises(IntegrityError):
            Restaurant.objects.create(
                name="Second Restaurant",
                address="456 Ave",
                cuisine_type="mexican",
                google_place_id="ChIJ_duplicate",  # Duplicate!
            )

    def test_get_price_display_symbol(self):
        """Test price level symbol display"""
        test_cases = [(1, "$"), (2, "$$"), (3, "$$$"), (4, "$$$$"), (None, "N/A")]

        for price_level, expected_symbol in test_cases:
            restaurant = Restaurant.objects.create(
                name=f"Restaurant {price_level}",
                address="Test",
                cuisine_type="italian",
                google_place_id=f"ChIJ_{price_level}",
                price_level=price_level,
            )
            self.assertEqual(restaurant.get_price_display_symbol(), expected_symbol)

    def test_restaurant_ordering(self):
        """Test restaurants are ordered by rating desc, then name"""
        r1 = Restaurant.objects.create(
            name="B Restaurant",
            address="Test",
            cuisine_type="italian",
            google_place_id="ChIJ_1",
            rating=4.5,
        )
        r2 = Restaurant.objects.create(
            name="A Restaurant",
            address="Test",
            cuisine_type="italian",
            google_place_id="ChIJ_2",
            rating=4.5,
        )
        r3 = Restaurant.objects.create(
            name="C Restaurant",
            address="Test",
            cuisine_type="italian",
            google_place_id="ChIJ_3",
            rating=4.8,
        )

        restaurants = list(Restaurant.objects.all())
        self.assertEqual(restaurants[0], r3)  # Highest rating first
        self.assertEqual(restaurants[1], r2)  # Then alphabetically
        self.assertEqual(restaurants[2], r1)

    def test_restaurant_optional_fields(self):
        """Test that optional fields can be null/blank"""
        restaurant = Restaurant.objects.create(
            name="Minimal Restaurant",
            address="Test Address",
            cuisine_type="italian",
            google_place_id="ChIJ_minimal",
        )

        self.assertIsNone(restaurant.rating)
        self.assertEqual(restaurant.user_ratings_total, 0)
        self.assertIsNone(restaurant.price_level)
        self.assertIsNone(restaurant.latitude)
        self.assertIsNone(restaurant.longitude)
        self.assertEqual(restaurant.maps_url, "")
        self.assertEqual(restaurant.summary, "")


class TripRestaurantModelTests(TestCase):
    """Test TripRestaurant linking model"""

    def setUp(self):
        self.user = User.objects.create_user("testuser", "test@test.com", "pass")
        self.destination = Destination.objects.create(name="Paris", country="France")
        self.trip = Trip.objects.create(
            user=self.user, title="Paris Vacation", destination=self.destination
        )
        self.restaurant = Restaurant.objects.create(
            name="Test Restaurant",
            address="123 Test St",
            cuisine_type="italian",
            google_place_id="ChIJ_test",
        )

    def test_trip_restaurant_creation(self):
        """Test creating a trip-restaurant link"""
        trip_restaurant = TripRestaurant.objects.create(
            trip=self.trip,
            restaurant=self.restaurant,
            cuisine_search_type="italian",
            is_selected=False,
            search_batch=1,
        )

        self.assertIsNotNone(trip_restaurant)
        self.assertEqual(trip_restaurant.trip, self.trip)
        self.assertEqual(trip_restaurant.restaurant, self.restaurant)
        self.assertFalse(trip_restaurant.is_selected)
        self.assertEqual(trip_restaurant.search_batch, 1)

    def test_trip_restaurant_string_representation(self):
        """Test __str__ method"""
        trip_restaurant = TripRestaurant.objects.create(
            trip=self.trip,
            restaurant=self.restaurant,
            cuisine_search_type="italian",
            is_selected=False,
        )

        expected = "Test Restaurant - Paris Vacation (Pending)"
        self.assertEqual(str(trip_restaurant), expected)

        trip_restaurant.is_selected = True
        trip_restaurant.save()
        expected = "Test Restaurant - Paris Vacation (Selected)"
        self.assertEqual(str(trip_restaurant), expected)

    def test_unique_together_constraint(self):
        """Test that trip + restaurant + cuisine_type must be unique"""
        TripRestaurant.objects.create(
            trip=self.trip,
            restaurant=self.restaurant,
            cuisine_search_type="italian",
            is_selected=False,
        )

        with self.assertRaises(IntegrityError):
            TripRestaurant.objects.create(
                trip=self.trip,
                restaurant=self.restaurant,
                cuisine_search_type="italian",  # Same combination!
                is_selected=True,
            )

    def test_same_restaurant_different_cuisines(self):
        """Test same restaurant can be linked for different cuisine searches"""
        TripRestaurant.objects.create(
            trip=self.trip,
            restaurant=self.restaurant,
            cuisine_search_type="italian",
            is_selected=False,
        )

        # Should succeed with different cuisine_search_type
        trip_restaurant2 = TripRestaurant.objects.create(
            trip=self.trip,
            restaurant=self.restaurant,
            cuisine_search_type="mediterranean",
            is_selected=False,
        )

        self.assertIsNotNone(trip_restaurant2)

    def test_cascading_deletes(self):
        """Test that deleting trip or restaurant cascades properly"""
        trip_restaurant = TripRestaurant.objects.create(
            trip=self.trip, restaurant=self.restaurant, cuisine_search_type="italian"
        )

        # Delete trip - should delete TripRestaurant
        trip_id = self.trip.id
        self.trip.delete()
        self.assertFalse(TripRestaurant.objects.filter(id=trip_restaurant.id).exists())

        # Recreate for next test
        trip2 = Trip.objects.create(
            user=self.user, title="New Trip", destination=self.destination
        )
        restaurant2 = Restaurant.objects.create(
            name="Restaurant 2",
            address="456 Ave",
            cuisine_type="mexican",
            google_place_id="ChIJ_test2",
        )
        trip_restaurant2 = TripRestaurant.objects.create(
            trip=trip2, restaurant=restaurant2, cuisine_search_type="mexican"
        )

        # Delete restaurant - should delete TripRestaurant
        restaurant2.delete()
        self.assertFalse(TripRestaurant.objects.filter(id=trip_restaurant2.id).exists())
