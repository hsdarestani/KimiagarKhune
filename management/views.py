import json
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db.models import Count, Max, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Advisor, Profile, Student
from management.utils import send_sms_message, send_telegram_message
from plans.models import Course, Session
from .models import ChatMessage, Notification, NotificationRecipient, Payment
from .serializers import (AdvisorOptionSerializer, ChatMessageSerializer,
                          NotificationRecipientSerializer,
                          NotificationTargetSerializer, PaymentSerializer,
                          UserProfileSerializer)

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
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return (
            Payment.objects.select_related('student__profile')
            .order_by('-created_at')
        )

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


class CurrentUserProfileView(APIView):
    """بازگرداندن و بروزرسانی پروفایل کاربر جاری."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_profile(self, request):
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return None
        return profile

    def get(self, request):
        profile = self._get_profile(request)
        if not profile:
            return Response({'detail': 'پروفایل یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        profile = self._get_profile(request)
        if not profile:
            return Response({'detail': 'پروفایل یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdvisorListView(APIView):
    """"
    بازگرداندن لیست مشاوران برای فیلتر کردن برنامه‌ها توسط ادمین.
    """

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        advisors = (
            Advisor.objects.select_related('profile__user')
            .order_by('profile__first_name', 'profile__last_name', 'profile__user__username')
        )
        serializer = AdvisorOptionSerializer(advisors, many=True)
        return Response(serializer.data)


class AdminReportSummaryView(APIView):
    """"
    ارائه گزارش‌های عملکردی برای داشبورد ادمین بر اساس فیلترهای انتخابی.
    """

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        today = timezone.localdate()
        start_raw = request.query_params.get('start_date') or request.query_params.get('from')
        end_raw = request.query_params.get('end_date') or request.query_params.get('to')
        advisor_raw = request.query_params.get('advisor_id') or request.query_params.get('advisor')

        end_date = parse_date(end_raw) if end_raw else today
        start_date = parse_date(start_raw) if start_raw else None

        if end_date is None:
            end_date = today

        if start_date is None:
            start_date = end_date - timedelta(days=29)

        if start_date and end_date and start_date > end_date:
            return Response({'detail': 'بازه زمانی نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        advisor_id = None
        if advisor_raw:
            try:
                advisor_id = int(advisor_raw)
            except (TypeError, ValueError):
                return Response({'detail': 'شناسه مشاور نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        advisor_queryset = Advisor.objects.select_related('profile__user')
        if advisor_id:
            advisor_queryset = advisor_queryset.filter(id=advisor_id)
        advisors = list(advisor_queryset)

        advisor_name_map = {
            advisor.id: advisor.profile.get_full_name() if getattr(advisor, 'profile', None) else ''
            for advisor in advisors
        }
        advisor_user_map = {
            advisor.profile.user_id: advisor.id
            for advisor in advisors
            if getattr(advisor, 'profile', None) and advisor.profile.user_id
        }

        range_start = start_date
        range_end = end_date

        start_dt = None
        end_dt = None
        if range_start:
            start_dt = datetime.combine(range_start, time.min)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
        if range_end:
            end_dt = datetime.combine(range_end, time.max)
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt, timezone.get_current_timezone())

        overdue_sessions_qs = (
            Session.objects.select_related(
                'course__student__profile__user',
                'course__advisor__profile__user',
            )
            .filter(is_completed=False)
            .filter(date__lte=today)
        )
        if advisor_id:
            overdue_sessions_qs = overdue_sessions_qs.filter(course__advisor_id=advisor_id)

        overdue_sessions = []
        for session in overdue_sessions_qs:
            course = session.course
            student = getattr(course, 'student', None)
            advisor = getattr(course, 'advisor', None)
            student_profile = getattr(student, 'profile', None)
            advisor_profile = getattr(advisor, 'profile', None)
            overdue_sessions.append({
                'session_id': session.id,
                'course_id': course.id if course else None,
                'session_number': session.session_number,
                'date': session.date.isoformat() if session.date else None,
                'student': {
                    'id': student.id if student else None,
                    'name': student_profile.get_full_name() if student_profile else '',
                },
                'advisor': {
                    'id': advisor.id if advisor else None,
                    'name': advisor_profile.get_full_name() if advisor_profile else '',
                },
                'day_of_week': course.day_of_week if course else None,
                'start_time': course.start_time.isoformat() if course and course.start_time else None,
            })

        completion_sessions = Session.objects.filter(is_completed=True, session_number=4)
        if range_start:
            completion_sessions = completion_sessions.filter(date__gte=range_start)
        if range_end:
            completion_sessions = completion_sessions.filter(date__lte=range_end)
        if advisor_id:
            completion_sessions = completion_sessions.filter(course__advisor_id=advisor_id)

        course_completions_by_day = [
            {
                'date': entry['date'].isoformat() if entry['date'] else None,
                'count': entry['total'],
            }
            for entry in (
                completion_sessions.values('date')
                .order_by('date')
                .annotate(total=Count('course', distinct=True))
            )
        ]

        sessions_without_plan_qs = Session.objects.filter(is_completed=True).filter(
            Q(video_url__isnull=True) | Q(video_url='')
        )
        if range_start:
            sessions_without_plan_qs = sessions_without_plan_qs.filter(date__gte=range_start)
        if range_end:
            sessions_without_plan_qs = sessions_without_plan_qs.filter(date__lte=range_end)
        if advisor_id:
            sessions_without_plan_qs = sessions_without_plan_qs.filter(course__advisor_id=advisor_id)

        sessions_without_plan = []
        for session in sessions_without_plan_qs.select_related(
            'course__student__profile__user',
            'course__advisor__profile__user',
        ):
            course = session.course
            student = getattr(course, 'student', None)
            advisor = getattr(course, 'advisor', None)
            student_profile = getattr(student, 'profile', None)
            advisor_profile = getattr(advisor, 'profile', None)
            sessions_without_plan.append({
                'session_id': session.id,
                'course_id': course.id if course else None,
                'session_number': session.session_number,
                'date': session.date.isoformat() if session.date else None,
                'student': {
                    'id': student.id if student else None,
                    'name': student_profile.get_full_name() if student_profile else '',
                },
                'advisor': {
                    'id': advisor.id if advisor else None,
                    'name': advisor_profile.get_full_name() if advisor_profile else '',
                },
                'day_of_week': course.day_of_week if course else None,
                'start_time': course.start_time.isoformat() if course and course.start_time else None,
            })

        advisor_session_counts_map = {
            advisor.id: 0 for advisor in advisors
        }
        session_activity_qs = Session.objects.filter(is_completed=True)
        if range_start:
            session_activity_qs = session_activity_qs.filter(date__gte=range_start)
        if range_end:
            session_activity_qs = session_activity_qs.filter(date__lte=range_end)
        if advisor_id:
            session_activity_qs = session_activity_qs.filter(course__advisor_id=advisor_id)

        for entry in (
            session_activity_qs.values('course__advisor_id')
            .annotate(total=Count('id'))
        ):
            advisor_key = entry['course__advisor_id']
            if advisor_key in advisor_session_counts_map:
                advisor_session_counts_map[advisor_key] = entry['total']

        dropout_courses = Course.objects.filter(is_active=False)
        if advisor_id:
            dropout_courses = dropout_courses.filter(advisor_id=advisor_id)
        dropout_courses = dropout_courses.annotate(
            incomplete_sessions=Count('sessions', filter=Q(sessions__is_completed=False)),
            last_session_date=Max('sessions__date'),
        ).annotate(
            dropout_date=Coalesce('last_session_date', 'start_date'),
        ).filter(incomplete_sessions__gt=0)

        if range_start:
            dropout_courses = dropout_courses.filter(dropout_date__gte=range_start)
        if range_end:
            dropout_courses = dropout_courses.filter(dropout_date__lte=range_end)

        advisor_dropout_counts_map = {advisor.id: 0 for advisor in advisors}
        for entry in (
            dropout_courses.values('advisor_id')
            .annotate(total=Count('student_id', distinct=True))
        ):
            advisor_key = entry['advisor_id']
            if advisor_key in advisor_dropout_counts_map:
                advisor_dropout_counts_map[advisor_key] = entry['total']

        students_qs_ids = Student.objects.all()
        if advisor_id:
            students_qs_ids = students_qs_ids.filter(advisor_id=advisor_id)
        student_ids = list(students_qs_ids.values_list('id', flat=True))

        courses_for_students = (
            Course.objects.filter(student_id__in=student_ids)
            .select_related('advisor__profile__user', 'student__profile__user')
            .prefetch_related('sessions')
        )

        student_course_map = defaultdict(list)
        for course in courses_for_students:
            student_course_map[course.student_id].append(course)

        def course_end_date(course_obj):
            session_dates = [s.date for s in course_obj.sessions.all() if s.date]
            if session_dates:
                return max(session_dates)
            if course_obj.start_date:
                return course_obj.start_date
            return None

        advisor_non_renew_map = {advisor.id: 0 for advisor in advisors}
        for course_list in student_course_map.values():
            if any(course.is_active for course in course_list):
                continue
            last_course = None
            last_course_date = None
            for course in course_list:
                candidate_date = course_end_date(course)
                if not candidate_date:
                    continue
                if last_course is None or candidate_date > last_course_date:
                    last_course = course
                    last_course_date = candidate_date
            if not last_course or not last_course_date:
                continue
            if range_start and last_course_date < range_start:
                continue
            if range_end and last_course_date > range_end:
                continue
            advisor_key = last_course.advisor_id
            if advisor_key in advisor_non_renew_map:
                advisor_non_renew_map[advisor_key] += 1

        students_qs = Student.objects.select_related(
            'advisor__profile__user', 'grade', 'major'
        )
        if advisor_id:
            students_qs = students_qs.filter(advisor_id=advisor_id)

        distribution_by_advisor = []
        for entry in (
            students_qs.values('advisor_id')
            .annotate(total=Count('id'))
        ):
            adv_id = entry['advisor_id']
            distribution_by_advisor.append({
                'advisor_id': adv_id,
                'advisor_name': advisor_name_map.get(adv_id, 'بدون مشاور') if adv_id else 'بدون مشاور',
                'count': entry['total'],
            })

        distribution_by_grade = [
            {
                'grade_id': entry['grade_id'],
                'grade_name': entry['grade__name'] or 'نامشخص',
                'count': entry['total'],
            }
            for entry in (
                students_qs.values('grade_id', 'grade__name')
                .annotate(total=Count('id'))
                .order_by('grade__name')
            )
        ]

        distribution_by_major = [
            {
                'major_id': entry['major_id'],
                'major_name': entry['major__name'] or 'نامشخص',
                'count': entry['total'],
            }
            for entry in (
                students_qs.values('major_id', 'major__name')
                .annotate(total=Count('id'))
                .order_by('major__name')
            )
        ]

        conversations = defaultdict(list)
        chat_qs = ChatMessage.objects.select_related(
            'sender__profile__user', 'receiver__profile__user'
        )
        if start_dt:
            chat_qs = chat_qs.filter(timestamp__gte=start_dt)
        if end_dt:
            chat_qs = chat_qs.filter(timestamp__lte=end_dt)
        if advisor_user_map:
            chat_qs = chat_qs.filter(
                Q(sender_id__in=advisor_user_map.keys()) |
                Q(receiver_id__in=advisor_user_map.keys())
            )
        else:
            chat_qs = chat_qs.none()

        for message in chat_qs:
            advisor_key = None
            other_user = None
            if message.sender_id in advisor_user_map:
                advisor_key = advisor_user_map[message.sender_id]
                other_user = message.receiver
            elif message.receiver_id in advisor_user_map:
                advisor_key = advisor_user_map[message.receiver_id]
                other_user = message.sender
            if not advisor_key or advisor_key not in advisor_name_map:
                continue
            other_profile = getattr(other_user, 'profile', None)
            if other_profile and other_profile.role and other_profile.role != 'student':
                continue
            conversations[(advisor_key, other_user.id if other_user else None)].append(message)

        advisor_chat_stats_map = {
            advisor.id: {'answered': 0, 'unanswered': 0}
            for advisor in advisors
        }
        for (advisor_key, _), messages in conversations.items():
            if not messages:
                continue
            ordered = sorted(messages, key=lambda item: item.timestamp)
            last_message = ordered[-1]
            if last_message.sender_id in advisor_user_map:
                advisor_chat_stats_map[advisor_key]['answered'] += 1
            else:
                advisor_chat_stats_map[advisor_key]['unanswered'] += 1

        advisor_session_counts = [
            {
                'advisor_id': advisor.id,
                'advisor_name': advisor_name_map.get(advisor.id, ''),
                'count': advisor_session_counts_map.get(advisor.id, 0),
            }
            for advisor in advisors
        ]

        advisor_dropout_counts = [
            {
                'advisor_id': advisor.id,
                'advisor_name': advisor_name_map.get(advisor.id, ''),
                'count': advisor_dropout_counts_map.get(advisor.id, 0),
            }
            for advisor in advisors
        ]

        advisor_non_renewal_counts = [
            {
                'advisor_id': advisor.id,
                'advisor_name': advisor_name_map.get(advisor.id, ''),
                'count': advisor_non_renew_map.get(advisor.id, 0),
            }
            for advisor in advisors
        ]

        advisor_chat_stats = [
            {
                'advisor_id': advisor.id,
                'advisor_name': advisor_name_map.get(advisor.id, ''),
                'answered': advisor_chat_stats_map.get(advisor.id, {}).get('answered', 0),
                'unanswered': advisor_chat_stats_map.get(advisor.id, {}).get('unanswered', 0),
            }
            for advisor in advisors
        ]

        response_payload = {
            'filters': {
                'start_date': range_start.isoformat() if range_start else None,
                'end_date': range_end.isoformat() if range_end else None,
                'advisor_id': advisor_id,
            },
            'overdue_sessions': overdue_sessions,
            'course_completions_by_day': course_completions_by_day,
            'sessions_without_plan': sessions_without_plan,
            'advisor_session_counts': advisor_session_counts,
            'advisor_dropout_counts': advisor_dropout_counts,
            'advisor_non_renewal_counts': advisor_non_renewal_counts,
            'student_distribution': {
                'by_advisor': distribution_by_advisor,
                'by_grade': distribution_by_grade,
                'by_major': distribution_by_major,
            },
            'advisor_chat_stats': advisor_chat_stats,
        }

        return Response(response_payload)


class ConversationListView(APIView):
    """
    View برای نمایش لیست گفتگوهای کاربر لاگین کرده.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, 'profile', None)

        def serialize_user(user_obj):
            if not user_obj:
                return None
            cached = serialized_users.get(user_obj.id)
            if cached:
                return cached

            profile_obj = getattr(user_obj, 'profile', None)
            profile_data = None
            full_name_parts = []
            if profile_obj:
                profile_data = UserProfileSerializer(
                    profile_obj,
                    context={'request': request},
                ).data
                first_name = getattr(profile_obj, 'first_name', '') or ''
                last_name = getattr(profile_obj, 'last_name', '') or ''
                if first_name:
                    full_name_parts.append(first_name)
                if last_name:
                    full_name_parts.append(last_name)

            display_name = ' '.join(part for part in full_name_parts if part).strip()
            if not display_name:
                display_name = user_obj.get_username() or f'کاربر {user_obj.id}'

            payload = {
                'id': user_obj.id,
                'username': user_obj.get_username(),
                'profile': profile_data,
                'display_name': display_name,
            }
            if profile_obj:
                payload['role'] = getattr(profile_obj, 'role', None)
            serialized_users[user_obj.id] = payload
            return payload

        def format_preview(message):
            if message.text:
                return message.text
            if message.file:
                return '📎 فایل ضمیمه'
            if message.voice:
                return '🎤 پیام صوتی'
            return ''

        serialized_users = {}
        allowed_user_ids = set()
        if profile:
            if profile.role == 'student':
                student = (
                    Student.objects.select_related('advisor__profile__user')
                    .filter(profile=profile)
                    .first()
                )
                advisor_user_id = (
                    student.advisor.profile.user_id
                    if student
                    and student.advisor
                    and student.advisor.profile
                    and student.advisor.profile.user_id
                    else None
                )
                if advisor_user_id:
                    allowed_user_ids.add(advisor_user_id)
            elif profile.role == 'advisor':
                advisor = (
                    Advisor.objects.select_related('profile__user')
                    .filter(profile=profile)
                    .first()
                )
                if advisor:
                    students = (
                        Student.objects.filter(advisor=advisor)
                        .select_related('profile__user')
                    )
                    for student in students:
                        if student.profile and student.profile.user_id:
                            allowed_user_ids.add(student.profile.user_id)
            elif profile.role == 'admin':
                allowed_user_ids.update(
                    User.objects.exclude(id=user.id).values_list('id', flat=True)
                )

        base_messages = ChatMessage.objects.select_related(
            'sender__profile', 'receiver__profile'
        )
        direct_messages = base_messages.filter(
            Q(sender=user) | Q(receiver=user)
        )

        conversation_meta = {}
        for msg in direct_messages:
            other_user = msg.receiver if msg.sender_id == user.id else msg.sender
            other_user_id = getattr(other_user, 'id', None)
            if not other_user_id:
                continue

            meta = conversation_meta.setdefault(
                other_user_id,
                {
                    'last_message': '',
                    'last_message_at': None,
                    'unread_count': 0,
                },
            )

            if not meta['last_message_at'] or msg.timestamp > meta['last_message_at']:
                meta['last_message'] = format_preview(msg)
                meta['last_message_at'] = msg.timestamp

            if msg.receiver_id == user.id and not msg.is_read:
                meta['unread_count'] += 1

        for allowed_id in allowed_user_ids:
            conversation_meta.setdefault(
                allowed_id,
                {
                    'last_message': '',
                    'last_message_at': None,
                    'unread_count': 0,
                },
            )

        pair_meta = {}
        pair_user_ids = set()
        if profile and profile.role == 'admin':
            other_messages = base_messages.exclude(
                Q(sender=user) | Q(receiver=user)
            )
            for msg in other_messages:
                sender_id = msg.sender_id
                receiver_id = msg.receiver_id
                if not sender_id or not receiver_id or sender_id == receiver_id:
                    continue
                participants = tuple(sorted((sender_id, receiver_id)))
                if user.id in participants:
                    continue

                meta = pair_meta.setdefault(
                    participants,
                    {
                        'last_message': '',
                        'last_message_at': None,
                    },
                )

                if not meta['last_message_at'] or msg.timestamp > meta['last_message_at']:
                    meta['last_message'] = format_preview(msg)
                    meta['last_message_at'] = msg.timestamp

                pair_user_ids.update(participants)

        user_ids_needed = set(conversation_meta.keys()) | pair_user_ids | {user.id}
        if not user_ids_needed:
            return Response([])

        users_map = {
            u.id: u
            for u in User.objects.filter(id__in=user_ids_needed).select_related('profile')
        }

        fallback_sort = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
        current_user_payload = serialize_user(user)

        entries = []
        for user_id, meta in conversation_meta.items():
            other_user = users_map.get(user_id)
            if not other_user:
                continue
            other_payload = serialize_user(other_user)
            last_at = meta.get('last_message_at') or fallback_sort
            entry = {
                'id': f'user:{user_id}',
                'type': 'direct',
                'participants': [payload for payload in [current_user_payload, other_payload] if payload],
                'display_name': (other_payload or {}).get('display_name', f'کاربر {user_id}'),
                'last_message': meta.get('last_message', ''),
                'last_message_at': meta['last_message_at'].isoformat() if meta.get('last_message_at') else None,
                'unread_count': meta.get('unread_count', 0),
                '_sort': last_at,
            }
            entries.append(entry)

        for participants, meta in pair_meta.items():
            first_id, second_id = participants
            first_user = users_map.get(first_id)
            second_user = users_map.get(second_id)
            if not first_user or not second_user:
                continue
            first_payload = serialize_user(first_user)
            second_payload = serialize_user(second_user)
            if not first_payload or not second_payload:
                continue
            display_name = (
                f"{first_payload.get('display_name', f'کاربر {first_id}')} ↔ "
                f"{second_payload.get('display_name', f'کاربر {second_id}')}"
            )
            last_at = meta.get('last_message_at') or fallback_sort
            entry = {
                'id': f'pair:{first_id}:{second_id}',
                'type': 'pair',
                'participants': [first_payload, second_payload],
                'display_name': display_name,
                'last_message': meta.get('last_message', ''),
                'last_message_at': meta['last_message_at'].isoformat() if meta.get('last_message_at') else None,
                'unread_count': 0,
                '_sort': last_at,
            }
            entries.append(entry)

        if not entries:
            return Response([])

        entries.sort(key=lambda item: item.get('_sort') or fallback_sort, reverse=True)
        for entry in entries:
            entry.pop('_sort', None)

        return Response(entries)


