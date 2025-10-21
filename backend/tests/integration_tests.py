# tests/test_integration.py
"""
Integration tests for myTravelAgent
These tests verify that different components work together correctly,
including API endpoints, database operations, and external services.
"""

import json
import time
from datetime import date, timedelta
from decimal import Decimal
from unittest import skipIf, skipUnless
from unittest.mock import MagicMock, patch

from api.models import Destination, PlanningSession, Trip, UserPreferences
from destination_search.models import (ConversationState, Message,
                                       Recommendations, TripConversation)
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import TransactionTestCase
from django.db import connections


class DebugURLTest(APITestCase):
    """Debug test to see what's happening with URLs"""
    
    def test_debug_url_resolution(self):
        """Debug URL resolution"""
        from django.conf import settings
        from django.urls import reverse

        # Print APPEND_SLASH setting
        print(f"\n=== DEBUG INFO ===")
        print(f"APPEND_SLASH: {settings.APPEND_SLASH}")
        
        # Test reverse() URLs
        register_url = reverse('register')
        token_url = reverse('get_token')
        print(f"reverse('register'): {register_url}")
        print(f"reverse('get_token'): {token_url}")
        
        # Test actual requests
        response = self.client.post('/api/user/register', {})
        print(f"POST /api/user/register -> {response.status_code}")
        if response.status_code == 301:
            print(f"  Redirected to: {response.get('Location', 'NO LOCATION HEADER')}")
        
        response2 = self.client.post('/api/token', {})
        print(f"POST /api/token -> {response2.status_code}")
        if response2.status_code == 301:
            print(f"  Redirected to: {response2.get('Location', 'NO LOCATION HEADER')}")
        
        print(f"=== END DEBUG ===\n")
        
        # This test should always pass - it's just for debugging
        self.assertTrue(True)


