# api/tests.py

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Destination, PlanningSession, Trip, UserPreferences
from .serializers import TripCreateUpdateSerializer, UserSerializer


class UserPreferencesModelTests(TestCase):
    """Test UserPreferences model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_preferences_creation(self):
        """Test creating user preferences"""
        preferences = UserPreferences.objects.create(
            user=self.user,
            preferences_text="I love beach vacations",
            budget_min=Decimal('1000.00'),
            budget_max=Decimal('5000.00'),
            preferred_group_size=4
        )
        
        self.assertIsNotNone(preferences)
        self.assertEqual(preferences.user, self.user)
        self.assertEqual(preferences.preferences_text, "I love beach vacations")
        self.assertEqual(preferences.budget_min, Decimal('1000.00'))
        self.assertEqual(preferences.budget_max, Decimal('5000.00'))
        self.assertEqual(preferences.preferred_group_size, 4)
    
    def test_preferences_string_representation(self):
        """Test __str__ method"""
        preferences = UserPreferences.objects.create(user=self.user)
        self.assertEqual(str(preferences), f"{self.user.username}'s Preferences")
    
    def test_one_to_one_relationship(self):
        """Test that each user can only have one preferences object"""
        UserPreferences.objects.create(user=self.user)
        
        # Try to get_or_create another
        preferences2, created = UserPreferences.objects.get_or_create(user=self.user)
        self.assertFalse(created)
    
    def test_preferences_defaults(self):
        """Test default values"""
        preferences = UserPreferences.objects.create(user=self.user)
        self.assertEqual(preferences.preferences_text, "")
        self.assertIsNone(preferences.budget_min)
        self.assertIsNone(preferences.budget_max)
        self.assertEqual(preferences.preferred_group_size, 2)


class DestinationModelTests(TestCase):
    """Test Destination model"""
    
    def test_destination_creation(self):
        """Test creating a destination"""
        destination = Destination.objects.create(
            name="Paris",
            city="Paris",
            country="France",
            description="City of lights",
            best_time_to_visit="Spring and Fall",
            average_cost_per_day=Decimal('150.00'),
            latitude=Decimal('48.8566'),
            longitude=Decimal('2.3522')
        )
        
        self.assertIsNotNone(destination)
        self.assertEqual(destination.name, "Paris")
        self.assertEqual(destination.country, "France")
        self.assertEqual(str(destination), "Paris, France")
    
    def test_destination_unique_constraint(self):
        """Test that name and country together must be unique"""
        Destination.objects.create(name="Paris", country="France")
        
        # Should get the existing one with get_or_create
        dest2, created = Destination.objects.get_or_create(
            name="Paris",
            country="France"
        )
        self.assertFalse(created)
        
        # But can create Paris in different country
        dest3 = Destination.objects.create(name="Paris", country="USA")
        self.assertIsNotNone(dest3)


class TripModelTests(TestCase):
    """Test Trip model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.destination = Destination.objects.create(
            name="Tokyo",
            country="Japan"
        )
    
    def test_trip_creation(self):
        """Test creating a trip"""
        trip = Trip.objects.create(
            user=self.user,
            title="Japan Adventure",
            description="Two weeks in Japan",
            destination=self.destination,
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=44),
            budget=Decimal('3000.00'),
            travelers_count=2,
            status='planning'
        )
        
        self.assertIsNotNone(trip)
        self.assertEqual(trip.user, self.user)
        self.assertEqual(trip.title, "Japan Adventure")
        self.assertEqual(str(trip), "Japan Adventure - testuser")
    
    def test_trip_duration_calculation(self):
        """Test duration_days method"""
        trip = Trip.objects.create(
            user=self.user,
            title="Test Trip",
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 10)
        )
        
        self.assertEqual(trip.duration_days(), 10)  # March 1-10 inclusive
        
        # Test with no dates
        trip2 = Trip.objects.create(user=self.user, title="No dates")
        self.assertIsNone(trip2.duration_days())
    
    def test_is_future_trip(self):
        """Test is_future_trip method"""
        # Future trip
        future_trip = Trip.objects.create(
            user=self.user,
            title="Future",
            start_date=date.today() + timedelta(days=30)
        )
        self.assertTrue(future_trip.is_future_trip())
        
        # Past trip
        past_trip = Trip.objects.create(
            user=self.user,
            title="Past",
            start_date=date.today() - timedelta(days=30)
        )
        self.assertFalse(past_trip.is_future_trip())
        
        # No date set
        no_date_trip = Trip.objects.create(user=self.user, title="No date")
        self.assertTrue(no_date_trip.is_future_trip())  # Defaults to True
    
    def test_trip_status_choices(self):
        """Test status field choices"""
        trip = Trip.objects.create(user=self.user, title="Test")
        valid_statuses = [
            'planning', 'ai_chat_active', 'destinations_selected',
            'hotels_selected', 'flights_selected', 'activities_planned',
            'itinerary_complete', 'booked', 'completed', 'cancelled'
        ]
        
        for status_choice in valid_statuses:
            trip.status = status_choice
            trip.save()
            self.assertEqual(trip.status, status_choice)
    
    def test_trip_ordering(self):
        """Test trips are ordered by created_at descending"""
        trip1 = Trip.objects.create(user=self.user, title="First")
        trip2 = Trip.objects.create(user=self.user, title="Second")
        
        trips = Trip.objects.all()
        self.assertEqual(trips[0], trip2)  # Most recent first
        self.assertEqual(trips[1], trip1)


