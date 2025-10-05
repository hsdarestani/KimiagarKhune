from rest_framework import serializers
from .models import Course, Session, Comment
from accounts.serializers import ProfileSerializer
class CommentSerializer(serializers.ModelSerializer):
    author = ProfileSerializer(source='author.profile', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'author', 'text', 'attachment', 'voice_note', 'created_at']
        read_only_fields = ['author', 'created_at']

class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = ['id', 'session_number', 'date', 'is_completed', 'video_url']

class CourseSerializer(serializers.ModelSerializer):
    # Serializer های تو در تو برای نمایش کامل جزئیات
    sessions = SessionSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    student_name = serializers.CharField(source='student.profile.get_full_name', read_only=True)
    advisor_name = serializers.CharField(source='advisor.profile.get_full_name', read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'student', 'advisor', 'student_name', 'advisor_name', 
            'day_of_week', 'start_time', 'start_date', 'is_active', 
            'sessions', 'comments'
        ]

