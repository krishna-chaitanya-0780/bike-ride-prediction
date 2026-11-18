# Wayfare — Bike, Auto & Car Future Ride Forecaster (Project 03)

Independent seven-day ride planning platform with live road-distance lookup (OSRM public demo, development only), real Open-Meteo weather forecasts, optional TomTom current traffic, a real-data-required ML training path, provider access status, plan persistence, and an explicit **10-minute predeparture activation** window. Original dark graphite / amber / blue responsive interface with procedural route graphics.

```bash
pip install -r requirements.txt
uvicorn server.app:app --reload --port 8003
```

Open http://localhost:8003, API docs at `/docs`. Run `pytest -q` and `node --check web/assets/app.js`.

**Critical distinctions:**

- Uber and Ola fare estimate APIs are subject to developer/partner approval. Rapido does not have a verified public fare API in this project. No third-party prices, bookings, reserve slots, or price locks are connected.
- The site does not invent prices: `POST /api/fare/model-estimate` returns 503 until historical settled-price observations have been lawfully provided and the model trained. The training script reports temporally separated holdout INR MAE and RMSE. The resulting output is an independent estimate, **not** a platform price.
- A future plan becomes eligible for the locally calculated activation window 10 minutes before the requested pickup, but it **does not initiate any ride booking**. An approved provider's real time quote and user approval would still be needed.
- Short rides should emphasize near-term weather (5–10 hours); longer journeys should consider 7-day forecast variation. Future actual driver supply or surge prices cannot be guaranteed.
- Real route distance is looked up via OSRM during network access. A manually entered distance is clearly labeled `user_supplied`.
- `TOMTOM_API_KEY` can enable the optional CURRENT traffic endpoint. That data must not be presented as third-day traffic prediction.

Optional model training with 150+ legitimately obtained historical actual-fare examples across 21+ days:

```bash
python scripts/train_fares.py --csv real_fare_observations.csv --source 'Authorized dataset source details'
```

Data schema is documented in the script. Data rights and provider terms must be checked prior to integrating proprietary fares. The dataset is NOT bundled.

Research: [Uber developer approval](https://developer.uber.com/docs/riders/references/api/v1.2/estimates-price-get), [Ola Partner API](https://developers.olacabs.com/docs/overview), [OSRM routing](https://github.com/Project-OSRM/osrm-backend), [TomTom current traffic](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/traffic-flow-service).

Local SQLite database only. No cloud DB, payments, bookings, background scheduling service or public deployment is activated.
