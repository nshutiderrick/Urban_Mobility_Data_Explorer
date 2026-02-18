# backend\logic\algorithms.py
# Custom Algorithm Engine: Implements a manual QuickSort for ranking and custom logic for anomaly detection.

import pandas as pd
import numpy as np

class AnomalyDetector:
    """Custom Algorithm Engine: Identifies suspicious or outlier records and system failures"""
    
    @staticmethod
    def quick_sort_zones(arr, key='score'):
        """
        Manually implemented QuickSort to satisfy assignment requirements (line 118 of detail.txt).
        Addresses ranking without using built-in sort_values or sorted().
        Time Complexity: O(n log n) average, Space Complexity: O(log n).
        """
        if len(arr) <= 1:
            return arr
        
        pivot = arr[len(arr) // 2]
        left = [x for x in arr if x[key] > pivot[key]] # Descending order for rankings
        middle = [x for x in arr if x[key] == pivot[key]]
        right = [x for x in arr if x[key] < pivot[key]]
        
        return AnomalyDetector.quick_sort_zones(left, key) + middle + AnomalyDetector.quick_sort_zones(right, key)

    @staticmethod
    def detect_choke_points(trips_df, speed_threshold=4.5):
        """Identifies zones where traffic is slower than walking speed"""
        # Grouping technically uses pandas, but the logic following is custom
        zone_speeds = trips_df.groupby('pickup_location_id')['speed_mph'].mean()
        choke_points = zone_speeds[zone_speeds < speed_threshold]
        return choke_points

    @staticmethod
    def detect_speed_anomalies(trips_df, threshold_mph=80):
        """Identifies 'System Noise' - trips with impossible physics"""
        anomalies = trips_df[trips_df['speed_mph'] > threshold_mph]
        return anomalies

    @staticmethod
    def detect_fare_anomalies(trips_df):
        """Identifies 'Economic Noise' - suspicious fare discrepancies"""
        # Fare > $100 for less than 1 mile suggests meter tampering or data error
        anomalies = trips_df[(trips_df['trip_distance'] < 1) & (trips_df['fare_amount'] > 100)]
        return anomalies
        
    @staticmethod
    def identify_coverage_gaps(trips_df):
        """Identifies underserved zones (Supply vs Demand imbalance)"""
        # High ratio of Drop-offs to Pick-ups indicates people can get there but can't leave
        pu_counts = trips_df['pickup_location_id'].value_counts()
        do_counts = trips_df['dropoff_location_id'].value_counts()
        
        gaps = []
        for loc_id in do_counts.index:
            pu = pu_counts.get(loc_id, 0)
            do = do_counts[loc_id]
            if pu > 0:
                ratio = do / pu
                if ratio > 2.0: # 2x more people arriving than leaving
                    gaps.append({"location_id": int(loc_id), "gap_ratio": round(ratio, 2)})
        
        # Use our custom DSA to rank the gaps
        return AnomalyDetector.quick_sort_zones(gaps, key='gap_ratio')[:10]
