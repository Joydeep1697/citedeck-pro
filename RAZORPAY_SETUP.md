# File: production/RAZORPAY_SETUP.md
# Standalone file - fixes packaging audit

# CiteDeck Production Payment Setup - End-to-End

## Architecture
```
User clicks Pay
  ↓
Razorpay Payment Link (Rs. 999)
  ↓
User pays
  ↓
Razorpay -> POST raw body to your webhook
  ↓
Webhook verifies HMAC of raw body (not json.dumps)
  ↓
Webhook writes to Supabase pro_users (is_pro=true)
  ↓
Streamlit app checks Supabase and unlocks Pro
```

## Step 1: Supabase Setup

1. Go to supabase.com -> New Project
2. SQL Editor -> Paste `production/supabase_table.sql` -> Run
3. Verify tables created:
   ```sql
   SELECT * FROM pro_users LIMIT 1;
   SELECT * FROM payment_webhooks LIMIT 1;
   ```
4. Get credentials: Settings -> API -> URL and anon/service_role keys
5. Save:
   - SUPABASE_URL = https://xyz.supabase.co
   - SUPABASE_KEY = service_role key (for webhook server) and anon key (for Streamlit read)

## Step 2: Deploy Webhook Server

Choose one:

### Render.com (recommended)
1. Push `production/webhook_server.py` to GitHub repo
2. Render -> New Web Service -> Connect repo
3. Build command: `pip install flask supabase razorpay`
4. Start command: `python production/webhook_server.py`
5. Env vars:
   - SUPABASE_URL
   - SUPABASE_KEY (service_role)
   - RAZORPAY_WEBHOOK_SECRET (generate random string, e.g., `whsec_123abc`)
   - PORT = 5000
6. Deploy -> Note URL: `https://citedeck-webhook.onrender.com`

### Fly.io
```bash
fly launch
fly secrets set SUPABASE_URL=... SUPABASE_KEY=... RAZORPAY_WEBHOOK_SECRET=...
fly deploy
```

### Railway
Similar steps.

## Step 3: Configure Razorpay Webhook

1. Razorpay Dashboard -> Settings -> Webhooks -> Add Webhook
2. Webhook URL: `https://your-app.onrender.com/razorpay-webhook`
3. Active Events: Check `payment_link.paid`, `payment.authorized`, `payment.captured`
4. Secret: Paste same value as RAZORPAY_WEBHOOK_SECRET env var
5. Save -> Note webhook secret

## Step 4: Streamlit App Secrets

In Streamlit Cloud -> App -> Settings -> Secrets:

```toml
TAVILY_API_KEY = "tvly-..."
OPENAI_API_KEY = "sk-..."
SUPABASE_URL = "https://xyz.supabase.co"
SUPABASE_KEY = "your-anon-key-for-client-read"
RAZORPAY_KEY_ID = "rzp_live_..."
RAZORPAY_KEY_SECRET = "your_razorpay_secret"
RAZORPAY_WEBHOOK_SECRET = "same_as_webhook_secret_above"
WEBHOOK_URL = "https://your-app.onrender.com/razorpay-webhook"
```

## Step 5: E2E Test

### Automated tests (no real money)
```bash
pip install supabase razorpay requests python-dotenv
python production/test_e2e_payment.py
```

Checks:
- Supabase connection
- Webhook health
- Raw body signature verification (proves json.dumps issue)
- Simulated webhook flow

### Real payment test (Rs.1)
```bash
# Create real payment link
curl -u $RAZORPAY_KEY_ID:$RAZORPAY_KEY_SECRET \
  https://api.razorpay.com/v1/payment_links \
  -d '{
    "amount": 100,
    "currency": "INR",
    "description": "CiteDeck Pro E2E Test",
    "customer": {"email": "your-email@example.com"}
  }'

# Pay at returned short_url with test card

# Check:
# 1. Render logs should show "Pro granted to your-email@example.com"
# 2. Supabase pro_users table should have your email is_pro=true
# 3. Streamlit app should unlock Pro
```

Test card: 4111 1111 1111 1111, any future date, any CVV

## Step 6: Verify Production Ready

Checklist:
- [ ] Supabase table exists and RLS enabled
- [ ] Webhook deployed and /health returns production_ready=true
- [ ] Razorpay webhook configured with correct URL and secret
- [ ] Raw body verification works (test via test_e2e_payment.py)
- [ ] Real Rs.1 payment goes through: Razorpay -> webhook -> Supabase -> Streamlit unlocks
- [ ] Audit logs in payment_webhooks table

## Security Notes

- Always verify raw body BEFORE json parsing: `request.get_data()` not `request.json`
- Use service_role key in webhook server (server-side), anon key in Streamlit (client read)
- Webhook secret must match in Razorpay dashboard and env var
- Enable RLS on Supabase tables
- Log all webhooks for audit

## Troubleshooting

- Signature invalid: Check raw body is used, not json.dumps(payload)
- Supabase write fails: Check table exists, RLS policy allows service_role
- Webhook not called: Check Razorpay webhook URL is public HTTPS, not localhost
- Pro not unlocking in Streamlit: Check SUPABASE_URL and SUPABASE_KEY in Streamlit secrets, and that pro_users table has is_pro=true for email
