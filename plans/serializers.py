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
    plan_uploaded_by = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = [
            'id',
            'session_number',
            'date',
            'is_completed',
            'video_url',
            'plan_file',
            'plan_uploaded_at',
            'plan_uploaded_by',
        ]
        read_only_fields = ['plan_file', 'plan_uploaded_at', 'plan_uploaded_by']

    def get_plan_uploaded_by(self, obj):
        user = getattr(obj, 'plan_uploaded_by', None)
        if not user:
            return None
        profile = getattr(user, 'profile', None)
        if profile:
            return ProfileSerializer(profile, context=self.context).data
        return {
            'id': user.id,
            'username': user.get_username(),
            'full_name': user.get_full_name() or user.get_username(),
        }

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
            'class_link', 'sessions', 'comments'
        ]

