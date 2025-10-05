from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Payment, ChatMessage
from accounts.models import Profile

class UserProfileSerializer(serializers.ModelSerializer):
    """
    یک سریالایزر ساده برای نمایش اطلاعات کاربر در چت.
    """
    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'profile_picture']


class PaymentSerializer(serializers.ModelSerializer):
    """
    سریالایزر برای مدل پرداخت‌ها.
    """
    # نمایش نام دانش‌آموز به جای آیدی
    student_name = serializers.CharField(source='student.profile.get_full_name', read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'student', 'student_name', 'course', 'amount', 'reference_number', 'payment_date', 'status', 'created_at', 'admin_notes']
        read_only_fields = ['student_name', 'created_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    سریالایزر برای پیام‌های چت.
    """
    sender_profile = UserProfileSerializer(source='sender.profile', read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'sender', 'sender_profile', 'receiver', 'text', 'file', 'voice', 'timestamp', 'is_read']
        read_only_fields = ['sender', 'sender_profile', 'timestamp']


class ConversationSerializer(serializers.ModelSerializer):
    """
    سریالایزر برای نمایش لیست گفتگوها.
    """
    profile = UserProfileSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'profile', 'last_message', 'last_message_at', 'unread_count']

    def _get_meta(self, obj):
        meta = self.context.get('conversation_meta', {})
        return meta.get(obj.id, {})

    def get_last_message(self, obj):
        meta = self._get_meta(obj)
        return meta.get('last_message', '')

    def get_last_message_at(self, obj):
        meta = self._get_meta(obj)
        ts = meta.get('last_message_at')
        return ts.isoformat() if ts else None

    def get_unread_count(self, obj):
        meta = self._get_meta(obj)
        return meta.get('unread_count', 0)
