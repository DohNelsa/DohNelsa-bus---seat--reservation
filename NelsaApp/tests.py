import json
from datetime import timedelta

from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Booking, BookingGroup, Bus, NotificationJob, Passenger, PaymentWebhookEvent, Route, Schedule


class HardeningTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pw12345", email="u1@example.com")
        self.staff = User.objects.create_user(
            username="staff1", password="pw12345", email="staff@example.com", is_staff=True
        )
        self.bus = Bus.objects.create(bus_number="BUS-001", bus_type="Standard", capacity=40, is_available=True)
        self.route = Route.objects.create(
            start_location="Douala",
            end_location="Yaounde",
            distance=240,
            duration=4,
            price=5000,
        )
        now = timezone.now()
        self.schedule = Schedule.objects.create(
            bus=self.bus,
            route=self.route,
            departure_time=now + timedelta(days=1),
            arrival_time=now + timedelta(days=1, hours=4),
            price=5000,
            is_available=True,
        )
        self.schedule2 = Schedule.objects.create(
            bus=self.bus,
            route=self.route,
            departure_time=now + timedelta(days=2),
            arrival_time=now + timedelta(days=2, hours=4),
            price=5200,
            is_available=True,
        )
        self.passenger = Passenger.objects.create(name="P One", email="u1@example.com", phone="+237675315422")

    def _grant(self, user: User, codename: str):
        p = Permission.objects.get(codename=codename, content_type__app_label="NelsaApp")
        user.user_permissions.add(p)

    @override_settings(
        PAYMENT_WEBHOOK_SECRET="whsec-test",
        PAYMENT_WEBHOOK_HMAC_SECRET="hmac-test",
        PAYMENT_WEBHOOK_MAX_SKEW_SECONDS=300,
    )
    def test_webhook_replay_nonce_blocked(self):
        bg = BookingGroup.objects.create(
            passenger=self.passenger,
            schedule=self.schedule,
            total_amount=5000,
            status="Pending",
            transaction_verified=False,
        )
        payload = {
            "event_id": "evt_1",
            "provider": "GENERIC",
            "booking_group_id": bg.id,
            "transaction_id": "txn_1",
            "payment_method": "MOMO",
            "status": "SUCCESS",
            "amount": "5000",
        }
        body = json.dumps(payload).encode("utf-8")
        import hashlib
        import hmac

        sig = hmac.new(b"hmac-test", body, hashlib.sha256).hexdigest()
        headers = {
            "HTTP_X_PAYMENT_WEBHOOK_SECRET": "whsec-test",
            "HTTP_X_WEBHOOK_BODY_SIGNATURE": sig,
            "HTTP_X_WEBHOOK_TIMESTAMP": str(int(timezone.now().timestamp())),
            "HTTP_X_WEBHOOK_NONCE": "nonce-abc",
            "content_type": "application/json",
        }
        r1 = self.client.post(reverse("payment_webhook"), data=body, **headers)
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.post(reverse("payment_webhook"), data=body, **headers)
        self.assertEqual(r2.status_code, 409)

    def test_rbac_blocks_staff_without_permission(self):
        self.client.login(username="staff1", password="pw12345")
        resp = self.client.get(reverse("admin_payment_webhooks"))
        self.assertNotEqual(resp.status_code, 200)

    def test_state_changing_admin_actions_are_post_only(self):
        self._grant(self.staff, "cancel_bookinggroup")
        self.client.login(username="staff1", password="pw12345")
        bg = BookingGroup.objects.create(passenger=self.passenger, schedule=self.schedule, total_amount=5000, status="Pending")
        resp = self.client.get(reverse("admin_cancel_booking", kwargs={"booking_group_id": bg.id}))
        self.assertEqual(resp.status_code, 405)

    def test_book_seat_duplicate_blocked(self):
        self.client.login(username="u1", password="pw12345")
        payload = {
            "schedule_id": self.schedule.id,
            "seat_ids": [1],
            "customer_name": "User One",
            "customer_phone": "+237675315422",
        }
        r1 = self.client.post(reverse("book_seats_api"), data=json.dumps(payload), content_type="application/json")
        self.assertEqual(r1.status_code, 200)
        body1 = r1.json()
        self.assertTrue(body1.get("success"))

        r2 = self.client.post(reverse("book_seats_api"), data=json.dumps(payload), content_type="application/json")
        body2 = r2.json()
        self.assertFalse(body2.get("success"))

    def test_confirm_booking_queues_async_jobs(self):
        self._grant(self.staff, "confirm_bookinggroup")
        self.client.login(username="staff1", password="pw12345")
        bg = BookingGroup.objects.create(
            passenger=self.passenger,
            schedule=self.schedule,
            total_amount=5000,
            status="Pending",
            payment_waived=True,
            transaction_id="WAIVED-1",
            transaction_verified=True,
        )
        Booking.objects.create(passenger=self.passenger, schedule=self.schedule, seat_number=4, status="Pending", booking_group=bg)
        resp = self.client.post(reverse("admin_confirm_booking", kwargs={"booking_group_id": bg.id}))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(NotificationJob.objects.filter(booking_group=bg, status="PENDING").count(), 2)

    def test_rebook_flow_creates_new_group_and_cancels_old(self):
        self._grant(self.staff, "manage_refunds_rebooks")
        self._grant(self.staff, "access_admin_bookings")
        self.client.login(username="staff1", password="pw12345")
        old = BookingGroup.objects.create(
            passenger=self.passenger,
            schedule=self.schedule,
            total_amount=5000,
            status="Confirmed",
            transaction_id="txn-old",
            transaction_verified=True,
        )
        Booking.objects.create(passenger=self.passenger, schedule=self.schedule, seat_number=1, status="Confirmed", booking_group=old)

        resp = self.client.post(
            reverse("admin_rebook_booking", kwargs={"booking_group_id": old.id}),
            data={"schedule_id": str(self.schedule2.id), "seat_numbers": "2"},
        )
        self.assertEqual(resp.status_code, 302)
        old.refresh_from_db()
        self.assertEqual(old.status, "Cancelled")
        new_group = BookingGroup.objects.get(rebooking_of=old)
        self.assertEqual(new_group.status, "Pending")
        self.assertTrue(new_group.payment_waived)
        self.assertEqual(new_group.bookings.count(), 1)
