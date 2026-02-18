# backend\dal\trip_dal.py
# Trip Data Access Layer: Handles CRUD operations for taxi trip records and zone metadata.
# Includes methods for bulk insertion of cleaned trip data.

import sqlite3
import os
import json

class TripDAL:
    """Data Access Layer for Trip operations"""
    def __init__(self, db_path):
        self.db_path = db_path

    def insert_trips(self, trips_df):
        """Efficiently inserts trip data into the database using bulk operations"""
        conn = sqlite3.connect(self.db_path)
        try:
            df_to_save = trips_df.copy()
            
            # Map raw CSV columns to schema.sql names
            column_mapping = {
                'VendorID': 'vendor_id',
                'RatecodeID': 'rate_code_id',
                'PULocationID': 'pickup_location_id',
                'DOLocationID': 'dropoff_location_id',
                'payment_type': 'payment_type_id',
                'tpep_pickup_datetime': 'pickup_time', # For now, use raw datetime or handle IDs
                'tpep_dropoff_datetime': 'dropoff_time'
            }
            df_to_save = df_to_save.rename(columns=column_mapping)
            
            # Filter only columns that exist in the target table
            # Note: trips table doesn't have pickup_time/dropoff_time, it has IDs.
            # For simplicity, we'll temporarily drop columns that don't match or add them to schema
            # But let's follow the schema: speed_mph, fare_per_mile, tip_percentage (renamed to tip_percent?)
            
            # Let's ensure columns match schema.sql exactly
            target_columns = [
                'vendor_id', 'passenger_count', 'trip_distance', 'rate_code_id', 
                'payment_type_id', 'fare_amount', 'extra', 'mta_tax', 'tip_amount', 
                'pickup_location_id', 'dropoff_location_id', 'tolls_amount', 
                'improvement_surcharge', 'total_amount', 'congestion_surcharge', 
                'speed_mph', 'fare_per_mile', 'trip_duration_seconds'
            ]
            
            # Force columns to match and handle missing
            df_final = df_to_save.reindex(columns=target_columns)
            
            df_final.to_sql('trips', conn, if_exists='append', index=False)
            conn.commit()
            print(f"Successfully inserted {len(df_final)} rows into 'trips' table.")
        except Exception as e:
            print(f"Error inserting trips: {e}")
            # print(trips_df.columns) # Helpful for debugging
        finally:
            conn.close()

    def insert_zones(self, zones_data):
        """Inserts taxi zone data using INSERT OR IGNORE to avoid duplicates"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            for zone in zones_data:
                attr = zone['attributes']
                geom = zone['geometry']
                cur.execute('''
                    INSERT OR IGNORE INTO taxi_zones (location_id, borough, zone, geojson)
                    VALUES (?, ?, ?, ?)
                ''', (
                    attr.get('LocationID'), 
                    attr.get('borough'), 
                    attr.get('zone'), 
                    json.dumps(geom)
                ))
            conn.commit()
            print(f"Successfully inserted {len(zones_data)} zones into 'taxi_zones' table.")
        except Exception as e:
            print(f"Error inserting zones: {e}")
        finally:
            conn.close()
