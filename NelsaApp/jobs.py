from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .customer_notify import sync_customer_notification_status
from .models import BookingGroup, NotificationJob
from .monitoring import send_ops_alert
from .notifications import send_booking_confirmed_email
from .sms import send_booking_confirmed_sms


def enqueue_notification_job(booking_group_id: int, job_type: str, payload=None) -> NotificationJob:
    return NotificationJob.objects.create(
        booking_group_id=booking_group_id,
        job_type=job_type,
        status="PENDING",
        payload=payload or {},
    )


def process_one_notification_job(job: NotificationJob) -> bool:
    job.status = "PROCESSING"
    job.save(update_fields=["status", "updated_at"])
    try:
        bg = BookingGroup.objects.get(pk=job.booking_group_id)
        if job.job_type == "BOOKING_CONFIRMED_EMAIL":
            ok = send_booking_confirmed_email(bg, source="admin")
            sync_customer_notification_status(bg.pk)
        elif job.job_type == "BOOKING_CONFIRMED_SMS":
            ok = send_booking_confirmed_sms(bg, source="admin")
            sync_customer_notification_status(bg.pk)
            bg.refresh_from_db()
            if not ok:
                had_email = bool(bg.confirmation_email_sent_at)
                if not had_email:
                    send_booking_confirmed_email(bg, source="admin")
                    sync_customer_notification_status(bg.pk)
                    bg.refresh_from_db()
                    if not bg.confirmation_email_sent_at:
                        BookingGroup.objects.filter(pk=bg.pk).update(
                            customer_notification_status="DELIVERY_FAILED",
                        )
                        if getattr(settings, "ALERT_ON_NOTIFICATION_FAILURE", False):
                            send_ops_alert(
                                "Booking confirmation delivery failed",
                                f"booking_group_id={bg.id}: SMS failed and email fallback failed.\n",
                            )
                        ok = False
                    else:
                        ok = True
                else:
                    ok = True
        else:
            raise ValueError(f"Unsupported job type: {job.job_type}")

        if ok:
            job.status = "DONE"
            job.error_message = None
        else:
            job.status = "FAILED"
            job.error_message = job.error_message or "Provider send failed."
        job.save(update_fields=["status", "error_message", "updated_at"])
        return ok
    except Exception as exc:
        job.status = "FAILED"
        job.error_message = str(exc)
        job.retry_count = (job.retry_count or 0) + 1
        job.run_after = timezone.now() + timezone.timedelta(minutes=min(30, max(1, job.retry_count)))
        job.save(update_fields=["status", "error_message", "retry_count", "run_after", "updated_at"])
        return False


def process_pending_notification_jobs(limit: int = 50) -> dict:
    now = timezone.now()
    processed = 0
    success = 0
    failed = 0
    with transaction.atomic():
        jobs = list(
            NotificationJob.objects.select_for_update(skip_locked=True)
            .filter(status__in=["PENDING", "FAILED"], run_after__lte=now)
            .order_by("run_after", "id")[:limit]
        )
    for job in jobs:
        processed += 1
        if process_one_notification_job(job):
            success += 1
        else:
            failed += 1
    return {"processed": processed, "success": success, "failed": failed}
