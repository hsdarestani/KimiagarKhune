from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Payment, ChatMessage
from .serializers import PaymentSerializer, ChatMessageSerializer, ConversationSerializer

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
        # پیدا کردن تمام پیام‌هایی که کاربر فرستاده یا دریافت کرده
        messages = ChatMessage.objects.filter(Q(sender=user) | Q(receiver=user))
        # استخراج آی‌دی تمام کاربرانی که با آن‌ها چت شده
        user_ids = set()
        for msg in messages:
            user_ids.add(msg.sender_id)
            user_ids.add(msg.receiver_id)
        
        # حذف آی‌دی کاربر فعلی
        user_ids.discard(user.id)
        
        # گرفتن اطلاعات کاربران برای نمایش در لیست
        conversations = User.objects.filter(id__in=user_ids)
        serializer = ConversationSerializer(conversations, many=True, context={'request': request})
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
        other_user = User.objects.get(id=user_id)
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
        data = request.data.copy()
        data['sender'] = request.user.id
        data['receiver'] = user_id
        
        serializer = ChatMessageSerializer(data=data)
        if serializer.is_valid():
            serializer.save(sender=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
