# Wayfare — Bike, Auto & Car Future Ride Forecasting

**Aether Noir Project 03: an independent runnable local full-stack site.** Dark responsive frontend, FastAPI backend, SQLite persistence, OSRM road routing, Open-Meteo weather, opt-in TomTom present-time traffic, ten-minute predeparture activation, actual-fare ML training pipeline, and automated tests.

## Complete source code

The complete tested codebase is included under [`source/wayfare-complete-source.tar.xz.base64`](source/wayfare-complete-source.tar.xz.base64). This GitHub connector publishes text files; this source package is therefore stored as a base64-encoded XZ-compressed TAR archive. The ordinary ready-to-extract ZIP is also available in the ChatGPT conversation.

To restore it on **Linux/macOS** from a cloned repository:

```bash
base64 --decode source/wayfare-complete-source.tar.xz.base64 > wayfare.tar.xz
tar -xJf wayfare.tar.xz
cd Aether_Project_03_Ride_Forecast
pip install -r requirements.txt
PYTHONPATH=. pytest -q
node --check web/assets/app.js
uvicorn server.app:app --reload --port 8003
```

On **Windows PowerShell**:

```powershell
$encoded = (Get-Content source/wayfare-complete-source.tar.xz.base64 -Raw) -replace '\s',''
[IO.File]::WriteAllBytes("wayfare.tar.xz", [Convert]::FromBase64String($encoded))
tar -xJf wayfare.tar.xz
cd Aether_Project_03_Ride_Forecast
pip install -r requirements.txt
python -m pytest -q
uvicorn server.app:app --reload --port 8003
```

Open `http://localhost:8003`. API reference is `http://localhost:8003/docs`.

## Accuracy and restrictions

- **6 local backend tests passed**, JS syntax validated; no verified real provider integration test.
- **No actual Uber, Ola or Rapido quote or booking is enabled.** Partner access is required.
- The ten-minute activation is an internal plan-status window, **not a scheduled price lock**.
- Fare predictions are disabled until legitimate historical settled-fare data is provided and the model is trained with a time-based holdout.
- Public OSRM demo server is for development and does not provide traffic-aware routes.
- No secret tokens, model weights, customer payment data, or external service credentials are included.
- No cloud database, commercial hosting, or paid service is active.

See the restored project's README for full data requirements, provenance, evaluation, endpoints and disclaimers.
