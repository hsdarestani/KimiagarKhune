from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (ConversationListView, MessageListView,
                    NotificationSendView, PaymentStatusView,
                    PaymentSubmissionView, PaymentViewSet)

# ساخت یک روتر برای ViewSet ها
router = DefaultRouter()
router.register(r'payments', PaymentViewSet, basename='payment')

# تعریف URL های اپ
urlpatterns = [
    # URL های مربوط به روتر (مثلا /api/management/payments/)
    path('', include(router.urls)),
    
    # URL های مربوط به چت
    path('chat/conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('chat/messages/<int:user_id>/', MessageListView.as_view(), name='message-list'),
    path('payments/submit/', PaymentSubmissionView.as_view(), name='payment-submit'),
    path('payments/mine/', PaymentStatusView.as_view(), name='payment-status'),
    path('notifications/send/', NotificationSendView.as_view(), name='notification-send'),
]

