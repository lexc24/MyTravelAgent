# destination_search/tests.py

from datetime import timedelta
from unittest.mock import MagicMock, patch

from api.models import Trip
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import (ConversationState, Message, Recommendations,
                     TripConversation)
from .serializers import (ConversationSerializer, ConversationStateSerializer,
                          MessageSerializer)


class TripConversationModelTests(TestCase):
    """Test TripConversation model"""
    
    def setUp(self):
        """Set up test data - runs before each test"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.trip = Trip.objects.create(
            user=self.user,
            title="Test Vacation",
            description="Test Trip for test cases"
        )   

    def test_conversation_creation(self):
        """Test creating a conversation"""
        conversation = TripConversation.objects.create(trip=self.trip)
        self.assertIsNotNone(conversation)
        self.assertEqual(conversation.trip, self.trip)
        expected_str = f"Destination conversation for {self.trip.title}"
        self.assertEqual(str(conversation), expected_str)

    def test_conversation_one_to_one_relationship(self):
        """Test that each trip can only have one conversation"""
        conversation = TripConversation.objects.create(trip=self.trip)
        conversation2, created = TripConversation.objects.get_or_create(trip=self.trip)
        self.assertEqual(conversation, conversation2)
        self.assertFalse(created)


class MessageModelTests(TestCase):
    """Test Message model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.trip = Trip.objects.create(
            user=self.user,
            title="Test Vacation",
            description="Test Trip for test cases"
        )   
        self.convo = TripConversation.objects.create(trip=self.trip)

    def test_message_creation_user_message(self):
        """Test creating a user message"""
        message = Message.objects.create(
            conversation=self.convo,
            is_user=True, 
            content="hello Ai"
        )
        self.assertTrue(message.is_user)
        self.assertEqual(message.content, "hello Ai")  
        self.assertIn("User:", str(message))

    def test_message_creation_ai_message(self):
        """Test creating an AI message"""
        message = Message.objects.create(
            conversation=self.convo,
            is_user=False,
            content="Hello! How can I help you?"
        )
        self.assertFalse(message.is_user)
        self.assertIn("AI:", str(message))
    
    def test_message_ordering(self):
        """Test messages are ordered by timestamp"""
        msg1 = Message.objects.create(
            conversation=self.convo,
            is_user=True,
            content="First message"
        )
        msg2 = Message.objects.create(
            conversation=self.convo,
            is_user=False,
            content="Second message"
        )
        msg3 = Message.objects.create(
            conversation=self.convo,
            is_user=True,
            content="Third message"
        )
        
        messages = Message.objects.filter(conversation=self.convo)
        self.assertEqual(list(messages), [msg1, msg2, msg3])
    
    def test_message_belongs_to_conversation(self):
        """Test message foreign key relationship"""
        message = Message.objects.create(
            conversation=self.convo,
            is_user=True,
            content="Test message"
        )
        self.assertEqual(message.conversation, self.convo)
        
        # Query through related_name
        conversation_messages = self.convo.messages.all()
        self.assertIn(message, conversation_messages)