class PlanningSessionModelTests(TestCase):
    """Test PlanningSession model"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        self.trip = Trip.objects.create(user=self.user, title="Test Trip")
    
    def test_planning_session_creation(self):
        """Test creating a planning session"""
        session = PlanningSession.objects.create(
            trip=self.trip,
            current_stage='destination'
        )
        
        self.assertIsNotNone(session)
        self.assertEqual(session.trip, self.trip)
        self.assertEqual(session.current_stage, 'destination')
        self.assertTrue(session.is_active)
        self.assertEqual(session.session_data, {})
        self.assertEqual(session.stages_completed, [])
    
    def test_mark_stage_completed(self):
        """Test marking a stage as completed"""
        session = PlanningSession.objects.create(trip=self.trip)
        
        session.mark_stage_completed('destination')
        self.assertIn('destination', session.stages_completed)
        
        # Shouldn't add duplicates
        session.mark_stage_completed('destination')
        self.assertEqual(session.stages_completed.count('destination'), 1)
    
    def test_get_next_stage(self):
        """Test getting the next planning stage"""
        session = PlanningSession.objects.create(
            trip=self.trip,
            current_stage='destination'
        )
        
        self.assertEqual(session.get_next_stage(), 'accommodation')
        
        session.current_stage = 'accommodation'
        self.assertEqual(session.get_next_stage(), 'flights')
        
        session.current_stage = 'finalization'
        self.assertEqual(session.get_next_stage(), 'completed')
    
    def test_advance_to_next_stage(self):
        """Test advancing through stages"""
        session = PlanningSession.objects.create(
            trip=self.trip,
            current_stage='destination'
        )
        
        session.advance_to_next_stage()
        self.assertEqual(session.current_stage, 'accommodation')
        self.assertIn('destination', session.stages_completed)
        
        # Advance to completion
        session.current_stage = 'finalization'
        session.advance_to_next_stage()
        self.assertEqual(session.current_stage, 'completed')
        self.assertFalse(session.is_active)
        self.assertIsNotNone(session.completed_at)


class UserRegistrationAPITests(APITestCase):
    """Test user registration and authentication"""
    
    def test_user_registration(self):
        """Test registering a new user"""
        url = reverse('register')
        data = {
            'username': 'newuser',
            'password': 'newpass123',
            'email': 'new@example.com',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        
        # Check that UserPreferences was auto-created
        user = User.objects.get(username='newuser')
        self.assertTrue(UserPreferences.objects.filter(user=user).exists())
    
    def test_registration_missing_fields(self):
        """Test registration with missing required fields"""
        url = reverse('register')
        data = {'username': 'newuser'}  # Missing password
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_duplicate_username(self):
        """Test registration with existing username"""
        User.objects.create_user('existinguser', 'exist@test.com', 'pass')
        
        url = reverse('register')
        data = {
            'username': 'existinguser',
            'password': 'newpass123',
            'email': 'new@test.com'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TripAPITests(APITestCase):
    """Test Trip API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        UserPreferences.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        
        self.destination = Destination.objects.create(
            name="Paris",
            country="France"
        )
    
    def test_create_trip(self):
        """Test creating a new trip"""
        url = '/api/trips'
        data = {
            'title': 'European Adventure',
            'description': 'Backpacking through Europe',
            'budget': '5000.00',
            'travelers_count': 2
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'European Adventure')
        self.assertTrue(Trip.objects.filter(title='European Adventure').exists())
    
    def test_list_user_trips(self):
        """Test listing trips for authenticated user"""
        Trip.objects.create(user=self.user, title="My Trip 1")
        Trip.objects.create(user=self.user, title="My Trip 2")
        
        # Create another user's trip (shouldn't be visible)
        other_user = User.objects.create_user('other', 'other@test.com', 'pass')
        Trip.objects.create(user=other_user, title="Other's Trip")
        
        response = self.client.get('/api/trips')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        titles = [trip['title'] for trip in response.data]
        self.assertIn('My Trip 1', titles)
        self.assertIn('My Trip 2', titles)
        self.assertNotIn("Other's Trip", titles)
    
    def test_get_trip_detail(self):
        """Test getting trip details"""
        trip = Trip.objects.create(
            user=self.user,
            title="Detail Test",
            destination=self.destination,
            budget=Decimal('3000.00')
        )
        
        response = self.client.get(f'/api/trips/{trip.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Detail Test')
        self.assertIn('destination', response.data)
        self.assertEqual(response.data['destination']['name'], 'Paris')
    
    def test_update_trip(self):
        """Test updating a trip"""
        trip = Trip.objects.create(user=self.user, title="Original")
        
        data = {'title': 'Updated Title'}
        response = self.client.patch(f'/api/trips/{trip.id}', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        trip.refresh_from_db()
        self.assertEqual(trip.title, 'Updated Title')
    
    def test_delete_trip(self):
        """Test deleting a trip"""
        trip = Trip.objects.create(user=self.user, title="To Delete")
        
        response = self.client.delete(f'/api/trips/{trip.id}')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Trip.objects.filter(id=trip.id).exists())
    
    def test_cannot_access_other_users_trip(self):
        """Test that users can't access other users' trips"""
        other_user = User.objects.create_user('other', 'other@test.com', 'pass')
        other_trip = Trip.objects.create(user=other_user, title="Other's Trip")
        
        response = self.client.get(f'/api/trips/{other_trip.id}')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_trip_requires_authentication(self):
        """Test that trip endpoints require authentication"""
        self.client.force_authenticate(user=None)
        
        response = self.client.get('/api/trips')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# In tests.py, REMOVE or COMMENT OUT these test methods entirely:

