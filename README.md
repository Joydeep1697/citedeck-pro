# CiteDeck Pro

CiteDeck generates PowerPoint presentations from user documents and cited web research. Every numeric value in every slide bullet must map to a real source passage with a page, spreadsheet cell, document paragraph, CSV row, or URL. If verification fails, the presentation cannot be downloaded.

## What is verified

1. PDF, Excel, DOCX, and CSV sources are parsed with explicit source locations.
2. Optional Tavily research contributes its actual URL passages to generation.
3. The language model receives only the collected document and web evidence.
4. Every numeric span in every bullet is independently matched against its exact source passage.
5. Every slide stores all of its claims and evidence mappings in PowerPoint speaker notes.
6. The final PowerPoint is checked for missing claims, unsupported numbers, visible-text changes, and audit metadata integrity.
7. Export is blocked unless every check succeeds.

`CITEDECK_SIGNING_KEY` enables keyed HMAC integrity for slide audit metadata. Without it, notes are checksum-verified but are not cryptographically tamper-resistant.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
export OPENAI_API_KEY=your-key
export TAVILY_API_KEY=your-key
export CITEDECK_REQUIRE_PRO=false
streamlit run app.py
```

For Windows, activate with `.venv\Scripts\activate`. Set `CITEDECK_REQUIRE_PRO=false` only for isolated local development.

The production Streamlit entry point is `app.py`. `App-Production-Clean.py` is only a compatibility wrapper. Existing earlier prototype files remain for historical reference and should not be selected as deployment entry points.

## Templates

Templates already stored in the repository root are detected automatically. A future `templates/` directory is supported as well. If no template exists, CiteDeck creates a clean PowerPoint using the default theme; verification rules remain identical.

## Production configuration

Configure these values as server-side Streamlit secrets or deployment environment variables:

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Yes | Grounded slide generation. |
| `OPENAI_MODEL` | No | Defaults to `gpt-4o-mini`. |
| `TAVILY_API_KEY` | For web research | Cited market and competitor research. |
| `SUPABASE_URL` | For authentication | Supabase project URL. |
| `SUPABASE_ANON_KEY` | For authentication | Public client key, protected by restrictive RLS. |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | For checkout | Server-side Razorpay payment link creation. |
| `CITEDECK_PRO_AMOUNT_PAISE` | No | Pro price in the smallest currency unit; defaults to `99900`. |
| `CITEDECK_PRO_CURRENCY` | No | Defaults to `INR`. |
| `CITEDECK_PRODUCT_CODE` | No | Payment-link product marker; defaults to `citedeck_pro`. |
| `CITEDECK_SIGNING_KEY` | Strongly recommended | HMAC integrity for presentation audit records. |
| `CITEDECK_REQUIRE_PRO` | No | Defaults to `true`; do not disable in production. |

Deploy `webhook_server.py` as a separate backend service. Its environment additionally requires `SUPABASE_SERVICE_ROLE_KEY` and `RAZORPAY_WEBHOOK_SECRET`. The service-role key must never be passed to client-side or browser code. See [RAZORPAY_SETUP.md](RAZORPAY_SETUP.md).

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
ruff check .
```

The automated suite does not require external API keys, mutate a real database, or create real payment links. `test_e2e_payment.py` is a separately invoked manual integration script and is not collected by the CI unit-test command.

## Limitations

- Verification confirms that a source passage contains the claimed numeric value and applies deterministic context scoring; it is not a guarantee that the source itself is trustworthy.
- Legacy `.xls` files are not supported. Convert them to `.xlsx` first.
- PDF extraction requires selectable text; scanned PDFs need OCR before upload.
- Payment activation requires a deployed and correctly configured Razorpay webhook.