class ConversationStateModelTests(TestCase):
    """Test ConversationState model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.trip = Trip.objects.create(
            user=self.user,
            title="Test Trip"
        )
        self.conversation = TripConversation.objects.create(trip=self.trip)
    
    def test_state_creation_with_defaults(self):
        """Test state creation with default values"""
        state = ConversationState.objects.create(conversation=self.conversation)
        self.assertEqual(state.current_stage, 'initial')
        self.assertEqual(state.questions_asked, 0)
        self.assertEqual(state.total_questions, 0)
        self.assertEqual(state.question_queue, [])
    
    def test_progress_calculation_zero_questions(self):
        """Test progress percentage when no questions"""
        state = ConversationState.objects.create(
            conversation=self.conversation,
            total_questions=0
        )
        self.assertEqual(state.get_progress_percentage(), 0)
    
    def test_progress_calculation_partial(self):
        """Test progress percentage calculation"""
        state = ConversationState.objects.create(
            conversation=self.conversation,
            questions_asked=3,
            total_questions=5
        )
        self.assertEqual(state.get_progress_percentage(), 60)
    
    def test_progress_calculation_complete(self):
        """Test progress percentage when all questions asked"""
        state = ConversationState.objects.create(
            conversation=self.conversation,
            questions_asked=5,
            total_questions=5
        )
        self.assertEqual(state.get_progress_percentage(), 100)
    
    def test_is_complete_with_complete_stages(self):
        """Test is_complete returns True for completed stages"""
        state = ConversationState.objects.create(
            conversation=self.conversation,
            current_stage='destinations_complete'
        )
        self.assertTrue(state.is_complete())
        
        state.current_stage = 'commitment_detected'
        state.save()
        self.assertTrue(state.is_complete())
    
    def test_is_complete_with_incomplete_stages(self):
        """Test is_complete returns False for incomplete stages"""
        state = ConversationState.objects.create(
            conversation=self.conversation,
            current_stage='initial'
        )
        self.assertFalse(state.is_complete())
        
        state.current_stage = 'asking_clarifications'
        state.save()
        self.assertFalse(state.is_complete())


class RecommendationsModelTests(TestCase):
    """Test Recommendations model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.trip = Trip.objects.create(
            user=self.user,
            title="Test Trip"
        )
        self.conversation = TripConversation.objects.create(trip=self.trip)
    
    def test_recommendations_creation(self):
        """Test creating recommendations"""
        locations = [
            {'name': 'Paris', 'country': 'France', 'description': 'City of lights'},
            {'name': 'Tokyo', 'country': 'Japan', 'description': 'Modern metropolis'},
            {'name': 'New York', 'country': 'USA', 'description': 'The Big Apple'}
        ]
        
        recommendations = Recommendations.objects.create(
            conversation=self.conversation,
            locations=locations
        )
        
        self.assertIsNotNone(recommendations)
        self.assertEqual(len(recommendations.locations), 3)
        self.assertEqual(recommendations.locations[0]['name'], 'Paris')
    
    def test_multiple_recommendations_per_conversation(self):
        """Test that conversations can have multiple recommendation sets"""
        recs1 = Recommendations.objects.create(
            conversation=self.conversation,
            locations=[{'name': 'Paris', 'country': 'France', 'description': 'First set'}]
        )
        
        recs2 = Recommendations.objects.create(
            conversation=self.conversation,
            locations=[{'name': 'London', 'country': 'UK', 'description': 'Second set'}]
        )
        
        all_recs = Recommendations.objects.filter(conversation=self.conversation)
        self.assertEqual(all_recs.count(), 2)
        self.assertIn(recs1, all_recs)
        self.assertIn(recs2, all_recs)
        self.assertNotEqual(recs1.created_at, recs2.created_at)