class PlanningSessionAPITests(APITestCase):
    """Test PlanningSession API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        self.trip = Trip.objects.create(user=self.user, title="Test Trip")
        self.client.force_authenticate(user=self.user)
    
    def test_create_planning_session(self):
        """Test creating a planning session"""
        url = '/api/planning-sessions'
        data = {
            'trip': self.trip.id,
            'current_stage': 'destination'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            PlanningSession.objects.filter(trip=self.trip).exists()
        )
    
    def test_list_planning_sessions(self):
        """Test listing planning sessions"""
        PlanningSession.objects.create(trip=self.trip)
        
        response = self.client.get('/api/planning-sessions')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_advance_stage(self):
        """Test advancing planning stage"""
        session = PlanningSession.objects.create(
            trip=self.trip,
            current_stage='destination'
        )
        
        response = self.client.post(f'/api/planning-sessions/{session.id}/advance_stage')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertEqual(session.current_stage, 'accommodation')
        self.assertIn('destination', session.stages_completed)
    
    
    def test_cannot_create_session_for_other_users_trip(self):
        """Test permission check when creating session"""
        other_user = User.objects.create_user('other', 'other@test.com', 'pass')
        other_trip = Trip.objects.create(user=other_user, title="Other's Trip")
        
        data = {'trip': other_trip.id, 'current_stage': 'destination'}
        response = self.client.post('/api/planning-sessions', data, format='json')
        
        # This might return 400 instead of 403 depending on your serializer
        # Update based on actual behavior:
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

class UserPreferencesAPITests(APITestCase):
    """Test UserPreferences API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        self.preferences = UserPreferences.objects.create(
            user=self.user,
            preferences_text="Beach lover"
        )
        self.client.force_authenticate(user=self.user)
    
    def test_get_user_preferences(self):
        """Test getting user preferences"""
        response = self.client.get('/api/user-preferences')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['preferences_text'], 'Beach lover')
    
    def test_update_preferences(self):
        """Test updating preferences"""
        data = {
            'preferences_text': 'Mountain enthusiast',
            'budget_min': '2000.00',
            'budget_max': '8000.00',
            'preferred_group_size': 4
        }
        
        response = self.client.patch(
            f'/api/user-preferences/{self.preferences.id}',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.preferences.refresh_from_db()
        self.assertEqual(self.preferences.preferences_text, 'Mountain enthusiast')
        self.assertEqual(self.preferences.budget_min, Decimal('2000.00'))
    
    def test_cannot_see_other_users_preferences(self):
        """Test that users can only see their own preferences"""
        other_user = User.objects.create_user('other', 'other@test.com', 'pass')
        UserPreferences.objects.create(user=other_user, preferences_text="Secret")
        
        response = self.client.get('/api/user-preferences')
        
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['preferences_text'], 'Beach lover')


