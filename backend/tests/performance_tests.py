# tests/test_performance.py
"""
Performance tests for myTravelAgent
These tests measure and verify performance characteristics including
response times, database query efficiency, and recommendation engine speed.
"""

import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import skipIf, skipUnless
from unittest.mock import MagicMock, patch

from api.models import Destination, PlanningSession, Trip, UserPreferences
from destination_search.models import (
    ConversationState,
    Message,
    Recommendations,
    TripConversation,
)
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection, reset_queries
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase


class DatabasePerformanceTests(TransactionTestCase):
    """Test database query performance and optimization"""

    def setUp(self):
        self.user = User.objects.create_user("perfuser", "perf@test.com", "pass123")

        # Create test data
        for i in range(10):
            Trip.objects.create(
                user=self.user, title=f"Trip {i}", budget=Decimal("1000") * (i + 1)
            )

    @override_settings(DEBUG=True)  # Need DEBUG=True to track queries
    def test_trip_list_query_count(self):
        """Test that trip list endpoint uses optimal number of queries"""
        from django.db import reset_queries
        from django.test import Client

        client = Client()
        client.force_login(self.user)

        # Reset query counter
        reset_queries()

        # Make request
        with self.assertNumQueries(3):  # Expected: auth, count, trips
            response = client.get("/api/trips/")
            self.assertEqual(response.status_code, 200)

    def test_database_indexes_exist(self):
        """Test that important database indexes exist"""
        with connection.cursor() as cursor:
            # Check for index on frequently queried fields
            if "postgresql" in connection.vendor:
                # Check Trip.user_id index
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM pg_indexes
                    WHERE tablename = 'api_trip'
                    AND indexdef LIKE '%user_id%'
                """
                )
                result = cursor.fetchone()[0]
                self.assertGreater(result, 0, "Missing index on Trip.user_id")

                # Check Trip.status index
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM pg_indexes
                    WHERE tablename = 'api_trip'
                    AND indexdef LIKE '%status%'
                """
                )
                result = cursor.fetchone()[0]
                # Status index might not exist by default, just warn
                if result == 0:
                    print(
                        "\nWarning: Consider adding index on Trip.status for better performance"
                    )

                # Check Message.conversation_id index (foreign key should auto-create)
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM pg_indexes
                    WHERE tablename = 'destination_search_message'
                    AND indexdef LIKE '%conversation_id%'
                """
                )
                result = cursor.fetchone()[0]
                self.assertGreater(
                    result, 0, "Missing index on Message.conversation_id"
                )

    def test_n_plus_one_queries(self):
        """Test for N+1 query problems"""
        # Create trips with destinations
        destinations = []
        for i in range(5):
            dest = Destination.objects.create(
                name=f"Destination {i}", country=f"Country {i}"
            )
            destinations.append(dest)

        for i in range(5):
            Trip.objects.create(
                user=self.user, title=f"Trip with dest {i}", destination=destinations[i]
            )

        with self.assertNumQueries(3):  # Should use select_related/prefetch_related
            trips = Trip.objects.filter(user=self.user).select_related("destination")
            # Force evaluation
            trip_data = [
                {
                    "title": t.title,
                    "dest": t.destination.name if t.destination else None,
                }
                for t in trips
            ]
            self.assertEqual(len(trip_data), 15)  # 10 initial + 5 with destinations

    def test_bulk_operations_performance(self):
        """Test bulk create/update operations are used where appropriate"""
        start_time = time.time()

        # Bulk create should be fast
        trips_to_create = [
            Trip(user=self.user, title=f"Bulk trip {i}") for i in range(100)
        ]
        Trip.objects.bulk_create(trips_to_create)

        bulk_time = time.time() - start_time

        # Should complete quickly (under 1 second for 100 records)
        self.assertLess(
            bulk_time,
            1.0,
            f"Bulk create of 100 trips took {bulk_time:.2f}s, should be under 1s",
        )

        # Verify records were created
        self.assertEqual(
            Trip.objects.filter(title__startswith="Bulk trip").count(), 100
        )


class APIResponseTimeTests(APITestCase):
    """Test API endpoint response times"""

    def setUp(self):
        self.user = User.objects.create_user("apiuser", "api@test.com", "pass123")
        self.client.force_authenticate(user=self.user)

        # Create test data
        self.trip = Trip.objects.create(user=self.user, title="Performance Test")

    def test_trip_list_response_time(self):
        """Test trip list endpoint responds quickly"""
        # Create multiple trips
        for i in range(20):
            Trip.objects.create(user=self.user, title=f"Trip {i}")

        start_time = time.time()
        response = self.client.get("/api/trips/")
        response_time = time.time() - start_time

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            response_time,
            0.5,
            f"Trip list took {response_time:.2f}s, should be under 0.5s",
        )

    def test_trip_create_response_time(self):
        """Test trip creation responds quickly"""
        start_time = time.time()
        response = self.client.post(
            "/api/trips/", {"title": "Quick Create Test", "budget": "5000"}
        )
        response_time = time.time() - start_time

        self.assertEqual(response.status_code, 201)
        self.assertLess(
            response_time,
            0.3,
            f"Trip creation took {response_time:.2f}s, should be under 0.3s",
        )

    @skipIf(os.environ.get("SKIP_SLOW_TESTS"), "Skipping slow tests")
    def test_concurrent_request_handling(self):
        """Test system handles concurrent requests efficiently"""
        import queue
        import threading

        results = queue.Queue()

        def make_request():
            start = time.time()
            response = self.client.get("/api/trips/")
            results.put((response.status_code, time.time() - start))

        # Launch concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        total_time = 0
        success_count = 0

        while not results.empty():
            status_code, response_time = results.get()
            if status_code == 200:
                success_count += 1
                total_time += response_time

        self.assertEqual(success_count, 10, "All concurrent requests should succeed")

        avg_time = total_time / 10
        self.assertLess(
            avg_time,
            1.0,
            f"Average response time {avg_time:.2f}s is too high for concurrent requests",
        )


class RecommendationEnginePerformanceTests(APITestCase):
    """Test recommendation engine performance"""

    def setUp(self):
        self.user = User.objects.create_user("recuser", "rec@test.com", "pass123")
        self.client.force_authenticate(user=self.user)
        self.trip = Trip.objects.create(
            user=self.user, title="Recommendation Test", status="planning"
        )

    @patch("destination_search.views.workflow_manager")
    def test_chat_response_time(self, mock_wf):
        """Test chat endpoint responds within acceptable time"""
        # Mock the workflow to avoid actual API calls
        mock_wf.process_initial_message.return_value = {
            "info": "User wants beach vacation",
            "question_queue": ["Budget?", "Duration?"],
        }
        mock_wf.get_next_question.return_value = "What is your budget?"

        start_time = time.time()
        response = self.client.post(
            "/destination_search/chat/", {"trip_id": self.trip.id, "message": "10 days"}
        )
        response_time = time.time() - start_time

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            response_time,
            2.0,
            f"Recommendation generation took {response_time:.2f}s, should be under 2s",
        )

    def test_conversation_history_retrieval_performance(self):
        """Test conversation history retrieval performance with many messages"""
        # Create conversation with many messages
        conversation = TripConversation.objects.create(trip=self.trip)

        # Bulk create messages for performance
        messages = []
        for i in range(100):
            messages.append(
                Message(
                    conversation=conversation,
                    is_user=(i % 2 == 0),
                    content=f'Message {i}: {"User" if i % 2 == 0 else "AI"} content',
                )
            )
        Message.objects.bulk_create(messages)

        start_time = time.time()
        response = self.client.get(f"/destination_search/conversations/{self.trip.id}/")
        response_time = time.time() - start_time

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["messages"]), 100)
        self.assertLess(
            response_time,
            0.5,
            f"Retrieving 100 messages took {response_time:.2f}s, should be under 0.5s",
        )


class CachingPerformanceTests(TestCase):
    """Test caching performance and configuration"""

    def test_cache_operations_performance(self):
        """Test cache read/write performance"""
        from django.core.cache import cache

        # Test write performance
        start_time = time.time()
        for i in range(100):
            cache.set(f"test_key_{i}", f"value_{i}", 60)
        write_time = time.time() - start_time

        self.assertLess(
            write_time,
            0.5,
            f"Writing 100 cache entries took {write_time:.2f}s, should be under 0.5s",
        )

        # Test read performance
        start_time = time.time()
        for i in range(100):
            value = cache.get(f"test_key_{i}")
            self.assertEqual(value, f"value_{i}")
        read_time = time.time() - start_time

        self.assertLess(
            read_time,
            0.2,
            f"Reading 100 cache entries took {read_time:.2f}s, should be under 0.2s",
        )

        # Clean up
        for i in range(100):
            cache.delete(f"test_key_{i}")

    @skipIf(settings.DEBUG, "Only test in production-like environment")
    def test_static_files_caching(self):
        """Test that static files are properly cached"""
        from django.test import Client

        client = Client()

        # Request a static file
        response = client.get("/static/admin/css/base.css")

        if response.status_code == 200:
            # Check for cache headers
            self.assertIn(
                "Cache-Control",
                response,
                "Static files should have Cache-Control header",
            )

            # WhiteNoise should add cache headers
            cache_control = response.get("Cache-Control", "")
            if "max-age" in cache_control:
                # Extract max-age value
                import re

                match = re.search(r"max-age=(\d+)", cache_control)
                if match:
                    max_age = int(match.group(1))
                    # Should cache for at least 1 hour
                    self.assertGreaterEqual(
                        max_age,
                        3600,
                        "Static files should be cached for at least 1 hour",
                    )


class MemoryUsageTests(TransactionTestCase):
    """Test memory usage and potential memory leaks"""

    @skipIf(os.environ.get("SKIP_MEMORY_TESTS"), "Skipping memory tests")
    def test_large_dataset_memory_usage(self):
        """Test memory usage with large datasets"""
        import gc
        import tracemalloc

        # Start memory tracking
        tracemalloc.start()

        # Create user
        user = User.objects.create_user("memtest", "mem@test.com", "pass123")

        # Take initial snapshot
        snapshot1 = tracemalloc.take_snapshot()

        # Create many objects
        trips = []
        for i in range(1000):
            trip = Trip.objects.create(
                user=user, title=f"Memory test trip {i}", budget=Decimal("1000")
            )
            trips.append(trip)

        # Take second snapshot
        snapshot2 = tracemalloc.take_snapshot()

        # Calculate memory increase
        top_stats = snapshot2.compare_to(snapshot1, "lineno")
        total_increase = sum(stat.size_diff for stat in top_stats) / 1024 / 1024  # MB

        # Clean up
        Trip.objects.filter(user=user).delete()
        trips.clear()
        gc.collect()

        # Memory increase should be reasonable
        self.assertLess(
            total_increase,
            50,  # 50 MB for 1000 trips
            f"Memory usage increased by {total_increase:.2f} MB for 1000 trips",
        )

        tracemalloc.stop()

    def test_queryset_iterator_memory_efficiency(self):
        """Test that large querysets use iterator for memory efficiency"""
        user = User.objects.create_user("iterator", "iter@test.com", "pass123")

        # Create many trips
        Trip.objects.bulk_create(
            [Trip(user=user, title=f"Iterator trip {i}") for i in range(1000)]
        )

        # Process with iterator (memory efficient)
        count = 0
        for trip in Trip.objects.filter(user=user).iterator(chunk_size=100):
            count += 1

        self.assertEqual(count, 1000)

        # Clean up
        Trip.objects.filter(user=user).delete()


class ScalabilityTests(TransactionTestCase):
    """Test system scalability"""

    def test_pagination_performance(self):
        """Test pagination performance with large datasets"""
        user = User.objects.create_user("pagtest", "pag@test.com", "pass123")

        # Create many trips
        Trip.objects.bulk_create(
            [Trip(user=user, title=f"Page trip {i}") for i in range(500)]
        )

        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user)

        # Test first page
        start_time = time.time()
        response = client.get("/api/trips/?page=1&page_size=20")
        first_page_time = time.time() - start_time

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertLess(first_page_time, 0.3, "First page should load quickly")

        # Test middle page (should be similar performance)
        start_time = time.time()
        response = client.get("/api/trips/?page=10&page_size=20")
        middle_page_time = time.time() - start_time

        self.assertEqual(response.status_code, 200)
        self.assertLess(middle_page_time, 0.3, "Middle pages should also load quickly")

        # Performance shouldn't degrade significantly for later pages
        self.assertLess(
            abs(middle_page_time - first_page_time),
            0.1,
            "Pagination performance should be consistent",
        )

    def test_search_performance(self):
        """Test search functionality performance"""
        # Create destinations
        destinations = []
        for i in range(100):
            dest = Destination.objects.create(
                name=f"Destination {i}",
                country=f"Country {i % 10}",
                description=f"Beautiful place number {i}",
            )
            destinations.append(dest)

        from rest_framework.test import APIClient

        user = User.objects.create_user("search", "search@test.com", "pass123")
        client = APIClient()
        client.force_authenticate(user=user)

        # Test search performance
        start_time = time.time()
        response = client.get("/api/destinations/?search=Beautiful")
        search_time = time.time() - start_time

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            search_time, 0.5, f"Search took {search_time:.2f}s, should be under 0.5s"
        )


class LoadTestingSimulation(TransactionTestCase):
    """Simulate load testing scenarios"""

    @skipIf(os.environ.get("SKIP_LOAD_TESTS"), "Skipping load tests")
    def test_simulated_peak_load(self):
        """Simulate peak load conditions"""
        import queue
        import threading

        from django.test import Client

        # Create test users
        users = []
        for i in range(20):
            user = User.objects.create_user(f"load{i}", f"load{i}@test.com", "pass123")
            users.append(user)

        results = queue.Queue()
        errors = queue.Queue()

        def simulate_user_activity(user_index):
            try:
                client = Client()
                user = users[user_index]

                # Login
                token_response = client.post(
                    "/api/token/", {"username": user.username, "password": "pass123"}
                )

                if token_response.status_code == 200:
                    token = token_response.json()["access"]

                    # Simulate various activities
                    start = time.time()

                    # Create trip
                    client.post(
                        "/api/trips/",
                        {"title": f"Load test trip {user_index}"},
                        HTTP_AUTHORIZATION=f"Bearer {token}",
                    )

                    # List trips
                    client.get("/api/trips/", HTTP_AUTHORIZATION=f"Bearer {token}")

                    # Get destinations
                    client.get(
                        "/api/destinations/", HTTP_AUTHORIZATION=f"Bearer {token}"
                    )

                    elapsed = time.time() - start
                    results.put(("success", elapsed))
                else:
                    results.put(("auth_failed", 0))

            except Exception as e:
                errors.put(str(e))
                results.put(("error", 0))

        # Launch concurrent users
        threads = []
        start_time = time.time()

        for i in range(20):
            thread = threading.Thread(target=simulate_user_activity, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=10)

        total_time = time.time() - start_time

        # Analyze results
        success_count = 0
        total_response_time = 0

        while not results.empty():
            status, response_time = results.get()
            if status == "success":
                success_count += 1
                total_response_time += response_time

        # Check error queue
        error_list = []
        while not errors.empty():
            error_list.append(errors.get())

        # Assertions
        self.assertGreaterEqual(
            success_count,
            18,  # At least 90% success rate
            f"Only {success_count}/20 users succeeded. Errors: {error_list[:3]}",
        )

        if success_count > 0:
            avg_response = total_response_time / success_count
            self.assertLess(
                avg_response,
                5.0,
                f"Average user activity time {avg_response:.2f}s is too high",
            )

        self.assertLess(
            total_time,
            15.0,
            f"Total load test took {total_time:.2f}s, should complete within 15s",
        )


# class OptimizationRecommendationTests(TestCase):
#     """Tests that provide optimization recommendations"""

#     def test_identify_slow_queries(self):
#         """Identify potentially slow database queries"""
#         # This test provides recommendations rather than failing
#         recommendations = []

#         # Check for missing select_related/prefetch_related
#         from django.db import connection

#         with connection.cursor() as cursor:
#             if 'postgresql' in connection.vendor:
#                 # Check for tables without proper indexes
#                 cursor.execute("""
#                     SELECT
#                         schemaname,
#                         tablename,
#                         pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
#                     FROM pg_tables
#                     WHERE schemaname = 'public'
#                     ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
#                     LIMIT 5
#                 """)

