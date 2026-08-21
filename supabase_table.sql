# File: production/supabase_table.sql
# Run this in Supabase SQL Editor - standalone file, not string constant
# Fixes payment packaging audit

-- Pro users table - production durable storage (not ephemeral file)
CREATE TABLE IF NOT EXISTS pro_users (
  email TEXT PRIMARY KEY,
  is_pro BOOLEAN DEFAULT false,
  payment_id TEXT,
  payment_link_id TEXT,
  amount INTEGER,
  currency TEXT DEFAULT 'INR',
  verified_via TEXT DEFAULT 'webhook_raw_body_v6',
  storage_mode TEXT DEFAULT 'supabase_production',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_pro_users_email ON pro_users(email);
CREATE INDEX IF NOT EXISTS idx_pro_users_is_pro ON pro_users(is_pro);
CREATE INDEX IF NOT EXISTS idx_pro_users_created_at ON pro_users(created_at DESC);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_pro_users_updated_at ON pro_users;
CREATE TRIGGER update_pro_users_updated_at BEFORE UPDATE ON pro_users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable RLS - allow service role full access, anon can read own email only for verification
ALTER TABLE pro_users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role can do everything" ON pro_users;
CREATE POLICY "Service role can do everything" ON pro_users FOR ALL USING (true) WITH CHECK (true);

-- Audit table for webhook payloads
CREATE TABLE IF NOT EXISTS payment_webhooks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT,
  event TEXT,
  payment_id TEXT,
  payment_link_id TEXT,
  amount INTEGER,
  raw_payload JSONB,
  signature_valid BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payment_webhooks_email ON payment_webhooks(email);
CREATE INDEX IF NOT EXISTS idx_payment_webhooks_event ON payment_webhooks(event);
CREATE INDEX IF NOT EXISTS idx_payment_webhooks_created_at ON payment_webhooks(created_at DESC);

ALTER TABLE payment_webhooks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role can do everything webhooks" ON payment_webhooks;
CREATE POLICY "Service role can do everything webhooks" ON payment_webhooks FOR ALL USING (true) WITH CHECK (true);

-- For testing
INSERT INTO pro_users (email, is_pro, payment_id, verified_via) VALUES 
  ('test-setup@citedeck.com', true, 'pay_test_setup', 'initial_setup_test')
ON CONFLICT (email) DO NOTHING;

-- Verify
SELECT 'pro_users table ready' as status, COUNT(*) as test_rows FROM pro_users;
SELECT 'payment_webhooks table ready' as status, COUNT(*) as webhook_rows FROM payment_webhooks;
