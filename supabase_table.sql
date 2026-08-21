-- Execute as a privileged role in the Supabase SQL Editor.
-- Client applications must use SUPABASE_ANON_KEY; only the webhook service
-- receives SUPABASE_SERVICE_ROLE_KEY. Service-role keys bypass RLS.

CREATE TABLE IF NOT EXISTS public.pro_users (
    email TEXT PRIMARY KEY,
    is_pro BOOLEAN NOT NULL DEFAULT FALSE,
    payment_id TEXT,
    payment_link_id TEXT,
    amount INTEGER CHECK (amount IS NULL OR amount > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    verified_via TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pro_users_payment_id ON public.pro_users (payment_id);

CREATE OR REPLACE FUNCTION public.citedeck_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS citedeck_pro_users_updated_at ON public.pro_users;
CREATE TRIGGER citedeck_pro_users_updated_at
BEFORE UPDATE ON public.pro_users
FOR EACH ROW EXECUTE FUNCTION public.citedeck_set_updated_at();

ALTER TABLE public.pro_users ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pro_users FROM anon;
REVOKE ALL ON public.pro_users FROM authenticated;
GRANT SELECT ON public.pro_users TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.pro_users TO service_role;

DROP POLICY IF EXISTS "Service role can do everything" ON public.pro_users;
DROP POLICY IF EXISTS "Authenticated users can read their own entitlement" ON public.pro_users;
CREATE POLICY "Authenticated users can read their own entitlement"
ON public.pro_users
FOR SELECT
TO authenticated
USING (lower(email) = lower(COALESCE(auth.jwt() ->> 'email', '')));

CREATE TABLE IF NOT EXISTS public.payment_webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key TEXT UNIQUE NOT NULL,
    event TEXT NOT NULL,
    payment_id TEXT,
    signature_valid BOOLEAN NOT NULL DEFAULT FALSE,
    processing_status TEXT NOT NULL DEFAULT 'processing'
        CHECK (processing_status IN ('processing', 'processed', 'rejected', 'error')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Upgrade installations created by the earlier V6 schema.
ALTER TABLE public.payment_webhooks ADD COLUMN IF NOT EXISTS event_key TEXT;
ALTER TABLE public.payment_webhooks ADD COLUMN IF NOT EXISTS processing_status TEXT DEFAULT 'processed';
UPDATE public.payment_webhooks
SET event_key = COALESCE(event_key, 'legacy:' || id::text),
    processing_status = COALESCE(processing_status, 'processed')
WHERE event_key IS NULL OR processing_status IS NULL;
ALTER TABLE public.payment_webhooks ALTER COLUMN event_key SET NOT NULL;
ALTER TABLE public.payment_webhooks ALTER COLUMN processing_status SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_webhooks_event_key ON public.payment_webhooks (event_key);

CREATE INDEX IF NOT EXISTS idx_payment_webhooks_payment_id ON public.payment_webhooks (payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_webhooks_created_at ON public.payment_webhooks (created_at DESC);

ALTER TABLE public.payment_webhooks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.payment_webhooks FROM anon;
REVOKE ALL ON public.payment_webhooks FROM authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.payment_webhooks TO service_role;
DROP POLICY IF EXISTS "Service role can do everything webhooks" ON public.payment_webhooks;
-- Deliberately no client-access policies: only the backend service role may
-- read or write webhook events, and its access comes from BYPASSRLS.
