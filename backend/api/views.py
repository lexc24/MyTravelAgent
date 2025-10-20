from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import Destination, PlanningSession, Trip, UserPreferences
from .serializers import (DestinationSerializer,
                          PlanningSessionCreateSerializer,
                          PlanningSessionDetailSerializer,
                          PlanningSessionListSerializer,
                          TripCreateUpdateSerializer, TripDetailSerializer,
                          TripListSerializer, UserPreferencesSerializer,
                          UserSerializer)
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator


@method_decorator(ratelimit(key='ip', rate='5/h', method='POST', block=True), name='create')
class CreateUserView(generics.CreateAPIView):
    """Enhanced user registration view with rate limiting"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return Response(
                {'error': 'Too many registration attempts. Please try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        return super().create(request, *args, **kwargs)


class UserPreferencesViewSet(viewsets.ModelViewSet):
    """User preferences management"""
    serializer_class = UserPreferencesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserPreferences.objects.filter(user=self.request.user)

class TripPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class TripViewSet(viewsets.ModelViewSet):
    """Trip management with CRUD operations"""
    permission_classes = [IsAuthenticated]
    pagination_class = TripPagination  # Add this line
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'destination']
    ordering_fields = ['created_at', 'start_date', 'title']
    ordering = ['-created_at']

    def get_queryset(self):
        """Only return trips for the authenticated user"""
        return Trip.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return TripListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return TripCreateUpdateSerializer
        return TripDetailSerializer

    def perform_create(self, serializer):
        """Set the trip owner to the current user"""
        serializer.save(user=self.request.user)

    @method_decorator(ratelimit(key='user', rate='100/h', method='GET', block=True))
    def list(self, request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return Response(
                {'error': 'Rate limit exceeded'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        return super().list(request, *args, **kwargs)
    
    @method_decorator(ratelimit(key='user', rate='20/h', method='POST', block=True))
    def create(self, request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return Response(
                {'error': 'Rate limit exceeded'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        return super().create(request, *args, **kwargs)


class PlanningSessionViewSet(viewsets.ModelViewSet):
    """
    Tracks planning workflow state - which stage of planning we're in.
    No pause/resume - the current_stage IS the state.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['current_stage', 'trip']
    ordering = ['-last_interaction_at']

    def get_queryset(self):
        return PlanningSession.objects.filter(trip__user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return PlanningSessionListSerializer
        elif self.action == 'create':
            return PlanningSessionCreateSerializer
        return PlanningSessionDetailSerializer

    def perform_create(self, serializer):
        trip = serializer.validated_data['trip']
        if trip.user != self.request.user:
            raise PermissionDenied("You can only create planning sessions for your own trips")
        
        # Only one session per trip - delete old ones
        PlanningSession.objects.filter(trip=trip).delete()
        serializer.save()

    @action(detail=True, methods=['post'])
    def advance_stage(self, request, pk=None):
        """Move to the next planning stage"""
        session = self.get_object()
        
        old_stage = session.current_stage
        next_stage = session.get_next_stage()
        
        if next_stage == 'completed':
            session.current_stage = 'completed'
            session.is_active = False
            session.completed_at = timezone.now()
        else:
            session.current_stage = next_stage
        
        session.mark_stage_completed(old_stage)
        session.last_interaction_at = timezone.now()
        session.save()
        
        # Update trip status
        self._sync_trip_status(session)
        
        return Response({
            'previous_stage': old_stage,
            'current_stage': session.current_stage,
            'is_complete': session.current_stage == 'completed'
        })

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get current planning status"""
        session = self.get_object()
        
        stages = ['destination', 'accommodation', 'flights', 'activities', 'itinerary', 'finalization']
        current_index = stages.index(session.current_stage) if session.current_stage in stages else 0
        
        return Response({
            'current_stage': session.current_stage,
            'completed_stages': session.stages_completed,
            'progress_percentage': round((current_index / len(stages)) * 100, 1),
            'can_continue': session.current_stage != 'completed'
        })
    
    def _sync_trip_status(self, session):
        """Keep trip status in sync with planning stage"""
        stage_to_status = {
            'destination': 'destinations_selected',
            'accommodation': 'hotels_selected',
            'flights': 'flights_selected',
            'activities': 'activities_planned',
            'itinerary': 'itinerary_complete',
            'completed': 'booked'
        }
        
        if session.current_stage in stage_to_status:
            session.trip.status = stage_to_status[session.current_stage]
            session.trip.save()


class DestinationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only destination browsing"""
    queryset = Destination.objects.all()
    serializer_class = DestinationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'city', 'country']
    ordering = ['name']