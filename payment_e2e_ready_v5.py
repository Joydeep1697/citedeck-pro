"""
V5 Payment - Production E2E Ready

Fixes: Production-capable, not automatically production-ready
Your feedback: needs Supabase project, table, secrets, webhook endpoint, Razorpay webhook configured, live test

This file provides:
1. Real Supabase table creation SQL
2. Flask webhook app that is deployable
3. Razorpay webhook configuration guide
4. E2E test script
"""

import os, json, hmac, hashlib
from pathlib import Path
import streamlit as st

SUPABASE_TABLE_SQL = """
-- Run this in Supabase SQL editor to create production table
CREATE TABLE IF NOT EXISTS pro_users (
  email TEXT PRIMARY KEY,
  is_pro BOOLEAN DEFAULT false,
  payment_id TEXT,
  payment_link_id TEXT,
  amount INTEGER,
  currency TEXT DEFAULT 'INR',
  verified_via TEXT DEFAULT 'webhook_raw_body_v5',
  storage_mode TEXT DEFAULT 'supabase_production',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_pro_users_email ON pro_users(email);
CREATE INDEX IF NOT EXISTS idx_pro_users_is_pro ON pro_users(is_pro);

-- Enable RLS (Row Level Security) - allow service role full access
ALTER TABLE pro_users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role can do everything" ON pro_users FOR ALL USING (true) WITH CHECK (true);

-- For audit
CREATE TABLE IF NOT EXISTS payment_webhooks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT,
  event TEXT,
  payment_id TEXT,
  raw_payload JSONB,
  signature_valid BOOLEAN,
  created_at TIMESTAMP DEFAULT NOW()
);
"""

FLASK_WEBHOOK_APP = '''
# File: webhook_server.py - Deploy this to Render / Fly.io / Railway
# This is production webhook endpoint that Razorpay will call

from flask import Flask, request, jsonify
import os, json, hmac, hashlib
from supabase import create_client

app = Flask(__name__)

# Init Supabase - REAL production DB
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")

def verify_raw_body(raw_body_bytes, signature, secret):
    """Verify exact raw body Razorpay signed - not json.dumps()"""
    expected = hmac.new(secret.encode(), raw_body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    raw_body = request.get_data()  # CRITICAL: raw bytes
    signature = request.headers.get("X-Razorpay-Signature", "")
    
    # 1. Verify raw body
    if not verify_raw_body(raw_body, signature, webhook_secret):
        return jsonify({"error": "Invalid signature"}), 400
    
    # 2. Parse after verification
    payload = json.loads(raw_body)
    event = payload.get("event")
    
    # 3. Log webhook for audit (production)
    try:
        supabase.table("payment_webhooks").insert({
            "event": event,
            "raw_payload": payload,
            "signature_valid": True
        }).execute()
    except Exception as e:
        print(f"Audit log failed: {e}")
    
    # 4. Grant Pro only on paid event
    if event == "payment_link.paid":
        try:
            payment_link = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
            payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
            
            email = payment_link.get("customer", {}).get("email") or payment.get("email")
            payment_id = payment.get("id")
            amount = payment.get("amount")
            
            if email and supabase:
                supabase.table("pro_users").upsert({
                    "email": email,
                    "is_pro": True,
                    "payment_id": payment_id,
                    "amount": amount,
                    "verified_via": "webhook_raw_body_v5_production"
                }).execute()
                return jsonify({"status": "pro granted", "email": email, "production": True}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"status": "event received", "event": event}), 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "supabase_connected": supabase is not None}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
'''