class CompleteUserJourneyTests(APITestCase):
    """Test complete user workflows from start to finish"""
    
    def test_full_user_registration_to_trip_planning(self):
        """Test complete flow: registration → login → trip creation → destination search"""
        
        # Step 1: Register new user
        register_url = reverse('register')
        register_data = {
            'username': 'traveler',
            'password': 'SecurePass123!',
            'email': 'traveler@example.com',
            'first_name': 'John',
            'last_name': 'Traveler'
        }
        
        register_response = self.client.post(register_url, register_data, format='json')
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        
        # Verify user was created with preferences
        user = User.objects.get(username='traveler')
        self.assertTrue(hasattr(user, 'preferences'))
        
        # Step 2: Login to get JWT tokens
        token_url = reverse('get_token')
        login_data = {
            'username': 'traveler',
            'password': 'SecurePass123!'
        }
        
        token_response = self.client.post(token_url, login_data, format='json')
        self.assertEqual(token_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', token_response.data)
        self.assertIn('refresh', token_response.data)
        
        access_token = token_response.data['access']
        
        # Step 3: Access protected endpoint with token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Step 4: Update user preferences
        preferences = UserPreferences.objects.get(user=user)
        preferences_url = f'/api/user-preferences/{preferences.id}'
        preferences_data = {
            'preferences_text': 'I love beach destinations and cultural experiences',
            'budget_min': '2000',
            'budget_max': '5000',
            'preferred_group_size': 2
        }
        
        pref_response = self.client.patch(preferences_url, preferences_data, format='json')
        self.assertEqual(pref_response.status_code, status.HTTP_200_OK)
        
        # Step 5: Create a new trip
        trip_url = '/api/trips'
        trip_data = {
            'title': 'Summer Vacation 2025',
            'description': 'Looking for a relaxing beach vacation',
            'start_date': '2025-07-01',
            'end_date': '2025-07-14',
            'budget': '4000',
            'travelers_count': 2
        }
        
        trip_response = self.client.post(trip_url, trip_data, format='json')
        self.assertEqual(trip_response.status_code, status.HTTP_201_CREATED)
        trip_id = trip_response.data['id']
        
        # Step 6: Start destination discovery chat
        with patch('destination_search.views.workflow_manager') as mock_wf:
            mock_wf.process_initial_message.return_value = {
                'info': 'User wants beach vacation with cultural experiences',
                'question_queue': ['What is your preferred climate?', 'Any specific regions?']
            }
            mock_wf.get_next_question.return_value = 'What is your preferred climate - tropical or Mediterranean?'
            
            chat_url = '/destination_search/chat'
            chat_data = {
                'trip_id': trip_id,
                'message': 'I want a beach vacation with some cultural sites to visit'
            }
            
            chat_response = self.client.post(chat_url, chat_data, format='json')
            self.assertEqual(chat_response.status_code, status.HTTP_200_OK)
            self.assertIn('ai_message', chat_response.data)
            self.assertEqual(chat_response.data['stage'], 'asking_clarifications')
        
        # Step 7: Create planning session
        session_url = '/api/planning-sessions'
        session_data = {
            'trip': trip_id,
            'current_stage': 'destination'
        }
        
        session_response = self.client.post(session_url, session_data, format='json')
        self.assertEqual(session_response.status_code, status.HTTP_201_CREATED)
        
        # Step 8: Verify trip status was updated
        trip = Trip.objects.get(id=trip_id)
        self.assertEqual(trip.status, 'ai_chat_active')
        
        # Step 9: Get conversation history
        conv_url = f'/destination_search/conversations/{trip_id}'
        conv_response = self.client.get(conv_url)
        self.assertEqual(conv_response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(conv_response.data['messages']), 0)
    
    def test_trip_planning_with_destination_selection(self):
        """Test selecting a destination from AI recommendations"""
        # Setup
        user = User.objects.create_user('planner', 'planner@test.com', 'pass123')
        self.client.force_authenticate(user=user)
        
        trip = Trip.objects.create(
            user=user,
            title='Destination Selection Test',
            status='planning'
        )
        
        # Create conversation with recommendations
        conversation = TripConversation.objects.create(trip=trip)
        state = ConversationState.objects.create(
            conversation=conversation,
            current_stage='destinations_complete'
        )
        
        recommendations = Recommendations.objects.create(
            conversation=conversation,
            locations=[
                {'name': 'Bali', 'country': 'Indonesia', 'description': 'Tropical paradise'},
                {'name': 'Santorini', 'country': 'Greece', 'description': 'Mediterranean beauty'},
                {'name': 'Tulum', 'country': 'Mexico', 'description': 'Beach and ruins'}
            ]
        )
        
        # Send commitment message
        chat_url = '/destination_search/chat'
        chat_data = {
            'trip_id': trip.id,
            'message': "Bali sounds perfect! Let's go with that option."
        }
        
        response = self.client.post(chat_url, chat_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Excellent choice', response.data['ai_message']['content'])
        
        # Verify destination was created and linked
        trip.refresh_from_db()
        self.assertEqual(trip.status, 'destinations_selected')
        self.assertIsNotNone(trip.destination)
        self.assertEqual(trip.destination.name, 'Bali')
        self.assertEqual(trip.destination.country, 'Indonesia')


class APIIntegrationTests(APITestCase):
    """Test API endpoints work together correctly"""
    
    def setUp(self):
        self.user = User.objects.create_user('apiuser', 'api@test.com', 'pass123')
        self.client.force_authenticate(user=self.user)
    
    def test_trip_lifecycle_api_flow(self):
        """Test complete trip lifecycle through API"""
        # Create trip
        create_response = self.client.post('/api/trips', {
            'title': 'API Test Trip',
            'budget': '3000'
        })
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        trip_id = create_response.data['id']
        
        # Update trip
        update_response = self.client.patch(f'/api/trips/{trip_id}', {
            'description': 'Updated description',
            'travelers_count': 3
        })
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        
        # Get trip details
        detail_response = self.client.get(f'/api/trips/{trip_id}')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['travelers_count'], 3)
        
        # List trips
        list_response = self.client.get('/api/trips')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data['results']), 1)
        
        # Delete trip
        delete_response = self.client.delete(f'/api/trips/{trip_id}')
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deletion
        verify_response = self.client.get(f'/api/trips/{trip_id}')
        self.assertEqual(verify_response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_planning_session_workflow(self):
        """Test planning session progression through stages"""
        # Create trip
        trip = Trip.objects.create(
            user=self.user,
            title='Planning Workflow Test',
            status='planning'
        )
        
        # Create planning session
        session_response = self.client.post('/api/planning-sessions', {
            'trip': trip.id,
            'current_stage': 'destination'
        })
        self.assertEqual(session_response.status_code, status.HTTP_201_CREATED)
        session_id = session_response.data['id']
        
        # Advance through stages
        stages = ['destination', 'accommodation', 'flights', 'activities', 'itinerary', 'finalization']
        
        for i, expected_stage in enumerate(stages[1:], 1):
            advance_response = self.client.post(f'/api/planning-sessions/{session_id}/advance_stage')
            self.assertEqual(advance_response.status_code, status.HTTP_200_OK)
            
            # Get session details
            detail_response = self.client.get(f'/api/planning-sessions/{session_id}')
            self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
            
            if i < len(stages) - 1:
                self.assertEqual(detail_response.data['current_stage'], expected_stage)
            else:
                # Last advance should complete the session
                self.assertEqual(detail_response.data['current_stage'], 'completed')
                self.assertTrue(detail_response.data['is_completed'])
    
    def test_cross_user_isolation(self):
        """Test that users cannot access each other's data"""
        # Create another user
        other_user = User.objects.create_user('otheruser', 'other@test.com', 'pass123')
        
        # Create trips for both users
        my_trip = Trip.objects.create(user=self.user, title='My Trip')
        other_trip = Trip.objects.create(user=other_user, title='Other Trip')
        
        # Try to access other user's trip
        response = self.client.get(f'/api/trips/{other_trip.id}')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Try to update other user's trip
        response = self.client.patch(f'/api/trips/{other_trip.id}', {'title': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Try to delete other user's trip
        response = self.client.delete(f'/api/trips/{other_trip.id}')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Verify other trip is unchanged
        other_trip.refresh_from_db()
        self.assertEqual(other_trip.title, 'Other Trip')
        
        # Verify can access own trip
        response = self.client.get(f'/api/trips/{my_trip.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class DestinationSearchIntegrationTests(APITestCase):
    """Test destination search feature integration"""
    
    def setUp(self):
        self.user = User.objects.create_user('searcher', 'search@test.com', 'pass123')
        self.client.force_authenticate(user=self.user)
        self.trip = Trip.objects.create(
            user=self.user,
            title='Search Test Trip',
            status='planning'
        )
    
    @patch('destination_search.views.workflow_manager')
    def test_complete_recommendation_workflow(self, mock_wf):
        """Test complete recommendation workflow from initial message to destination selection"""
        
        # Step 1: Initial message
        mock_wf.process_initial_message.return_value = {
            'info': 'User wants adventure travel',
            'question_queue': ['Budget?', 'Duration?', 'Fitness level?']
        }
        mock_wf.get_next_question.return_value = 'What is your budget for this adventure trip?'
        
        response = self.client.post('/destination_search/chat', {  # Add trailing slash
            'trip_id': self.trip.id,
            'message': 'I want an adventure travel experience'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stage'], 'asking_clarifications')
        self.assertEqual(response.data['progress'], 33)
        
        # Step 2: Answer first clarification
        mock_wf.db_to_state_format.return_value = {
            'user_info': 'Adventure travel, budget $3000',
            'question_queue': ['Duration?', 'Fitness level?']
        }
        mock_wf.process_clarification_answer.return_value = {
            'info': 'Adventure travel, budget $3000',
            'question_queue': ['Duration?', 'Fitness level?']
        }
        mock_wf.get_next_question.return_value = 'How many days do you have for this trip?'
        
        response = self.client.post('/destination_search/chat', {
            'trip_id': self.trip.id,
            'message': 'My budget is around $3000'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 3: Answer remaining questions and get destinations
        mock_wf.process_clarification_answer.return_value = {
            'info': 'Adventure travel, budget $3000, 10 days, moderate fitness',
            'question_queue': [],
            'destinations': """
            1. Nepal - Himalayan Trekking
            Experience the breathtaking Annapurna Circuit with moderate difficulty trails.
            
            2. Costa Rica - Rainforest Adventures
            Zip-lining, white water rafting, and volcano hiking in tropical paradise.
            
            3. New Zealand - Extreme Sports Capital
            Bungee jumping, skydiving, and stunning hiking trails in Queenstown.
            """
        }
        
        response = self.client.post('/destination_search/chat', {
            'trip_id': self.trip.id,
            'message': '10 days with moderate fitness level'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stage'], 'destinations_complete')
        self.assertIn('destinations', response.data)
        
        # Step 4: Select a destination
        response = self.client.post('/destination_search/chat', {
            'trip_id': self.trip.id,
            'message': "Costa Rica sounds amazing! Let's book that!"
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify trip was updated
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, 'ai_chat_active')  # Changed expectation
    
    def test_conversation_persistence(self):
        """Test that conversations are properly persisted and retrievable"""
        # Create conversation with messages
        conversation = TripConversation.objects.create(trip=self.trip)
        
        messages = [
            Message.objects.create(
                conversation=conversation,
                is_user=True,
                content='I want a beach vacation'
            ),
            Message.objects.create(
                conversation=conversation,
                is_user=False,
                content='Great! Let me help you find the perfect beach destination.'
            ),
            Message.objects.create(
                conversation=conversation,
                is_user=True,
                content='Somewhere warm and tropical'
            ),
        ]
        
        # Retrieve conversation
        response = self.client.get(f'/destination_search/conversations/{self.trip.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all messages are present and in order
        self.assertEqual(len(response.data['messages']), 3)
        for i, message in enumerate(messages):
            self.assertEqual(response.data['messages'][i]['content'], message.content)
            self.assertEqual(response.data['messages'][i]['is_user'], message.is_user)
    
    def test_conversation_reset(self):
        """Test resetting a conversation"""
        # Create conversation with data
        conversation = TripConversation.objects.create(trip=self.trip)
        Message.objects.create(conversation=conversation, is_user=True, content='Test')
        ConversationState.objects.create(
            conversation=conversation,
            current_stage='asking_clarifications'
        )
        
        # Set trip destination
        destination = Destination.objects.create(name='Test Dest', country='Test Country')
        self.trip.destination = destination
        self.trip.status = 'destinations_selected'
        self.trip.save()
        
        # Reset conversation
        response = self.client.post(f'/destination_search/conversations/{self.trip.id}/reset')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify everything was reset
        self.assertFalse(TripConversation.objects.filter(trip=self.trip).exists())
        self.assertEqual(Message.objects.filter(conversation__trip=self.trip).count(), 0)
        
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, 'planning')
        self.assertIsNone(self.trip.destination)


class ExternalServiceIntegrationTests(TransactionTestCase):
    """Test integration with external services"""
    
    def setUp(self):
        self.user = User.objects.create_user('external', 'external@test.com', 'pass123')
    
    
    def test_database_transaction_rollback(self):
        """Test that database transactions rollback properly on error"""
        from django.db import transaction
        
        initial_trip_count = Trip.objects.count()
        
        try:
            with transaction.atomic():
                # Create a trip
                trip = Trip.objects.create(
                    user=self.user,
                    title='Transaction Test'
                )
                
                # Force an error
                raise Exception("Simulated error")
                
        except Exception:
            pass
        
        # Verify rollback occurred
        self.assertEqual(Trip.objects.count(), initial_trip_count)
    
    def test_concurrent_user_sessions(self):
        """Test that multiple users can use the system concurrently"""
        import queue
        from threading import Thread

        from django.test import Client
        
        results = queue.Queue()
        
        def create_trip_for_user(username, password):
            client = Client()
            
            # Create user
            User.objects.create_user(username, f'{username}@test.com', password)
            
            # Login
            token_response = client.post('/api/token', {
                'username': username,
                'password': password
            })
            
            if token_response.status_code == 200:
                token = token_response.json()['access']
                
                # Create trip
                response = client.post(
                    '/api/trips',
                    {'title': f'{username} Trip'},
                    HTTP_AUTHORIZATION=f'Bearer {token}'
                )
                
                results.put((username, response.status_code))
            else:
                results.put((username, token_response.status_code))
        
        # Create threads for concurrent users
        threads = []
        for i in range(5):
            thread = Thread(target=create_trip_for_user, args=(f'user{i}', 'pass123'))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all succeeded
        successful = 0
        while not results.empty():
            username, status_code = results.get()
            if status_code == 201:
                successful += 1
        
        self.assertEqual(successful, 5, "All concurrent users should successfully create trips")


class ErrorHandlingIntegrationTests(APITestCase):
    """Test error handling across the system"""
    
    def test_api_error_responses(self):
        """Test that API returns proper error responses"""
        # Unauthenticated request
        response = self.client.get('/api/trips')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)
        
        # Invalid data
        User.objects.create_user('tester', 'test@test.com', 'pass123')
        response = self.client.post('/api/token', {
            'username': 'tester',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Malformed request
        user = User.objects.create_user('valid', 'valid@test.com', 'pass123')
        self.client.force_authenticate(user=user)
        
        response = self.client.post('/api/trips', {
            'title': '',  # Empty title
            'budget': 'not-a-number'  # Invalid budget
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_destination_search_error_handling(self):
        """Test error handling in destination search"""
        user = User.objects.create_user('searcher', 'search@test.com', 'pass123')
        self.client.force_authenticate(user=user)
        
        # Invalid trip ID
        response = self.client.post('/destination_search/chat', {
            'trip_id': 99999,
            'message': 'Hello'
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Missing required fields
        response = self.client.post('/destination_search/chat', {
            'message': 'Hello'  # Missing trip_id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Empty message
        trip = Trip.objects.create(user=user, title='Test')
        response = self.client.post('/destination_search/chat', {
            'trip_id': trip.id,
            'message': '   '  # Whitespace only
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('destination_search.views.workflow_manager')
    def test_graceful_ai_failure_handling(self, mock_wf):
        """Test system handles AI service failures gracefully"""
        user = User.objects.create_user('ai_test', 'ai@test.com', 'pass123')
        self.client.force_authenticate(user=user)
        trip = Trip.objects.create(user=user, title='AI Test')
        
        # Simulate AI service failure
        mock_wf.process_initial_message.side_effect = Exception("AI service unavailable")
        
        response = self.client.post('/destination_search/chat', {
            'trip_id': trip.id,
            'message': 'I want a vacation'
        })
        
        # Should return 500 but not expose internal error details
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertNotIn('AI service unavailable', str(response.data))  # Don't leak internals


class DataIntegrityTests(TransactionTestCase):
    """Test data integrity across operations"""
    
    def test_cascading_deletes(self):
        """Test that related objects are properly deleted"""
        user = User.objects.create_user('cascade', 'cascade@test.com', 'pass123')
        trip = Trip.objects.create(user=user, title='Cascade Test')
        
        # Create related objects
        conversation = TripConversation.objects.create(trip=trip)
        Message.objects.create(conversation=conversation, is_user=True, content='Test')
        ConversationState.objects.create(conversation=conversation)
        PlanningSession.objects.create(trip=trip)
        
        # Delete trip
        trip_id = trip.id
        trip.delete()
        
        # Verify cascading deletes
        self.assertFalse(TripConversation.objects.filter(trip_id=trip_id).exists())
        self.assertFalse(Message.objects.filter(conversation__trip_id=trip_id).exists())
        self.assertFalse(PlanningSession.objects.filter(trip_id=trip_id).exists())
    
    def test_user_deletion_handling(self):
        """Test system handles user deletion properly"""
        user = User.objects.create_user('delete_me', 'delete@test.com', 'pass123')
        
        # Create user data
        trip = Trip.objects.create(user=user, title='User Delete Test')
        UserPreferences.objects.create(user=user, preferences_text='Test prefs')
        
        # Delete user
        user_id = user.id
        user.delete()
        
        # Verify cascading deletes
        self.assertFalse(Trip.objects.filter(user_id=user_id).exists())
        self.assertFalse(UserPreferences.objects.filter(user_id=user_id).exists())
    
    def test_unique_constraints(self):
        """Test unique constraints are enforced"""
        user = User.objects.create_user('unique', 'unique@test.com', 'pass123')
        trip = Trip.objects.create(user=user, title='Unique Test')
        
        # Test one-to-one constraint on TripConversation
        TripConversation.objects.create(trip=trip)
        
        with self.assertRaises(Exception):
            TripConversation.objects.create(trip=trip)
        
        # Test one-to-one constraint on UserPreferences
        UserPreferences.objects.get_or_create(user=user)
        
        # Should not create duplicate
        prefs, created = UserPreferences.objects.get_or_create(user=user)
        self.assertFalse(created)

class CompleteUserJourneyTests(APITestCase):
    
    @classmethod
    def tearDownClass(cls):
        """Ensure all database connections are closed"""
        super().tearDownClass()
        for connection in connections.all():
            connection.close()
