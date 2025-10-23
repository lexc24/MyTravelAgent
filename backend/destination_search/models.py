## models.py for destination recommendation django app

# Import Trip from your other app
from api.models import Trip
from django.contrib.auth.models import User
from django.db import models


class TripConversation(models.Model):
    trip = models.OneToOneField(
        Trip, on_delete=models.CASCADE, related_name="destination_conversation"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Destination conversation for {self.trip.title}"


class Message(models.Model):
    conversation = models.ForeignKey(
        TripConversation, on_delete=models.CASCADE, related_name="messages"
    )
    is_user = models.BooleanField()  # True for user messages, False for AI
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        sender = "User" if self.is_user else "AI"
        return f"{sender}: {self.content[:50]}..."


class Recommendations(models.Model):
    conversation = models.ForeignKey(
        TripConversation, on_delete=models.CASCADE, related_name="recommendations"
    )
    locations = models.JSONField()  # Store the 3 recommendations with details
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recommendations for {self.conversation.trip.title}"


class ConversationState(models.Model):
    """Store AI workflow state between messages"""

    conversation = models.OneToOneField(
        TripConversation, on_delete=models.CASCADE, related_name="state"
    )

    # Workflow state tracking
    WORKFLOW_STAGES = [
        ("initial", "Getting Initial Preferences"),
        ("generating_questions", "Generating Clarifying Questions"),
        ("asking_clarifications", "Asking Clarification Questions"),
        ("generating_destinations", "Generating Destination Recommendations"),
        ("destinations_complete", "Destinations Generated"),
        ("commitment_detected", "User Committed to Destination"),
    ]
    current_stage = models.CharField(
        max_length=50, choices=WORKFLOW_STAGES, default="initial"
    )

    # State data from LangGraph workflow
    user_info = models.TextField(
        default="", help_text="Accumulated user preferences and answers"
    )
    question_queue = models.JSONField(
        default=list, help_text="Remaining questions to ask user"
    )
    current_question_index = models.IntegerField(
        default=0, help_text="Track which question we're on"
    )
    destinations_text = models.TextField(
        blank=True, default="", help_text="Raw AI-generated destinations text"
    )

    # Metadata
    questions_asked = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"State for {self.conversation.trip.title} - {self.current_stage}"

    def is_complete(self):
        """Check if destination discovery is complete"""
        return self.current_stage in ["destinations_complete", "commitment_detected"]

    def get_progress_percentage(self):
        """Calculate conversation progress"""
        if self.total_questions > 0:
            return int((self.questions_asked / self.total_questions) * 100)
        return 0
