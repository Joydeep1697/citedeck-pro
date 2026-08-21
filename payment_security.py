"""Provider-independent, fail-closed Razorpay webhook validation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import os


@dataclass(frozen=True)
class PaymentPolicy:
    minimum_amount: int = 99900
    currency: str = "INR"
    allowed_payment_link_ids: tuple[str, ...] = ()
    account_id: str | None = None
    product_code: str = "citedeck_pro"

    @classmethod
    def from_environment(cls):
        amount = int(os.getenv("CITEDECK_PRO_AMOUNT_PAISE", "99900"))
        if amount <= 0:
            raise ValueError("CITEDECK_PRO_AMOUNT_PAISE must be positive")
        links = tuple(value.strip() for value in os.getenv("RAZORPAY_ALLOWED_PAYMENT_LINK_IDS", "").split(",") if value.strip())
        return cls(minimum_amount=amount, currency=os.getenv("CITEDECK_PRO_CURRENCY", "INR").upper(), allowed_payment_link_ids=links, account_id=os.getenv("RAZORPAY_ACCOUNT_ID") or None, product_code=os.getenv("CITEDECK_PRODUCT_CODE", "citedeck_pro"))


def verify_raw_body(raw_body: bytes, signature: str, secret: str | None) -> bool:
    if not raw_body or not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def validate_paid_event(payload: dict, policy: PaymentPolicy) -> dict:
    if payload.get("event") != "payment_link.paid":
        raise ValueError("Only payment_link.paid events can grant access")
    if policy.account_id and payload.get("account_id") != policy.account_id:
        raise ValueError("The webhook belongs to an unexpected Razorpay account")

    data = payload.get("payload") or {}
    link = ((data.get("payment_link") or {}).get("entity") or {})
    payment = ((data.get("payment") or {}).get("entity") or {})
    email = str(((link.get("customer") or {}).get("email") or payment.get("email") or "")).strip().casefold()
    payment_id = str(payment.get("id") or "").strip()
    payment_link_id = str(link.get("id") or "").strip()
    amount = payment.get("amount")
    currency = str(payment.get("currency") or link.get("currency") or "").upper()
    payment_status = str(payment.get("status") or "").casefold()
    link_status = str(link.get("status") or "").casefold()

    if "@" not in email or not payment_id or not payment_link_id:
        raise ValueError("Paid event is missing its customer email, payment ID, or payment link ID")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < policy.minimum_amount:
        raise ValueError("Paid amount does not satisfy the configured Pro price")
    if currency != policy.currency:
        raise ValueError("Payment currency does not match the configured Pro currency")
    if payment_status not in {"captured", "authorized"}:
        raise ValueError("Payment has not been authorized or captured")
    if link_status and link_status != "paid":
        raise ValueError("Payment link is not marked paid")
    if policy.allowed_payment_link_ids and payment_link_id not in policy.allowed_payment_link_ids:
        raise ValueError("Payment link is not approved for CiteDeck Pro")
    product = str((link.get("notes") or {}).get("product") or (payment.get("notes") or {}).get("product") or "")
    if not policy.allowed_payment_link_ids and product != policy.product_code:
        raise ValueError("Payment link does not identify the configured CiteDeck Pro product")

    return {"email": email, "payment_id": payment_id, "payment_link_id": payment_link_id, "amount": amount, "currency": currency}
