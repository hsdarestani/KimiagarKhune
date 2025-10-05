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
    
    class Meta:
        model = User
        fields = ['id', 'username', 'profile', 'last_message', 'unread_count']

    def get_last_message(self, obj):
        # این متد آخرین پیام را برای نمایش در لیست چت‌ها برمی‌گرداند
        # پیاده‌سازی کامل آن نیاز به کوئری پیچیده‌تر در ویو دارد
        return "آخرین پیام..."

    def get_unread_count(self, obj):
        # این متد تعداد پیام‌های خوانده‌نشده را برمی‌گرداند
        # پیاده‌سازی کامل آن نیاز به کوئری در ویو دارد
        return 0
