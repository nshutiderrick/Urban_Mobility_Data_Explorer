# backend\etl\processing\cleaner.py
# Data Cleaning Module: Implements rules for filtering outliers, handling missing values, and ensuring financial sanity in the dataset.

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger("DataCleaner")

class DataCleaner:
    """Handles data quality and cleaning steps"""
    
    @staticmethod
    def clean_trip_data(df):
        """
        Applies cleaning rules:
        1. Remove trips with negative fare, extra, or mta_tax
        2. Remove trips with zero or negative distance
        3. Remove trips with zero passenger count (optional but recommended)
        4. Handle missing values (fill or drop)
        """
        initial_count = len(df)
        
        # 1. Financial sanity
        df = df[df['fare_amount'] >= 0]
        df = df[df['total_amount'] >= 0]
        
        # 2. Distance sanity
        df = df[df['trip_distance'] > 0]
        
        # 3. Passenger count (if column exists)
        if 'passenger_count' in df.columns:
            df = df[df['passenger_count'] > 0]
            
        # 4. Handle NaNs
        # For this project, we'll drop rows with missing critical IDs
        df = df.dropna(subset=['PULocationID', 'DOLocationID', 'tpep_pickup_datetime'])
        
        logger.info(f"Cleaning complete. Reduced rows from {initial_count} to {len(df)}.")
        return df

    @staticmethod
    def clean_zone_data(zones_list):
        """Cleans spatial data if necessary"""
        # Ensure all zones have valid geometry
        return [z for z in zones_list if z.get('geometry')]
