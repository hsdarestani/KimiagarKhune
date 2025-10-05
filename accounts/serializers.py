from rest_framework import serializers
from .models import Profile, Student, Advisor

class ProfileSerializer(serializers.ModelSerializer):
    """
    سریالایزر برای مدل پروفایل جهت نمایش اطلاعات پایه کاربر.
    """
    # متد زیر نام کامل کاربر را برمی‌گرداند
    full_name = serializers.CharField(source='__str__', read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'user', 'role', 'first_name', 'last_name', 'phone_number', 'email', 'profile_picture', 'telegram_chat_id', 'full_name']


class AdvisorSerializer(serializers.ModelSerializer):
    """
    سریالایزر برای نمایش اطلاعات مشاور.
    """
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = Advisor
        fields = ['id', 'profile', 'bio']


class StudentSerializer(serializers.ModelSerializer):
    """
    سریالایزر برای نمایش اطلاعات دانش‌آموز.
    """
    profile = ProfileSerializer(read_only=True)
    advisor = AdvisorSerializer(read_only=True)
    major_name = serializers.CharField(source='major.name', read_only=True)
    grade_name = serializers.CharField(source='grade.name', read_only=True)

    class Meta:
        model = Student
        fields = ['id', 'profile', 'school', 'major_name', 'grade_name', 'advisor']

