
# api/urls.py (new file for API app URLs)
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (ActivityViewSet, DestinationViewSet, FlightViewSet,
                    HotelViewSet, PlanningSessionViewSet, TripViewSet,
                    UserPreferencesViewSet)

# Create router and register ViewSets
router = DefaultRouter()
router.register(r'user-preferences', UserPreferencesViewSet, basename='userpreferences')
router.register(r'trips', TripViewSet, basename='trips')
router.register(r'planning-sessions', PlanningSessionViewSet, basename='planningsessions')
router.register(r'destinations', DestinationViewSet, basename='destinations')
router.register(r'hotels', HotelViewSet, basename='hotels')
router.register(r'flights', FlightViewSet, basename='flights')
router.register(r'activities', ActivityViewSet, basename='activities')

urlpatterns = [
    path('', include(router.urls)),
]

# ========================================
# COMPLETE API ENDPOINTS AVAILABLE:

"""
Authentication:
POST /api/user/register/           - Create new user account
POST /api/token/                   - Get JWT access token
POST /api/token/refresh/           - Refresh JWT token

User Preferences:
GET    /api/user-preferences/      - List user preferences
POST   /api/user-preferences/      - Create preferences
GET    /api/user-preferences/{id}/ - Get specific preferences
PUT    /api/user-preferences/{id}/ - Update preferences
DELETE /api/user-preferences/{id}/ - Delete preferences

Trips (CRUD):
GET    /api/trips/                 - List user's trips
POST   /api/trips/                 - Create new trip
GET    /api/trips/{id}/            - Get trip details
PUT    /api/trips/{id}/            - Update trip
DELETE /api/trips/{id}/            - Delete trip

Trip Actions:
POST   /api/trips/{id}/select_hotel/    - Select hotel for trip
POST   /api/trips/{id}/select_flights/  - Select flights for trip

Planning Sessions (CRUD):
GET    /api/planning-sessions/           - List user's planning sessions
POST   /api/planning-sessions/          - Create new planning session
GET    /api/planning-sessions/{id}/     - Get session details
PUT    /api/planning-sessions/{id}/     - Update session
DELETE /api/planning-sessions/{id}/     - Delete session

Planning Session Actions:
POST   /api/planning-sessions/{id}/send_message/   - Send message to AI
POST   /api/planning-sessions/{id}/advance_stage/  - Advance to next stage
POST   /api/planning-sessions/{id}/pause/          - Pause session
POST   /api/planning-sessions/{id}/resume/         - Resume paused session

Browse Options (Read-only):
GET    /api/destinations/         - Browse destinations
GET    /api/hotels/              - Browse hotels (filter by destination)
GET    /api/flights/             - Browse flights (filter by destination/origin)
GET    /api/activities/          - Browse activities (filter by destination)
"""