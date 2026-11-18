# TerraPulse — Crop Yield & Field Intelligence (Project 02)

A real-data-oriented, independent **desktop/web** project for an agricultural field monitoring workflow. Original 2D graphical dark-green UI, weather charts, Sentinel-2 STAC scene discovery, pixel NDVI calculation, locally stored observation history and an offline **real-data-required** crop-yield model training pipeline.

Run:

```bash
pip install -r requirements.txt
uvicorn server.app:app --reload --port 8002
```

Open http://localhost:8002 or http://localhost:8002/docs.

**Data authenticity**:
- Live weather calls use Open-Meteo. When unreachable, API returns 503, not simulated numbers. API forecasts usually cover up to 16 days; requests for 17–25 days explicitly report missing days.
- Real Sentinel-2 catalog metadata comes from Element84 Earth Search STAC (`sentinel-2-c1-l2a`). Thumbnail URLs link to remote source assets. Actual multispectral raster processing and field/polygon statistics are not implemented.
- `POST /api/ndvi/pixel` calculates NDVI from provided **real** Red B04 / NIR B08 reflectance values with an SCL class exclusion check. It is not a satellite imagery pixel downloader.
- Yield prediction is **disabled** until you supply actual area, production and environmental training records; a training script with time-based holdout is included. Run `python scripts/train_yield.py --csv actual_harvest.csv --source '...actual source...'` with at least 80 records and 4 years. It reports MAE/RMSE/R²; that is still not a guarantee of farm-specific accuracy.
- There is no cloud database, no remote dataset written, and no public deployment.

Research: [Open-Meteo](https://open-meteo.com/en/docs), [Element84 Earth Search](https://github.com/Element84/earth-search), [Copernicus Sentinel-2](https://documentation.dataspace.copernicus.eu/Data/Sentinel2.html), [Indian govt crop yields](https://data.desagri.gov.in/website/crops-report-district-level-web).

To validate: `pytest -q` and `node --check web/assets/app.js`.
