# destination_recommendations/urls.py

from django.urls import path
from . import views

app_name = 'destination_recommendations'

urlpatterns = [
    # Main chat endpoint - handles all message processing
    path('chat/', views.chat_message, name='chat_message'),
    
    # Get conversation history for a trip
    path('conversations/<int:trip_id>/', views.get_conversation, name='get_conversation'),
    
    # Reset conversation (start over)
    path('conversations/<int:trip_id>/reset/', views.reset_conversation, name='reset_conversation'),
]

