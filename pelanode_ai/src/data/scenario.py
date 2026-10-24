import pandas as pd
import logging
from src.config.settings import config

logger = logging.getLogger(__name__)


class ScenarioDateMapper:
    """
    Applies the EIT Hackathon Common 2025 Scenario Timeline rules (P0-19 §4.7).
    Maps historical records (2021) to 2025 for UI navigation while preserving source provenance.
    """

    @staticmethod
    def apply_scenario_timeline(df: pd.DataFrame, dataset_type: str) -> pd.DataFrame:
        """
        Args:
            df: The dataframe with a 'date' column.
            dataset_type: 'danube' (historical) or 'iskar' (native 2025)
        """
        df_mapped = df.copy()

        # Ensure date is a datetime object
        df_mapped['date'] = pd.to_datetime(df_mapped['date'], errors='coerce')

        # Keep the original date strictly isolated
        df_mapped['source_date'] = df_mapped['date'].dt.strftime('%Y-%m-%d')

        if dataset_type == 'danube':
            # Shift 2021 dates to 2025 (keeping month and day)
            df_mapped['scenario_date'] = df_mapped['date'].apply(
                lambda d: d.replace(year=config.scenario_year).strftime('%Y-%m-%d') if pd.notna(d) else None
            )
            df_mapped['time_alignment_method'] = 'year_harmonised_to_2025'
            df_mapped['scenario_assumption'] = True
            df_mapped['claim_scope'] = 'measured'
            df_mapped['ui_badge'] = 'SCENARIO 2025 / SOURCE HISTORICAL'

        elif dataset_type == 'iskar':
            # Iskar is natively 2025, no shift required
            df_mapped['scenario_date'] = df_mapped['source_date']
            df_mapped['time_alignment_method'] = 'native_2025'
            df_mapped['scenario_assumption'] = False
            df_mapped['claim_scope'] = 'scenario_aligned'
            df_mapped['ui_badge'] = 'SCENARIO-ALIGNED TRIBUTARY'

        else:
            raise ValueError(f"Unknown dataset_type: {dataset_type}")

        return df_mapped