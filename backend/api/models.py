from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# User Preferences Model
class UserPreferences(models.Model):
    """Store user travel preferences discovered by AI"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    
    # AI-discovered preferences stored as text
    preferences_text = models.TextField(blank=True, help_text="AI-discovered user travel preferences")
    
    # Optional structured data for future use
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    preferred_group_size = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Preferences"


# Destination Model (Basic for sprint)
class Destination(models.Model):
    """Basic destination information"""
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    
    # Basic travel info
    best_time_to_visit = models.CharField(max_length=200, null=True, blank=True)
    average_cost_per_day = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Geographic info
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}, {self.country}"

    class Meta:
        unique_together = ['name', 'country']


# Trip Model - Core entity
class Trip(models.Model):
    """Main trip planning entity"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trips')
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    
    # Trip details
    destination = models.ForeignKey(Destination, on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Trip status
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('ai_chat_active', 'AI Chat Active'),
        ('destinations_selected', 'Destination Selected'),
        ('hotels_selected', 'Hotels Selected'),
        ('flights_selected', 'Flights Selected'),
        ('activities_planned', 'Activities Planned'),
        ('itinerary_complete', 'Itinerary Complete'),
        ('booked', 'Booked'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=21, choices=STATUS_CHOICES, default='planning')
    
    # Number of travelers
    travelers_count = models.PositiveIntegerField(default=1)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def duration_days(self):
        """Calculate trip duration in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return None

    def is_future_trip(self):
        """Check if trip is in the future"""
        if self.start_date:
            return self.start_date > timezone.now().date()
        return True  # Default to True if no date set

    class Meta:
        ordering = ['-created_at']


# Planning Session Model - AI Conversation Management
class PlanningSession(models.Model):
    """Manages AI conversation sessions for trip planning"""
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='planning_sessions')
    
    # Planning stages
    PLANNING_STAGES = [
        ('destination', 'Destination Selection'),
        ('accommodation', 'Hotel/Accommodation Planning'),
        ('flights', 'Flight Planning'),
        ('activities', 'Activity Planning'),
        ('itinerary', 'Itinerary Building'),
        ('finalization', 'Final Review'),
        ('completed', 'Planning Completed'),
        ('paused', 'Session Paused'),
    ]
    current_stage = models.CharField(max_length=20, choices=PLANNING_STAGES, default='destination')
    
    # Session state
    is_active = models.BooleanField(default=True)
    session_data = models.JSONField(default=dict, blank=True)  # Store session context
    
    # Progress tracking
    stages_completed = models.JSONField(default=list, blank=True)  # List of completed stages
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    last_interaction_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Planning Session for {self.trip.title} - Stage: {self.current_stage}"

    def mark_stage_completed(self, stage):
        """Mark a planning stage as completed"""
        if stage not in self.stages_completed:
            self.stages_completed.append(stage)
            self.save()

    def get_next_stage(self):
        """Get the next planning stage"""
        stage_order = [choice[0] for choice in self.PLANNING_STAGES[:-2]]  # Exclude completed and paused
        try:
            current_index = stage_order.index(self.current_stage)
            if current_index < len(stage_order) - 1:
                return stage_order[current_index + 1]
        except ValueError:
            pass
        return 'completed'

    def advance_to_next_stage(self):
        """Advance to the next planning stage"""
        self.mark_stage_completed(self.current_stage)
        next_stage = self.get_next_stage()
        self.current_stage = next_stage
        if next_stage == 'completed':
            self.is_active = False
            self.completed_at = timezone.now()
        self.save()

    class Meta:
        ordering = ['-last_interaction_at']


# Conversation Model - AI Chat History
class Conversation(models.Model):
    """Store individual messages in AI conversation"""
    planning_session = models.ForeignKey(PlanningSession, on_delete=models.CASCADE, related_name='conversations')
    
    MESSAGE_TYPES = [
        ('user', 'User Message'),
        ('ai', 'AI Response'),
        ('system', 'System Message'),
    ]
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    content = models.TextField()
    
    # Context
    stage_when_sent = models.CharField(max_length=20, null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.message_type.title()} message in {self.planning_session.trip.title}"

    class Meta:
        ordering = ['created_at']


# Mock Models for Bookings (Basic for testing)
class Hotel(models.Model):
    """Mock hotel data for testing"""
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='hotels')
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2)
    rating = models.DecimalField(max_digits=2, decimal_places=1, validators=[MinValueValidator(0), MaxValueValidator(5)])
    
    # Hotel details
    address = models.TextField(null=True, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    room_types = models.JSONField(default=list, blank=True)  # ['Standard', 'Deluxe', 'Suite']
    
    # Availability (simplified for mock data)
    available = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.destination.name}"


class Flight(models.Model):
    """Mock flight data for testing"""
    origin = models.CharField(max_length=100)
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='flights')
    airline = models.CharField(max_length=100)
    flight_number = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_minutes = models.PositiveIntegerField()
    
    # Flight details
    departure_time = models.TimeField()
    arrival_time = models.TimeField()
    stops = models.PositiveIntegerField(default=0)
    aircraft_type = models.CharField(max_length=100, null=True, blank=True)
    
    # Flight type
    FLIGHT_TYPES = [
        ('outbound', 'Outbound'),
        ('return', 'Return'),
        ('domestic', 'Domestic/Internal'),
    ]
    flight_type = models.CharField(max_length=10, choices=FLIGHT_TYPES, default='outbound')
    
    # Availability (simplified for mock data)
    available_seats = models.PositiveIntegerField(default=100)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.airline} {self.flight_number} - {self.origin} to {self.destination.name}"

    def duration_formatted(self):
        """Return flight duration in HH:MM format"""
        hours = self.duration_minutes // 60
        minutes = self.duration_minutes % 60
        return f"{hours}h {minutes}m"


class Activity(models.Model):
    """Mock activity data for testing"""
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='activities')
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    duration_hours = models.PositiveIntegerField(null=True, blank=True)
    
    ACTIVITY_CATEGORIES = [
        ('cultural', 'Cultural'),
        ('adventure', 'Adventure'),
        ('food', 'Food & Dining'),
        ('nature', 'Nature & Outdoors'),
        ('entertainment', 'Entertainment'),
        ('shopping', 'Shopping'),
        ('relaxation', 'Relaxation'),
    ]
    category = models.CharField(max_length=20, choices=ACTIVITY_CATEGORIES)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.destination.name}"


class Flight(models.Model):
    """Mock flight data for testing"""
    origin = models.CharField(max_length=100)
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='flights')
    airline = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_minutes = models.PositiveIntegerField()
    
    # Flight details
    departure_time = models.TimeField(null=True, blank=True)
    arrival_time = models.TimeField(null=True, blank=True)
    stops = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.airline} - {self.origin} to {self.destination.name}"