from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class WindowDays(BaseModel):
    min: int
    max: int

class StationEdge(BaseModel):
    from_station: str
    to_station: str
    n_common_observations: int
    data_gap_rate: float
    r_level_lag0: Optional[float] = None
    optimal_lag_days_level: Optional[int] = None
    optimal_lag_days_delta_h: Optional[int] = None
    r_delta_h: Optional[float] = None
    monitoring_window_days: Optional[WindowDays] = None
    quality_class: str
    operational: bool
    note: Optional[str] = None

class LagsResponse(BaseModel):
    source: str = "EIT Water Hackathon organiser data"
    provenance: str = "derived_from_organiser"
    period: Dict[str, str] = {"from": "2021-06-06", "to": "2021-11-09"}
    method: Dict[str, Any]
    edges: List[StationEdge]
    note: str = "Lag = historical propagation of the river-level signal. It is not a pollutant travel time."

class AnomalyMethod(BaseModel):
    id: str = "neighbour_mean_robust_z_v1"
    threshold: float
    threshold_status: str = "proposed_demo_tuning"

class AnomalyResponse(BaseModel):
    method: AnomalyMethod
    candidates: List[Dict[str, Any]]
    note: str = "Candidate anomalies relative to neighbouring stations. No source attribution. Ground truth unavailable."