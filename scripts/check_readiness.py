"""Check production configuration without printing credential values."""

from __future__ import annotations

import argparse
import os


APP_REQUIRED = (
    "OPENAI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
    "CITEDECK_SIGNING_KEY",
)
WEBHOOK_REQUIRED = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "RAZORPAY_WEBHOOK_SECRET",
)


def inspect_configuration(environment, component: str = "all") -> list[str]:
    required = ()
    if component in {"app", "all"}:
        required += APP_REQUIRED
    if component in {"webhook", "all"}:
        required += WEBHOOK_REQUIRED

    issues = [f"Missing {key}" for key in dict.fromkeys(required) if not environment.get(key)]
    if component in {"app", "all"} and str(environment.get("CITEDECK_REQUIRE_PRO", "true")).casefold() in {"false", "0", "no"}:
        issues.append("CITEDECK_REQUIRE_PRO must remain enabled in production")

    anonymous = environment.get("SUPABASE_ANON_KEY")
    privileged = environment.get("SUPABASE_SERVICE_ROLE_KEY")
    if anonymous and privileged and anonymous == privileged:
        issues.append("SUPABASE_ANON_KEY must not contain the service-role key")

    try:
        if int(environment.get("CITEDECK_PRO_AMOUNT_PAISE", "99900")) <= 0:
            issues.append("CITEDECK_PRO_AMOUNT_PAISE must be positive")
    except (TypeError, ValueError):
        issues.append("CITEDECK_PRO_AMOUNT_PAISE must be a positive integer")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=("app", "webhook", "all"), default="all")
    arguments = parser.parse_args()
    issues = inspect_configuration(os.environ, arguments.component)
    if issues:
        print(f"NOT READY: {len(issues)} configuration issue(s)")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"READY: {arguments.component} production configuration is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
