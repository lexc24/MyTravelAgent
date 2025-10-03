# api/models.py - Core Models for Travel Planning

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class UserPreferences(models.Model):
    """Store user travel preferences discovered by AI conversations"""
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


class Trip(models.Model):
    """Main trip planning entity"""
    # id field is automatically created by Django as primary key
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


# Updated PlanningSession model in api/models.py

class PlanningSession(models.Model):
    """Manages different planning phases for trip planning"""
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='planning_sessions')
    
    # Planning stages - REMOVED 'paused' option
    PLANNING_STAGES = [
        ('destination', 'Destination Selection'),
        ('accommodation', 'Hotel/Accommodation Planning'),
        ('flights', 'Flight Planning'),
        ('activities', 'Activity Planning'),
        ('itinerary', 'Itinerary Building'),
        ('finalization', 'Final Review'),
        ('completed', 'Planning Completed'),
        # REMOVED: ('paused', 'Session Paused'),
    ]
    current_stage = models.CharField(max_length=20, choices=PLANNING_STAGES, default='destination')
    
    # Session state - Consider removing is_active field entirely
    # is_active just duplicates what we can infer from current_stage != 'completed'
    is_active = models.BooleanField(default=True)  # Consider removing this
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
        stage_order = ['destination', 'accommodation', 'flights', 'activities', 'itinerary', 'finalization', 'completed']
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
            self.is_active = False  # Or remove this line if you remove is_active field
            self.completed_at = timezone.now()
        self.save()
    
    def get_progress_percentage(self):
        """Calculate progress through planning stages"""
        stage_order = ['destination', 'accommodation', 'flights', 'activities', 'itinerary', 'finalization']
        if self.current_stage == 'completed':
            return 100
        try:
            current_index = stage_order.index(self.current_stage)
            return round((current_index / len(stage_order)) * 100, 1)
        except ValueError:
            return 0
    
    @property
    def is_completed(self):
        """Check if planning is complete"""
        return self.current_stage == 'completed'

    class Meta:
        ordering = ['-last_interaction_at']
        # Add constraint: only one non-completed session per trip
        constraints = [
            models.UniqueConstraint(
                fields=['trip'],
                condition=~models.Q(current_stage='completed'),
                name='unique_active_session_per_trip'
            )
        ]

# ============================================
# Mock Models for Future Features (Basic for testing)
# ============================================


