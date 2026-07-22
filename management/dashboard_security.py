from __future__ import annotations

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.response import Response

from accounts.models import Advisor, Student
from management.views import ConversationListView, MessageListView


def _is_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profile = getattr(user, "profile", None)
    return getattr(profile, "role", None) == "admin"


def _allowed_direct_user_ids(user) -> set[int]:
    if _is_admin(user):
        return set(
            User.objects.exclude(pk=user.pk).values_list("pk", flat=True)
        )

    profile = getattr(user, "profile", None)
    role = getattr(profile, "role", None)

    if role == "student":
        advisor_user_id = (
            Student.objects.filter(profile=profile)
            .values_list("advisor__profile__user_id", flat=True)
            .first()
        )
        return {advisor_user_id} if advisor_user_id else set()

    if role == "advisor":
        advisor = Advisor.objects.filter(profile=profile).first()
        if not advisor:
            return set()
        return set(
            Student.objects.filter(advisor=advisor)
            .exclude(profile__user_id__isnull=True)
            .values_list("profile__user_id", flat=True)
        )

    return set()


class SecuredConversationListView(ConversationListView):
    """Keep conversation discovery aligned with role relationships."""

    def get(self, request):
        response = super().get(request)
        if response.status_code != status.HTTP_200_OK or _is_admin(request.user):
            return response

        allowed = _allowed_direct_user_ids(request.user)
        filtered = []
        for item in response.data or []:
            conversation_id = str(item.get("id") or "")
            if not conversation_id.startswith("user:"):
                continue
            try:
                other_id = int(conversation_id.split(":", 1)[1])
            except (IndexError, TypeError, ValueError):
                continue
            if other_id in allowed:
                filtered.append(item)
        response.data = filtered
        return response


class SecuredMessageListView(MessageListView):
    """Reject direct chat access outside the assigned advisor/student graph."""

    def _resolve_conversation(self, request, raw_conversation_id):
        conversation = super()._resolve_conversation(request, raw_conversation_id)
        if conversation.get("type") != "direct" or _is_admin(request.user):
            return conversation

        other_user = conversation.get("other_user")
        if not other_user or other_user.pk not in _allowed_direct_user_ids(request.user):
            raise PermissionError
        return conversation
