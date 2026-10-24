import logging
import uvicorn
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from contextlib import asynccontextmanager

from src.config.settings import config
from src.data.loader import DanubeDataLoader
from src.analytics.propagation import PropagationAnalyzer
from src.analytics.anomaly import TemperatureAnomalyDetector
from src.analytics.tributary import TributaryHandoffEngine
from src.api.schemas import LagsResponse, AnomalyResponse, AnomalyMethod

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing PelaNode Engine...")
    try:
        loader = DanubeDataLoader()
        df_matrix = loader.get_normalized_danube_matrix()

        # Initialize and cache core engines
        app.state.prop_engine = PropagationAnalyzer(df_matrix)

        anomaly_engine = TemperatureAnomalyDetector(df_matrix)
        app.state.anomaly_results = anomaly_engine.compute_scores()
        app.state.anomaly_engine = anomaly_engine

        # Initialize Tributary Engine (Steps 2, 3, & 4)
        iskar_path = config.raw_data_dir / config.iskar_file
        app.state.tributary_engine = TributaryHandoffEngine(str(iskar_path), app.state.prop_engine)

        logger.info("Data loaded and engines cached successfully.")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")

    yield  # The API runs while yielded

    logger.info("Shutting down PelaNode Engine...")


app = FastAPI(title="PelaNode Intelligence API", version="1.3", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/danube/lags", response_model=LagsResponse)
async def get_lags(source: Optional[str] = None):
    engine: PropagationAnalyzer = app.state.prop_engine
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    edges = []
    if source:
        targets = ["Bechet", "Turnu Magurele", "Giurgiu"] if source == "Calafat" else []
        for target in targets:
            res = engine.analyze_pair(source, target)
            edges.append(res)

    method_meta = {
        "id": "pearson_lagged_daily_v1",
        "max_lag_days": config.prop_config.max_lag_days,
        "min_n": config.prop_config.class_b_min_n,
        "status": "proposed_demo_tuning"
    }

    return LagsResponse(method=method_meta, edges=edges)


@app.get("/api/v1/danube/anomalies", response_model=AnomalyResponse)
async def get_anomalies(station: Optional[str] = None, date: Optional[str] = None):
    results = app.state.anomaly_results
    if results is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    mask = (results['robust_z'].abs() > config.anomaly_config.z_threshold)

    if station:
        mask &= (results['station'] == station)
    if date:
        mask &= (results['date'] == date)

    filtered = results[mask].copy()
    filtered['date'] = filtered['date'].dt.strftime('%Y-%m-%d')

    method_meta = AnomalyMethod(threshold=config.anomaly_config.z_threshold)

    return AnomalyResponse(
        method=method_meta,
        candidates=filtered.to_dict(orient="records")
    )


@app.get("/api/v1/scenario/tributaries/iskar")
async def get_iskar_handoff(date: str = "2025-11-06"):
    """Executes the topological handoff for the Iskar scenario (Tasks T-16)."""
    engine: TributaryHandoffEngine = app.state.tributary_engine
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    result = engine.execute_handoff(date)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)