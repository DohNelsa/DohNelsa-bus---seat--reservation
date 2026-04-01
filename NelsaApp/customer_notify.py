"""
Customer-visible notification status derived from SMS + email delivery state.
"""

from datetime import timedelta

from django.utils import timezone

from .models import BookingGroup


def sync_customer_notification_status(booking_group_id: int) -> None:
    """
    Recompute BookingGroup.customer_notification_status from sms_status and confirmation_email_sent_at.
    """
    try:
        bg = BookingGroup.objects.get(pk=booking_group_id)
    except BookingGroup.DoesNotExist:
        return

    if bg.status != "Confirmed":
        if bg.customer_notification_status != "N/A":
            BookingGroup.objects.filter(pk=booking_group_id).update(customer_notification_status="N/A")
        return

    has_email = bool(bg.confirmation_email_sent_at)
    sms = (bg.sms_status or "NOT_SENT").upper()

    if sms == "SENT" and has_email:
        status = "SMS_AND_EMAIL"
    elif sms == "SENT":
        status = "SMS_DELIVERED"
    elif sms == "FAILED" and has_email:
        status = "SMS_FAILED_EMAIL_DELIVERED"
    elif has_email:
        status = "EMAIL_DELIVERED"
    elif sms == "FAILED" and not has_email:
        status = "SMS_FAILED_EMAIL_FAILED"
    elif sms == "NOT_SENT":
        status = "PROCESSING"
    else:
        status = bg.customer_notification_status or "PROCESSING"

    if status != bg.customer_notification_status:
        bg.customer_notification_status = status
        bg.save(update_fields=["customer_notification_status"])


def refund_sla_due_at(requested_at, hours: int):
    if requested_at is None or hours <= 0:
        return None
    return requested_at + timedelta(hours=hours)
