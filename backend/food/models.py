# restaurants/models.py
from api.models import Trip
from django.contrib.auth.models import User
from django.db import models


class Restaurant(models.Model):
    """
    Represents a restaurant with AI-generated summary from reviews.
    """

    PRICE_LEVEL_CHOICES = [
        (1, "$"),  # Inexpensive
        (2, "$$"),  # Moderate
        (3, "$$$"),  # Expensive
        (4, "$$$$"),  # Very Expensive
    ]

    # Core restaurant info
    name = models.CharField(max_length=255)
    address = models.TextField()
    cuisine_type = models.CharField(
        max_length=100,
        help_text="Cuisine type from search (e.g., 'Italian', 'Mexican')",
    )

    # Rating and pricing
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Average rating (0.0 - 5.0)",
    )
    user_ratings_total = models.IntegerField(
        default=0, help_text="Total number of reviews"
    )
    price_level = models.IntegerField(
        choices=PRICE_LEVEL_CHOICES,
        null=True,
        blank=True,
        help_text="Price level from Google Places API",
    )

    # Location data
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    # External references
    google_place_id = models.CharField(
        max_length=255, unique=True, help_text="Google Places API unique identifier"
    )
    maps_url = models.URLField(max_length=500, blank=True, help_text="Google Maps URL")

    # AI-generated content (for later background task)
    summary = models.TextField(
        blank=True, help_text="AI-generated summary from reviews"
    )
    summary_generated_at = models.DateTimeField(
        null=True, blank=True, help_text="When the summary was last generated"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-rating", "name"]
        indexes = [
            models.Index(fields=["cuisine_type"]),
            models.Index(fields=["rating"]),
            models.Index(fields=["google_place_id"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.cuisine_type}"

    def get_price_display_symbol(self):
        """Returns the $ symbol representation"""
        if self.price_level:
            return dict(self.PRICE_LEVEL_CHOICES).get(self.price_level, "")
        return "N/A"


class TripRestaurant(models.Model):
    """
    Links restaurants to trips with selection tracking.
    Enables temporary loading and user filtering workflow.
    """

    trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE, related_name="trip_restaurants"
    )
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="trip_associations"
    )
    cuisine_search_type = models.CharField(
        max_length=100,
        help_text="Which cuisine search this came from (e.g., 'italian')",
    )
    is_selected = models.BooleanField(
        default=False, help_text="Has user chosen to keep this restaurant?"
    )
    search_batch = models.IntegerField(
        default=1, help_text="Which generation batch (for tracking regenerations)"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["trip", "restaurant", "cuisine_search_type"]
        indexes = [
            models.Index(fields=["trip", "cuisine_search_type", "is_selected"]),
        ]

    def __str__(self):
        status = "Selected" if self.is_selected else "Pending"
        return f"{self.restaurant.name} - {self.trip.title} ({status})"
