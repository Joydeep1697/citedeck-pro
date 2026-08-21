# Production Razorpay and Supabase setup

## 1. Create the database tables

Run the entire [`supabase_table.sql`](supabase_table.sql) file in your Supabase SQL Editor. The migration is safe to rerun and upgrades earlier CiteDeck V6 webhook tables.

The schema deliberately grants authenticated users **read-only access to their own entitlement**. Anonymous users cannot read customer records, and neither anonymous nor authenticated users can modify payments or Pro access. The webhook service uses the separate service-role key.

Enable Supabase Authentication email/password sign-in and configure confirmation requirements to match your deployment.

## 2. Configure the Streamlit application

Deploy with `streamlit run app.py` and configure server-side secrets:

```toml
OPENAI_API_KEY = "..."
TAVILY_API_KEY = "..."
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-anon-client-key"
RAZORPAY_KEY_ID = "rzp_live_..."
RAZORPAY_KEY_SECRET = "..."
CITEDECK_PRO_AMOUNT_PAISE = "99900"
CITEDECK_PRO_CURRENCY = "INR"
CITEDECK_PRODUCT_CODE = "citedeck_pro"
CITEDECK_SIGNING_KEY = "a-long-random-server-side-secret"
CITEDECK_REQUIRE_PRO = "true"
```

Never substitute a service-role key for `SUPABASE_ANON_KEY`.

## 3. Deploy the webhook backend

Deploy the same repository to a separate HTTPS-enabled backend service with:

```bash
gunicorn --bind 0.0.0.0:$PORT webhook_server:app
```

Set these backend-only environment variables:

```text
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
RAZORPAY_WEBHOOK_SECRET=a-long-random-webhook-secret
CITEDECK_PRO_AMOUNT_PAISE=99900
CITEDECK_PRO_CURRENCY=INR
CITEDECK_PRODUCT_CODE=citedeck_pro
```

Optional restrictions:

```text
RAZORPAY_ACCOUNT_ID=acc_...
RAZORPAY_ALLOWED_PAYMENT_LINK_IDS=plink_123,plink_456
```

`GET /health` returns HTTP 200 only when both persistence and webhook signing are configured.

## 4. Configure Razorpay events

In Razorpay Dashboard → Settings → Webhooks, add:

```text
https://your-backend.example.com/razorpay-webhook
```

Use the exact `RAZORPAY_WEBHOOK_SECRET` value from the backend. Subscribe to:

- `payment_link.paid`
- `payment.refunded`
- `refund.processed`, when available for your account

The endpoint verifies the original raw request body with HMAC before decoding JSON. Pro access is granted only if the signed event has the expected amount, currency, real payment/link identifiers, and an authorized/captured payment. Duplicate event IDs are handled idempotently.

## 5. Validate without creating a real charge

```bash
python -m unittest discover -s tests -v
curl -i https://your-backend.example.com/health
```

For a real payment test, create a payment link for the **configured production amount** using an authenticated test account or Razorpay test mode. A ₹1 link cannot activate a ₹999 subscription. After payment, refresh the signed-in subscription in the Streamlit sidebar.

## Security checklist

- The webhook service has the service-role key; the Streamlit database client uses only the anon key.
- The Supabase `pro_users` policy is restricted to `authenticated` and the caller's own JWT email.
- `payment_webhooks` has no client-readable RLS policy.
- Pro price and currency match between the app and webhook service.
- Webhook payloads are not stored in full, and customer emails are not returned in webhook responses.
- Refund events revoke access for the matching payment ID.
- `CITEDECK_SIGNING_KEY` is long, random, and kept server-side.
