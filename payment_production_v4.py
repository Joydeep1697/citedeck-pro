"""Compatibility imports for the retired V4 payment implementation.

V4 silently fell back to ephemeral local files. Payment grants now happen only
through the signed, durable webhook service in ``webhook_server.py``.
"""

from payment_security import PaymentPolicy, validate_paid_event, verify_raw_body

__all__ = ["PaymentPolicy", "validate_paid_event", "verify_raw_body"]