class MessageListView(APIView):
    """
    View برای نمایش پیام‌های یک گفتگوی خاص و ارسال پیام جدید.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _resolve_conversation(self, request, raw_conversation_id):
        conversation_id = str(raw_conversation_id or '').strip()
        if not conversation_id:
            raise ValueError('invalid conversation id')

        if conversation_id.isdigit():
            conversation_id = f'user:{conversation_id}'

        if conversation_id.startswith('user:'):
            try:
                target_id = int(conversation_id.split(':', 1)[1])
            except (IndexError, ValueError):
                raise ValueError('invalid conversation id')
            if target_id == request.user.id:
                raise ValueError('invalid conversation id')
            other_user = User.objects.get(id=target_id)
            return {
                'type': 'direct',
                'other_user': other_user,
                'key': f'user:{other_user.id}',
            }

        if conversation_id.startswith('pair:'):
            if not request.user.is_staff:
                raise PermissionError
            parts = conversation_id.split(':')
            if len(parts) != 3:
                raise ValueError('invalid conversation id')
            try:
                first = int(parts[1])
                second = int(parts[2])
            except ValueError:
                raise ValueError('invalid conversation id')
            if first == second:
                raise ValueError('invalid conversation id')
            ordered = tuple(sorted((first, second)))
            user_a = User.objects.get(id=ordered[0])
            user_b = User.objects.get(id=ordered[1])
            return {
                'type': 'pair',
                'user_ids': ordered,
                'users': (user_a, user_b),
                'key': f'pair:{ordered[0]}:{ordered[1]}',
            }

        raise ValueError('invalid conversation id')

    def get(self, request, conversation_id):
        try:
            conversation = self._resolve_conversation(request, conversation_id)
        except User.DoesNotExist:
            return Response({'detail': 'کاربر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError:
            return Response({'detail': 'دسترسی مجاز نیست.'}, status=status.HTTP_403_FORBIDDEN)
        except ValueError:
            return Response({'detail': 'شناسه گفتگو نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        if conversation['type'] == 'direct':
            other_user = conversation['other_user']
            messages = ChatMessage.objects.filter(
                (Q(sender=request.user) & Q(receiver=other_user))
                | (Q(sender=other_user) & Q(receiver=request.user))
            ).order_by('timestamp')
            messages.filter(receiver=request.user, is_read=False).update(is_read=True)
        else:
            user_a_id, user_b_id = conversation['user_ids']
            participant_ids = {user_a_id, user_b_id}
            admin_id = request.user.id
            messages = ChatMessage.objects.filter(
                (Q(sender_id=user_a_id, receiver_id=user_b_id)
                 | Q(sender_id=user_b_id, receiver_id=user_a_id)
                 | Q(sender_id=admin_id, receiver_id__in=participant_ids)
                 | Q(sender_id__in=participant_ids, receiver_id=admin_id))
            ).order_by('timestamp')

        serializer = ChatMessageSerializer(
            messages,
            many=True,
            context={'request': request},
        )
        return Response(serializer.data)

    def post(self, request, conversation_id):
        try:
            conversation = self._resolve_conversation(request, conversation_id)
        except User.DoesNotExist:
            return Response({'detail': 'کاربر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError:
            return Response({'detail': 'دسترسی مجاز نیست.'}, status=status.HTTP_403_FORBIDDEN)
        except ValueError:
            return Response({'detail': 'شناسه گفتگو نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ChatMessageSerializer(
            data=request.data,
            context={'request': request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if conversation['type'] == 'direct':
            other_user = conversation['other_user']
            message = serializer.save(sender=request.user, receiver=other_user)
            response_serializer = ChatMessageSerializer(
                message,
                context={'request': request},
            )
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        if not request.user.is_staff:
            return Response({'detail': 'دسترسی مجاز نیست.'}, status=status.HTTP_403_FORBIDDEN)

        validated = serializer.validated_data
        text = validated.get('text') or ''
        file_obj = validated.get('file')
        voice_obj = validated.get('voice')

        file_content = file_name = None
        if file_obj:
            try:
                file_obj.seek(0)
            except Exception:  # noqa: BLE001
                pass
            file_content = file_obj.read()
            file_name = getattr(file_obj, 'name', 'attachment')

        voice_content = voice_name = None
        if voice_obj:
            try:
                voice_obj.seek(0)
            except Exception:  # noqa: BLE001
                pass
            voice_content = voice_obj.read()
            voice_name = getattr(voice_obj, 'name', 'voice-message.webm')

        target_value = request.data.get('target') or request.data.get('target_user_id')
        participant_ids = set(conversation['user_ids'])

        if target_value in (None, '', 'both', 'all'):
            target_ids = list(participant_ids)
        else:
            try:
                target_id = int(target_value)
            except (TypeError, ValueError):
                return Response({'detail': 'شناسه گیرنده نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)
            if target_id not in participant_ids:
                return Response({'detail': 'گیرنده انتخاب‌شده در این گفتگو مجاز نیست.'}, status=status.HTTP_400_BAD_REQUEST)
            target_ids = [target_id]

        created_messages = []
        for target_id in target_ids:
            message_kwargs = {}
            if text:
                message_kwargs['text'] = text
            if file_content is not None:
                message_kwargs['file'] = ContentFile(file_content, name=file_name)
            if voice_content is not None:
                message_kwargs['voice'] = ContentFile(voice_content, name=voice_name)

            message = ChatMessage.objects.create(
                sender=request.user,
                receiver_id=target_id,
                **message_kwargs,
            )
            created_messages.append(message)

        response_serializer = ChatMessageSerializer(
            created_messages,
            many=True,
            context={'request': request},
        )
        payload = response_serializer.data
        if isinstance(payload, list) and len(payload) == 1:
            payload = payload[0]

        return Response(payload, status=status.HTTP_201_CREATED)


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
        return Response(
            {
                'message': 'پرداخت شما ثبت شد و در انتظار تایید ادمین است.',
                'payment': serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentStatusView(APIView):
    """نمایش وضعیت پرداخت‌ها برای کاربر جاری."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            payments = (
                Payment.objects.select_related('student__profile')
                .order_by('-created_at')
            )
        else:
            profile = getattr(request.user, 'profile', None)
            if not profile or profile.role != 'student':
                return Response([], status=status.HTTP_200_OK)

            student = (
                Student.objects.select_related('profile')
                .filter(profile=profile)
                .first()
            )
            if not student:
                return Response([], status=status.HTTP_200_OK)

            payments = (
                Payment.objects.select_related('student__profile')
                .filter(student=student)
                .order_by('-created_at')
            )

        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)
