import logging

from api.decorators import rate_limit_api
from api.models import Destination, Trip
from api.validators import sanitize_input, validate_no_sql_injection
from django.db import transaction
from django.forms import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .logic.recommendation_engine import WorkflowManager
from .models import (ConversationState, Message, Recommendations,
                     TripConversation)

logger = logging.getLogger(__name__)

# Initialize the workflow manager
workflow_manager = WorkflowManager()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='10/m', method='POST', block=False)

def chat_message(request):
    """
    Main endpoint for destination discovery chat.
    Processes messages through the LangGraph workflow.
    
    Expected payload:
    {
        "trip_id": 123,
        "message": "I want a beach vacation"
    }
    """
    # Check if rate limited
    if getattr(request, 'limited', False):
        return Response(
            {'error': 'Too many requests. Please wait a moment and try again.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    try:
        trip_id = request.data.get('trip_id')
       ## message_text = unescape(raw)
        message_text = request.data.get('message', '').strip()
        
        # Validate and sanitize input
        try:
            validate_no_sql_injection(message_text)
            ##message_text = sanitize_input(message_text)
        except ValidationError as e:
            return Response(
                {'error': 'Invalid input detected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not trip_id or not message_text:
            return Response(
                {'error': 'trip_id and message are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get trip and verify ownership
        trip = get_object_or_404(Trip, id=trip_id, user=request.user)
        
        # Update trip status if needed
        if trip.status == 'planning':
            trip.status = 'ai_chat_active'
            trip.save()
        
        with transaction.atomic():
            # Get or create conversation
            conversation, created = TripConversation.objects.get_or_create(trip=trip)
            
            # Get or create conversation state
            conv_state, state_created = ConversationState.objects.get_or_create(
                conversation=conversation,
                defaults={'current_stage': 'initial'}
            )
            
            # Save user message
            user_message = Message.objects.create(
                conversation=conversation,
                is_user=True,
                content=message_text
            )
            
            # Process based on current stage
            ai_response_text = ""
            workflow_state = {}
            
            if conv_state.current_stage == 'initial':
                # First message - start the workflow
                workflow_state = workflow_manager.process_initial_message(message_text)
                
                # Update conversation state
                conv_state.user_info = workflow_state.get('info', '')
                conv_state.question_queue = workflow_state.get('question_queue', [])
                conv_state.total_questions = len(conv_state.question_queue)
                conv_state.current_stage = 'asking_clarifications'
                conv_state.save()
                
                # Get first question
                ai_response_text = workflow_manager.get_next_question(workflow_state)
                if ai_response_text:
                    conv_state.questions_asked = 1
                    conv_state.save()
            
            elif conv_state.current_stage == 'asking_clarifications':
                # Process answer to clarification question
                # Reconstruct workflow state from DB
                current_state = workflow_manager.db_to_state_format({
                    'user_info': conv_state.user_info,
                    'question_queue': conv_state.question_queue,
                    'destinations_text': conv_state.destinations_text,
                    'feedback': ''
                })
                
                # Process the answer
                workflow_state = workflow_manager.process_clarification_answer(current_state, message_text)
                
                # Update conversation state
                conv_state.user_info = workflow_state.get('info', '')
                conv_state.question_queue = workflow_state.get('question_queue', [])
                
                # Check if we have destinations or more questions
                if workflow_state.get('destinations'):
                    # We got destinations!
                    conv_state.destinations_text = workflow_state['destinations']
                    conv_state.current_stage = 'destinations_complete'
                    ai_response_text = workflow_state['destinations']
                    
                    # Parse and save recommendations
                    recommendations = Recommendations.objects.create(
                        conversation=conversation,
                        locations=parse_destinations(workflow_state['destinations'])
                    )
                else:
                    # More questions to ask
                    next_question = workflow_manager.get_next_question(workflow_state)
                    if next_question:
                        ai_response_text = next_question
                        conv_state.questions_asked += 1
                    else:
                        # No more questions but no destinations? Shouldn't happen
                        ai_response_text = "Let me think about some destinations for you..."
                        conv_state.current_stage = 'generating_destinations'
                
                conv_state.save()
            
            elif conv_state.current_stage == 'destinations_complete':
                # User is asking about or responding to destinations
                ai_response_text = handle_post_destination_message(
                    message_text, 
                    conversation, 
                    conv_state,
                    trip
                )
            
            else:
                # Unexpected stage
                ai_response_text = "I'm not sure what happened. Let's start over - what kind of vacation are you looking for?"
                logger.warning(f"Unexpected conversation stage: {conv_state.current_stage}")
            
            # Save AI response
            ai_message = Message.objects.create(
                conversation=conversation,
                is_user=False,
                content=ai_response_text
            )
            
            # Prepare response
            response_data = {
                'user_message': {
                    'id': user_message.id,
                    'is_user': True,                 
                    'content': user_message.content,
                    'timestamp': user_message.timestamp.isoformat()
                },
                'ai_message': {
                    'id': ai_message.id,
                    'is_user': False,                
                    'content': ai_message.content,
                    'timestamp': ai_message.timestamp.isoformat()
                },
                'conversation_id': conversation.id,
                'stage': conv_state.current_stage,
                'progress': conv_state.get_progress_percentage() if conv_state.current_stage == 'asking_clarifications' else 100
            }
            
            # Add metadata if we're asking questions
            if conv_state.current_stage == 'asking_clarifications':
                response_data['metadata'] = {
                    'question_number': conv_state.questions_asked,
                    'total_questions': conv_state.total_questions
                }
            
            # Add destinations if we just generated them
            if conv_state.current_stage == 'destinations_complete' and conv_state.destinations_text:
                latest_recs = conversation.recommendations.last()
                if latest_recs:
                    response_data['destinations'] = latest_recs.locations
            
            return Response(response_data, status=status.HTTP_200_OK)
            
    except Http404:
        # Re-raise Http404 so DRF handles it properly
        raise

    except Exception as e:
        logger.error(f"Error in chat_message: {str(e)}", exc_info=True)
        return Response(
            {'error': 'An error occurred processing your message'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
    sections = re.split(r'\n(?=\d+\.|\n)', destinations_text)
    
    for i, section in enumerate(sections[:3], 1):  # Take first 3 sections
        if section.strip():
            # Extract first line as name
            lines = section.strip().split('\n')
            name = lines[0] if lines else f"Destination {i}"
            
            # Clean up the name
            name = re.sub(r'^[\d\.\)\-\*\s]+', '', name).strip()
            
            # Try to extract country if mentioned
            country = ""
            if ',' in name:
                parts = name.split(',')
                name = parts[0].strip()
                country = parts[1].strip() if len(parts) > 1 else ""
            
            destinations.append({
                'name': name[:100],  # Limit length
                'country': country[:100],
                'description': '\n'.join(lines[1:])[:500] if len(lines) > 1 else ""
            })
    
    # Ensure we have 3 destinations
    while len(destinations) < 3:
        destinations.append({
            'name': f"Option {len(destinations) + 1}",
            'country': "",
            'description': "Additional destination option"
        })
    
    return destinations[:3]


def handle_post_destination_message(message_text, conversation, conv_state, trip):
    """
    Handle messages after destinations have been generated.
    Check for commitment phrases and update trip if needed.
    """
    # Simple commitment detection
    commitment_phrases = [
        "let's do", "let's go with", "i want to plan", "book",
        "perfect", "that's the one", "yes to", "definitely",
        "i choose", "i pick", "i'll take", "sounds perfect"
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
            dest_name = dest.get('name', '').lower()
            dest_country = dest.get('country', '').lower()
            
            if dest_name in message_lower or (dest_country and dest_country in message_lower):
                # Found the destination!
                # Create or get destination in database
                destination, created = Destination.objects.get_or_create(
                    name=dest['name'],
                    defaults={'country': dest.get('country', '')}
                )
                
                # Update trip
                trip.destination = destination
                trip.status = 'destinations_selected'
                trip.save()
                
                # Update conversation state
                conv_state.current_stage = 'commitment_detected'
                conv_state.save()
                
                return f"Excellent choice! {dest['name']} it is! I've updated your trip. You're ready to move on to planning accommodations and activities!"
        
        # Committed but couldn't identify which destination
        return "Great! Which of the three destinations would you like to go with? Just let me know the name or number (1, 2, or 3)."
    
    # Not committing, just asking questions or discussing
    return "I'd be happy to tell you more about any of these destinations! Which one interests you most, or would you like me to suggest different options?"


@api_view(['GET'])
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
            messages = Message.objects.filter(conversation=conversation).order_by('timestamp')
            
            # Get conversation state
            conv_state = None
            if hasattr(conversation, 'state'):
                conv_state = conversation.state
            
            # Build response
            response_data = {
                'conversation_id': conversation.id,
                'trip_id': trip.id,
                'trip_title': trip.title,
                'messages': [
                    {
                        'id': msg.id,
                        'is_user': msg.is_user,
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat()
                    }
                    for msg in messages
                ],
                'state': {
                    'current_stage': conv_state.current_stage if conv_state else 'initial',
                    'progress': conv_state.get_progress_percentage() if conv_state else 0,
                    'questions_asked': conv_state.questions_asked if conv_state else 0,
                    'total_questions': conv_state.total_questions if conv_state else 0
                } if conv_state else None
            }
            
            # Add recommendations if they exist
            if conversation.recommendations.exists():
                latest_recs = conversation.recommendations.last()
                response_data['destinations'] = latest_recs.locations
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except TripConversation.DoesNotExist:
            return Response(
                {'message': 'No conversation started yet for this trip'},
                status=status.HTTP_404_NOT_FOUND
            )
            
    except Http404:
        # Re-raise Http404 so DRF handles it properly
        raise

    except Exception as e:
        logger.error(f"Error in get_conversation: {str(e)}", exc_info=True)
        return Response(
            {'error': 'An error occurred fetching the conversation'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
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
            trip.status = 'planning'
            trip.destination = None
            trip.save()
            
            return Response(
                {'message': 'Conversation reset successfully'},
                status=status.HTTP_200_OK
            )
    except Http404:
        # Re-raise Http404 so DRF handles it properly
        raise

    except Exception as e:
        logger.error(f"Error in reset_conversation: {str(e)}", exc_info=True)
        return Response(
            {'error': 'An error occurred resetting the conversation'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )