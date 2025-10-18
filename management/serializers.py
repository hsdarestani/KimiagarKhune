from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.models import Advisor, Profile

from .models import ChatMessage, NotificationRecipient, Payment

class UserProfileSerializer(serializers.ModelSerializer):
    """
    یک سریالایزر ساده برای نمایش اطلاعات کاربر در چت و ویرایش پروفایل.
    """

    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'profile_picture', 'profile_picture_url']
        extra_kwargs = {
            'profile_picture': {'required': False, 'allow_null': True},
        }

    def get_profile_picture_url(self, obj):
        if not obj or not getattr(obj, 'profile_picture', None):
            return None
        request = self.context.get('request') if isinstance(self.context, dict) else None
        try:
            url = obj.profile_picture.url
        except ValueError:
            return None
        if request:
            return request.build_absolute_uri(url)
        return url


class PaymentSerializer(serializers.ModelSerializer):
    """
    سریالایزر برای مدل پرداخت‌ها.
    """
    # نمایش نام دانش‌آموز به جای آیدی
    student_name = serializers.CharField(source='student.profile.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'student',
            'student_name',
            'course',
            'amount',
            'reference_number',
            'payment_date',
            'status',
            'status_display',
            'created_at',
            'admin_notes',
        ]
        read_only_fields = ['student_name', 'status_display', 'created_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    سریالایزر برای پیام‌های چت.
    """
    sender_profile = UserProfileSerializer(source='sender.profile', read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'sender',
            'sender_profile',
            'receiver',
            'text',
            'file',
            'voice',
            'timestamp',
            'is_read',
        ]
        read_only_fields = ['id', 'sender', 'sender_profile', 'receiver', 'timestamp', 'is_read']
        extra_kwargs = {
            'text': {'required': False, 'allow_blank': True},
            'file': {'required': False, 'allow_null': True},
            'voice': {'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        text = attrs.get('text')
        file_obj = attrs.get('file')
        voice_obj = attrs.get('voice')

        if isinstance(text, str):
            cleaned = text.strip()
            attrs['text'] = cleaned
        else:
            cleaned = ''
            attrs['text'] = cleaned

        if not cleaned and not file_obj and not voice_obj:
            raise serializers.ValidationError('حداقل یکی از فیلدهای متن، فایل یا صوت باید ارسال شود.')

        return attrs


class AdvisorOptionSerializer(serializers.ModelSerializer):
    """"
    سریالایزر ساده برای بازگرداندن گزینه‌های مشاور برای فیلتر ادمین.
    """

    full_name = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source='profile.user_id', read_only=True)

    class Meta:
        model = Advisor
        fields = ['id', 'user_id', 'full_name']

    def get_full_name(self, obj):
        profile = getattr(obj, 'profile', None)
        if profile:
            return profile.get_full_name()
        return ''


class NotificationTargetSerializer(serializers.ModelSerializer):
    """Simple serializer for notification recipient options."""

    user_id = serializers.IntegerField(source='user.id', read_only=True)
    full_name = serializers.SerializerMethodField()
    role_display = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    advisor_id = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'user_id',
            'full_name',
            'role',
            'role_display',
            'phone_number',
            'telegram_chat_id',
            'student_id',
            'advisor_id',
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_role_display(self, obj):
        return obj.get_role_display()

    def get_student_id(self, obj):
        student = getattr(obj, 'student', None)
        return student.id if student else None

    def get_advisor_id(self, obj):
        advisor = getattr(obj, 'advisor', None)
        return advisor.id if advisor else None


class NotificationRecipientSerializer(serializers.ModelSerializer):
    """Serializer for delivered notifications shown to end users."""

    notification_id = serializers.IntegerField(source='notification.id', read_only=True)
    message = serializers.CharField(source='notification.message', read_only=True)
    created_at = serializers.DateTimeField(source='notification.created_at', read_only=True)
    sender_name = serializers.SerializerMethodField()
    channels = serializers.SerializerMethodField()

    class Meta:
        model = NotificationRecipient
        fields = [
            'id',
            'notification_id',
            'message',
            'created_at',
            'is_read',
            'telegram_sent',
            'sms_sent',
            'telegram_error',
            'sms_error',
            'sender_name',
            'channels',
        ]
        read_only_fields = fields

    def get_sender_name(self, obj):
        notification = getattr(obj, 'notification', None)
        sender = getattr(notification, 'sender', None)
        profile = getattr(sender, 'profile', None)
        if profile:
            return profile.get_full_name()
        if sender and sender.get_username():
            return sender.get_username()
        return 'ادمین'

    def get_channels(self, obj):
        notification = getattr(obj, 'notification', None)
        return {
            'panel': bool(getattr(notification, 'send_via_panel', False)),
            'telegram': bool(getattr(notification, 'send_via_telegram', False)),
            'sms': bool(getattr(notification, 'send_via_sms', False)),
        }
