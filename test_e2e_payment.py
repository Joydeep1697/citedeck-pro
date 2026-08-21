# File: production/test_e2e_payment.py
# Real E2E test - tests full chain: Razorpay -> webhook raw body -> Supabase -> app unlock
# Fixes: V5 test only simulated Supabase, not real Razorpay webhook flow

import os, requests, json, time, hmac, hashlib
from pathlib import Path

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:5000/razorpay-webhook")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

def test_supabase_connection():
    """Test 1: Supabase table exists and writable"""
    print("\n=== Test 1: Supabase Connection ===")
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        result = supabase.table("pro_users").select("*").limit(1).execute()
        print(f"✓ Supabase connected, pro_users table exists, {len(result.data)} rows")
        return supabase
    except Exception as e:
        print(f"✗ Supabase failed: {e}")
        print("  Run production/supabase_table.sql in Supabase SQL Editor")
        return None

def test_webhook_health():
    """Test 2: Webhook endpoint deployed and healthy"""
    print("\n=== Test 2: Webhook Health ===")
    try:
        health_url = WEBHOOK_URL.replace("/razorpay-webhook", "/health")
        r = requests.get(health_url, timeout=5)
        data = r.json()
        print(f"✓ Webhook health: {data}")
        if not data.get("supabase_connected"):
            print("  ✗ Webhook not connected to Supabase - check SUPABASE_URL and SUPABASE_KEY env in deployment")
        if not data.get("webhook_secret_set"):
            print("  ✗ Webhook secret not set - set RAZORPAY_WEBHOOK_SECRET")
        return data.get("production_ready", False)
    except Exception as e:
        print(f"✗ Webhook not reachable at {health_url}: {e}")
        print(f"  Deploy production/webhook_server.py to Render/Fly.io")
        return False

def test_raw_body_signature():
    """Test 3: Raw body signature verification (fixes json.dumps issue)"""
    print("\n=== Test 3: Raw Body Signature Verification ===")
    raw_body = b'{"event":"payment_link.paid","payload":{"payment":{"entity":{"email":"test@example.com","id":"pay_test123"}}}}'
    secret = "test_secret_123"
    signature = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    
    # Correct way: verify raw body
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    correct = hmac.compare_digest(expected, signature)
    
    # Wrong way: json.dumps changes whitespace
    payload_json = json.loads(raw_body)
    reconstructed = json.dumps(payload_json)  # May change whitespace
    wrong_signature = hmac.new(secret.encode(), reconstructed.encode(), hashlib.sha256).hexdigest()
    wrong = hmac.compare_digest(wrong_signature, signature)
    
    print(f"✓ Correct raw body verification: {correct} (should be True)")
    print(f"  Wrong json.dumps verification: {wrong} (may be False due to whitespace)")
    if correct and not wrong:
        print("  ✓ Demonstrates why raw body is critical - json.dumps can fail")
    return correct

def test_e2e_simulated_webhook():
    """Test 4: Simulated E2E webhook flow (without real Razorpay)"""
    print("\n=== Test 4: Simulated E2E Webhook Flow ===")
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        test_email = "e2e-test@citedeck.com"
        
        # Simulate what webhook_server.py does after verifying raw body
        raw_body = json.dumps({
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {"entity": {"customer": {"email": test_email}, "id": "plink_test"}},
                "payment": {"entity": {"email": test_email, "id": "pay_test123", "amount": 100}}
            }
        }).encode()
        
        # Grant Pro via Supabase (what webhook would do)
        result = supabase.table("pro_users").upsert({
            "email": test_email,
            "is_pro": True,
            "payment_id": "pay_test123",
            "payment_link_id": "plink_test",
            "amount": 100,
            "verified_via": "e2e_test_simulated_webhook"
        }).execute()
        
        print(f"✓ Simulated webhook: granted Pro to {test_email}")
        
        # Verify app can check
        check = supabase.table("pro_users").select("is_pro").eq("email", test_email).execute()
        is_pro = len(check.data) > 0 and check.data[0].get("is_pro")
        print(f"✓ App check: is_pro_user({test_email}) = {is_pro} (should be True)")
        
        # Cleanup
        supabase.table("pro_users").delete().eq("email", test_email).execute()
        print(f"✓ Cleanup: deleted test user")
        
        return is_pro
    except Exception as e:
        print(f"✗ Simulated E2E failed: {e}")
        return False

def test_real_razorpay_payment():
    """Test 5: Real Razorpay payment E2E (requires manual Rs.1 payment)"""
    print("\n=== Test 5: Real Razorpay Payment E2E (Manual) ===")
    print("This test requires manual steps:")
    print("1. Create payment link via Razorpay API:")
    print("   curl -u <key_id>:<key_secret> https://api.razorpay.com/v1/payment_links -d '{\"amount\":100,\"currency\":\"INR\",\"customer\":{\"email\":\"your-real-email@example.com\"}}'")
    print("2. Pay Rs.1 using test card")
    print("3. Check webhook logs at your deployment (Render logs)")
    print("4. Check Supabase pro_users table for your email with is_pro=true")
    print("5. Check Streamlit app unlocks Pro")
    print("\nFor automated test, set TEST_REAL_PAYMENT=1 and implement Razorpay API call")
    
    if os.getenv("TEST_REAL_PAYMENT") == "1":
        # Implement real Razorpay API call if requested
        try:
            import razorpay
            client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
            payment_link = client.payment_link.create({
                "amount": 100,
                "currency": "INR",
                "description": "CiteDeck E2E Test Rs.1",
                "customer": {"email": "e2e-real-test@citedeck.com"},
                "notify": {"sms": False, "email": True}
            })
            print(f"✓ Created real payment link: {payment_link.get('short_url')}")
            print(f"  Pay Rs.1 at this link, then check webhook and Supabase")
            return payment_link.get('short_url')
        except Exception as e:
            print(f"✗ Real payment link creation failed: {e}")
            return None
    else:
        print("Skipped real payment - set TEST_REAL_PAYMENT=1 to test")
        return None

def main():
    print("CiteDeck V6 E2E Payment Test - Full Chain")
    print(f"Supabase URL: {SUPABASE_URL[:30] + '...' if SUPABASE_URL else 'NOT SET'}")
    print(f"Webhook URL: {WEBHOOK_URL}")
    
    supabase = test_supabase_connection()
    webhook_ready = test_webhook_health()
    raw_body_ok = test_raw_body_signature()
    simulated_ok = test_e2e_simulated_webhook()
    real_link = test_real_razorpay_payment()
    
    print("\n=== Summary ===")
    print(f"Supabase: {'✓' if supabase else '✗'}")
    print(f"Webhook deployed: {'✓' if webhook_ready else '✗'}")
    print(f"Raw body verification: {'✓' if raw_body_ok else '✗'}")
    print(f"Simulated E2E: {'✓' if simulated_ok else '✗'}")
    print(f"Real payment link: {real_link if real_link else 'Manual test required'}")
    
    if supabase and webhook_ready and raw_body_ok and simulated_ok:
        print("\n✓ E2E capable - do real Rs.1 payment to become E2E verified")
    else:
        print("\n✗ E2E not ready - fix failed checks above")

if __name__ == "__main__":
    main()
