# Wayfare — Bike, Auto & Car Future Ride Forecasting

An independent FastAPI and responsive frontend project for seven-day ride planning, genuine Open-Meteo weather forecasts, OSRM road-distance routing, and an opt-in real-data ML fare-training pipeline.

## Running locally

```bash
pip install -r requirements.txt
uvicorn server.app:app --reload --port 8003
pytest -q
node --check web/assets/app.js
```

No actual Uber, Ola, or Rapido booking, price lock, or live platform fare quote is enabled. The ten-minute activation window only indicates a local plan status. Without training on legitimate fare records, the application refuses to invent predicted fares. Production needs provider authorizations, real historical ride labels, and infrastructure/security validation.

Part of the Aether Noir Four Independent Projects series. This repository is a public source-code project, not a hosted ride service.
