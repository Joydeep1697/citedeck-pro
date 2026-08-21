"""Production webhook service. Run behind Gunicorn; never expose service keys."""

from __future__ import annotations

import json
import logging
import os

from flask import Flask, jsonify, request

from payment_security import PaymentPolicy, validate_paid_event, verify_raw_body


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger("citedeck.webhook")
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024


def create_database_client():
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_key:
        return None
    try:
        from supabase import create_client

        return create_client(url, service_key)
    except Exception:
        LOGGER.exception("Unable to initialize webhook persistence")
        return None


DATABASE = create_database_client()
WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")


def _duplicate_error(exc: Exception) -> bool:
    return "23505" in str(exc) or "duplicate" in str(exc).casefold()


@app.post("/razorpay-webhook")
def razorpay_webhook():
    if DATABASE is None or not WEBHOOK_SECRET:
        return jsonify({"error": "Webhook service is not ready"}), 503

    raw_body = request.get_data(cache=False)
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not verify_raw_body(raw_body, signature, WEBHOOK_SECRET):
        return jsonify({"error": "Invalid webhook signature"}), 400

    try:
        payload = json.loads(raw_body)
        if not isinstance(payload, dict):
            raise ValueError("Webhook payload must be a JSON object")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return jsonify({"error": "Invalid webhook payload"}), 400

    event = str(payload.get("event") or "")
    event_id = request.headers.get("X-Razorpay-Event-Id", "").strip()
    event_payload = payload.get("payload") or {}
    payment_entity = (event_payload.get("payment") or {}).get("entity") or {}
    refund_entity = (event_payload.get("refund") or {}).get("entity") or {}
    payment_id = str(payment_entity.get("id") or refund_entity.get("payment_id") or "").strip()
    event_key = event_id or (f"{event}:{payment_id}" if payment_id else "")
    if not event_key:
        return jsonify({"error": "Webhook event is missing an idempotency key"}), 400

    try:
        DATABASE.table("payment_webhooks").insert({"event_key": event_key, "event": event, "payment_id": payment_id or None, "signature_valid": True, "processing_status": "processing"}).execute()
    except Exception as exc:
        if _duplicate_error(exc):
            try:
                existing = DATABASE.table("payment_webhooks").select("processing_status").eq("event_key", event_key).limit(1).execute()
                status = existing.data[0]["processing_status"] if existing.data else "processing"
                if status in {"processed", "rejected"}:
                    return jsonify({"status": "already_processed"}), 200
                if status == "processing":
                    return jsonify({"error": "Webhook event is already being processed"}), 409
                resumed = DATABASE.table("payment_webhooks").update({"processing_status": "processing"}).eq("event_key", event_key).eq("processing_status", "error").execute()
                if not resumed.data:
                    return jsonify({"error": "Webhook event is already being retried"}), 409
            except Exception:
                LOGGER.exception("Unable to inspect a duplicate webhook event")
                return jsonify({"error": "Unable to inspect webhook idempotency state"}), 503
        else:
            LOGGER.exception("Unable to reserve webhook event")
            return jsonify({"error": "Unable to persist webhook event"}), 503

    try:
        if event == "payment_link.paid":
            verified = validate_paid_event(payload, PaymentPolicy.from_environment())
            DATABASE.table("pro_users").upsert({**verified, "is_pro": True, "verified_via": "razorpay_signed_webhook"}, on_conflict="email").execute()
            status = "pro_granted"
        elif event in {"payment.refunded", "refund.processed"}:
            if not payment_id:
                raise ValueError("Refund event does not reference a payment")
            DATABASE.table("pro_users").update({"is_pro": False}).eq("payment_id", payment_id).execute()
            status = "pro_revoked"
        else:
            status = "ignored"

        DATABASE.table("payment_webhooks").update({"processing_status": "processed"}).eq("event_key", event_key).execute()
        return jsonify({"status": status, "event_id": event_key}), 200
    except ValueError as exc:
        DATABASE.table("payment_webhooks").update({"processing_status": "rejected"}).eq("event_key", event_key).execute()
        return jsonify({"error": str(exc)}), 422
    except Exception:
        LOGGER.exception("Unable to apply signed webhook event")
        try:
            DATABASE.table("payment_webhooks").update({"processing_status": "error"}).eq("event_key", event_key).execute()
        except Exception:
            LOGGER.exception("Unable to record webhook processing error")
        return jsonify({"error": "Unable to process webhook"}), 503


@app.get("/health")
def health():
    ready = bool(DATABASE is not None and WEBHOOK_SECRET)
    return jsonify({"status": "ready" if ready else "not_ready"}), 200 if ready else 503


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
