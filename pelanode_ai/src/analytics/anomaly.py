import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List
from src.config.settings import config

logger = logging.getLogger(__name__)


class TemperatureAnomalyDetector:
    """
    Computes candidate temperature anomalies relative to neighboring river stations.
    Implements robust z-scores (MAD) and the neighbour-influence deduplication rule.
    """

    def __init__(self, df_temp: pd.DataFrame):
        """
        Args:
            df_temp: DataFrame containing 'date', 'station', 'water_temperature_c', and 'river_kilometer'.
        """
        self.cfg = config.anomaly_config

        # 1. Sort stations topologically (descending river km = upstream to downstream)
        station_meta = df_temp[['station', 'river_kilometer']].drop_duplicates().dropna()
        self.station_order = station_meta.sort_values(by='river_kilometer', ascending=False)['station'].tolist()

        # 2. Filter out stations with zero temperature coverage (e.g., Vidin Bridge, Ruse Bridge)
        temp_coverage = df_temp.groupby('station')['water_temperature_c'].count()
        self.valid_stations = [s for s in self.station_order if temp_coverage.get(s, 0) > 0]

        # 3. Pivot to Date x Station matrix for fast vectorized operations
        self.temps = df_temp.pivot(index='date', columns='station', values='water_temperature_c')
        self.all_scores = pd.DataFrame()

    def _get_neighbours(self, station: str) -> Dict[str, str]:
        """Finds the nearest valid upstream and downstream stations."""
        idx = self.valid_stations.index(station)
        up_st = self.valid_stations[idx - 1] if idx > 0 else None
        down_st = self.valid_stations[idx + 1] if idx < len(self.valid_stations) - 1 else None
        return {'upstream': up_st, 'downstream': down_st}

    def compute_scores(self) -> pd.DataFrame:
        """Calculates expected temperatures, robust baseline, and z-scores per station-day."""
        results = []

        for station in self.valid_stations:
            neighbours = self._get_neighbours(station)
            up_st, down_st = neighbours['upstream'], neighbours['downstream']

            # Determine reference type (two-sided preferred, one-sided for end-of-chain)
            if up_st and down_st:
                t_ref = (self.temps[up_st] + self.temps[down_st]) / 2.0
                ref_type = "two_sided"
                n_list = [up_st, down_st]
            elif up_st:
                t_ref = self.temps[up_st]
                ref_type = "one_sided"
                n_list = [up_st]
            elif down_st:
                t_ref = self.temps[down_st]
                ref_type = "one_sided"
                n_list = [down_st]
            else:
                continue

            # Residual: e(s,t) = T(s,t) - T_ref(s,t)
            e_st = self.temps[station] - t_ref

            # Robust baseline: median and MAD
            m_s = e_st.median()
            mad = (e_st - m_s).abs().median()
            sigma_s = 1.4826 * mad if mad != 0 else np.nan

            # Robust z-score
            z_st = (e_st - m_s) / sigma_s if pd.notna(sigma_s) else np.nan

            # Structure the results
            station_df = pd.DataFrame({
                'date': self.temps.index,
                'station': station,
                'observed_c': self.temps[station],
                'expected_c': t_ref,
                'residual_c': e_st,
                'robust_z': z_st,
            }).dropna(subset=['robust_z'])

            station_df['baseline_median_c'] = round(m_s, 3)
            station_df['baseline_mad_c'] = round(mad, 3)
            station_df['reference_type'] = ref_type
            station_df['neighbours'] = [n_list] * len(station_df)

            results.append(station_df)

        self.all_scores = pd.concat(results, ignore_index=True)
        return self._apply_neighbour_rule()

    def _apply_neighbour_rule(self) -> pd.DataFrame:
        """
        Applies §9.3 logic: If adjacent stations flag with opposite signs on the same day,
        the one with the largest |z| is primary; the others are neighbour-influenced.
        """
        # Filter to candidate flags only
        flags = self.all_scores[self.all_scores['robust_z'].abs() > self.cfg.z_threshold].copy()
        flags['role'] = 'primary'
        flags['influenced_by'] = None

        # Group by date to resolve conflicts
        for date, group in flags.groupby('date'):
            if len(group) > 1:
                # Sort by absolute z-score descending
                sorted_group = group.assign(abs_z=group['robust_z'].abs()).sort_values(by='abs_z', ascending=False)

                primary_idx = sorted_group.index[0]
                primary_row = sorted_group.iloc[0]
                primary_station = primary_row['station']
                primary_z = primary_row['robust_z']

                # Check for adjacent, opposite-sign flags
                for idx, row in sorted_group.iloc[1:].iterrows():
                    # If the primary station is in this station's reference neighbors, and signs are opposite
                    if primary_station in row['neighbours'] and (row['robust_z'] * primary_z < 0):
                        flags.at[idx, 'role'] = 'neighbour_influenced'
                        flags.at[idx, 'influenced_by'] = primary_station

        return flags.sort_values(by=['date', 'robust_z'], ascending=[True, False])