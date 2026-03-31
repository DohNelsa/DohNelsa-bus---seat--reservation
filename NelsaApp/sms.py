"""
SMS notifications via Twilio when SMS_PROVIDER=twilio and SMS_ENABLED=True.

Use SMS_PROVIDER=mock for local/dev without sending real SMS.
"""

import logging
import hashlib
import secrets

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_sms(to_number: str, message: str) -> tuple[bool, str | None]:
    """
    Send an SMS to `to_number`.

    Returns True if the SMS provider accepted the message (or mock/logging path succeeds).
    """
    if not to_number:
        return False, "Missing destination phone number."

    # Keep it safe: only send when explicitly enabled.
    if not getattr(settings, "SMS_ENABLED", False):
        logger.info("SMS disabled. Would send to=%s message=%s", to_number, message)
        return False, "SMS is disabled (SMS_ENABLED is False)."

    provider = getattr(settings, "SMS_PROVIDER", "mock")

    if provider == "mock":
        logger.info("MOCK SMS to=%s message=%s", to_number, message)
        return True, None

    if provider == "twilio":
        # Import lazily so the project can still run without Twilio installed
        try:
            from twilio.rest import Client  # type: ignore
        except Exception as exc:
            logger.exception("Twilio provider selected but twilio package import failed: %s", exc)
            return False, f"Twilio import failed: {exc}"

        account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        from_number = getattr(settings, "TWILIO_PHONE_NUMBER", "")

        if not account_sid or not auth_token or not from_number:
            logger.warning(
                "Twilio not configured (missing TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_PHONE_NUMBER)."
            )
            return False, "Twilio not configured. Missing SID, auth token, or from number."

        try:
            client = Client(account_sid, auth_token)
            sms = client.messages.create(
                body=message,
                from_=from_number,
                to=to_number,
            )
            if bool(getattr(sms, "sid", None)):
                return True, None
            return False, "Twilio did not return a message SID."
        except Exception as exc:
            logger.exception("Twilio SMS send failed to=%s: %s", to_number, exc)
            return False, f"Twilio send failed: {exc}"

    # Providers not wired (no credentials / no dependencies).
    logger.warning("SMS provider '%s' not configured. to=%s", provider, to_number)
    return False, f"Unsupported SMS provider '{provider}'."


def _build_receipt_code() -> str:
    # Short human-enterable code (still unique enough for this use case).
    # Park staff can validate it via the backend endpoint (cannot be forged).
    token = secrets.token_hex(6).upper()  # 12 chars
    return f"MOG-{token}"


def _validate_receipt_message(*, message: str, passenger_name: str, date_str: str, time_str: str, bus_type: str, seat_numbers_str: str) -> bool:
    """
    Ensure the receipt message includes the critical fields.

    This is used to decide whether we are allowed to set sms_status='SENT'.
    """
    checks = [
        "MOGHAMO" in message.upper(),
        passenger_name.strip() and passenger_name.strip() in message,
        date_str in message,
        time_str in message,
        bus_type.strip() and bus_type.strip() in message,
        seat_numbers_str in message,
    ]
    return all(checks)


def _format_departure_parts(dt):
    # Deterministic formatting so both message + validation use same strings.
    local_dt = timezone.localtime(dt)
    date_str = local_dt.strftime("%Y-%m-%d")
    time_str = local_dt.strftime("%H:%M")
    return date_str, time_str


def _build_booking_sms_receipt(bg, *, source: str) -> tuple[str, str]:
    """
    Returns (receipt_code, message).
    Message is intentionally short and structured like a mini-receipt.
    """
    company = getattr(settings, "COMPANY_NAME", "MOGHAMO EXPRESS")
    company_word = "MOGHAMO"

    passenger_name = (bg.passenger.name or "").strip()
    date_str, time_str = _format_departure_parts(bg.schedule.departure_time)
    bus_type = (bg.schedule.bus.bus_type or "").strip()
    seat_numbers = sorted(bg.bookings.values_list("seat_number", flat=True))
    seat_numbers_str = ", ".join(str(s) for s in seat_numbers) if seat_numbers else "—"

    # Use existing code if already generated/sent.
    receipt_code = bg.sms_receipt_code or _build_receipt_code()

    # Compact mini-receipt format (still includes everything we validate).
    msg = (
        f"{company_word} APPROVED | {passenger_name} | "
        f"{date_str} {time_str} | {bus_type} | "
        f"Seats:{seat_numbers_str} | Code:{receipt_code}"
    )

    return receipt_code, msg


