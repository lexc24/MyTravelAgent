# api/views.py - Enhanced with OpenAPI/Swagger Documentation

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Destination, PlanningSession, Trip, UserPreferences
from .serializers import (
    DestinationSerializer,
    PlanningSessionCreateSerializer,
    PlanningSessionDetailSerializer,
    PlanningSessionListSerializer,
    TripCreateUpdateSerializer,
    TripDetailSerializer,
    TripListSerializer,
    UserPreferencesSerializer,
    UserSerializer,
)


@method_decorator(
    ratelimit(key="ip", rate="5/h", method="POST", block=True), name="create"
)
@extend_schema_view(
    post=extend_schema(
        summary="Register a new user",
        description="""
        Create a new user account with username, password, and email.

        **Rate Limit:** 5 registrations per hour per IP address.

        **What happens on success:**
        - User account is created
        - UserPreferences object is automatically created
        - Returns user details (password is not included in response)

        **Common validation errors:**
        - Username already taken
        - Password too short or too common
        - Invalid email format
        """,
        request=UserSerializer,
        responses={
            201: OpenApiResponse(
                response=UserSerializer,
                description="User created successfully",
                examples=[
                    OpenApiExample(
                        "Success Response",
                        value={
                            "id": 1,
                            "username": "traveler123",
                            "email": "traveler@example.com",
                            "first_name": "John",
                            "last_name": "Doe",
                            "preferences": {
                                "id": 1,
                                "preferences_text": "",
                                "budget_min": None,
                                "budget_max": None,
                                "preferred_group_size": 2,
                                "updated_at": "2024-01-20T12:00:00Z",
                            },
                        },
                    )
                ],
            ),
            400: OpenApiResponse(
                description="Validation error",
                examples=[
                    OpenApiExample(
                        "Username Already Exists",
                        value={
                            "username": ["A user with that username already exists."]
                        },
                    ),
                    OpenApiExample(
                        "Weak Password",
                        value={
                            "password": [
                                "This password is too short. It must contain at least 8 characters.",
                                "This password is too common.",
                            ]
                        },
                    ),
                    OpenApiExample(
                        "Missing Required Fields",
                        value={
                            "username": ["This field is required."],
                            "password": ["This field is required."],
                            "email": ["This field is required."],
                        },
                    ),
                ],
            ),
            429: OpenApiResponse(
                description="Rate limit exceeded - too many registration attempts from this IP"
            ),
        },
        examples=[
            OpenApiExample(
                "Valid Registration",
                value={
                    "username": "traveler123",
                    "password": "SecurePass123!",
                    "email": "traveler@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                },
                request_only=True,
            )
        ],
        tags=["Authentication"],
    )
)
class CreateUserView(generics.CreateAPIView):
    """User registration endpoint"""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            return Response(
                {"error": "Too many registration attempts. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return super().create(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(
        summary="List user preferences",
        description="Get the preferences for the authenticated user. Each user has exactly one preferences object.",
        tags=["User Preferences"],
    ),
    retrieve=extend_schema(
        summary="Get specific preference details",
        description="Retrieve detailed information about a specific user preference object.",
        tags=["User Preferences"],
    ),
    partial_update=extend_schema(
        summary="Update user preferences",
        description="""
        Update travel preferences discovered through AI conversations or manually set by user.

        All fields are optional - only include fields you want to update.
        """,
        examples=[
            OpenApiExample(
                "Update Preferences",
                value={
                    "preferences_text": "I love beach destinations and cultural experiences",
                    "budget_min": "2000.00",
                    "budget_max": "5000.00",
                    "preferred_group_size": 2,
                },
                request_only=True,
            )
        ],
        responses={
            200: OpenApiResponse(description="Preferences updated successfully"),
            400: OpenApiResponse(
                description="Validation error",
                examples=[
                    OpenApiExample(
                        "Invalid Budget",
                        value={
                            "budget_min": [
                                "Ensure this value is greater than or equal to 0."
                            ]
                        },
                    )
                ],
            ),
            404: OpenApiResponse(description="Preferences object not found"),
        },
        tags=["User Preferences"],
    ),
)
class UserPreferencesViewSet(viewsets.ModelViewSet):
    """User preferences management"""

    serializer_class = UserPreferencesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserPreferences.objects.filter(user=self.request.user)


class TripPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


@extend_schema_view(
    list=extend_schema(
        summary="List all trips",
        description="""
        Get all trips for the authenticated user with pagination, filtering, and sorting.

        **Pagination:** 10 trips per page by default
        **Filtering:** Filter by status or destination
        **Sorting:** Sort by created_at, start_date, or title
        """,
        parameters=[
            OpenApiParameter(
                name="status",
                description="Filter by trip status",
                enum=[
                    "planning",
                    "ai_chat_active",
                    "destinations_selected",
                    "hotels_selected",
                    "flights_selected",
                    "activities_planned",
                    "itinerary_complete",
                    "booked",
                    "completed",
                    "cancelled",
                ],
            ),
            OpenApiParameter(
                name="destination",
                type=int,
                description="Filter by destination ID",
            ),
            OpenApiParameter(
                name="ordering",
                description="Sort results (prefix with - for descending)",
                enum=[
                    "created_at",
                    "-created_at",
                    "start_date",
                    "-start_date",
                    "title",
                    "-title",
                ],
            ),
            OpenApiParameter(
                name="page",
                type=int,
                description="Page number",
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                description="Number of results per page (max 100)",
            ),
        ],
        responses={
            200: TripListSerializer(many=True),
            429: OpenApiResponse(
                description="Rate limit exceeded (100 requests per hour)"
            ),
        },
        tags=["Trips"],
    ),
    create=extend_schema(
        summary="Create a new trip",
        description="""
        Create a new trip for the authenticated user.

        **Trip Status Flow:**
        planning → ai_chat_active → destinations_selected → hotels_selected →
        flights_selected → activities_planned → itinerary_complete → booked → completed

        **Required Fields:** Only `title` is required. All other fields are optional.

        **Automatic Behaviors:**
        - Status automatically set to "planning"
        - User automatically set to authenticated user
        - Created timestamp automatically recorded
        """,
        request=TripCreateUpdateSerializer,
        responses={
            201: OpenApiResponse(
                response=TripDetailSerializer,
                description="Trip created successfully",
                examples=[
                    OpenApiExample(
                        "Success Response",
                        value={
                            "id": 1,
                            "title": "Summer Vacation 2024",
                            "description": "Beach getaway in Greece",
                            "destination": None,
                            "start_date": "2024-07-01",
                            "end_date": "2024-07-14",
                            "budget": "3000.00",
                            "status": "planning",
                            "travelers_count": 2,
                            "created_at": "2024-01-20T12:00:00Z",
                            "updated_at": "2024-01-20T12:00:00Z",
                        },
                    )
                ],
            ),
            400: OpenApiResponse(
                description="Validation error",
                examples=[
                    OpenApiExample(
                        "Missing Title",
                        value={"title": ["This field is required."]},
                    ),
                    OpenApiExample(
                        "Invalid Date Range",
                        value={
                            "non_field_errors": ["End date must be after start date"]
                        },
                    ),
                    OpenApiExample(
                        "Invalid Budget",
                        value={
                            "budget": [
                                "Ensure this value is greater than or equal to 0."
                            ]
                        },
                    ),
                ],
            ),
            429: OpenApiResponse(
                description="Rate limit exceeded (20 creations per hour)"
            ),
        },
        examples=[
            OpenApiExample(
                "Minimal Trip",
                value={"title": "Weekend Getaway"},
                request_only=True,
            ),
            OpenApiExample(
                "Complete Trip",
                value={
                    "title": "Summer Vacation 2024",
                    "description": "Beach getaway with family",
                    "start_date": "2024-07-01",
                    "end_date": "2024-07-14",
                    "budget": "3000.00",
                    "travelers_count": 4,
                },
                request_only=True,
            ),
        ],
        tags=["Trips"],
    ),
    retrieve=extend_schema(
        summary="Get trip details",
        description="Retrieve detailed information about a specific trip, including destination details if selected.",
        responses={
            200: TripDetailSerializer,
            404: OpenApiResponse(
                description="Trip not found or you don't have permission to view it"
            ),
        },
        tags=["Trips"],
    ),
    partial_update=extend_schema(
        summary="Update a trip",
        description="""
        Update trip details. All fields are optional - only include fields you want to change.

        **Note:** The `status` field is read-only and managed automatically by the system.
        It changes as you progress through destination selection, planning sessions, etc.
        """,
        request=TripCreateUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=TripDetailSerializer,
                description="Trip updated successfully",
            ),
            400: OpenApiResponse(
                description="Validation error",
                examples=[
                    OpenApiExample(
                        "Invalid Date Range",
                        value={
                            "non_field_errors": ["End date must be after start date"]
                        },
                    )
                ],
            ),
            404: OpenApiResponse(description="Trip not found"),
        },
        examples=[
            OpenApiExample(
                "Update Budget",
                value={"budget": "4500.00"},
                request_only=True,
            ),
            OpenApiExample(
                "Update Dates",
                value={
                    "start_date": "2024-08-01",
                    "end_date": "2024-08-15",
                },
                request_only=True,
            ),
        ],
        tags=["Trips"],
    ),
    destroy=extend_schema(
        summary="Delete a trip",
        description="""
        Permanently delete a trip and all associated data (planning sessions, conversations, etc.).

        **Warning:** This action cannot be undone.
        """,
        responses={
            204: OpenApiResponse(description="Trip deleted successfully"),
            404: OpenApiResponse(description="Trip not found"),
        },
        tags=["Trips"],
    ),
)
class TripViewSet(viewsets.ModelViewSet):
    """Trip management with CRUD operations"""

    permission_classes = [IsAuthenticated]
    pagination_class = TripPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "destination"]
    ordering_fields = ["created_at", "start_date", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Only return trips for the authenticated user"""
        return Trip.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == "list":
            return TripListSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return TripCreateUpdateSerializer
        return TripDetailSerializer

    def perform_create(self, serializer):
        """Set the trip owner to the current user"""
        serializer.save(user=self.request.user)

    @method_decorator(ratelimit(key="user", rate="100/h", method="GET", block=True))
    def list(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            return Response(
                {"error": "Rate limit exceeded"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return super().list(request, *args, **kwargs)

    @method_decorator(ratelimit(key="user", rate="20/h", method="POST", block=True))
    def create(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            return Response(
                {"error": "Rate limit exceeded"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return super().create(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(
        summary="List planning sessions",
        description="Get all planning sessions for the authenticated user's trips.",
        tags=["Planning Sessions"],
    ),
    create=extend_schema(
        summary="Create a planning session",
        description="""
        Start a new planning session for a trip.

        **Important:** Only one active session per trip. Creating a new session will delete any existing session for that trip.

        **Planning Stages:**
        1. destination - Selecting where to go
        2. accommodation - Finding hotels/stays
        3. flights - Booking transportation
        4. activities - Planning things to do
        5. itinerary - Creating day-by-day schedule
        6. finalization - Final review
        7. completed - Planning finished
        """,
        request=PlanningSessionCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=PlanningSessionDetailSerializer,
                description="Planning session created successfully",
            ),
            400: OpenApiResponse(
                description="Validation error - invalid trip ID",
            ),
            403: OpenApiResponse(
                description="You can only create planning sessions for your own trips",
            ),
        },
        examples=[
            OpenApiExample(
                "Create Session",
                value={"trip": 1, "current_stage": "destination"},
                request_only=True,
            )
        ],
        tags=["Planning Sessions"],
    ),
    retrieve=extend_schema(
        summary="Get planning session details",
        description="Retrieve detailed information about a specific planning session.",
        responses={
            200: PlanningSessionDetailSerializer,
            404: OpenApiResponse(description="Planning session not found"),
        },
        tags=["Planning Sessions"],
    ),
)
class PlanningSessionViewSet(viewsets.ModelViewSet):
    """
    Tracks planning workflow state - which stage of planning we're in.
    No pause/resume - the current_stage IS the state.
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["current_stage", "trip"]
    ordering = ["-last_interaction_at"]

    def get_queryset(self):
        return PlanningSession.objects.filter(trip__user=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return PlanningSessionListSerializer
        elif self.action == "create":
            return PlanningSessionCreateSerializer
        return PlanningSessionDetailSerializer

    def perform_create(self, serializer):
        trip = serializer.validated_data["trip"]
        if trip.user != self.request.user:
            raise PermissionDenied(
                "You can only create planning sessions for your own trips"
            )

        # Only one session per trip - delete old ones
        PlanningSession.objects.filter(trip=trip).delete()
        serializer.save()

    @extend_schema(
        summary="Advance to next planning stage",
        description="""
        Move the planning session to the next stage in the workflow.

        **Stage Progression:**
        destination → accommodation → flights → activities → itinerary → finalization → completed

        **Side Effects:**
        - Marks current stage as completed
        - Updates trip status to match new planning stage
        - Records timestamp of advancement
        - If advancing to 'completed', marks session as inactive
        """,
        request=None,
        responses={
            200: OpenApiResponse(
                description="Advanced to next stage successfully",
                examples=[
                    OpenApiExample(
                        "Stage Advanced",
                        value={
                            "previous_stage": "destination",
                            "current_stage": "accommodation",
                            "is_complete": False,
                        },
                    ),
                    OpenApiExample(
                        "Planning Completed",
                        value={
                            "previous_stage": "finalization",
                            "current_stage": "completed",
                            "is_complete": True,
                        },
                    ),
                ],
            ),
            404: OpenApiResponse(description="Planning session not found"),
        },
        tags=["Planning Sessions"],
    )
    @action(detail=True, methods=["post"])
    def advance_stage(self, request, pk=None):
        """Move to the next planning stage"""
        session = self.get_object()

        old_stage = session.current_stage
        next_stage = session.get_next_stage()

        if next_stage == "completed":
            session.current_stage = "completed"
            session.is_active = False
            session.completed_at = timezone.now()
        else:
            session.current_stage = next_stage

        session.mark_stage_completed(old_stage)
        session.last_interaction_at = timezone.now()
        session.save()

        # Update trip status
        self._sync_trip_status(session)

        return Response(
            {
                "previous_stage": old_stage,
                "current_stage": session.current_stage,
                "is_complete": session.current_stage == "completed",
            }
        )

    @extend_schema(
        summary="Get planning progress status",
        description="""
        Get detailed progress information about the planning session.

        **Returns:**
        - Current stage
        - List of completed stages
        - Progress percentage (0-100)
        - Whether planning can continue
        """,
        responses={
            200: OpenApiResponse(
                description="Progress status retrieved successfully",
                examples=[
                    OpenApiExample(
                        "Progress Status",
                        value={
                            "current_stage": "accommodation",
                            "completed_stages": ["destination"],
                            "progress_percentage": 16.7,
                            "can_continue": True,
                        },
                    )
                ],
            ),
            404: OpenApiResponse(description="Planning session not found"),
        },
        tags=["Planning Sessions"],
    )
    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        """Get current planning status"""
        session = self.get_object()

        stages = [
            "destination",
            "accommodation",
            "flights",
            "activities",
            "itinerary",
            "finalization",
        ]
        current_index = (
            stages.index(session.current_stage)
            if session.current_stage in stages
            else 0
        )

        return Response(
            {
                "current_stage": session.current_stage,
                "completed_stages": session.stages_completed,
                "progress_percentage": round((current_index / len(stages)) * 100, 1),
                "can_continue": session.current_stage != "completed",
            }
        )

    def _sync_trip_status(self, session):
        """Keep trip status in sync with planning stage"""
        stage_to_status = {
            "destination": "destinations_selected",
            "accommodation": "hotels_selected",
            "flights": "flights_selected",
            "activities": "activities_planned",
            "itinerary": "itinerary_complete",
            "completed": "booked",
        }

        if session.current_stage in stage_to_status:
            session.trip.status = stage_to_status[session.current_stage]
            session.trip.save()


@extend_schema_view(
    list=extend_schema(
        summary="Browse destinations",
        description="""
        Get a list of available travel destinations.

        **Features:**
        - Search by destination name, city, or country
        - Sort alphabetically by name
        - Read-only endpoint (destinations managed by admin)
        """,
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search by name, city, or country",
                type=str,
            )
        ],
        tags=["Destinations"],
    ),
    retrieve=extend_schema(
        summary="Get destination details",
        description="Retrieve detailed information about a specific destination including description, best time to visit, and average costs.",
        tags=["Destinations"],
    ),
)
class DestinationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only destination browsing"""

    queryset = Destination.objects.all()
    serializer_class = DestinationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "city", "country"]
    ordering = ["name"]
