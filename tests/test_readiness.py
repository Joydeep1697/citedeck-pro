from __future__ import annotations

import unittest

from scripts.check_readiness import inspect_configuration


class ReadinessTests(unittest.TestCase):
    @staticmethod
    def production_environment():
        return {
            "OPENAI_API_KEY": "openai-test",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_ANON_KEY": "anonymous-test",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-test",
            "RAZORPAY_KEY_ID": "razorpay-test",
            "RAZORPAY_KEY_SECRET": "razorpay-secret-test",
            "RAZORPAY_WEBHOOK_SECRET": "webhook-test",
            "CITEDECK_SIGNING_KEY": "signing-test",
            "CITEDECK_REQUIRE_PRO": "true",
            "CITEDECK_PRO_AMOUNT_PAISE": "99900",
        }

    def test_valid_production_environment_is_ready(self):
        self.assertEqual(inspect_configuration(self.production_environment()), [])

    def test_missing_credential_is_reported_without_disclosing_values(self):
        environment = self.production_environment()
        environment.pop("OPENAI_API_KEY")
        self.assertIn("Missing OPENAI_API_KEY", inspect_configuration(environment))

    def test_privileged_key_cannot_be_reused_as_client_key(self):
        environment = self.production_environment()
        environment["SUPABASE_ANON_KEY"] = environment["SUPABASE_SERVICE_ROLE_KEY"]
        self.assertTrue(any("service-role" in issue for issue in inspect_configuration(environment)))

    def test_production_billing_cannot_be_disabled(self):
        environment = self.production_environment()
        environment["CITEDECK_REQUIRE_PRO"] = "false"
        self.assertTrue(any("enabled" in issue for issue in inspect_configuration(environment)))

    def test_invalid_subscription_price_is_rejected(self):
        environment = self.production_environment()
        environment["CITEDECK_PRO_AMOUNT_PAISE"] = "0"
        self.assertTrue(any("positive" in issue for issue in inspect_configuration(environment)))


if __name__ == "__main__":
    unittest.main()
