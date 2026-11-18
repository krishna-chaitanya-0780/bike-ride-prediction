# Merchant marketplace, prices, test payments and courier workflows

## Implemented, tested locally

The `server/commerce.py` API layer is separate from the legacy 8-species demo dataset. Demo nursery inventory never becomes verified automatically. Sellers sign in with a normal account and submit an application at **Sell plants**. Their applications and offers remain `PENDING_REVIEW` until an operator intentionally approves them via `/owner` (or `/api/commerce/owner/...`) with the private `VERDANT_OWNER_TOKEN` header. A changed seller offer loses approval and requires review again.

- `POST /api/commerce/seller/apply`: seller account application (auth + CSRF)
- `GET /api/commerce/seller/me`: owner-specific applications and offers
- `POST /api/commerce/seller/offers`: seller-submitted draft offer
- `PUT /api/commerce/seller/offers/{id}`: replace offer, revoke prior approval
- `GET /api/commerce/owner/review`: owner queue, private token required
- `POST /api/commerce/owner/merchants/{id}/review`: approve/reject merchant
- `POST /api/commerce/owner/offers/{id}/review`: approve/reject offer
- `GET /api/commerce/offers`: public APPROVED offers owned by VERIFIED merchants only
- `POST /api/commerce/checkout/quote`: server-calculated total and price provenance, explicitly not a shipping offer
- `POST /api/commerce/checkout/create-test-order`: only with Razorpay **test** account and opt-in flag
- `POST /api/commerce/checkout/verify-test-payment`: HMAC signature + independent payment fetch + captured status + exact order/amount checks
- `POST /api/commerce/webhooks/razorpay-test`: signed webhook, duplicate-event handling
- `GET /api/commerce/orders`: authenticated account test orders
- `GET /api/commerce/delivery/quote`: optional Shiprocket serviceability **read-only** query (requires token and opt-in)
- `GET /api/commerce/price-references`: cited historical institutional prices, **not current transaction offers**.

The owner portal exists at `/owner`. An administrator must review genuine business identity, plant identity, propagation legality, shipping restrictions, actual inventory and price evidence *outside the site* before approving. Approval is an administrative state, not a scientific or regulatory certification.

## How to activate test payments (not live)

Environment options:

```ini
ENABLE_TEST_CHECKOUT=1
RAZORPAY_KEY_ID=rzp_test_REPLACE
RAZORPAY_KEY_SECRET=REPLACE
RAZORPAY_TEST_WEBHOOK_SECRET=REPLACE
```

Razorpay **live** key IDs are rejected even if `ENABLE_TEST_CHECKOUT=1`. The storefront dynamically loads the Razorpay test checkout UI only on a user-initiated sandbox attempt. No browser secret is bundled. The server generates payment orders using server-derived prices, only for offers reviewed by an operator. Test captured events are not proof that live money changed hands. Shipment booking remains disabled.

Security: The signature from Checkout is compared with HMAC SHA-256 using the server-side secret and its stored gateway order ID; the Razorpay payment API is consulted to verify `captured`, amount, currency, payment ID and order linkage. A signed webhook is also checked using the raw request body. Replays of the same event are recorded. **Never infer "paid" from a client-side JavaScript success callback alone.**

The payment flow is a functional test adapter, **not** a completed production payments system. Before production: implement idempotent provider order creation, reservation expiry/reconciliation, chargebacks/refunds, durable event queues, fraud controls, merchant settlement, taxes, financial ledger, external PCI review, and production account approval. Some failure/reconciliation paths deliberately require manual handling.

## Shipping

The only wired external courier operation is an optional **read-only** Shiprocket serviceability lookup, disabled by default. It requests eligible couriers for pickup/delivery pincodes and returns provider-supplied indicative rate and days when the service is enabled and available.

```ini
ENABLE_SHIPROCKET_QUOTES=1
SHIPROCKET_API_TOKEN=REPLACE
```

No bookings, airway bills, packages, returns, dispatch or pickup requests are sent. Local sample freight values belong to *demo* checkout only. The verified-offer sandbox checkout currently uses an explicit **₹0 sandbox assumption** for shipping, not a customer-safe freight quotation. This is why live payment processing remains disabled by code.

The future production delivery workflow requires seller pickup address verification, parcel weight/dimensions, plant shipping legality, weather and live-plant packaging rules, serviceability, tracking, return policies and merchant-specific delivery agreements. Make real freight part of the final bill before enabling real payment.

## Historic market reference prices are NOT live prices

The Indian Directorate of Medicinal and Aromatic Plants Research has publicly listed historical propagation prices for plant species, including a Tulsi group entry. These figures are useful research context but not evidence that a plant can presently be purchased at that price. The user-facing API identifies each as historical, illustrative and without delivery charges.

- [DMAPR pricelist](https://www.dmapr.org.in/HeadPage/Pricelist.html)
- [Razorpay integration requirements](https://razorpay.com/docs/server-integration/python/test-app/)
- [Shiprocket API documentation](https://apidocs.shiprocket.in/)

## Launch blockers

1. Actual authorized merchant registration, identity checks, tax and seller agreements.
2. Real offers and stock feeds confirmed by those merchants.
3. Current market pricing and verified delivery/serviceability for each postal code.
4. Authorized production merchant payment credentials (never requested or provisioned automatically).
5. An approved, secure hosting database and object storage account.
6. License-checked, actually downloaded real plant photographs and updated credit records.
7. Independent security, privacy, medical claim, packaging/legal, accessibility and load tests.
8. GitHub connection for an authenticated repository push.
