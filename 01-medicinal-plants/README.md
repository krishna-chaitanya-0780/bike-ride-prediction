# VERDANT ATLAS — Medicinal Plant Commerce 3.0

Shopping-first dark botanical plant store with real botanical reference-photo links, sourced descriptions, intelligent search, regional sample inventory, user accounts, basket, wishlist, owner-approved nursery applications, verified merchant offers, Razorpay **sandbox-only** payment integration code and a **read-only** Shiprocket delivery adapter.

**This is a reproducible local application, not an operating commercial marketplace.** Seeded sellers, prices, inventory and sample orders are examples; they are always marked as such. No actual payment, shipping, seller contract, real cloud database, or public hosting has occurred.

## Start

```bash
python -m venv .venv
# activate for your OS
pip install -r requirements.txt
uvicorn server.app:app --reload --port 8000
```

- Shopper store: `http://localhost:8000/`
- Seller application/portal: click **Sell plants** on the shop header.
- Owner-only review: `http://localhost:8000/owner` (requires a private configured backend owner token)
- API docs: `http://localhost:8000/docs`
- System status: `http://localhost:8000/api/health`, `/api/commerce/status`

## Features

1. Distinctly dark botanical e-commerce aesthetic using pine charcoal, brass, sage, species-specific hues, 2D motion, subtle depth, original vector logo, responsive grids, drawer animations, and accessible reduced-motion CSS.
2. Eight scientific species entries with habitat/origin, forest context, historical use descriptions, cultivation notes, medical-safety limits, Kew/GBIF links, and photo credit/Creative Commons source pages.
3. Search supports vernacular aliases, scientific names, Hindi/Telugu inputs, partial matches, typo tolerance, category, sample price, region, stock, and autocomplete.
4. Local accounts, CSRF-protected forms, password hashing, sample baskets and no-money demo orders.
5. Separate seller portal and merchant database; draft offers cannot appear publicly until manually approved and a verified merchant exists.
6. Owner queue `/owner` to review merchants and offers using a backend-only token. Seller changes revoke offer approval.
7. Razorpay **test-only** order generation, immutable server quote amount, reserved stock, payment signature verification, independent gateway `captured` check, signed webhook processing, and repeat-event handling (requires test credentials; not activated).
8. Optional Shiprocket read-only delivery serviceability query (requires authorization; not activated), with shipping costs never falsely presented as live without provider confirmation.
9. Historical government/nursery research price references explicitly separated from live offers.

## Quality checks

```bash
pytest -q                   # 17 passing backend security + API + commerce tests
node --check web/assets/app.js
```

The original tests remain and the commerce integration tests cover both success and explicit failure paths without calling any real provider.

## Local data, images, secrets

- SQLite is stored at `data/verdant_atlas.sqlite3`; delete it to reset **local test data**. The ZIP excludes the database file.
- PostgreSQL can be configured via `DATABASE_URL`, but no cloud database is provisioned or connected.
- Real photographs are **linked from Wikimedia Commons** rather than image-generated; none of the image binaries are included in this ZIP. When online, the frontend requests Commons images. See `docs/REAL_PHOTOGRAPHY_AND_BOTANY.md` for provenance limitations.
- `COOKIE_SECURE=1` is required when deploying behind HTTPS. Do not use sample passwords or tokens for real customers.
- See `.env.example` for *optional* sandbox credentials. Never commit `.env` or secrets.
- The project is not production-ready. See `docs/COMMERCE_OPERATIONS.md` and `docs/RELEASE_REPORT.md` for remaining compliance, external-service and reliability work.

## GitHub and cloud

A `.github/workflows/test.yml` workflow, `.gitignore`, source tree and README are included. This is **GitHub-ready**, but cannot be described as pushed without a connected authenticated GitHub tool. Nothing was published publicly, and no cloud account was created or billed.
