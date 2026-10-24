import pandas as pd
import logging
from typing import Dict, Any, List
from src.config.settings import config
from src.analytics.propagation import PropagationAnalyzer

logger = logging.getLogger(__name__)


class TributaryHandoffEngine:
    """
    Handles the Iskar -> Danube scenario handoff (Task T-16, P0-19 §8.7).
    Inherits downstream windows without calculating false cross-year correlations.
    """

    def __init__(self, iskar_filepath: str, prop_engine: PropagationAnalyzer):
        self.filepath = iskar_filepath
        self.prop_engine = prop_engine

        # Define the exact handoff gauges dictated by P0-19 (skipping Nikopol)
        self.handoff_nodes = {
            "ro_bulletin": "Corabia",
            "bg_automatic": "Zagrazhden"
        }

        # P0-19 Rule: Tributary event triggers on consecutive daily rise >= 5 m3/s
        self.trigger_threshold = 5.0

    def load_and_find_events(self) -> pd.DataFrame:
        """Loads Iskar data and identifies valid event trigger days."""
        df = pd.read_csv(self.filepath)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['discharge'] = pd.to_numeric(df['discharge(m3/s)'], errors='coerce')

        # Sort and calculate daily rise
        df = df.sort_values('date').reset_index(drop=True)

        # Ensure we only calculate diff for consecutive days (P0-19 §4.7 gap rule)
        df['days_diff'] = df['date'].diff().dt.days
        df['rise'] = df['discharge'].diff()
        df.loc[df['days_diff'] > 1, 'rise'] = None

        # Filter for the shared 2025 scenario window
        mask = (df['date'] >= '2025-07-12') & (df['date'] <= '2025-11-09')
        df_window = df[mask].copy()

        # Flag events where the rise meets the threshold
        df_window['is_event'] = df_window['rise'] >= self.trigger_threshold

        return df_window[df_window['is_event']]

    def execute_handoff(self, event_date: str) -> Dict[str, Any]:
        """
        Executes the topological handoff for a specific event date,
        inheriting the historically learned Danube windows.
        """
        events = self.load_and_find_events()
        event_row = events[events['date'] == event_date]

        if event_row.empty:
            return {"error": f"No valid tributary event found on {event_date}"}

        discharge_val = event_row['discharge'].values[0]
        rise_val = event_row['rise'].values[0]

        # Generate the inherited windows from the propagation engine
        handoff_chains = []
        for chain, gauge in self.handoff_nodes.items():
            # For the demo, we statically define the targets downstream of the handoff nodes
            targets = []
            if gauge == "Corabia":
                targets = ["Turnu Magurele", "Zimnicea", "Giurgiu", "Oltenita"]
            elif gauge == "Zagrazhden":
                targets = ["Svishtov", "Ruse Bridge", "Ryahovo", "Malak Preslavets"]

            windows = []
            for target in targets:
                edge = self.prop_engine.analyze_pair(gauge, target)
                if edge['operational']:
                    windows.append({
                        "station_id": edge['to_station'],
                        "window_days": edge['monitoring_window_days'],
                        "quality_class": edge['quality_class']
                    })

            handoff_chains.append({
                "chain": chain,
                "gauge": gauge,
                "downstream_windows": windows
            })

        return {
            "event_type": "tributary_input_event",
            "station_id": "Orehovitsa",
            "source_date": event_date,
            "discharge_m3s": round(discharge_val, 1),
            "change_24h_m3s": round(rise_val, 1),
            "confluence_km": 637,
            "handoff": handoff_chains,
            "claim_scope": "scenario_aligned",
            "note": "Scenario handoff only. Iskar (2025) and Danube (2021) records do not overlap natively; no pollutant travel time or Danube-level impact is inferred."
        }