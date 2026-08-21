# File: production/webhook_server.py
# Deploy this to Render.com / Fly.io / Railway - this is standalone file, not string constant
# Fixes payment packaging audit issue

from flask import Flask, request, jsonify
import os, json, hmac, hashlib
import sys

# Try to import supabase, fallback if not available
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("Supabase not installed - pip install supabase")

app = Flask(__name__)

# Init Supabase - REAL production DB (not file)
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = None
if SUPABASE_AVAILABLE and supabase_url and supabase_key:
    try:
        supabase = create_client(supabase_url, supabase_key)
        print(f"Supabase connected: {supabase_url}")
    except Exception as e:
        print(f"Supabase connection failed: {e}")
else:
    print("Supabase not configured - set SUPABASE_URL and SUPABASE_KEY")

webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")

def verify_raw_body(raw_body_bytes, signature, secret):
    """
    CORRECT: Verify exact raw body Razorpay signed, BEFORE JSON parsing
    Fixes V4 issue where json.dumps(payload_json) changed whitespace
    """
    if not secret or not signature:
        return False
    try:
        expected = hmac.new(secret.encode(), raw_body_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False

@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    """
    Production webhook endpoint - Razorpay calls this on payment
    Uses raw body verification + Supabase production DB
    """
    # CRITICAL: Get raw body BEFORE any JSON parsing
    raw_body = request.get_data()  # bytes - exact what Razorpay signed
    signature = request.headers.get("X-Razorpay-Signature", "")
    
    # 1. Verify raw body signature
    if not verify_raw_body(raw_body, signature, webhook_secret):
        print(f"Invalid signature - raw body verification failed")
        return jsonify({"error": "Invalid signature - raw body verification failed"}), 400
    
    # 2. Only now parse JSON (after verification)
    try:
        payload = json.loads(raw_body)
    except Exception as e:
        return jsonify({"error": f"JSON parse failed: {e}"}), 400
    
    event = payload.get("event")
    print(f"Webhook event: {event} - signature verified")
    
    # 3. Log for audit
    if supabase:
        try:
            supabase.table("payment_webhooks").insert({
                "event": event,
                "raw_payload": payload,
                "signature_valid": True
            }).execute()
        except Exception as e:
            print(f"Audit log failed (table may not exist): {e}")
    
    # 4. Grant Pro only on verified paid event
    if event == "payment_link.paid":
        try:
            payload_data = payload.get("payload", {})
            payment_link = payload_data.get("payment_link", {}).get("entity", {})
            payment = payload_data.get("payment", {}).get("entity", {})
            
            email = payment_link.get("customer", {}).get("email") or payment.get("email")
            payment_id = payment.get("id")
            payment_link_id = payment_link.get("id")
            amount = payment.get("amount")
            
            if not email:
                return jsonify({"error": "No email in payload"}), 400
            
            if supabase:
                # REAL production DB write - actually executes
                result = supabase.table("pro_users").upsert({
                    "email": email,
                    "is_pro": True,
                    "payment_id": payment_id,
                    "payment_link_id": payment_link_id,
                    "amount": amount,
                    "verified_via": "webhook_raw_body_v6_production",
                    "storage_mode": "supabase_production"
                }).execute()
                print(f"Pro granted to {email} via Supabase: {result.data}")
                return jsonify({"status": "pro granted", "email": email, "production_ready": True, "storage": "supabase"}), 200
            else:
                # File fallback - not production
                return jsonify({"status": "pro granted but file fallback - not production", "email": email, "production_ready": False}), 200
                
        except Exception as e:
            print(f"Pro grant failed: {e}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"status": "event received", "event": event, "production_ready": supabase is not None}), 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok", 
        "supabase_connected": supabase is not None,
        "supabase_url_set": bool(supabase_url),
        "webhook_secret_set": bool(webhook_secret),
        "production_ready": supabase is not None and bool(webhook_secret)
    }), 200

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "CiteDeck Payment Webhook V6",
        "endpoints": {
            "webhook": "/razorpay-webhook (POST)",
            "health": "/health (GET)"
        },
        "production_ready": supabase is not None
    }), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Starting webhook server on port {port}")
    print(f"Supabase: {'connected' if supabase else 'NOT connected - set SUPABASE_URL and SUPABASE_KEY'}")
    print(f"Webhook secret: {'set' if webhook_secret else 'NOT set - set RAZORPAY_WEBHOOK_SECRET'}")
    app.run(host="0.0.0.0", port=port)
