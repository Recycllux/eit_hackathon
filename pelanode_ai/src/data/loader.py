import pandas as pd
import numpy as np
import logging
from pathlib import Path
from src.config.settings import config

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


class DanubeDataLoader:
    def __init__(self):
        # Resolve file paths based on config
        self.bulletin_path = config.raw_data_dir / config.danube_bulletin_file
        self.automatic_path = config.raw_data_dir / config.bg_automatic_file

    def _load_and_clean(self, filepath: Path, numeric_cols: list) -> pd.DataFrame:
        df = pd.read_csv(filepath)
        df = df.dropna(subset=['station'])
        df['date'] = pd.to_datetime(df['date'], errors='coerce')

        for col in numeric_cols:
            if col in df.columns:
                # Remove '+' signs if present, convert to numeric safely
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('+', ''), errors='coerce')
                # Replace the P0-19 null indicator (-987) with NaN
                df.loc[df[col] == config.null_value_indicator, col] = np.nan

        # Drop duplicates in case of double recordings
        df = df.drop_duplicates(subset=['date', 'station'])
        return df

    def get_normalized_danube_matrix(self) -> pd.DataFrame:
        """
        Combines bulletin levels and automatic gauge temperatures into an aligned matrix.
        """
        logging.info("Ingesting Danube Bulletin levels...")

        # NOTE: 'river_kilometer' must be in both to allow topological sorting later
        df_levels = self._load_and_clean(
            self.bulletin_path,
            numeric_cols=['water_level_cm', 'change_over_24_hours_cm', 'river_kilometer']
        )

        logging.info("Ingesting Bulgarian Automatic gauges...")
        df_auto = self._load_and_clean(
            self.automatic_path,
            numeric_cols=['water_level_cm', 'water_temperature_c', 'river_kilometer']
        )

        # Drop the invalid "Tributaries" header row if it exists in the bulletin
        df_levels = df_levels[df_levels['station'] != 'Tributaries']

        # Vertically stack both networks to get the full 73-station matrix
        merged_matrix = pd.concat([df_levels, df_auto], ignore_index=True)

        # Enforce the 157-day boundary (June 6 to Nov 9, 2021)
        mask = (merged_matrix['date'] >= config.start_date) & (merged_matrix['date'] <= config.end_date)
        aligned_matrix = merged_matrix[mask].copy()

        logging.info(f"Generated aligned daily matrix: {len(aligned_matrix)} rows.")
        return aligned_matrix