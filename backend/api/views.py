from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import (
    UserPreferences, Trip, PlanningSession, Conversation,
    Destination, Hotel, Flight, Activity
)
from .serializers import (
    UserSerializer, UserPreferencesSerializer, TripListSerializer,
    TripDetailSerializer, TripCreateUpdateSerializer, PlanningSessionListSerializer,
    PlanningSessionDetailSerializer, PlanningSessionCreateSerializer,
    ConversationSerializer, DestinationSerializer, HotelSerializer,
    FlightSerializer, ActivitySerializer, SendMessageSerializer,
    SelectHotelSerializer, SelectFlightsSerializer
)


class CreateUserView(generics.CreateAPIView):
    """Enhanced user registration view"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]


class UserPreferencesViewSet(viewsets.ModelViewSet):
    """User preferences management"""
    serializer_class = UserPreferencesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserPreferences.objects.filter(user=self.request.user)


class TripViewSet(viewsets.ModelViewSet):
    """Trip management with CRUD operations"""
    permission_classes = [IsAuthenticated]
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

    @action(detail=True, methods=['post'])
    def select_hotel(self, request, pk=None):
        """Select hotel for trip and update status"""
        trip = self.get_object()
        serializer = SelectHotelSerializer(data=request.data)
        
        if serializer.is_valid():
            hotel_id = serializer.validated_data['hotel_id']
            
            try:
                hotel = Hotel.objects.get(id=hotel_id)
                trip.selected_hotel = hotel
                
                # Update hotel booking details if provided
                if 'checkin_date' in serializer.validated_data:
                    trip.hotel_checkin_date = serializer.validated_data['checkin_date']
                if 'checkout_date' in serializer.validated_data:
                    trip.hotel_checkout_date = serializer.validated_data['checkout_date']
                if 'guests' in serializer.validated_data:
                    trip.hotel_guests = serializer.validated_data['guests']
                if 'rooms' in serializer.validated_data:
                    trip.hotel_rooms = serializer.validated_data['rooms']
                
                # Automatically update trip status
                if trip.status in ['ai_chat_active', 'destinations_selected']:
                    trip.status = 'hotels_selected'
                
                trip.save()
                
                return Response({
                    'message': 'Hotel selected successfully',
                    'trip': TripDetailSerializer(trip).data
                })
                
            except Hotel.DoesNotExist:
                return Response(
                    {'error': 'Hotel not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def select_flights(self, request, pk=None):
        """Select flights for trip and update status"""
        trip = self.get_object()
        serializer = SelectFlightsSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Select outbound flight
                outbound_flight = Flight.objects.get(id=serializer.validated_data['outbound_flight_id'])
                trip.selected_outbound_flight = outbound_flight
                
                # Select return flight if provided
                if 'return_flight_id' in serializer.validated_data:
                    return_flight = Flight.objects.get(id=serializer.validated_data['return_flight_id'])
                    trip.selected_return_flight = return_flight
                
                # Update flight booking details
                if 'outbound_date' in serializer.validated_data:
                    trip.outbound_flight_date = serializer.validated_data['outbound_date']
                if 'return_date' in serializer.validated_data:
                    trip.return_flight_date = serializer.validated_data['return_date']
                if 'passengers' in serializer.validated_data:
                    trip.flight_passengers = serializer.validated_data['passengers']
                
                # Automatically update trip status
                if trip.status in ['ai_chat_active', 'destinations_selected', 'hotels_selected']:
                    trip.status = 'flights_selected'
                
                trip.save()
                
                return Response({
                    'message': 'Flights selected successfully',
                    'trip': TripDetailSerializer(trip).data
                })
                
            except Flight.DoesNotExist:
                return Response(
                    {'error': 'One or more flights not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PlanningSessionViewSet(viewsets.ModelViewSet):
    """Planning session management for AI conversations"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['current_stage', 'is_active']
    ordering = ['-last_interaction_at']

    def get_queryset(self):
        """Only return planning sessions for user's trips"""
        return PlanningSession.objects.filter(trip__user=self.request.user)

    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return PlanningSessionListSerializer
        elif self.action in ['create']:
            return PlanningSessionCreateSerializer
        return PlanningSessionDetailSerializer

    def perform_create(self, serializer):
        """Ensure trip belongs to user"""
        trip = serializer.validated_data['trip']
        if trip.user != self.request.user:
            raise PermissionDenied("You can only create planning sessions for your own trips")
        serializer.save()

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send message to AI and get response"""
        planning_session = self.get_object()
        serializer = SendMessageSerializer(data=request.data)
        
        if serializer.is_valid():
            user_message = serializer.validated_data['message']
            
            # Save user message
            user_conversation = Conversation.objects.create(
                planning_session=planning_session,
                message_type='user',
                content=user_message,
                stage_when_sent=planning_session.current_stage
            )
            
            # TODO: Integrate with your existing AI workflow here
            # For now, return a placeholder response
            ai_response = "Thank you for your message. AI integration coming soon!"
            
            # Save AI response
            ai_conversation = Conversation.objects.create(
                planning_session=planning_session,
                message_type='ai',
                content=ai_response,
                stage_when_sent=planning_session.current_stage
            )
            
            # Update last interaction time
            planning_session.last_interaction_at = timezone.now()
            planning_session.save()
            
            return Response({
                'user_message': ConversationSerializer(user_conversation).data,
                'ai_response': ConversationSerializer(ai_conversation).data,
                'session': PlanningSessionDetailSerializer(planning_session).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def advance_stage(self, request, pk=None):
        """Advance planning session to next stage"""
        planning_session = self.get_object()
        
        if not planning_session.is_active:
            return Response(
                {'error': 'Cannot advance inactive session'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_stage = planning_session.current_stage
        planning_session.advance_to_next_stage()
        
        # Update trip status to match planning stage
        trip = planning_session.trip
        stage_to_status_map = {
            'destination': 'destinations_selected',
            'accommodation': 'hotels_selected',
            'flights': 'flights_selected',
            'activities': 'activities_planned',
            'itinerary': 'itinerary_complete',
            'completed': 'itinerary_complete'
        }
        
        if planning_session.current_stage in stage_to_status_map:
            trip.status = stage_to_status_map[planning_session.current_stage]
            trip.save()
        
        return Response({
            'message': f'Advanced from {old_stage} to {planning_session.current_stage}',
            'session': PlanningSessionDetailSerializer(planning_session).data
        })

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause planning session"""
        planning_session = self.get_object()
        planning_session.current_stage = 'paused'
        planning_session.is_active = False
        planning_session.save()
        
        return Response({
            'message': 'Planning session paused',
            'session': PlanningSessionDetailSerializer(planning_session).data
        })

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume paused planning session"""
        planning_session = self.get_object()
        
        if planning_session.current_stage == 'paused':
            # Resume from last completed stage or destination
            if planning_session.stages_completed:
                last_stage = planning_session.stages_completed[-1]
                stage_order = ['destination', 'accommodation', 'flights', 'activities', 'itinerary']
                try:
                    current_index = stage_order.index(last_stage)
                    if current_index < len(stage_order) - 1:
                        planning_session.current_stage = stage_order[current_index + 1]
                    else:
                        planning_session.current_stage = 'completed'
                except ValueError:
                    planning_session.current_stage = 'destination'
            else:
                planning_session.current_stage = 'destination'
            
            planning_session.is_active = True
            planning_session.save()
            
            return Response({
                'message': 'Planning session resumed',
                'session': PlanningSessionDetailSerializer(planning_session).data
            })
        
        return Response(
            {'error': 'Session is not paused'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


class DestinationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only destination browsing"""
    queryset = Destination.objects.all()
    serializer_class = DestinationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'city', 'country']
    ordering = ['name']


class HotelViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only hotel browsing"""
    queryset = Hotel.objects.all()
    serializer_class = HotelSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['destination', 'rating']
    ordering = ['-rating', 'price_per_night']


class FlightViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only flight browsing"""
    queryset = Flight.objects.all()
    serializer_class = FlightSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['destination', 'origin', 'airline', 'flight_type']
    ordering = ['price', 'duration_minutes']


class ActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only activity browsing"""
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['destination', 'category']
    ordering = ['name']