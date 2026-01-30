# restaurants/tests/fixtures/google_api_responses.py
"""
Mock Google Places API responses for testing.
These simulate real API responses without hitting the actual API.
"""

MOCK_GEOCODE_RESPONSE = [{"geometry": {"location": {"lat": 48.8566, "lng": 2.3522}}}]

MOCK_ITALIAN_RESTAURANTS = {
    "results": [
        {
            "place_id": "ChIJ_italian_1",
            "name": "Trattoria Bella",
            "vicinity": "123 Main St, Paris",
            "rating": 4.5,
            "user_ratings_total": 250,
            "price_level": 2,
            "geometry": {"location": {"lat": 48.8566, "lng": 2.3522}},
        },
        {
            "place_id": "ChIJ_italian_2",
            "name": "Osteria Roma",
            "vicinity": "456 Oak Ave, Paris",
            "rating": 4.6,
            "user_ratings_total": 300,
            "price_level": 3,
            "geometry": {"location": {"lat": 48.8570, "lng": 2.3530}},
        },
        {
            "place_id": "ChIJ_italian_3",
            "name": "Pasta Paradise",
            "vicinity": "789 Pine Rd, Paris",
            "rating": 4.4,
            "user_ratings_total": 220,
            "price_level": 2,
            "geometry": {"location": {"lat": 48.8575, "lng": 2.3535}},
        },
        {
            "place_id": "ChIJ_italian_4",
            "name": "La Dolce Vita",
            "vicinity": "321 Elm St, Paris",
            "rating": 4.7,
            "user_ratings_total": 400,
            "price_level": 3,
            "geometry": {"location": {"lat": 48.8580, "lng": 2.3540}},
        },
        # Low quality restaurant (should be filtered out)
        {
            "place_id": "ChIJ_italian_lowquality",
            "name": "Bad Pizza Place",
            "vicinity": "999 Bad St, Paris",
            "rating": 3.2,
            "user_ratings_total": 50,
            "price_level": 1,
            "geometry": {"location": {"lat": 48.8560, "lng": 2.3520}},
        },
    ]
}

MOCK_MEXICAN_RESTAURANTS = {
    "results": [
        {
            "place_id": "ChIJ_mexican_1",
            "name": "Taco Fiesta",
            "vicinity": "111 Beach Blvd, Paris",
            "rating": 4.5,
            "user_ratings_total": 280,
            "price_level": 2,
            "geometry": {"location": {"lat": 48.8590, "lng": 2.3550}},
        },
        {
            "place_id": "ChIJ_mexican_2",
            "name": "El Mariachi",
            "vicinity": "222 Sunset Dr, Paris",
            "rating": 4.6,
            "user_ratings_total": 350,
            "price_level": 3,
            "geometry": {"location": {"lat": 48.8595, "lng": 2.3555}},
        },
        {
            "place_id": "ChIJ_mexican_3",
            "name": "Burrito King",
            "vicinity": "333 Wave St, Paris",
            "rating": 4.4,
            "user_ratings_total": 240,
            "price_level": 1,
            "geometry": {"location": {"lat": 48.8600, "lng": 2.3560}},
        },
        {
            "place_id": "ChIJ_mexican_4",
            "name": "La Cantina",
            "vicinity": "444 Palm Ave, Paris",
            "rating": 4.8,
            "user_ratings_total": 500,
            "price_level": 3,
            "geometry": {"location": {"lat": 48.8605, "lng": 2.3565}},
        },
    ]
}

MOCK_JAPANESE_RESTAURANTS = {
    "results": [
        {
            "place_id": "ChIJ_japanese_1",
            "name": "Sushi Heaven",
            "vicinity": "555 Cherry Ln, Paris",
            "rating": 4.7,
            "user_ratings_total": 320,
            "price_level": 3,
            "geometry": {"location": {"lat": 48.8610, "lng": 2.3570}},
        },
        {
            "place_id": "ChIJ_japanese_2",
            "name": "Ramen House",
            "vicinity": "666 Bamboo St, Paris",
            "rating": 4.5,
            "user_ratings_total": 280,
            "price_level": 2,
            "geometry": {"location": {"lat": 48.8615, "lng": 2.3575}},
        },
        {
            "place_id": "ChIJ_japanese_3",
            "name": "Tokyo Garden",
            "vicinity": "777 Sakura Rd, Paris",
            "rating": 4.6,
            "user_ratings_total": 300,
            "price_level": 3,
            "geometry": {"location": {"lat": 48.8620, "lng": 2.3580}},
        },
        {
            "place_id": "ChIJ_japanese_4",
            "name": "Wasabi Express",
            "vicinity": "888 Zen Ave, Paris",
            "rating": 4.4,
            "user_ratings_total": 260,
            "price_level": 2,
            "geometry": {"location": {"lat": 48.8625, "lng": 2.3585}},
        },
    ]
}

MOCK_REVIEWS = {
    "result": {
        "reviews": [
            {"text": "Amazing food! Best Italian restaurant in Paris.", "rating": 5},
            {"text": "Great atmosphere and authentic cuisine.", "rating": 5},
            {"text": "Good pasta but service was slow.", "rating": 4},
        ]
    }
}

MOCK_EMPTY_RESULTS = {"results": []}

# Edge case responses
MOCK_LOW_QUALITY_RESTAURANTS = {
    "results": [
        {
            "place_id": f"ChIJ_low_{i}",
            "name": f"Low Quality {i}",
            "vicinity": "Test St",
            "rating": 3.0,
            "user_ratings_total": 50,
            "price_level": 1,
            "geometry": {"location": {"lat": 48.8566, "lng": 2.3522}},
        }
        for i in range(10)
    ]
}
