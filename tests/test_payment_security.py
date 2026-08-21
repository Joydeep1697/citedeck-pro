from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
import unittest

from payment_security import PaymentPolicy, validate_paid_event, verify_raw_body


def signed_payload():
    return {
        "event": "payment_link.paid",
        "account_id": "acc_expected",
        "payload": {
            "payment_link": {"entity": {"id": "plink_expected", "status": "paid", "currency": "INR", "customer": {"email": "Owner@Example.com"}, "notes": {"product": "citedeck_pro"}}},
            "payment": {"entity": {"id": "pay_expected", "amount": 99900, "currency": "INR", "status": "captured", "email": "owner@example.com"}},
        },
    }


class PaymentSecurityTests(unittest.TestCase):
    def setUp(self):
        self.policy = PaymentPolicy(minimum_amount=99900, currency="INR", allowed_payment_link_ids=("plink_expected",), account_id="acc_expected")

    def test_raw_body_signature_uses_exact_bytes(self):
        raw = b'{"event": "payment_link.paid"}'
        secret = "a-real-webhook-secret"
        signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        self.assertTrue(verify_raw_body(raw, signature, secret))
        self.assertFalse(verify_raw_body(b'{"event":"payment_link.paid"}', signature, secret))
        self.assertFalse(verify_raw_body(raw, signature, None))

    def test_valid_paid_event_is_accepted(self):
        result = validate_paid_event(signed_payload(), self.policy)
        self.assertEqual(result["email"], "owner@example.com")
        self.assertEqual(result["amount"], 99900)

    def test_underpayment_is_rejected(self):
        payload = signed_payload()
        payload["payload"]["payment"]["entity"]["amount"] = 100
        with self.assertRaisesRegex(ValueError, "amount"):
            validate_paid_event(payload, self.policy)

    def test_wrong_currency_is_rejected(self):
        payload = signed_payload()
        payload["payload"]["payment"]["entity"]["currency"] = "USD"
        with self.assertRaisesRegex(ValueError, "currency"):
            validate_paid_event(payload, self.policy)

    def test_unapproved_payment_link_is_rejected(self):
        payload = signed_payload()
        payload["payload"]["payment_link"]["entity"]["id"] = "plink_other"
        with self.assertRaisesRegex(ValueError, "not approved"):
            validate_paid_event(payload, self.policy)

    def test_uncaptured_payment_is_rejected(self):
        payload = signed_payload()
        payload["payload"]["payment"]["entity"]["status"] = "created"
        with self.assertRaisesRegex(ValueError, "authorized or captured"):
            validate_paid_event(payload, self.policy)

    def test_wrong_merchant_account_is_rejected(self):
        payload = signed_payload()
        payload["account_id"] = "acc_other"
        with self.assertRaisesRegex(ValueError, "account"):
            validate_paid_event(payload, self.policy)

    def test_non_payment_event_cannot_grant_access(self):
        payload = signed_payload()
        payload["event"] = "payment.authorized"
        with self.assertRaisesRegex(ValueError, "payment_link.paid"):
            validate_paid_event(payload, self.policy)

    def test_unrelated_product_is_rejected_without_an_explicit_link_allowlist(self):
        payload = signed_payload()
        payload["payload"]["payment_link"]["entity"]["notes"]["product"] = "another_product"
        with self.assertRaisesRegex(ValueError, "product"):
            validate_paid_event(payload, PaymentPolicy(minimum_amount=99900, currency="INR"))


class DatabasePolicyTests(unittest.TestCase):
    def test_database_schema_does_not_allow_public_writes(self):
        schema = (Path(__file__).resolve().parents[1] / "supabase_table.sql").read_text(encoding="utf-8")
        self.assertTrue(schema.lstrip().startswith("--"))
        self.assertNotIn("USING (true)", schema)
        self.assertIn("TO authenticated", schema)
        self.assertIn("auth.jwt()", schema)
        self.assertIn("REVOKE ALL ON public.payment_webhooks FROM anon", schema)
        self.assertIn("event_key", schema)


if __name__ == "__main__":
    unittest.main()