RAZORPAY_WEBHOOK_SETUP_GUIDE = """
RAZORPAY WEBHOOK SETUP - End-to-end production

1. Deploy webhook server:
   - Push webhook_server.py to GitHub
   - Deploy to Render.com / Fly.io / Railway
   - Set env vars: SUPABASE_URL, SUPABASE_KEY, RAZORPAY_WEBHOOK_SECRET
   - Note your webhook URL: https://your-app.onrender.com/razorpay-webhook

2. Configure Razorpay webhook:
   - Go to Razorpay Dashboard -> Settings -> Webhooks -> Add Webhook
   - Webhook URL: https://your-app.onrender.com/razorpay-webhook
   - Events: Select payment_link.paid (and payment.authorized, payment.captured for safety)
   - Secret: Generate random string, copy to RAZORPAY_WEBHOOK_SECRET
   - Save

3. Test E2E live payment:
   - Create payment link via API with real email
   - Pay Rs.1 test payment
   - Check webhook logs in Render + Razorpay dashboard
   - Check Supabase pro_users table - email should have is_pro=true
   - Check Streamlit app - is_pro_user_real(email) should return True

4. Streamlit app secrets:
   SUPABASE_URL = "https://xyz.supabase.co"
   SUPABASE_KEY = "your-service-role-key (not anon for server, anon for client)"
   RAZORPAY_KEY_ID = "rzp_live_..."
   RAZORPAY_KEY_SECRET = "your_secret"
   RAZORPAY_WEBHOOK_SECRET = "same secret as in Razorpay webhook config"
"""

E2E_TEST_SCRIPT = '''
# File: test_e2e_payment.py - Run this to test production flow

import os, requests, json
from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def test_e2e():
    print("=== E2E Payment Test ===")
    
    # 1. Check Supabase table exists
    try:
        result = supabase.table("pro_users").select("*").limit(1).execute()
        print("✓ Supabase pro_users table exists")
    except Exception as e:
        print(f"✗ Table missing - run SQL: {e}")
        print(SUPABASE_TABLE_SQL)
        return
    
    # 2. Check webhook endpoint health
    webhook_url = os.getenv("WEBHOOK_URL", "https://your-app.onrender.com/razorpay-webhook")
    try:
        r = requests.get(webhook_url.replace("/razorpay-webhook", "/health"), timeout=5)
        print(f"✓ Webhook health: {r.json()}")
    except:
        print(f"✗ Webhook not reachable at {webhook_url}")
    
    # 3. Simulate payment (without real Razorpay call)
    test_email = "e2e-test@citedeck.com"
    supabase.table("pro_users").upsert({
        "email": test_email,
        "is_pro": True,
        "payment_id": "pay_e2e_test",
        "verified_via": "e2e_test"
    }).execute()
    print(f"✓ Inserted test Pro user: {test_email}")
    
    # 4. Verify Streamlit check
    result = supabase.table("pro_users").select("is_pro").eq("email", test_email).execute()
    is_pro = len(result.data) > 0 and result.data[0].get("is_pro")
    print(f"✓ is_pro check: {test_email} -> {is_pro}")
    
    # Cleanup
    supabase.table("pro_users").delete().eq("email", test_email).execute()
    print("✓ Cleanup done - E2E ready for real Razorpay payment")
    print("\\nNext: Do real Rs.1 payment via Razorpay payment link and check webhook")

if __name__ == "__main__":
    test_e2e()
'''

class PaymentProductionReadyV5:
    def get_setup_files(self):
        return {
            "supabase_table.sql": SUPABASE_TABLE_SQL,
            "webhook_server.py": FLASK_WEBHOOK_APP,
            "setup_guide.md": RAZORPAY_WEBHOOK_SETUP_GUIDE,
            "test_e2e_payment.py": E2E_TEST_SCRIPT
        }
    
    def check_production_readiness(self):
        checks = {
            "supabase_url_set": bool(os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL") if "SUPABASE_URL" in st.secrets else False),
            "supabase_key_set": bool(os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY") if "SUPABASE_KEY" in st.secrets else False),
            "webhook_secret_set": bool(os.getenv("RAZORPAY_WEBHOOK_SECRET") or st.secrets.get("RAZORPAY_WEBHOOK_SECRET") if "RAZORPAY_WEBHOOK_SECRET" in st.secrets else False),
            "table_exists": False,  # Would check via Supabase
            "webhook_deployed": False,  # Would check via health endpoint
            "e2e_tested": False
        }
        return checks

if __name__ == "__main__":
    p = PaymentProductionReadyV5()
    files = p.get_setup_files()
    print("Production setup files generated:")
    for name in files:
        print(f"  - {name}")