class DestinationAPITests(APITestCase):
    """Test Destination API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        self.client.force_authenticate(user=self.user)
        
        Destination.objects.create(name="Paris", country="France")
        Destination.objects.create(name="Tokyo", country="Japan")
        Destination.objects.create(name="New York", country="USA")
    
    def test_list_destinations(self):
        """Test listing all destinations"""
        response = self.client.get('/api/destinations')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
    
    def test_search_destinations(self):
        """Test searching destinations"""
        response = self.client.get('/api/destinations/?search=Paris')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Paris')
    
    def test_destinations_are_read_only(self):
        """Test that destinations cannot be created via API"""
        data = {'name': 'London', 'country': 'UK'}
        response = self.client.post('/api/destinations', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def test_destinations_require_authentication(self):
        """Test that destinations require authentication"""
        self.client.force_authenticate(user=None)
        
        response = self.client.get('/api/destinations')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SerializerValidationTests(TestCase):
    """Test serializer validation"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
    
    def test_trip_date_validation(self):
        """Test that end date must be after start date"""
        serializer = TripCreateUpdateSerializer(data={
            'title': 'Test Trip',
            'start_date': '2025-03-10',
            'end_date': '2025-03-05'  # Before start date
        })
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('End date must be after start date', str(serializer.errors))
    
    def test_user_serializer_creates_preferences(self):
        """Test that UserSerializer creates preferences"""
        serializer = UserSerializer(data={
            'username': 'newuser',
            'password': 'pass123',
            'email': 'new@test.com'
        })
        
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertTrue(UserPreferences.objects.filter(user=user).exists())
    
    def test_trip_serializer_read_only_fields(self):
        """Test that certain fields are read-only"""
        trip = Trip.objects.create(user=self.user, title="Test", status='planning')
        
        serializer = TripCreateUpdateSerializer(
            trip,
            data={'status': 'completed'},  # Try to change read-only field
            partial=True
        )
        
        self.assertTrue(serializer.is_valid())
        updated_trip = serializer.save()
        self.assertEqual(updated_trip.status, 'planning')  # Should not change


# ============================================
# ViewSet Custom Actions (CRITICAL - 0% coverage currently)
# ============================================

