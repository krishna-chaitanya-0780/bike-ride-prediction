# Data model, API and permission gates

## Endpoints

| Method | Route | Purpose | Status |
|---|---|---|---|
| GET | `/api/health` | Service + integration truth | Works locally |
| GET | `/api/regions` | Supported demo region labels | Works locally |
| GET | `/api/plants?q=&region=&sort=` | Search/filter records and sample prices | Works locally |
| GET | `/api/plants/{id}` | Complete plant + selected nursery listings | Works locally |
| GET | `/api/plants/{id}/taxonomy` | On-demand species match against GBIF | Live request, internet required |
| GET | `/api/sources` | Source directory | Works locally |
| POST | `/api/auth/register` | Create local account / HttpOnly session | Works locally |
| POST | `/api/auth/login` | Sign in | Works locally |
| GET | `/api/auth/me` | Restore session + CSRF token | Works locally |
| POST | `/api/auth/logout` | Revoke session | Works locally |
| POST | `/api/orders/demo` | Sample order, pricing + inventory transaction | Works locally, no payment |
| GET | `/api/orders` | Signed-in demo order history | Works locally |

## Logical database entities

- `plants`: immutable species identity, taxonomic family, aliases, origin, habitats, forest context, heritage, tradition, safety, evidence note, growing conditions, curated links and visual theme.
- `listings`: foreign key to `plants`, seller/city/region, product unit, server-owned INR price, sample shipping, inventory, verification status. Multiple regional listings per plant.
- `users`: unique email and PBKDF2 salt/hash. No plaintext password storage.
- `user_sessions`: hashed random session token, CSRF token, user id, expiry. HttpOnly cookie references the session.
- `orders`: user link, destination, server-computed totals and explicit demo-only status.
- `order_lines`: item snapshot, quantity, price and shipping charge at time of demo order.

## Production schema additions (pending permission and development)

- `sellers`, `seller_documents`, `nursery_certifications`, `stock_events`, `plant_sources`, `claims_reviews`, `localities`, `shipping_quotes`, `cart_items`, `payments`, `payment_webhooks`, `refunds`, `fulfillments`, `order_events`, `moderation`, and `audit_events`.
- Versioned review workflow for evidence and health/safety content.
- Vendor-provided media with explicit usage rights; do not indiscriminately scrape images from Pinterest.
- Seller inventory APIs, courier integration with serviceable pincode, live delivery charge, payment state machine, verified webhook HMAC signature and idempotency keys.
- Species sourcing standards: distinguish cultivated stock from wild-collected plants; verify legality and state restrictions for protected species.
- Location prices: provider-authorized real seller price, shipping/handling, region availability and last-verified timestamp.

## Approval boundary

There are no cloud credentials in this project and no remote data mutation. Before creating a DB or deployment, the project owner must approve:

1. Provider (for example, Neon, Supabase or a self-managed PostgreSQL instance).
2. Country/region and allowed data categories.
3. Whether the DB is private, staging, or public-facing and whether it contains personal data.
4. Monthly budget and expected usage.
5. Hosting and authentication model.
6. Which deployment/credential/configuration actions are authorized.

After approval: create the requested database through an approved provider integration, apply explicit migrations, set nonpublic environment secrets, add staging/production separation, test read/write with test data, verify backups and monitoring, and share connection status without exposing secrets.

## Automated tests performed

`pytest -q` — **7 passed**. This covers API contracts and local state. It does **not** represent a security audit, load test, third-party integration test, payment test, or production validation.

## Integration quality bar

A service is marked **connected** only after a real authenticated call succeeds, expected data is validated, errors and rate limits are handled, and logs/health checks provide evidence. Display `not_configured` otherwise. Do not use simulated prices or a static species record to claim a verified external service.
