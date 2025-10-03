from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Destination, PlanningSession, Trip, UserPreferences


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


# class HotelSerializer(serializers.ModelSerializer):
#     """Hotel serializer with destination details"""
#     destination = DestinationSerializer(read_only=True)

#     class Meta:
#         model = Hotel
#         fields = '__all__'


# class FlightSerializer(serializers.ModelSerializer):
#     """Flight serializer with destination details"""
#     destination = DestinationSerializer(read_only=True)
#     duration_formatted = serializers.ReadOnlyField()

#     class Meta:
#         model = Flight
#         fields = '__all__'


# class ActivitySerializer(serializers.ModelSerializer):
#     """Activity serializer"""
#     destination = DestinationSerializer(read_only=True)

#     class Meta:
#         model = Activity
#         fields = '__all__'


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
    # selected_hotel = HotelSerializer(read_only=True)
    # selected_outbound_flight = FlightSerializer(read_only=True)
    # selected_return_flight = FlightSerializer(read_only=True)
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
            'id',  # Include ID for the response
            'title', 
            'description', 
            'destination', 
            'start_date', 
            'end_date',
            'budget', 
            'travelers_count',
            'status'
        ]
        read_only_fields = ['id', 'status']  # ID and status are read-only
        extra_kwargs = {
            'description': {'required': False},
            'destination': {'required': False},
            'start_date': {'required': False},
            'end_date': {'required': False},
            'budget': {'required': False},
            'travelers_count': {'required': False},
        }

    def validate(self, data):
        """Validate trip dates"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError("End date must be after start date")
            
        return data

# Add these to api/serializers.py

class PlanningSessionListSerializer(serializers.ModelSerializer):
    """Planning session list serializer"""
    trip = TripListSerializer(read_only=True)
    progress_percentage = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()

    class Meta:
        model = PlanningSession
        fields = [
            'id', 'trip', 'current_stage', 'is_active', 'stages_completed',
            'started_at', 'last_interaction_at', 'completed_at',
            'progress_percentage', 'is_completed'
        ]


class PlanningSessionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for planning session"""
    trip = TripListSerializer(read_only=True)
    progress_percentage = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    duration_minutes = serializers.SerializerMethodField()
    next_stage = serializers.SerializerMethodField()
    
    class Meta:
        model = PlanningSession
        fields = [
            'id', 'trip', 'current_stage', 'is_active', 
            'session_data', 'stages_completed',
            'started_at', 'last_interaction_at', 'completed_at',
            'progress_percentage', 'is_completed', 'duration_minutes',
            'next_stage'
        ]
        read_only_fields = ['id', 'started_at', 'last_interaction_at', 'completed_at']
    
    
    def get_next_stage(self, obj):
        """Get the next stage in the workflow"""
        return obj.get_next_stage() if not obj.is_completed else None


class PlanningSessionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating planning sessions"""
    class Meta:
        model = PlanningSession
        fields = ['trip', 'current_stage', 'session_data']
        extra_kwargs = {
            'current_stage': {'required': False},  # Will default to 'destination'
            'session_data': {'required': False}
        }
    
    def validate_trip(self, value):
        """Ensure no other active session exists for this trip"""
        existing = PlanningSession.objects.filter(
            trip=value
        ).exclude(current_stage='completed').exists()
        
        if existing:
            raise serializers.ValidationError(
                "An active planning session already exists for this trip. Complete or delete it first."
            )
        return value


class PlanningSessionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating planning session"""
    class Meta:
        model = PlanningSession
        fields = ['current_stage', 'session_data', 'stages_completed']
        extra_kwargs = {
            'stages_completed': {'required': False}
        }
    
    def validate_current_stage(self, value):
        """Ensure valid stage value"""
        valid_stages = [stage[0] for stage in PlanningSession.PLANNING_STAGES]
        if value not in valid_stages:
            raise serializers.ValidationError(
                f"Invalid stage. Must be one of: {', '.join(valid_stages)}"
            )
        return value