#                 large_tables = cursor.fetchall()
#                 if large_tables:
#                     print("\n=== Performance Optimization Recommendations ===")
#                     print("\nLargest tables (consider adding indexes if slow):")
#                     for schema, table, size in large_tables:
#                         print(f"  - {table}: {size}")

#         # Check for missing database optimizations
#         if not getattr(settings, 'CONN_MAX_AGE', None):
#             recommendations.append("Consider setting CONN_MAX_AGE for connection pooling")

#         if recommendations:
#             print("\nDatabase optimizations to consider:")
#             for rec in recommendations:
#                 print(f"  - {rec}")

#     @skipIf(settings.DEBUG, "Only run in production-like environment")
#     # def test_production_optimizations(self):
#     """Check for production optimizations"""
#     optimizations = []

#     # Check for debug toolbar
#     if 'debug_toolbar' in settings.INSTALLED_APPS:
#         optimizations.append("Remove debug_toolbar from production")

#     # Check for template caching
#     template_config = settings.TEMPLATES[0]
#     if not template_config.get('OPTIONS', {}).get('loaders'):
#         optimizations.append("Enable template caching with cached.Loader")

#     # Check for session settings
#     if not getattr(settings, 'SESSION_ENGINE', '').endswith('cached_db'):
#         optimizations.append("Consider using cached_db for SESSION_ENGINE")

#     if optimizations:
#         print("\n=== Production Optimizations ===")
#         for opt in optimizations:
#             print(f"  - {opt}")
#     response_time = time.time() - start_time

#     self.assertEqual(response.status_code, 200)
#     self.assertLess(
#         response_time,
#         1.0,
#         f"Chat response took {response_time:.2f}s, should be under 1s (excluding AI processing)"
#     )

# @patch('destination_search.views.workflow_manager')
# def test_recommendation_generation_time(self, mock_wf):
#     """Test that recommendation generation completes in reasonable time"""
#     # Setup conversation in clarification stage
#     conversation = TripConversation.objects.create(trip=self.trip)
#     ConversationState.objects.create(
#         conversation=conversation,
#         current_stage='asking_clarifications',
#         question_queue=[],
#         questions_asked=2,
#         total_questions=2
#     )

#     # Mock final recommendation response
#     mock_wf.db_to_state_format.return_value = {'info': 'User preferences'}
#     mock_wf.process_clarification_answer.return_value = {
#         'info': 'Complete preferences',
#         'destinations': 'Mock destinations text',
#         'question_queue': []
#     }

#     start_time = time.time()
#     response = self.client.post('/destination_search/chat/', {
#         'trip_i
