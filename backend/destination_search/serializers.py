from rest_framework import serializers
from .models import TripConversation, Message, Recommendations, ConversationState


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages"""
    
    class Meta:
        model = Message
        fields = ['id', 'is_user', 'content', 'timestamp']
        read_only_fields = ['id', 'timestamp']


class ConversationStateSerializer(serializers.ModelSerializer):
    """Serializer for conversation state/progress"""
    progress = serializers.SerializerMethodField()
    
    class Meta:
        model = ConversationState
        fields = [
            'current_stage',
            'questions_asked', 
            'total_questions',
            'progress'
        ]
        read_only_fields = ['current_stage', 'questions_asked', 'total_questions', 'progress']
    
    def get_progress(self, obj):
        """Calculate progress percentage"""
        return obj.get_progress_percentage()


class RecommendationsSerializer(serializers.ModelSerializer):
    """Serializer for destination recommendations"""
    
    class Meta:
        model = Recommendations
        fields = ['id', 'locations', 'created_at']
        read_only_fields = ['id', 'locations', 'created_at']


class ConversationSerializer(serializers.ModelSerializer):
    """Full conversation with all messages and state"""
    messages = MessageSerializer(many=True, read_only=True)
    state = ConversationStateSerializer(read_only=True)
    latest_recommendations = serializers.SerializerMethodField()
    
    class Meta:
        model = TripConversation
        fields = [
            'id',
            'created_at',
            'messages',
            'state',
            'latest_recommendations'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_latest_recommendations(self, obj):
        """Get the most recent recommendations if they exist"""
        latest = obj.recommendations.last()
        if latest:
            return RecommendationsSerializer(latest).data
        return None