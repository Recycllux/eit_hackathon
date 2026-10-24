import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple
from src.config.settings import config

logger = logging.getLogger(__name__)


class PropagationAnalyzer:
    """
    Computes pairwise hydrological signal propagation between connected river stations.
    Implements the Pearson lagged daily Ah cross-correlation (Task T-01).
    """

    def __init__(self, df_matrix: pd.DataFrame):
        """
        Args:
            df_matrix: The aligned daily matrix from DanubeDataLoader.
        """
        self.cfg = config.prop_config
        # Pivot to a Date x Station matrix for water levels
        self.levels = df_matrix.pivot(index='date', columns='station', values='water_level_cm')

        # Enforce strict daily grid to ensure .diff() doesn't jump over missing days
        full_index = pd.date_range(start=config.start_date, end=config.end_date, freq='D')
        self.levels = self.levels.reindex(full_index)

        # Calculate daily change (Ah) - missing data yields NaN automatically
        self.dh = self.levels.diff(periods=1)

    def analyze_pair(self, u_station: str, d_station: str) -> Dict[str, Any]:
        """
        Analyzes the propagation from an upstream (u) to a downstream (d) station.
        """
        if u_station not in self.levels.columns or d_station not in self.levels.columns:
            logger.warning(f"Stations {u_station} or {d_station} not found in matrix.")
            return self._empty_result(u_station, d_station)

        # Extract series
        h_u = self.levels[u_station]
        h_d = self.levels[d_station]
        dh_u = self.dh[u_station]
        dh_d = self.dh[d_station]

        # Calculate overlap (n) on levels
        valid_mask = h_u.notna() & h_d.notna()
        n_common = valid_mask.sum()
        gap_rate = 1.0 - (n_common / self.cfg.total_analysis_days)

        # Reject if below absolute minimum overlap
        if n_common < self.cfg.class_b_min_n:
            return self._build_result(u_station, d_station, n_common, gap_rate, quality_class="C",
                                      note="Insufficient overlap (n < 60)")

        # Calculate cross-correlations for lags 0 to 6
        r_level_lags = []
        r_dh_lags = []

        for k in range(self.cfg.max_lag_days + 1):
            # Shift downstream station backwards to align d(t+k) with u(t)
            r_l = h_u.corr(h_d.shift(-k))
            r_dh = dh_u.corr(dh_d.shift(-k))
            r_level_lags.append(r_l if pd.notna(r_l) else 0.0)
            r_dh_lags.append(r_dh if pd.notna(r_dh) else 0.0)

        # Primary test: Best lag on Ah, Reported test: Best lag on levels
        best_lag_dh = int(np.argmax(r_dh_lags))
        best_lag_level = int(np.argmax(r_level_lags))

        best_r_dh = r_dh_lags[best_lag_dh]
        r_level_lag0 = r_level_lags[0]

        # Determine Quality Class (A, B, or C)
        quality_class = self._determine_quality_class(n_common, gap_rate, best_r_dh)

        # Define downstream window [min, max]
        window_min = min(best_lag_dh, best_lag_level)
        window_max = max(best_lag_dh, best_lag_level)

        return self._build_result(
            u_station, d_station, n_common, gap_rate,
            best_lag_level, best_lag_dh, best_r_dh, r_level_lag0,
            window_min, window_max, quality_class
        )

    def _determine_quality_class(self, n: int, gap_rate: float, r_dh: float) -> str:
        """Applies the strict P0-19 quality class rules."""
        if n >= self.cfg.class_a_min_n and r_dh >= self.cfg.class_a_min_r_dh and gap_rate <= self.cfg.class_a_max_gap:
            return "A"
        elif n >= self.cfg.class_b_min_n and r_dh >= self.cfg.class_b_min_r_dh:
            return "B"
        return "C"

    def _build_result(self, u, d, n, gap_rate, lag_lvl=None, lag_dh=None,
                      r_dh=None, r_lvl_0=None, w_min=None, w_max=None,
                      quality_class="C", note=None) -> Dict[str, Any]:
        """Structures the JSON-ready dictionary output per the API specs."""
        return {
            "from_station": u,
            "to_station": d,
            "n_common_observations": int(n),
            "data_gap_rate": round(gap_rate, 3),
            "r_level_lag0": round(r_lvl_0, 3) if r_lvl_0 else None,
            "optimal_lag_days_level": lag_lvl,
            "optimal_lag_days_delta_h": lag_dh,
            "r_delta_h": round(r_dh, 3) if r_dh else None,
            "monitoring_window_days": {"min": w_min, "max": w_max} if w_min is not None else None,
            "quality_class": quality_class,
            "operational": quality_class in ["A", "B"],
            "note": note
        }

    def _empty_result(self, u_station: str, d_station: str) -> Dict[str, Any]:
        return self._build_result(u_station, d_station, 0, 1.0, note="Missing station data")