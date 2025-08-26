from django.contrib.auth.models import User
from rest_framework import serializers
from .models import (
    UserPreferences, Trip, PlanningSession, Conversation,
    Destination, Hotel, Flight, Activity
)


class UserSerializer(serializers.ModelSerializer):
    """Enhanced user serializer with preferences"""
    preferences = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "password", "preferences"]
        extra_kwargs = {"password": {"write_only": True}}

    def get_preferences(self, obj):
        """Get user preferences if they exist"""
        try:
            return UserPreferencesSerializer(obj.preferences).data
        except UserPreferences.DoesNotExist:
            return None

    def create(self, validated_data):
        """Create user and associated preferences"""
        user = User.objects.create_user(**validated_data)
        # Auto-create UserPreferences when user registers
        UserPreferences.objects.create(user=user)
        return user


class UserPreferencesSerializer(serializers.ModelSerializer):
    """User preferences serializer"""
    class Meta:
        model = UserPreferences
        fields = ['id', 'preferences_text', 'budget_min', 'budget_max', 'preferred_group_size', 'updated_at']


class DestinationSerializer(serializers.ModelSerializer):
    """Destination serializer"""
    class Meta:
        model = Destination
        fields = '__all__'


class HotelSerializer(serializers.ModelSerializer):
    """Hotel serializer with destination details"""
    destination = DestinationSerializer(read_only=True)

    class Meta:
        model = Hotel
        fields = '__all__'


class FlightSerializer(serializers.ModelSerializer):
    """Flight serializer with destination details"""
    destination = DestinationSerializer(read_only=True)
    duration_formatted = serializers.ReadOnlyField()

    class Meta:
        model = Flight
        fields = '__all__'


class ActivitySerializer(serializers.ModelSerializer):
    """Activity serializer"""
    destination = DestinationSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = '__all__'


class TripListSerializer(serializers.ModelSerializer):
    """Simplified serializer for trip list view"""
    destination = DestinationSerializer(read_only=True)
    duration_days = serializers.ReadOnlyField()

    class Meta:
        model = Trip
        fields = [
            'id', 'title', 'destination', 'start_date', 'end_date', 
            'budget', 'status', 'travelers_count', 'duration_days',
            'created_at', 'updated_at'
        ]


class TripDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for trip detail view"""
    destination = DestinationSerializer(read_only=True)
    selected_hotel = HotelSerializer(read_only=True)
    selected_outbound_flight = FlightSerializer(read_only=True)
    selected_return_flight = FlightSerializer(read_only=True)
    duration_days = serializers.ReadOnlyField()
    total_estimated_cost = serializers.ReadOnlyField()
    user = UserSerializer(read_only=True)

    class Meta:
        model = Trip
        fields = '__all__'


class TripCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating trips"""
    class Meta:
        model = Trip
        fields = [
            'title', 'description', 'destination', 'start_date', 'end_date',
            'budget', 'travelers_count', 'hotel_checkin_date', 'hotel_checkout_date',
            'hotel_guests', 'hotel_rooms', 'outbound_flight_date', 'return_flight_date',
            'flight_passengers'
        ]

    def validate(self, data):
        """Validate trip dates"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError("End date must be after start date")
        
        # Validate hotel dates if provided
        checkin = data.get('hotel_checkin_date')
        checkout = data.get('hotel_checkout_date')
        
        if checkin and checkout and checkin >= checkout:
            raise serializers.ValidationError("Hotel checkout must be after checkin")
            
        return data


class ConversationSerializer(serializers.ModelSerializer):
    """Conversation serializer for chat messages"""
    class Meta:
        model = Conversation
        fields = ['id', 'message_type', 'content', 'stage_when_sent', 'created_at']


class PlanningSessionListSerializer(serializers.ModelSerializer):
    """Planning session list serializer"""
    trip = TripListSerializer(read_only=True)

    class Meta:
        model = PlanningSession
        fields = [
            'id', 'trip', 'current_stage', 'is_active', 'stages_completed',
            'started_at', 'last_interaction_at', 'completed_at'
        ]


class PlanningSessionDetailSerializer(serializers.ModelSerializer):
    """Detailed planning session serializer with conversations"""
    trip = TripDetailSerializer(read_only=True)
    conversations = ConversationSerializer(many=True, read_only=True)
    recent_conversations = serializers.SerializerMethodField()

    class Meta:
        model = PlanningSession
        fields = [
            'id', 'trip', 'current_stage', 'is_active', 'session_data',
            'stages_completed', 'started_at', 'last_interaction_at', 
            'completed_at', 'conversations', 'recent_conversations'
        ]

    def get_recent_conversations(self, obj):
        """Get last 20 conversations for context"""
        recent = obj.conversations.all()[:20]
        return ConversationSerializer(recent, many=True).data


class PlanningSessionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating planning sessions"""
    class Meta:
        model = PlanningSession
        fields = ['trip', 'current_stage', 'session_data']


class SendMessageSerializer(serializers.Serializer):
    """Serializer for sending messages to AI"""
    message = serializers.CharField(max_length=1000)
    
    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message cannot be empty")
        return value.strip()


class SelectHotelSerializer(serializers.Serializer):
    """Serializer for hotel selection"""
    hotel_id = serializers.IntegerField()
    checkin_date = serializers.DateField(required=False)
    checkout_date = serializers.DateField(required=False)
    guests = serializers.IntegerField(min_value=1, required=False)
    rooms = serializers.IntegerField(min_value=1, default=1)

    def validate(self, data):
        checkin = data.get('checkin_date')
        checkout = data.get('checkout_date')
        
        if checkin and checkout and checkin >= checkout:
            raise serializers.ValidationError("Checkout date must be after checkin date")
        
        return data


class SelectFlightsSerializer(serializers.Serializer):
    """Serializer for flight selection (both outbound and return)"""
    outbound_flight_id = serializers.IntegerField()
    return_flight_id = serializers.IntegerField(required=False)
    outbound_date = serializers.DateField(required=False)
    return_date = serializers.DateField(required=False)
    passengers = serializers.IntegerField(min_value=1, required=False)

    def validate(self, data):
        outbound_date = data.get('outbound_date')
        return_date = data.get('return_date')
        
        if outbound_date and return_date and outbound_date >= return_date:
            raise serializers.ValidationError("Return date must be after outbound date")
        
        return data