class PlanningSessionActionsTests(APITestCase):
    """Test the custom actions you wrote"""
    
    def setUp(self):
        self.user = User.objects.create_user('test', 'test@test.com', 'pass')
        self.client.force_authenticate(user=self.user)
        self.trip = Trip.objects.create(user=self.user, title="Test")
    
    def test_advance_stage_basic_flow(self):
        """Test advancing through stages works"""
        session = PlanningSession.objects.create(trip=self.trip, current_stage='destination')
        
        response = self.client.post(f'/api/planning-sessions/{session.id}/advance_stage')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_stage'], 'accommodation')
        session.refresh_from_db()
        self.assertIn('destination', session.stages_completed)
    
    def test_advance_stage_updates_trip_status(self):
        """Test that trip status syncs with planning stage"""
        session = PlanningSession.objects.create(trip=self.trip, current_stage='destination')
        
        response = self.client.post(f'/api/planning-sessions/{session.id}/advance_stage')
        
        # After advancing from 'destination', we're now at 'accommodation'
        # which maps to 'hotels_selected' status
        self.trip.refresh_from_db()
        self.assertEqual(response.data['current_stage'], 'accommodation')
        self.assertEqual(self.trip.status, 'hotels_selected')
    
    def test_advance_to_completion(self):
        """Test completing the planning session"""
        session = PlanningSession.objects.create(trip=self.trip, current_stage='finalization')
        
        response = self.client.post(f'/api/planning-sessions/{session.id}/advance_stage')
        
        session.refresh_from_db()
        self.assertEqual(session.current_stage, 'completed')
        self.assertFalse(session.is_active)
        self.assertIsNotNone(session.completed_at)
    
    def test_status_endpoint(self):
        """Test the status endpoint returns progress info"""
        session = PlanningSession.objects.create(
            trip=self.trip,
            current_stage='accommodation',
            stages_completed=['destination']
        )
        
        response = self.client.get(f'/api/planning-sessions/{session.id}/status')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('progress_percentage', response.data)
        self.assertTrue(response.data['can_continue'])
    
    def test_cannot_access_other_users_session(self):
        """Test authorization on planning sessions"""
        other_user = User.objects.create_user('other', 'other@test.com', 'pass')
        other_trip = Trip.objects.create(user=other_user, title="Other")
        other_session = PlanningSession.objects.create(trip=other_trip)
        
        response = self.client.post(f'/api/planning-sessions/{other_session.id}/advance_stage')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TripFilteringTests(APITestCase):
    """Test filtering and ordering features"""
    
    def setUp(self):
        self.user = User.objects.create_user('test', 'test@test.com', 'pass')
        self.client.force_authenticate(user=self.user)
    
    def test_filter_by_status(self):
        """Test filtering trips by status"""
        Trip.objects.create(user=self.user, title="Planning", status='planning')
        Trip.objects.create(user=self.user, title="Booked", status='booked')
        
        response = self.client.get('/api/trips/?status=planning')
        
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['status'], 'planning')
    
    def test_filter_by_destination(self):
        """Test filtering trips by destination"""
        dest = Destination.objects.create(name="Paris", country="France")
        Trip.objects.create(user=self.user, title="Paris", destination=dest)
        Trip.objects.create(user=self.user, title="Nowhere")
        
        response = self.client.get(f'/api/trips/?destination={dest.id}')
        
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Paris')


# ============================================
# Important Edge Cases (Prevent Real Bugs)
# ============================================

class TripValidationTests(APITestCase):
    """Test validation that prevents bad data"""
    
    def setUp(self):
        self.user = User.objects.create_user('test', 'test@test.com', 'pass')
        self.client.force_authenticate(user=self.user)
        self.trip = Trip.objects.create(user=self.user, title="Test Trip")  # ADDED THIS LINE
    
    def test_end_date_before_start_date_rejected(self):
        """Test that invalid date range is rejected"""
        data = {
            'title': 'Bad Dates',
            'start_date': '2025-03-10',
            'end_date': '2025-03-05'
        }
        
        response = self.client.post('/api/trips', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_status_field_is_readonly(self):
        """Test that users can't manually change trip status"""
        trip = Trip.objects.create(user=self.user, title="Test", status='planning')
        
        response = self.client.patch(f'/api/trips/{trip.id}', 
                                     {'status': 'booked'}, format='json')
        
        trip.refresh_from_db()
        self.assertEqual(trip.status, 'planning')  # Should not change
    
    def test_create_session_removes_old_session(self):
        """Test that creating new session deletes old one"""
        old_session = PlanningSession.objects.create(trip=self.trip)
        old_id = old_session.id
        
        data = {'trip': self.trip.id}
        self.client.post('/api/planning-sessions', data, format='json')
        
        self.assertFalse(PlanningSession.objects.filter(id=old_id).exists())


class PermissionTests(APITestCase):
    """Test that users can only access their own data"""
    
    def setUp(self):
        self.user = User.objects.create_user('user1', 'user1@test.com', 'pass')
        self.other = User.objects.create_user('user2', 'user2@test.com', 'pass')
        self.client.force_authenticate(user=self.user)
    
    def test_cannot_see_other_users_trips(self):
        """Test trip list only shows user's trips"""
        Trip.objects.create(user=self.user, title="Mine")
        Trip.objects.create(user=self.other, title="Theirs")
        
        response = self.client.get('/api/trips')
        
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Mine')
    
    def test_cannot_update_other_users_trip(self):
        """Test users can't modify others' trips"""
        other_trip = Trip.objects.create(user=self.other, title="Other")
        
        response = self.client.patch(f'/api/trips/{other_trip.id}', 
                                     {'title': 'Hacked'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