class ChatMessageAPITests(APITestCase):
    """Test chat message API endpoint"""
    
    def setUp(self):
        """Set up authenticated user and trip"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.trip = Trip.objects.create(
            user=self.user,
            title="Test Vacation",
            description="Test Trip for test cases"
        )   
        self.client.force_authenticate(user=self.user)
    
    def test_chat_requires_authentication(self):
        """Test that chat endpoint requires authentication"""
        self.client.force_authenticate(user=None)
        response = self.client.post('/destination_search/chat', {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_chat_requires_trip_id(self):
        """Test validation of trip_id field"""
        response = self.client.post('/destination_search/chat', {
            'message': 'Hello'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('trip_id', response.data['error'])
    
    def test_chat_requires_message(self):
        """Test validation of message field"""
        response = self.client.post('/destination_search/chat', {
            'trip_id': self.trip.id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('message', response.data['error'])
    
    def test_chat_empty_message_rejected(self):
        """Test that empty/whitespace messages are rejected"""
        response = self.client.post('/destination_search/chat', {
            'trip_id': self.trip.id,
            'message': '   '
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_chat_validates_trip_ownership(self):
        """Test users can only chat about their own trips"""
        other_user = User.objects.create_user('otheruser', 'other@test.com', 'pass')
        other_trip = Trip.objects.create(
            user=other_user,
            title="Other's Trip"
        )
        
        response = self.client.post('/destination_search/chat', {
            'trip_id': other_trip.id,
            'message': 'test message'
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_chat_nonexistent_trip(self):
        """Test handling of nonexistent trip ID"""
        response = self.client.post('/destination_search/chat', {
            'trip_id': 99999,
            'message': 'test message'
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('destination_search.views.workflow_manager')
    def test_chat_initial_message_success(self, mock_workflow_manager):
        """Test successful initial message processing"""
        mock_workflow_manager.process_initial_message.return_value = {
            'info': 'User wants beach vacation',
            'question_queue': ['Budget?', 'Duration?']
        }
        mock_workflow_manager.get_next_question.return_value = 'What is your budget?'
        
        response = self.client.post('/destination_search/chat', {
            'trip_id': self.trip.id,
            'message': 'I want a beach vacation'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user_message', response.data)
        self.assertIn('ai_message', response.data)
        self.assertEqual(response.data['stage'], 'asking_clarifications')
        
        # Verify database objects
        self.assertTrue(TripConversation.objects.filter(trip=self.trip).exists())
        self.assertEqual(Message.objects.filter(conversation__trip=self.trip).count(), 2)
        self.assertTrue(ConversationState.objects.filter(
            conversation__trip=self.trip,
            current_stage='asking_clarifications'
        ).exists())
    
    @patch('destination_search.views.workflow_manager')
    def test_chat_updates_trip_status(self, mock_workflow_manager):
        """Test that starting chat updates trip status"""
        mock_workflow_manager.process_initial_message.return_value = {
            'info': 'test',
            'question_queue': []
        }
        mock_workflow_manager.get_next_question.return_value = 'Question?'
        
        self.trip.status = 'planning'
        self.trip.save()
        
        response = self.client.post('/destination_search/chat', {
            'trip_id': self.trip.id,
            'message': 'Hello'
        })
        
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, 'ai_chat_active')
    
    @patch('destination_search.views.workflow_manager')
    def test_chat_handles_workflow_error(self, mock_workflow_manager):
        """Test error handling when workflow fails"""
        mock_workflow_manager.process_initial_message.side_effect = Exception("Workflow error")
        
        response = self.client.post('/destination_search/chat', {
            'trip_id': self.trip.id,
            'message': 'Hello'
        })
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertNotIn('Workflow error', response.data['error'])  # Should not expose internals


class GetConversationAPITests(APITestCase):
    """Test get conversation endpoint"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.trip = Trip.objects.create(
            user=self.user,
            title="Test Trip"
        )
        self.client.force_authenticate(user=self.user)
    
    def test_get_conversation_requires_authentication(self):
        """Test authentication is required"""
        self.client.force_authenticate(user=None)
        response = self.client.get(f'/destination_search/conversations/{self.trip.id}')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_nonexistent_conversation(self):
        """Test getting conversation that doesn't exist"""
        response = self.client.get(f'/destination_search/conversations/{self.trip.id}')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('message', response.data)
        self.assertIn('No conversation started', response.data['message'])
    
    def test_get_existing_conversation_empty(self):
        """Test getting conversation with no messages"""
        conversation = TripConversation.objects.create(trip=self.trip)
        
        response = self.client.get(f'/destination_search/conversations/{self.trip.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['messages']), 0)
        self.assertEqual(response.data['conversation_id'], conversation.id)
    
    def test_get_existing_conversation_with_messages(self):
        """Test getting conversation with messages"""
        conversation = TripConversation.objects.create(trip=self.trip)
        msg1 = Message.objects.create(
            conversation=conversation,
            is_user=True,
            content="Hello"
        )
        msg2 = Message.objects.create(
            conversation=conversation,
            is_user=False,
            content="Hi there!"
        )
        
        response = self.client.get(f'/destination_search/conversations/{self.trip.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['messages']), 2)
        
        # Check message fields
        first_msg = response.data['messages'][0]
        self.assertIn('id', first_msg)
        self.assertIn('is_user', first_msg)
        self.assertIn('content', first_msg)
        self.assertIn('timestamp', first_msg)
        
        # Check order
        self.assertEqual(response.data['messages'][0]['content'], "Hello")
        self.assertEqual(response.data['messages'][1]['content'], "Hi there!")
    
    def test_get_conversation_with_state(self):
        """Test that conversation state is included"""
        conversation = TripConversation.objects.create(trip=self.trip)
        state = ConversationState.objects.create(
            conversation=conversation,
            current_stage='asking_clarifications',
            questions_asked=2,
            total_questions=5
        )
        
        response = self.client.get(f'/destination_search/conversations/{self.trip.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('state', response.data)
        self.assertEqual(response.data['state']['current_stage'], 'asking_clarifications')
        self.assertEqual(response.data['state']['progress'], 40)
    
    def test_get_conversation_with_recommendations(self):
        """Test that recommendations are included if they exist"""
        conversation = TripConversation.objects.create(trip=self.trip)
        locations = [
            {'name': 'Paris', 'country': 'France', 'description': 'Beautiful'},
            {'name': 'Rome', 'country': 'Italy', 'description': 'Historic'},
            {'name': 'Berlin', 'country': 'Germany', 'description': 'Modern'}
        ]
        Recommendations.objects.create(
            conversation=conversation,
            locations=locations
        )
        
        response = self.client.get(f'/destination_search/conversations/{self.trip.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('destinations', response.data)
        self.assertEqual(len(response.data['destinations']), 3)
        self.assertEqual(response.data['destinations'][0]['name'], 'Paris')
    
    def test_cannot_get_other_users_conversation(self):
        """Test users can't access other users' conversations"""
        other_user = User.objects.create_user('other', 'other@test.com', 'pass')
        other_trip = Trip.objects.create(user=other_user, title="Other's Trip")
        TripConversation.objects.create(trip=other_trip)
        
        response = self.client.get(f'/destination_search/conversations/{other_trip.id}')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ResetConversationAPITests(APITestCase):
    """Test reset conversation endpoint"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.trip = Trip.objects.create(
            user=self.user,
            title="Test Trip"
        )
        self.client.force_authenticate(user=self.user)
    
    def test_reset_requires_authentication(self):
        """Test authentication is required"""
        self.client.force_authenticate(user=None)
        response = self.client.post(f'/destination_search/conversations/{self.trip.id}/reset')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_reset_nonexistent_trip(self):
        """Test resetting conversation for nonexistent trip"""
        response = self.client.post('/destination_search/conversations/99999/reset')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_reset_conversation_success(self):
        """Test successfully resetting a conversation"""
        # Create conversation with messages and state
        conversation = TripConversation.objects.create(trip=self.trip)
        Message.objects.create(conversation=conversation, is_user=True, content="Test")
        ConversationState.objects.create(conversation=conversation)
        
        # Set trip status
        self.trip.status = 'ai_chat_active'
        self.trip.save()
        
        response = self.client.post(f'/destination_search/conversations/{self.trip.id}/reset')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(TripConversation.objects.filter(trip=self.trip).exists())
        self.assertEqual(Message.objects.filter(conversation__trip=self.trip).count(), 0)
        
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, 'planning')
        self.assertIsNone(self.trip.destination)
    
    def test_reset_when_no_conversation_exists(self):
        """Test resetting when there's no conversation"""
        self.trip.status = 'ai_chat_active'
        self.trip.save()
        
        response = self.client.post(f'/destination_search/conversations/{self.trip.id}/reset')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, 'planning')
    
    def test_cannot_reset_other_users_conversation(self):
        """Test users can't reset other users' conversations"""
        other_user = User.objects.create_user('other', 'other@test.com', 'pass')
        other_trip = Trip.objects.create(user=other_user, title="Other's Trip")
        TripConversation.objects.create(trip=other_trip)
        
        response = self.client.post(f'/destination_search/conversations/{other_trip.id}/reset')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class HelperFunctionTests(TestCase):
    """Test helper functions"""
    
    def test_parse_destinations_with_numbered_list(self):
        """Test parsing destinations from numbered list format"""
        from destination_search.views import parse_destinations
        
        text = """
        1. Paris, France
        Beautiful city of lights with amazing culture and food
        
        2. Tokyo, Japan
        Modern metropolis with traditional temples
        
        3. New York, USA
        The city that never sleeps
        """
        
        destinations = parse_destinations(text)
        
        self.assertEqual(len(destinations), 3)
        self.assertEqual(destinations[0]['name'], 'Paris')
        self.assertEqual(destinations[0]['country'], 'France')
        self.assertIn('Beautiful city', destinations[0]['description'])
    
    def test_parse_destinations_without_numbers(self):
        """Test parsing destinations from non-numbered format"""
        from destination_search.views import parse_destinations
        
        text = """
        Paris, France
        The city of love
        
        Rome, Italy
        Ancient history
        """
        
        destinations = parse_destinations(text)
        self.assertEqual(len(destinations), 3)  # Should pad to 3
        self.assertEqual(destinations[0]['name'], 'Paris')
    
    def test_parse_destinations_ensures_three_results(self):
        """Test that parse_destinations always returns 3 destinations"""
        from destination_search.views import parse_destinations

        # Test with only 1 destination
        text_one = "Paris, France\nBeautiful city"
        destinations = parse_destinations(text_one)
        self.assertEqual(len(destinations), 3)
        
        # Test with 5 destinations
        text_five = """
        1. Paris
        2. London
        3. Rome
        4. Berlin
        5. Madrid
        """
        destinations = parse_destinations(text_five)
        self.assertEqual(len(destinations), 3)
    
    def test_handle_post_destination_message_commitment_detected(self):
        """Test detecting user commitment to a destination"""
        from api.models import Destination
        from destination_search.views import handle_post_destination_message

        # Setup
        user = User.objects.create_user('test', 'test@test.com', 'pass')
        trip = Trip.objects.create(user=user, title="Test", status='ai_chat_active')
        conversation = TripConversation.objects.create(trip=trip)
        state = ConversationState.objects.create(
            conversation=conversation,
            current_stage='destinations_complete'
        )
        
        locations = [
            {'name': 'Paris', 'country': 'France', 'description': 'City of lights'},
            {'name': 'Tokyo', 'country': 'Japan', 'description': 'Modern city'},
            {'name': 'Rome', 'country': 'Italy', 'description': 'Historic city'}
        ]
        Recommendations.objects.create(conversation=conversation, locations=locations)
        
        response = handle_post_destination_message(
            "Let's go with Paris!",
            conversation,
            state,
            trip
        )
        
        self.assertIn("Excellent choice", response)
        trip.refresh_from_db()
        self.assertIsNotNone(trip.destination)
        self.assertEqual(trip.destination.name, 'Paris')
        self.assertEqual(trip.status, 'destinations_selected')
    
    def test_handle_post_destination_message_no_commitment(self):
        """Test handling non-commitment messages"""
        from destination_search.views import handle_post_destination_message

        # Setup
        user = User.objects.create_user('test', 'test@test.com', 'pass')
        trip = Trip.objects.create(user=user, title="Test", status='ai_chat_active')
        conversation = TripConversation.objects.create(trip=trip)
        state = ConversationState.objects.create(
            conversation=conversation,
            current_stage='destinations_complete'
        )
        
        locations = [
            {'name': 'Paris', 'country': 'France', 'description': 'City of lights'}
        ]
        Recommendations.objects.create(conversation=conversation, locations=locations)
        
        response = handle_post_destination_message(
            "Tell me more about Paris",
            conversation,
            state,
            trip
        )
        
        self.assertIn("more about", response.lower())
        trip.refresh_from_db()
        self.assertIsNone(trip.destination)
        self.assertEqual(trip.status, 'ai_chat_active')


class SerializerTests(TestCase):
    """Test serializers"""
    
    def setUp(self):
        self.user = User.objects.create_user('test', 'test@test.com', 'pass')
        self.trip = Trip.objects.create(user=self.user, title="Test")
        self.conversation = TripConversation.objects.create(trip=self.trip)
    
    def test_message_serializer(self):
        """Test MessageSerializer"""
        message = Message.objects.create(
            conversation=self.conversation,
            is_user=True,
            content="Test message"
        )
        
        serializer = MessageSerializer(message)
        data = serializer.data
        
        self.assertIn('id', data)
        self.assertIn('is_user', data)
        self.assertIn('content', data)
        self.assertIn('timestamp', data)
        self.assertTrue(data['is_user'])
        self.assertEqual(data['content'], "Test message")
    
    def test_conversation_state_serializer_progress_field(self):
        """Test ConversationStateSerializer progress calculation"""
        state = ConversationState.objects.create(
            conversation=self.conversation,
            questions_asked=3,
            total_questions=5
        )
        
        serializer = ConversationStateSerializer(state)
        data = serializer.data
        
        self.assertIn('progress', data)
        self.assertEqual(data['progress'], 60)
        self.assertEqual(data['progress'], state.get_progress_percentage())
    
    def test_conversation_serializer_includes_related(self):
        """Test ConversationSerializer includes messages and state"""
        # Create related objects
        Message.objects.create(
            conversation=self.conversation,
            is_user=True,
            content="Hello"
        )
        ConversationState.objects.create(
            conversation=self.conversation,
            current_stage='initial'
        )
        Recommendations.objects.create(
            conversation=self.conversation,
            locations=[{'name': 'Paris', 'country': 'France', 'description': 'Nice'}]
        )
        
        serializer = ConversationSerializer(self.conversation)
        data = serializer.data
        
        self.assertIn('messages', data)
        self.assertIn('state', data)
        self.assertIn('latest_recommendations', data)
        self.assertEqual(len(data['messages']), 1)
        self.assertIsNotNone(data['state'])
        self.assertIsNotNone(data['latest_recommendations'])

def test_chat_blocks_sql_injection_attempts(self):
    """Test that SQL injection attempts are blocked in chat"""
    response = self.client.post('/destination_search/chat', {
        'trip_id': self.trip.id,
        'message': "'; DROP TABLE users; --"
    })
    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    self.assertEqual(response.data['error'], 'Invalid input detected')


class RateLimitingTests(APITestCase):
    """Test rate limiting on chat endpoint"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        self.trip = Trip.objects.create(user=self.user, title="Test Trip")
        self.client.force_authenticate(user=self.user)
    
    def test_chat_rate_limiting_enforced(self):
        """Test that rate limiting blocks after threshold"""
        # The decorator is set to 10/m, so 11 requests should trigger it
        for i in range(10):
            response = self.client.post('/destination_search/chat', {
                'trip_id': self.trip.id,
                'message': f'Test message {i}'
            })
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 11th request should be rate limited
        response = self.client.post('/destination_search/chat', {
            'trip_id': self.trip.id,
            'message': 'This should be blocked'
        })
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('too many requests', response.data['error'].lower())
        
def test_chat_sanitizes_html_input(self):
    """Test that HTML/XSS attempts are sanitized"""
    with patch('destination_search.views.workflow_manager') as mock_wf:
        mock_wf.process_initial_message.return_value = {
            'info': 'test', 'question_queue': []
        }
        mock_wf.get_next_question.return_value = 'Question?'
        
        response = self.client.post('/destination_search/chat', {
            'trip_id': self.trip.id,
            'message': "<script>alert('xss')</script>Hello"
        })
        
        # Should succeed but with sanitized input
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check the saved message is sanitized
        saved_message = Message.objects.filter(
            conversation__trip=self.trip,
            is_user=True
        ).last()
        self.assertNotIn('<script>', saved_message.content)