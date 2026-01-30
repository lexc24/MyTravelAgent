# restaurants/tests/fixtures/test_data.py
"""
Helper functions to create test data for restaurant tests using fixtures.
"""

import pandas as pd


def create_mock_restaurant_df(cuisine_type, count=4, prefix="test"):
    """
    Create a mock DataFrame of restaurants for testing.

    Args:
        cuisine_type: Type of cuisine (e.g., 'italian', 'mexican')
        count: Number of restaurants to create
        prefix: Prefix for place_ids (for uniqueness)

    Returns:
        pandas DataFrame with restaurant data
    """
    return pd.DataFrame(
        [
            {
                "google_place_id": f"ChIJ_{prefix}_{cuisine_type}_{i}",
                "name": f"{cuisine_type.title()} Restaurant {i}",
                "address": f"{i} Test St, Paris",
                "cuisine_type": cuisine_type,
                "rating": 4.5 + (i * 0.1),
                "user_ratings_total": 250 + (i * 50),
                "price_level": 2,
                "lat": 48.8566 + (i * 0.001),
                "lng": 2.3522 + (i * 0.001),
                "maps_url": f"https://maps.google.com/?cid={prefix}_{i}",
            }
            for i in range(count)
        ]
    )
