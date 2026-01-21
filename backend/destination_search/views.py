# destination_search/views.py - Enhanced with OpenAPI/Swagger Documentation

import logging

from api.decorators import rate_limit_api
from api.models import Destination, Trip
from api.validators import sanitize_input, validate_no_sql_injection
from django.db import transaction
from django.forms import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit

# ADD THESE IMPORTS for Swagger documentation
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .logic.recommendation_engine import WorkflowManager
from .models import ConversationState, Message, Recommendations, TripConversation

logger = logging.getLogger(__name__)

# Initialize the workflow manager
workflow_manager = WorkflowManager()


@extend_schema(
    summary="Send a message to the AI destination chat",
    description="""
    The core endpoint for AI-powered destination discovery. Users describe their ideal vacation,
    and the AI engages in a conversation to gather preferences and recommend destinations.

    **Conversation Flow:**
    1. **Initial Message** - User describes what they're looking for
    2. **Clarification Questions** - AI asks 2-5 questions to understand preferences
    3. **Destination Recommendations** - AI provides 3 personalized destination suggestions
    4. **Post-Recommendations** - User can ask questions or commit to a destination

    **Rate Limit:** 10 messages per minute per user

    **Important Notes:**
    - Trip must belong to the authenticated user
    - Empty or whitespace-only messages are rejected
    - Trip status automatically updates to 'ai_chat_active' when chat starts
    - When user commits to a destination, it's saved to the trip and status changes to 'destinations_selected'
    """,
    request=inline_serializer(
        name="ChatMessageRequest",
        fields={
            "trip_id": serializers.IntegerField(
                help_text="ID of the trip to chat about"
            ),
            "message": serializers.CharField(
                help_text="User's message to the AI assistant"
            ),
        },
    ),
    responses={
        200: OpenApiResponse(
            description="Message processed successfully",
            examples=[
                OpenApiExample(
                    "Initial Message Response",
                    value={
                        "user_message": {
                            "id": 1,
                            "is_user": True,
                            "content": "I want a beach vacation",
                            "timestamp": "2024-01-20T12:00:00Z",
                        },
                        "ai_message": {
                            "id": 2,
                            "is_user": False,
                            "content": "What's your budget for this trip?",
                            "timestamp": "2024-01-20T12:00:01Z",
                        },
                        "conversation_id": 1,
                        "stage": "asking_clarifications",
                        "progress": 20,
                        "metadata": {
                            "question_number": 1,
                            "total_questions": 5,
                        },
                    },
                ),
                OpenApiExample(
                    "Destinations Generated Response",
                    value={
                        "user_message": {
                            "id": 11,
                            "is_user": True,
                            "content": "Around $3000",
                            "timestamp": "2024-01-20T12:05:00Z",
                        },
                        "ai_message": {
                            "id": 12,
                            "is_user": False,
                            "content": "Here are 3 destinations...",
                            "timestamp": "2024-01-20T12:05:02Z",
                        },
                        "conversation_id": 1,
                        "stage": "destinations_complete",
                        "progress": 100,
                        "destinations": [
                            {
                                "name": "Bali",
                                "country": "Indonesia",
                                "description": "Tropical paradise with beaches and culture",
                            },
                            {
                                "name": "Greece",
                                "country": "Greece",
                                "description": "Mediterranean beauty with islands",
                            },
                            {
                                "name": "Thailand",
                                "country": "Thailand",
                                "description": "Affordable beaches and rich culture",
                            },
                        ],
                    },
                ),
            ],
        ),
        400: OpenApiResponse(
            description="Validation error",
            examples=[
                OpenApiExample(
                    "Missing Fields",
                    value={"error": "trip_id and message are required"},
                ),
                OpenApiExample(
                    "Empty Message",
                    value={"error": "trip_id and message are required"},
                ),
                OpenApiExample(
                    "Invalid Input Detected",
                    value={"error": "Invalid input detected"},
                ),
            ],
        ),
        404: OpenApiResponse(
            description="Trip not found or you don't have permission to access it"
        ),
        429: OpenApiResponse(
            description="Rate limit exceeded - too many messages sent (10 per minute)"
        ),
        500: OpenApiResponse(
            description="AI service error - the recommendation engine encountered an issue",
            examples=[
                OpenApiExample(
                    "AI Service Error",
                    value={"error": "An error occurred processing your message"},
                )
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "Initial Message",
            value={
                "trip_id": 1,
                "message": "I want a relaxing beach vacation with good food",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Answer Clarification",
            value={
                "trip_id": 1,
                "message": "My budget is around $3000 for 2 weeks",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Commitment to Destination",
            value={
                "trip_id": 1,
                "message": "Let's go with Bali! That sounds perfect.",
            },
            request_only=True,
        ),
    ],
    tags=["Destination Discovery"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@ratelimit(key="user", rate="10/m", method="POST", block=False)
def chat_message(request):
    """
    Main endpoint for destination discovery chat.
    Processes messages through the LangGraph workflow.
    """
    # Check if rate limited
    if getattr(request, "limited", False):
        return Response(
            {"error": "Too many requests. Please wait a moment and try again."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        trip_id = request.data.get("trip_id")
        message_text = request.data.get("message", "").strip()

        # Validate and sanitize input
        try:
            validate_no_sql_injection(message_text)
        except ValidationError as e:
            return Response(
                {"error": "Invalid input detected"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not trip_id or not message_text:
            return Response(
                {"error": "trip_id and message are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get trip and verify ownership
        trip = get_object_or_404(Trip, id=trip_id, user=request.user)

        # Update trip status if needed
        if trip.status == "planning":
            trip.status = "ai_chat_active"
            trip.save()

        with transaction.atomic():
            # Get or create conversation
            conversation, created = TripConversation.objects.get_or_create(trip=trip)

            # Get or create conversation state
            conv_state, state_created = ConversationState.objects.get_or_create(
                conversation=conversation, defaults={"current_stage": "initial"}
            )

            # Save user message
            user_message = Message.objects.create(
                conversation=conversation, is_user=True, content=message_text
            )

            # Process based on current stage
            ai_response_text = ""
            workflow_state = {}

            if conv_state.current_stage == "initial":
                # First message - start the workflow
                workflow_state = workflow_manager.process_initial_message(message_text)

                # Update conversation state
                conv_state.user_info = workflow_state.get("info", "")
                conv_state.question_queue = workflow_state.get("question_queue", [])
                conv_state.total_questions = len(conv_state.question_queue)
                conv_state.current_stage = "asking_clarifications"
                conv_state.save()

                # Get first question
                ai_response_text = workflow_manager.get_next_question(workflow_state)
                if ai_response_text:
                    conv_state.questions_asked = 1
                    conv_state.save()

            elif conv_state.current_stage == "asking_clarifications":
                # Process answer to clarification question
                # Reconstruct workflow state from DB
                current_state = workflow_manager.db_to_state_format(
                    {
                        "user_info": conv_state.user_info,
                        "question_queue": conv_state.question_queue,
                        "destinations_text": conv_state.destinations_text,
                        "feedback": "",
                    }
                )

                # Process the answer
                workflow_state = workflow_manager.process_clarification_answer(
                    current_state, message_text
                )

                # Update conversation state
                conv_state.user_info = workflow_state.get("info", "")
                conv_state.question_queue = workflow_state.get("question_queue", [])

                # Check if we have destinations or more questions
                if workflow_state.get("destinations"):
                    # We got destinations!
                    conv_state.destinations_text = workflow_state["destinations"]
                    conv_state.current_stage = "destinations_complete"
                    ai_response_text = workflow_state["destinations"]

                    # Parse and save recommendations
                    recommendations = Recommendations.objects.create(
                        conversation=conversation,
                        locations=parse_destinations(workflow_state["destinations"]),
                    )
                else:
                    # More questions to ask
                    next_question = workflow_manager.get_next_question(workflow_state)
                    if next_question:
                        ai_response_text = next_question
                        conv_state.questions_asked += 1
                    else:
                        # No more questions but no destinations? Shouldn't happen
                        ai_response_text = (
                            "Let me think about some destinations for you..."
                        )
                        conv_state.current_stage = "generating_destinations"

                conv_state.save()

            elif conv_state.current_stage == "destinations_complete":
                # User is asking about or responding to destinations
                ai_response_text = handle_post_destination_message(
                    message_text, conversation, conv_state, trip
                )

            else:
                # Unexpected stage
                ai_response_text = "I'm not sure what happened. Let's start over - what kind of vacation are you looking for?"
                logger.warning(
                    f"Unexpected conversation stage: {conv_state.current_stage}"
                )

            # Save AI response
            ai_message = Message.objects.create(
                conversation=conversation, is_user=False, content=ai_response_text
            )

            # Prepare response
            response_data = {
                "user_message": {
                    "id": user_message.id,
                    "is_user": True,
                    "content": user_message.content,
                    "timestamp": user_message.timestamp.isoformat(),
                },
                "ai_message": {
                    "id": ai_message.id,
                    "is_user": False,
                    "content": ai_message.content,
                    "timestamp": ai_message.timestamp.isoformat(),
                },
                "conversation_id": conversation.id,
                "stage": conv_state.current_stage,
                "progress": (
                    conv_state.get_progress_percentage()
                    if conv_state.current_stage == "asking_clarifications"
                    else 100
                ),
            }

            # Add metadata if we're asking questions
            if conv_state.current_stage == "asking_clarifications":
                response_data["metadata"] = {
                    "question_number": conv_state.questions_asked,
                    "total_questions": conv_state.total_questions,
                }

            # Add destinations if we just generated them
            if (
                conv_state.current_stage == "destinations_complete"
                and conv_state.destinations_text
            ):
                latest_recs = conversation.recommendations.last()
                if latest_recs:
                    response_data["destinations"] = latest_recs.locations

            return Response(response_data, status=status.HTTP_200_OK)

    except Http404:
        # Re-raise Http404 so DRF handles it properly
        raise

    except Exception as e:
        logger.error(f"Error in chat_message: {str(e)}", exc_info=True)
        return Response(
            {"error": "An error occurred processing your message"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def parse_destinations(destinations_text):
    """
    Parse the AI-generated destinations text into structured data.
    Returns a list of destination dictionaries.
    """
    # Simple parser - you can make this more sophisticated
    destinations = []

    # Try to split by numbers (1., 2., 3.) or double newlines
    import re

    sections = re.split(r"\n(?=\d+\.|\n)", destinations_text)

    for i, section in enumerate(sections[:3], 1):  # Take first 3 sections
        if section.strip():
            # Extract first line as name
            lines = section.strip().split("\n")
            name = lines[0] if lines else f"Destination {i}"

            # Clean up the name
            name = re.sub(r"^[\d\.\)\-\*\s]+", "", name).strip()

            # Try to extract country if mentioned
            country = ""
            if "," in name:
                parts = name.split(",")
                name = parts[0].strip()
                country = parts[1].strip() if len(parts) > 1 else ""

            destinations.append(
                {
                    "name": name[:100],  # Limit length
                    "country": country[:100],
                    "description": "\n".join(lines[1:])[:500] if len(lines) > 1 else "",
                }
            )

    # Ensure we have 3 destinations
    while len(destinations) < 3:
        destinations.append(
            {
                "name": f"Option {len(destinations) + 1}",
                "country": "",
                "description": "Additional destination option",
            }
        )

    return destinations[:3]


def handle_post_destination_message(message_text, conversation, conv_state, trip):
    """
    Handle messages after destinations have been generated.
    Check for commitment phrases and update trip if needed.
    """
    # Simple commitment detection
    commitment_phrases = [
        "let's do",
        "let's go with",
        "i want to plan",
        "book",
        "perfect",
        "that's the one",
        "yes to",
        "definitely",
        "i choose",
        "i pick",
        "i'll take",
        "sounds perfect",
    ]

    message_lower = message_text.lower()

    # Get latest recommendations
    latest_recs = conversation.recommendations.last()
    if not latest_recs:
        return "I don't see any destinations yet. Let me help you find some!"

    # Check for commitment
    committed = any(phrase in message_lower for phrase in commitment_phrases)

    if committed:
        # Try to identify which destination
        for dest in latest_recs.locations:
            dest_name = dest.get("name", "").lower()
            dest_country = dest.get("country", "").lower()

            if dest_name in message_lower or (
                dest_country and dest_country in message_lower
            ):
                # Found the destination!
                # Create or get destination in database
                destination, created = Destination.objects.get_or_create(
                    name=dest["name"], defaults={"country": dest.get("country", "")}
                )

                # Update trip
                trip.destination = destination
                trip.status = "destinations_selected"
                trip.save()

                # Update conversation state
                conv_state.current_stage = "commitment_detected"
                conv_state.save()

                return f"Excellent choice! {dest['name']} it is! I've updated your trip. You're ready to move on to planning accommodations and activities!"

        # Committed but couldn't identify which destination
        return "Great! Which of the three destinations would you like to go with? Just let me know the name or number (1, 2, or 3)."

    # Not committing, just asking questions or discussing
    return "I'd be happy to tell you more about any of these destinations! Which one interests you most, or would you like me to suggest different options?"


@extend_schema(
    summary="Get conversation history for a trip",
    description="""
    Retrieve the complete conversation history between the user and AI for a specific trip.

    **Returns:**
    - All messages in chronological order
    - Current conversation stage and progress
    - Latest destination recommendations (if generated)
    - Trip information

    **Conversation not started yet?**
    - Returns 404 with helpful message
    - Start a conversation by sending a message to the chat endpoint
    """,
    responses={
        200: OpenApiResponse(
            description="Conversation retrieved successfully",
            examples=[
                OpenApiExample(
                    "Conversation with Destinations",
                    value={
                        "conversation_id": 1,
                        "trip_id": 1,
                        "trip_title": "Summer Vacation 2024",
                        "messages": [
                            {
                                "id": 1,
                                "is_user": True,
                                "content": "I want a beach vacation",
                                "timestamp": "2024-01-20T12:00:00Z",
                            },
                            {
                                "id": 2,
                                "is_user": False,
                                "content": "What's your budget?",
                                "timestamp": "2024-01-20T12:00:01Z",
                            },
                        ],
                        "state": {
                            "current_stage": "destinations_complete",
                            "progress": 100,
                            "questions_asked": 5,
                            "total_questions": 5,
                        },
                        "destinations": [
                            {
                                "name": "Bali",
                                "country": "Indonesia",
                                "description": "Tropical paradise",
                            }
                        ],
                    },
                )
            ],
        ),
        404: OpenApiResponse(
            description="No conversation started yet for this trip",
            examples=[
                OpenApiExample(
                    "No Conversation",
                    value={"message": "No conversation started yet for this trip"},
                )
            ],
        ),
    },
    tags=["Destination Discovery"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_conversation(request, trip_id):
    """
    Get the full conversation history for a trip.
    """
    try:
        # Verify trip ownership
        trip = get_object_or_404(Trip, id=trip_id, user=request.user)

        # Get conversation if exists
        try:
            conversation = TripConversation.objects.get(trip=trip)

            # Get all messages
            messages = Message.objects.filter(conversation=conversation).order_by(
                "timestamp"
            )

            # Get conversation state
            conv_state = None
            if hasattr(conversation, "state"):
                conv_state = conversation.state

            # Build response
            response_data = {
                "conversation_id": conversation.id,
                "trip_id": trip.id,
                "trip_title": trip.title,
                "messages": [
                    {
                        "id": msg.id,
                        "is_user": msg.is_user,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in messages
                ],
                "state": (
                    {
                        "current_stage": (
                            conv_state.current_stage if conv_state else "initial"
                        ),
                        "progress": (
                            conv_state.get_progress_percentage() if conv_state else 0
                        ),
                        "questions_asked": (
                            conv_state.questions_asked if conv_state else 0
                        ),
                        "total_questions": (
                            conv_state.total_questions if conv_state else 0
                        ),
                    }
                    if conv_state
                    else None
                ),
            }

            # Add recommendations if they exist
            if conversation.recommendations.exists():
                latest_recs = conversation.recommendations.last()
                response_data["destinations"] = latest_recs.locations

            return Response(response_data, status=status.HTTP_200_OK)

        except TripConversation.DoesNotExist:
            return Response(
                {"message": "No conversation started yet for this trip"},
                status=status.HTTP_404_NOT_FOUND,
            )

    except Http404:
        # Re-raise Http404 so DRF handles it properly
        raise

    except Exception as e:
        logger.error(f"Error in get_conversation: {str(e)}", exc_info=True)
        return Response(
            {"error": "An error occurred fetching the conversation"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Reset/delete the conversation for a trip",
    description="""
    Start over with destination discovery by deleting the entire conversation.

    **What gets deleted:**
    - All conversation messages
    - Conversation state and progress
    - Generated destination recommendations

    **What gets reset:**
    - Trip status changes back to "planning"
    - Destination selection is cleared from trip

    **Warning:** This action cannot be undone. The conversation history will be permanently deleted.
    """,
    request=None,
    responses={
        200: OpenApiResponse(
            description="Conversation reset successfully",
            examples=[
                OpenApiExample(
                    "Reset Success",
                    value={"message": "Conversation reset successfully"},
                )
            ],
        ),
        404: OpenApiResponse(description="Trip not found or you don't have permission"),
    },
    tags=["Destination Discovery"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reset_conversation(request, trip_id):
    """
    Reset the conversation for a trip (start over).
    """
    try:
        # Verify trip ownership
        trip = get_object_or_404(Trip, id=trip_id, user=request.user)

        with transaction.atomic():
            # Delete existing conversation and all related data
            TripConversation.objects.filter(trip=trip).delete()

            # Reset trip status
            trip.status = "planning"
            trip.destination = None
            trip.save()

            return Response(
                {"message": "Conversation reset successfully"},
                status=status.HTTP_200_OK,
            )
    except Http404:
        # Re-raise Http404 so DRF handles it properly
        raise

    except Exception as e:
        logger.error(f"Error in reset_conversation: {str(e)}", exc_info=True)
        return Response(
            {"error": "An error occurred resetting the conversation"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
