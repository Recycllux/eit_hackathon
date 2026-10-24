from dataclasses import dataclass,field
from pathlib import Path
from typing import Dict, Any

@dataclass
class AnomalyConfig:
    z_threshold: float = 4.0
    threshold_status: str = "proposed_demo_tuning"
@dataclass
class PropagationConfig:
    max_lag_days: int = 6
    total_analysis_days: int = 157

    # Class A rules
    class_a_min_n: int = 120
    class_a_min_r_dh: float = 0.80
    class_a_max_gap: float = 0.10

    # Class B rules
    class_b_min_n: int = 60
    class_b_min_r_dh: float = 0.60
@dataclass
class DataConfig:
    # Base paths relative to the project root
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    raw_data_dir: Path = base_dir / "data" / "raw"
    processed_data_dir: Path = base_dir / "data" / "processed"

    # File names
    danube_bulletin_file: str = "Danube_River_Hydrological_Situation_Bulletin_EN.csv"
    bg_automatic_file: str = "Automatic_Hydrometric_Stations_EN.csv"
    iskar_file: str = "Iskar_Orehovitsa_2025.csv"

    # P0-19 Normalization Rules
    null_value_indicator: int = -987
    start_date: str = "2021-06-06"
    end_date: str = "2021-11-09"
    scenario_year: int = 2025

    # Nested configs
    prop_config: PropagationConfig = field(default_factory=PropagationConfig)
    anomaly_config: AnomalyConfig = field(default_factory=AnomalyConfig)

config = DataConfig()