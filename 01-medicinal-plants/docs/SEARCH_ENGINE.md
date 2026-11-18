# Storefront search — implemented algorithm and scaling plan

## Current implementation

`server/search.py` is a deterministic search layer over a small (eight-plant) seeded catalog.
It deliberately uses an in-memory scan, which is appropriate for this demo volume, not for
thousands of sellers. All ranking logic runs on the server. Main components:

1. **Unicode normalization:** NFKC and Unicode case folding. Regex tokenization retains
   Telugu and Devanagari characters; user inputs are capped at 90 characters.
2. **Weighted fields:** Common name (110), scientific name (85), vernacular terms (70),
   family (40), category (35), cultivation (20), habitat (12), origin (8).
3. **Name aliases:** A curated mapping (e.g., `holy basil`, `tulasi`, `pudina`,
   `kalabanda`) links everyday or regional terms to canonical plant records.
   Full alias matches receive 260 points; prefix and multiword-prefix matches
   are supported for autocomplete.
4. **Text matching:** Exact field match scores 2.4× field weight; prefix 1.45×;
   substring 1.04×; all-token prefix matches 0.6×. For significant misspellings,
   a conservative SequenceMatcher fuzzy fallback applies only to identity fields
   and queries of at least four characters (score requires similarity ≥ 0.72).
5. **Filters:** Region, category, in-stock, minimum price, maximum price.
   Price filters use the lowest **sample unit price** for eligible listings;
   shipment costs are shown separately at checkout.
6. **Sorting:** Relevance, sample unit price ascending/descending, alphabetical,
   sample inventory. Stable plant ID tie-breaker keeps results deterministic.
7. **Suggestions:** `/api/search/suggest?q=...` returns up to six ranked matches
   with a `name`, `scientific_name`, and score. The frontend debounces input
   and rejects stale API responses.

## Search contract examples

- `GET /api/catalog?q=holy%20basil` → Tulsi.
- `GET /api/catalog?q=ashwaganda` → typo-tolerant Ashwagandha.
- `GET /api/catalog?q=కలబంద` → Aloe vera via Telugu vernacular text.
- `GET /api/catalog?category=Aromatic%20herbs&sort=price_asc` → aromatic herbs ordered by sample price.
- `GET /api/catalog?region=Tamil%20Nadu&in_stock=true` → only listings in sample region with available quantities.
- `GET /api/search/suggest?q=hol%20bas` → Tulsi suggestion.

## Production migration

For a real marketplace, introduce:

- PostgreSQL full-text `tsvector` fields for names, descriptions and aliases,
  with a stored search document and GIN indexes.
- `pg_trgm` for typo-tolerant suggestions, with safe query thresholds.
- Dedicated `plant_aliases`, `plant_identifiers`, `product_variants`,
  `seller_inventory`, `shipping_zones`, and `seller_certifications` tables.
- Per-region stock/pricing snapshots refreshed from real verified sellers;
  never invent a live offer from botanical encyclopedias.
- Search-event telemetry only with user consent; monitor no-result queries,
  category coverage, latency p95, click-through, purchase conversion,
  false matches and ranking fairness across sellers.
- Relevance re-ranking must not infer medical efficacy, diagnosis or treatment.

### Complexity

At present, scanning N plants over their searchable text has O(N × fields × tokens)
behavior, plus sorting O(N log N). It is sufficient for eight demo plants;
indexed retrieval is needed for a production-size catalog.

### Known limits

The search index is seeded and small; it does not have real seller rating, confirmed
availability, delivery ETA, transaction history or a learned purchase-ranking model.
Search results label prices/inventory as **demonstration** data.