def send_booking_confirmed_sms(booking_group, *, source: str = "payment") -> bool:
    """
    Send the booking confirmation SMS receipt to the passenger (one canonical message).
    """
    try:
        bg = (
            type(booking_group)
            .objects.select_related("passenger", "schedule", "schedule__bus", "schedule__route")
            .prefetch_related("bookings")
            .get(pk=booking_group.pk)
        )
    except Exception as exc:
        logger.exception("Could not reload booking group for SMS: %s", exc)
        return False

    # Already delivered — idempotent, do not bump retry counters.
    if getattr(bg, "sms_status", "NOT_SENT") == "SENT":
        return True

    # Track each attempt for retry/error dashboards.
    bg.sms_retry_count = (bg.sms_retry_count or 0) + 1
    bg.sms_last_attempt_at = timezone.now()
    bg.save(update_fields=["sms_retry_count", "sms_last_attempt_at"])

    passenger = bg.passenger
    phone = (getattr(passenger, "phone", "") or "").strip()
    if not phone.startswith("+237"):
        logger.warning("Passenger phone must start with +237. bg=%s phone=%s", bg.id, phone)
        bg.sms_status = "FAILED"
        bg.sms_error_message = "Passenger phone must start with +237."
        bg.save(update_fields=["sms_status", "sms_error_message"])
        return False

    schedule = bg.schedule
    route = schedule.route
    bus = schedule.bus

    receipt_code, msg = _build_booking_sms_receipt(bg, source=source)

    # Validate required info is present before we are allowed to update sms_status='SENT'.
    passenger_name = (bg.passenger.name or "").strip()
    date_str, time_str = _format_departure_parts(bg.schedule.departure_time)
    bus_type = (bg.schedule.bus.bus_type or "").strip()
    seat_numbers = sorted(bg.bookings.values_list("seat_number", flat=True))
    seat_numbers_str = ", ".join(str(s) for s in seat_numbers) if seat_numbers else "—"

    if not _validate_receipt_message(
        message=msg,
        passenger_name=passenger_name,
        date_str=date_str,
        time_str=time_str,
        bus_type=bus_type,
        seat_numbers_str=seat_numbers_str,
    ):
        logger.warning("SMS receipt validation failed for bg=%s", bg.id)
        bg.sms_status = "FAILED"
        bg.sms_error_message = "Receipt message validation failed. Required fields missing in generated SMS."
        bg.save(update_fields=["sms_status", "sms_error_message"])
        return False

    # Send the short receipt message only once (no reminder SMS to keep message consistent for validation).
    ok, error_message = send_sms(phone, msg)
    if not ok:
        bg.sms_status = "FAILED"
        bg.sms_error_message = error_message or "Unknown SMS provider error."
        bg.save(update_fields=["sms_status", "sms_error_message"])
        return False

    # Persist sms receipt details for park verification + admin UI.
    bg.sms_receipt_code = receipt_code
    bg.sms_status = "SENT"
    bg.sms_sent_at = timezone.now()
    bg.sms_sent_by = getattr(bg, "verified_by", None)
    bg.sms_message_hash = hashlib.sha256(msg.encode("utf-8")).hexdigest()
    bg.sms_error_message = None
    bg.save(
        update_fields=[
            "sms_receipt_code",
            "sms_status",
            "sms_sent_at",
            "sms_sent_by",
            "sms_message_hash",
            "sms_error_message",
        ]
    )

    return True

