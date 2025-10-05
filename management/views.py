import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Advisor, Student
from plans.models import Course
from .models import ChatMessage, Payment
from .serializers import (ChatMessageSerializer, ConversationSerializer,
                          PaymentSerializer)

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    اجازه دسترسی کامل به ادمین و دسترسی فقط خواندنی به دیگران.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff

class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet برای مدیریت پرداخت‌ها. فقط ادمین دسترسی کامل دارد.
    """
    queryset = Payment.objects.all().order_by('-created_at')
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=True, methods=['post'], url_path='approve')
    def approve_payment(self, request, pk=None):
        payment = self.get_object()
        payment.status = 'approved'
        payment.save()
        # You can add logic here to activate the student's course
        return Response({'status': 'Payment approved'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject_payment(self, request, pk=None):
        payment = self.get_object()
        payment.status = 'rejected'
        notes = request.data.get('notes')
        if notes:
            payment.admin_notes = notes
        payment.save()
        return Response({'status': 'Payment rejected'}, status=status.HTTP_200_OK)


class ConversationListView(APIView):
    """
    View برای نمایش لیست گفتگوهای کاربر لاگین کرده.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        messages = ChatMessage.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).select_related('sender__profile', 'receiver__profile')

        conversation_meta = {}
        for msg in messages:
            other_user = msg.receiver if msg.sender_id == user.id else msg.sender
            if other_user_id := getattr(other_user, 'id', None):
                meta = conversation_meta.setdefault(
                    other_user_id,
                    {
                        'last_message': '',
                        'last_message_at': None,
                        'unread_count': 0,
                    },
                )

                if not meta['last_message_at'] or msg.timestamp > meta['last_message_at']:
                    if msg.text:
                        preview = msg.text
                    elif msg.file:
                        preview = '📎 فایل ضمیمه'
                    elif msg.voice:
                        preview = '🎤 پیام صوتی'
                    else:
                        preview = ''
                    meta['last_message'] = preview
                    meta['last_message_at'] = msg.timestamp

                if not msg.is_read and msg.receiver_id == user.id:
                    meta['unread_count'] += 1

        if not conversation_meta:
            return Response([])

        ordered_ids = sorted(
            conversation_meta.keys(),
            key=lambda uid: conversation_meta[uid]['last_message_at'] or timezone.now(),
            reverse=True,
        )

        users_qs = User.objects.filter(id__in=conversation_meta.keys()).select_related('profile')
        users_map = {u.id: u for u in users_qs}
        ordered_users = [users_map[uid] for uid in ordered_ids if uid in users_map]

        serializer = ConversationSerializer(
            ordered_users,
            many=True,
            context={'request': request, 'conversation_meta': conversation_meta},
        )
        return Response(serializer.data)


class MessageListView(APIView):
    """
    View برای نمایش پیام‌های یک گفتگوی خاص و ارسال پیام جدید.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        """
        دریافت لیست پیام‌ها بین کاربر لاگین کرده و کاربری با user_id.
        """
        try:
            other_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'کاربر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        messages = ChatMessage.objects.filter(
            (Q(sender=request.user) & Q(receiver=other_user)) |
            (Q(sender=other_user) & Q(receiver=request.user))
        ).order_by('timestamp')
        
        # Mark messages as read
        messages.filter(receiver=request.user, is_read=False).update(is_read=True)

        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    def post(self, request, user_id):
        """
        ارسال یک پیام جدید از کاربر لاگین کرده به کاربری با user_id.
        """
        try:
            other_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'کاربر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        data['sender'] = request.user.id
        data['receiver'] = user_id

        serializer = ChatMessageSerializer(data=data)
        if serializer.is_valid():
            serializer.save(sender=request.user, receiver=other_user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentSubmissionView(APIView):
    """ایجاد پرداخت توسط دانش‌آموزان یا ادمین."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else None
        if payload is None:
            try:
                payload = json.loads(request.body or '{}')
            except json.JSONDecodeError:
                return Response({'detail': 'داده نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        amount_raw = payload.get('amount')
        reference_number = payload.get('reference_number')
        payment_date_raw = payload.get('payment_date')
        course_id = payload.get('course')

        if not amount_raw or not reference_number or not payment_date_raw:
            return Response({'detail': 'تمام فیلدهای الزامی را تکمیل کنید.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError, ValueError):
            return Response({'detail': 'مبلغ نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({'detail': 'مبلغ باید بزرگتر از صفر باشد.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment_date = datetime.strptime(payment_date_raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return Response({'detail': 'تاریخ نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        student = None
        if request.user.is_staff and payload.get('student_id'):
            student = Student.objects.filter(id=payload['student_id']).select_related('profile').first()
        else:
            profile = getattr(request.user, 'profile', None)
            if profile and profile.role == 'student':
                student = Student.objects.filter(profile=profile).select_related('profile').first()

        if not student:
            return Response({'detail': 'شناسه دانش‌آموز یافت نشد.'}, status=status.HTTP_400_BAD_REQUEST)

        course = None
        if course_id:
            course = Course.objects.filter(id=course_id).first()

        payment = Payment.objects.create(
            student=student,
            course=course,
            amount=amount,
            reference_number=reference_number,
            payment_date=payment_date,
            status='pending',
        )

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


def _send_telegram_message(chat_id: str, text: str):
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise ValueError('TELEGRAM_BOT_TOKEN is not configured.')

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {'chat_id': chat_id, 'text': text}
    data = urllib_parse.urlencode(payload).encode()
    req = urllib_request.Request(url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib_request.urlopen(req, timeout=10) as response:
        body = json.loads(response.read().decode('utf-8'))

    if not body.get('ok'):
        raise ValueError(body.get('description', 'Failed to send telegram notification.'))


class NotificationSendView(APIView):
    """ارسال اعلان تلگرام برای لیست انتخاب شده از دانش‌آموزان و مشاوران."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        try:
            payload = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            payload = request.data if isinstance(request.data, dict) else {}

        message = (payload.get('message') or '').strip()
        if not message:
            return Response({'detail': 'متن پیام الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        student_ids = payload.get('student_ids', []) or []
        advisor_ids = payload.get('advisor_ids', []) or []

        students = Student.objects.filter(id__in=student_ids).select_related('profile')
        advisors = Advisor.objects.filter(id__in=advisor_ids).select_related('profile')

        if not students and not advisors:
            return Response({'detail': 'هیچ مخاطبی انتخاب نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        sent = []
        failures = []

        for obj in list(students) + list(advisors):
            profile = obj.profile
            chat_id = profile.telegram_chat_id or profile.phone_number
            if not chat_id:
                failures.append({'id': profile.id, 'name': profile.get_full_name(), 'reason': 'chat_id_missing'})
                continue
            try:
                _send_telegram_message(chat_id, message)
                sent.append({'id': profile.id, 'name': profile.get_full_name(), 'chat_id': chat_id})
            except Exception as exc:  # noqa: BLE001
                failures.append({'id': profile.id, 'name': profile.get_full_name(), 'reason': str(exc)})

        return Response({'sent': sent, 'failures': failures})
