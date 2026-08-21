"""Compatibility imports for the retired, insecure V5 payment prototype.

The old module embedded permissive SQL and executable webhook examples as string
constants. Use ``supabase_table.sql`` and ``webhook_server.py`` instead.
"""

from payment_security import PaymentPolicy, validate_paid_event, verify_raw_body

__all__ = ["PaymentPolicy", "validate_paid_event", "verify_raw_body"]
