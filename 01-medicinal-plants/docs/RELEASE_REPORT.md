# Release validation report — Verdant Atlas Commerce 3.0

Status date: 2026-11-18. This is a **local software release**, not a commercially operational plant marketplace.

| Area | Actual result | Limits |
|---|---|---|
| FastAPI / SQLAlchemy | Implemented and importable | Local SQLite default; PostgreSQL config supported but not deployed |
| Search | Alias / typo / scientific name / Telugu / filters | Small seed catalog; scalability has not been load tested |
| Botanical details | Eight species with habitat, origin, historical practices, safety notes, Commons source links | Editorial descriptions need expert editorial and regulatory review |
| Real photos | Eight externally sourced Wikimedia Commons photographs identified by filenames and attribution | Binary images not downloaded; not proof of photo/license metadata accuracy |
| Storefront | Responsive dark-theme product grid, details, basket and account interfaces | New seller UI was syntax checked; browser execution restricted in this environment |
| Seller onboarding | Account application, owned offers, owner review / invalidation | No real nursery has been independently onboarded |
| Server quotes | Price/stock checks for verified-offer sandbox; separates sample items | Shipping for sandbox is zero **assumption**, not a real rate |
| Payments | Razorpay test-only order adapter, HMAC verification, independent captured status check, signed webhook and replay tests | No credentials connected, no live payments, no actual payment capture performed |
| Shipping | Shiprocket read-only serviceability adapter | No courier credentials or booking; no parcels sent |
| Automation | 17 tests passing, JavaScript syntax checked | No production load, accessibility audit, or external end-to-end test |
| Repository | GitHub Actions workflow, .gitignore, source code and documentation | No GitHub push; connector not accessible |

## Verify locally

```bash
pip install -r requirements.txt
pytest -q
node --check web/assets/app.js
uvicorn server.app:app --reload
```

Browse `http://127.0.0.1:8000/`, `/owner`, and `/docs`. Never set production API keys inside source files. A `VERDANT_OWNER_TOKEN` is required to perform human verification from `/owner`.

The developer sandbox blocked Chromium navigation with `ERR_BLOCKED_BY_ADMINISTRATOR`, including a local route bridge. The backend API suite and JS syntax pass; this environment cannot provide a new accurate browser screenshot of the new seller portal.
