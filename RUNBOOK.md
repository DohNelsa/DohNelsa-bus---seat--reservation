# Operations runbook (Nelsa / MOGHAMO EXPRESS)

## Health checks

- **Liveness:** `GET /health/` — process is up.
- **Readiness:** `GET /health/ready/` — returns `503` if the database is unreachable (use for orchestrator / Render health checks).
- **Metrics (JSON):** `GET /internal/metrics/`  
  - Authenticated staff with **View payment webhook events**, **or**  
  - `X-Metrics-Token` / `?token=` matching `METRICS_AUTH_TOKEN` (for cron / external monitors).

## Payment webhooks

- **URL:** `POST /webhooks/payment/`
- **Headers:**  
  - `X-Payment-Webhook-Secret` — must match `PAYMENT_WEBHOOK_SECRET`.  
  - Optional `X-Webhook-Body-Signature` — hex SHA-256 HMAC of the raw body using `PAYMENT_WEBHOOK_HMAC_SECRET` (constant-time compare).
- **Payment success payload (conceptually):** `event_id`, `booking_group_id`, `payment_method` (MOMO/ORANGE/CARD), `transaction_id`, `status` in (`COMPLETED`,`SUCCESS`), `amount` equal to `BookingGroup.total_amount`.
- **Refund payload:** `event_id`, `booking_group_id`, `event_kind` = `refund` (or `status` in `REFUNDED` / `REFUND` / `REFUND_COMPLETED`). Marks `Payment` as `REFUNDED`, cancels seats, sets refund status to completed.
- **Idempotency:** same `event_id` is stored in `PaymentWebhookEvent` and ignored once processed.
- **Alerts:** set `ALERT_ON_WEBHOOK_FAILURE=True` and `ALERT_EMAIL_RECIPIENTS` to receive mail when a webhook is **rejected** (validation error).

## RBAC (groups & permissions)

- Migration `0019_rbac_default_groups` creates **Operations Full** (all custom permissions) and **Finance** (bookings dashboard + webhooks + audit + refunds) and adds **all existing staff users** to **Operations Full**.
- New staff users: assign groups in **Django admin → Users → Groups**, or they will get “permission denied” on app routes even if `is_staff` is true.
- Custom permissions live on **BookingGroup** (confirm, cancel, webhooks, SMS, routes, refunds, etc.).

## Refund & rebooking

- **Refund (manual):** Booking detail → **Request refund** → after the provider returns money → **Mark refund complete** (cancels seats, `Payment` → `REFUNDED`).
- **Rebook:** Booking detail → **Rebook** → pick a new schedule and the same number of seats; old group is cancelled, a new pending group is created with `payment_waived` and a zero-amount reconciling payment; **Confirm** the new group in the normal way.

## Monitoring checklist

1. Watch `/health/ready/` from your host.
2. Poll `/internal/metrics/` (with token) for webhook `rejected` / `failed` counts and pending booking groups.
3. Review **Payment Webhook Events** and **Admin audit log** in the staff UI.
4. Watch `logs/django.log` for `nelsa.ops` and `nelsa.audit` when email is not configured.
