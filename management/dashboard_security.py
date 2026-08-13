from __future__ import annotations

from django.contrib.auth.models import User
from rest_framework import status

from accounts.models import Advisor, Student
from management.serializers import UserProfileSerializer
from management.views import ConversationListView, MessageListView
from plans.advisor_access import assigned_students_for_advisor, effective_advisor_id


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
        student = Student.objects.filter(profile=profile).first()
        if not student:
            return set()
        advisor_id = effective_advisor_id(student)
        if not advisor_id:
            return set()
        advisor_user_id = (
            Advisor.objects.filter(pk=advisor_id)
            .values_list("profile__user_id", flat=True)
            .first()
        )
        return {advisor_user_id} if advisor_user_id else set()

    if role == "advisor":
        advisor = Advisor.objects.filter(profile=profile).first()
        if not advisor:
            return set()
        return set(
            assigned_students_for_advisor(advisor)
            .exclude(profile__user_id__isnull=True)
            .values_list("profile__user_id", flat=True)
        )

    return set()


def _serialize_chat_user(user_obj, request):
    if not user_obj:
        return None

    profile = getattr(user_obj, "profile", None)
    profile_data = None
    display_name = ""
    if profile:
        profile_data = UserProfileSerializer(
            profile,
            context={"request": request},
        ).data
        display_name = profile.get_full_name()

    if not display_name:
        display_name = user_obj.get_username() or f"کاربر {user_obj.pk}"

    payload = {
        "id": user_obj.pk,
        "username": user_obj.get_username(),
        "profile": profile_data,
        "display_name": display_name,
    }
    if profile:
        payload["role"] = getattr(profile, "role", None)
    return payload


class SecuredConversationListView(ConversationListView):
    """Keep conversation discovery aligned with current advisor assignments."""

    def get(self, request):
        response = super().get(request)
        if response.status_code != status.HTTP_200_OK or _is_admin(request.user):
            return response

        allowed = _allowed_direct_user_ids(request.user)
        filtered = []
        visible_user_ids = set()

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
                visible_user_ids.add(other_id)

        # ConversationListView historically seeded users only from the direct
        # Student.advisor FK. Legacy dashboard assignments may have a valid active
        # Course while that FK is still null. The centralized advisor policy above
        # already resolves those records correctly, so make sure every currently
        # allowed counterpart is present even before the first chat message exists.
        missing_user_ids = allowed - visible_user_ids
        if missing_user_ids:
            current_user = (
                User.objects.select_related("profile")
                .filter(pk=request.user.pk)
                .first()
            )
            current_payload = _serialize_chat_user(current_user, request)
            missing_users = (
                User.objects.filter(pk__in=missing_user_ids)
                .select_related("profile")
                .order_by("pk")
            )
            for other_user in missing_users:
                other_payload = _serialize_chat_user(other_user, request)
                filtered.append(
                    {
                        "id": f"user:{other_user.pk}",
                        "type": "direct",
                        "participants": [
                            payload
                            for payload in (current_payload, other_payload)
                            if payload
                        ],
                        "display_name": (
                            other_payload or {}
                        ).get("display_name", f"کاربر {other_user.pk}"),
                        "last_message": "",
                        "last_message_at": None,
                        "unread_count": 0,
                    }
                )

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
