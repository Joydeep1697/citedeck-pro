This document is retained only to preserve links to earlier CiteDeck prototypes.

The supported production entry point is app.py.
Current setup, security guidance, verification guarantees, and test commands
are maintained in README.md and RAZORPAY_SETUP.md.

All payment processing uses webhook_server.py and the restrictive policies in
supabase_table.sql. Older V4/V5 payment implementations have been retired.