class NotificationSendView(APIView):
    """ارسال اعلان برای لیست انتخاب شده از دانش‌آموزان و مشاوران."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else None
        if data is None:
            try:
                data = json.loads(request.body or '{}')
            except json.JSONDecodeError:
                data = {}

        message = (data.get('message') or '').strip()
        if not message:
            return Response({'detail': 'متن پیام الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        raw_channels = data.get('channels') or []
        if isinstance(raw_channels, str):
            raw_channels = [raw_channels]
        channels = [str(channel).strip().lower() for channel in raw_channels if str(channel).strip()]
        valid_channels = {'panel', 'telegram', 'sms'}
        if not channels:
            return Response({'detail': 'حداقل یک کانال ارسال باید انتخاب شود.'}, status=status.HTTP_400_BAD_REQUEST)
        if not set(channels).issubset(valid_channels):
            return Response({'detail': 'کانال ارسال نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        recipient_ids = data.get('recipient_ids') or data.get('user_ids') or []
        if isinstance(recipient_ids, str):
            recipient_ids = [recipient_ids]
        if not recipient_ids:
            student_ids = data.get('student_ids') or []
            advisor_ids = data.get('advisor_ids') or []
            if student_ids:
                recipient_ids.extend(
                    Student.objects.filter(id__in=student_ids)
                    .values_list('profile__user_id', flat=True)
                )
            if advisor_ids:
                recipient_ids.extend(
                    Advisor.objects.filter(id__in=advisor_ids)
                    .values_list('profile__user_id', flat=True)
                )

        cleaned_ids = []
        for value in recipient_ids:
            try:
                cleaned_ids.append(int(value))
            except (TypeError, ValueError):
                continue
        unique_ids = list(dict.fromkeys(cleaned_ids))
        if not unique_ids:
            return Response({'detail': 'حداقل یک مخاطب باید انتخاب شود.'}, status=status.HTTP_400_BAD_REQUEST)

        users = list(
            User.objects.filter(id__in=unique_ids)
            .select_related('profile')
        )
        found_user_ids = {user.id for user in users}
        missing_ids = sorted(set(unique_ids) - found_user_ids)
        if missing_ids:
            return Response(
                {'detail': 'برخی کاربران انتخاب‌شده یافت نشدند.', 'missing_ids': missing_ids},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not users:
            return Response({'detail': 'هیچ کاربری برای ارسال اعلان یافت نشد.'}, status=status.HTTP_400_BAD_REQUEST)

        send_via_panel = 'panel' in channels
        send_via_telegram = 'telegram' in channels
        send_via_sms = 'sms' in channels

        notification = Notification.objects.create(
            sender=request.user if request.user.is_authenticated else None,
            message=message,
            send_via_panel=send_via_panel,
            send_via_telegram=send_via_telegram,
            send_via_sms=send_via_sms,
        )

        recipient_records = []
        results = []

        for user in users:
            try:
                profile = user.profile
            except Profile.DoesNotExist:
                profile = None

            full_name = profile.get_full_name() if profile else user.get_username()
            telegram_success = False
            sms_success = False
            telegram_error = ''
            sms_error = ''

            if send_via_telegram:
                chat_id = getattr(profile, 'telegram_chat_id', None) if profile else None
                if chat_id:
                    try:
                        send_telegram_message(chat_id, message)
                        telegram_success = True
                    except Exception as exc:  # noqa: BLE001
                        telegram_error = str(exc)
                else:
                    telegram_error = 'شناسه تلگرام ثبت نشده است.'

            if send_via_sms:
                phone_number = getattr(profile, 'phone_number', None) if profile else None
                if phone_number:
                    try:
                        send_sms_message(phone_number, message)
                        sms_success = True
                    except Exception as exc:  # noqa: BLE001
                        sms_error = str(exc)
                else:
                    sms_error = 'شماره موبایل در پروفایل موجود نیست.'

            recipient_records.append(
                NotificationRecipient(
                    notification=notification,
                    user=user,
                    telegram_sent=telegram_success,
                    sms_sent=sms_success,
                    telegram_error=telegram_error or None,
                    sms_error=sms_error or None,
                )
            )

            sent_channels = []
            if send_via_panel:
                sent_channels.append('panel')
            if telegram_success:
                sent_channels.append('telegram')
            if sms_success:
                sent_channels.append('sms')

            failed_channels = []
            if telegram_error:
                failed_channels.append({'channel': 'telegram', 'reason': telegram_error})
            if sms_error:
                failed_channels.append({'channel': 'sms', 'reason': sms_error})

            results.append(
                {
                    'user_id': user.id,
                    'name': full_name,
                    'sent_channels': sent_channels,
                    'failed_channels': failed_channels,
                }
            )

        NotificationRecipient.objects.bulk_create(recipient_records)

        return Response(
            {
                'notification_id': notification.id,
                'results': results,
            },
            status=status.HTTP_201_CREATED,
        )


class NotificationRecipientListView(APIView):
    """بازگرداندن فهرست کاربران قابل انتخاب برای اعلان."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        queryset = (
            Profile.objects.filter(role__in=['student', 'advisor'])
            .select_related('user')
            .order_by('role', 'first_name', 'last_name', 'user__username')
        )

        search_query = (request.query_params.get('q') or '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(user__username__icontains=search_query)
                | Q(phone_number__icontains=search_query)
            )

        serializer = NotificationTargetSerializer(queryset, many=True)
        return Response(serializer.data)


class NotificationInboxView(APIView):
    """نمایش اعلان‌های قابل مشاهده در پنل برای کاربر جاری."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        recipients = (
            NotificationRecipient.objects.select_related(
                'notification__sender__profile',
                'notification__sender',
            )
            .filter(user=request.user, notification__send_via_panel=True)
            .order_by('-notification__created_at', '-created_at')
        )
        serializer = NotificationRecipientSerializer(recipients, many=True)
        return Response(serializer.data)


class NotificationMarkReadView(APIView):
    """علامت‌گذاری اعلان‌های خوانده شده."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else None
        if data is None:
            try:
                data = json.loads(request.body or '{}')
            except json.JSONDecodeError:
                data = {}

        ids = data.get('ids') or data.get('notification_ids') or []
        if isinstance(ids, str):
            ids = [ids]

        cleaned_ids = []
        for value in ids:
            try:
                cleaned_ids.append(int(value))
            except (TypeError, ValueError):
                continue

        if not cleaned_ids:
            return Response({'updated': 0}, status=status.HTTP_200_OK)

        updated = NotificationRecipient.objects.filter(
            user=request.user,
            id__in=cleaned_ids,
        ).update(is_read=True)

        return Response({'updated': updated}, status=status.HTTP_200_OK)
