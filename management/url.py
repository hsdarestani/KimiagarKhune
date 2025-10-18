from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (AdminReportSummaryView, AdvisorListView,
                    ConversationListView, CurrentUserProfileView, MessageListView,
                    NotificationInboxView, NotificationMarkReadView,
                    NotificationRecipientListView, NotificationSendView,
                    PaymentStatusView, PaymentSubmissionView, PaymentViewSet)

# ساخت یک روتر برای ViewSet ها
router = DefaultRouter()
router.register(r'payments', PaymentViewSet, basename='payment')

# تعریف URL های اپ
urlpatterns = [
    # مسیرهای اختصاصی که نباید با الگوهای روتر تداخل داشته باشند
    path('payments/submit/', PaymentSubmissionView.as_view(), name='payment-submit'),
    path('payments/mine/', PaymentStatusView.as_view(), name='payment-status'),
    path('notifications/send/', NotificationSendView.as_view(), name='notification-send'),
    path('notifications/recipients/', NotificationRecipientListView.as_view(), name='notification-recipient-list'),
    path('notifications/inbox/', NotificationInboxView.as_view(), name='notification-inbox'),
    path('notifications/mark-read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('advisors/', AdvisorListView.as_view(), name='advisor-list'),
    path('reports/summary/', AdminReportSummaryView.as_view(), name='reports-summary'),
    path('profile/', CurrentUserProfileView.as_view(), name='current-user-profile'),

    # URL های مربوط به چت
    path('chat/conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('chat/messages/<str:conversation_id>/', MessageListView.as_view(), name='message-list'),

    # URL های مربوط به روتر (مثلا /api/management/payments/)
    path('', include(router.urls)),
]

