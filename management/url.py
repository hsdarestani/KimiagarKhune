from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .dashboard_security import SecuredConversationListView, SecuredMessageListView
from .views import (
    AdminReportExportView,
    AdminReportSummaryView,
    AdvisorListView,
    CurrentUserProfileView,
    NotificationInboxView,
    NotificationMarkReadView,
    NotificationRecipientListView,
    NotificationSendView,
    PaymentStatusView,
    PaymentSubmissionView,
    PaymentViewSet,
)


router = DefaultRouter()
router.register(r"payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("payments/submit/", PaymentSubmissionView.as_view(), name="payment-submit"),
    path("payments/mine/", PaymentStatusView.as_view(), name="payment-status"),
    path("notifications/send/", NotificationSendView.as_view(), name="notification-send"),
    path("notifications/recipients/", NotificationRecipientListView.as_view(), name="notification-recipient-list"),
    path("notifications/inbox/", NotificationInboxView.as_view(), name="notification-inbox"),
    path("notifications/mark-read/", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path("advisors/", AdvisorListView.as_view(), name="advisor-list"),
    path("reports/summary/", AdminReportSummaryView.as_view(), name="reports-summary"),
    path("reports/export/", AdminReportExportView.as_view(), name="reports-export"),
    path("profile/", CurrentUserProfileView.as_view(), name="current-user-profile"),
    path("chat/conversations/", SecuredConversationListView.as_view(), name="conversation-list"),
    path("chat/messages/<str:conversation_id>/", SecuredMessageListView.as_view(), name="message-list"),
    path("", include(router.urls)),
]
