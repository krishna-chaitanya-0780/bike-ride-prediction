# Aether Noir — Four Independent Full-Stack Websites

**Real, navigable source files—not a `.tar`, `.base64` archive or download-only repository.**

This GitHub repository is currently named `bike-ride-prediction` because it is the existing writable repository connected to the account. Its contents are a **four-project monorepo**. Every project has its own runnable frontend (`web/`), FastAPI backend (`server/`), local data directory, scripts, tests, Dockerfile, and a detailed README.

## Open each project

| Folder | Site and purpose | Local URL | Verified reality |
|---|---|---|---|
| [01-medicinal-plants](./01-medicinal-plants/) | **Verdant Atlas:** dark medicinal plant e-commerce | http://localhost:8001 | Searchable products, demo cart/orders, seller-approval workflow; **no verified live sellers/payments** |
| [02-crop-yield](./02-crop-yield/) | **TerraPulse:** satellite/weather crop analysis | http://localhost:8002 | Weather and scene-search API adapters; **yield model requires harvest labels** |
| [03-ride-forecast](./03-ride-forecast/) | **Wayfare:** bike, auto and car planning | http://localhost:8003 | Routing, weather, seven-day planning; **no real Uber/Ola/Rapido quotes or booking** |
| [04-neural-translation](./04-neural-translation/) | **LingoAtlas:** Hindi/Telugu/Korean/English NMT | http://localhost:8004 | Translator UI and local model adapter; **no downloaded/licensed checkpoint** |

## GitHub source tree

```text
.
├── 01-medicinal-plants/
│   ├── server/        # Python API, search, commerce, local DB
│   ├── web/           # E-commerce HTML, CSS, JS, SVG logo
│   ├── docs/          # Botanical sourcing and commerce documentation
│   ├── scripts/       # Real Wikimedia image retrieval helper
│   ├── tests/         # API, account, basket, seller test suites
│   ├── Dockerfile
│   └── README.md
├── 02-crop-yield/
│   ├── server/  web/  scripts/  tests/  Dockerfile  README.md
├── 03-ride-forecast/
│   ├── server/  web/  scripts/  tests/  Dockerfile  README.md
├── 04-neural-translation/
│   ├── server/  web/  scripts/  tests/  Dockerfile  README.md
├── .github/workflows/verify-projects.yml
├── scripts/verify_all.py
├── compose.yaml
└── README.md
```

## Run all projects locally

Requires Python 3.12, or Docker Compose.

```bash
docker compose up --build
```

Alternatively, open a project's folder and run:

```bash
python -m pip install -r requirements.txt
uvicorn server.app:app --reload --port 8003
```

Use the respective project port in the table. The backend serves the **real frontend and API from the same origin**. Interactive API docs are available at `/docs`.

## Verify backend and frontend integration

```bash
python scripts/verify_all.py
```

Runs each project's API test suite, JavaScript syntax validation, and a smoke test that its HTML, CSS, JavaScript and health API can be served together.

## Production scope: actual vs blocked

- **Implemented and locally verified:** FastAPI/JS integration, automated tests, local SQLite storage, shopping and demo-order workflows, model adapter contracts and explicit unavailable states.
- **Needs external data/accounts:** verified plant nurseries and inventory, live payment/shipping, crop and ride training datasets, authorized ride provider APIs, licensed neural checkpoints.
- **Not provisioned:** cloud database, production deployment, charged payments, live ride booking. No credentials are committed.
- **Real botanical photographs:** externally credited Commons photos linked via their source URLs. They are not generated artwork. External image download and license compliance must be checked before republishing.

This is **functional local source with honest provider status**, not a claim that third-party networks and production ML models have been connected.
