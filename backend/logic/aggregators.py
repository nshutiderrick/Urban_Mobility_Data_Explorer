# backend\logic\aggregators.py
# Business Logic Layer: Handles complex SQL-based data aggregations for the dashboard charts and statistics.

import sqlite3
import os
import time

class TripAggregator:
    """Business Logic Layer: Handles complex data aggregations"""
    
    @staticmethod
    def get_global_summary(filters):
        """Ultra-High-Performance Aggregator: Bypasses heavy joins using deferral"""
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'taxi_data.db')
        conn = sqlite3.connect(db_path)
        # Performance Tuning
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        cur = conn.cursor()
        
        try:
            # 1. Map locations to boroughs (Fast, 263 rows)
            cur.execute("SELECT location_id, borough FROM taxi_zones")
            loc_to_borough = {r[0]: r[1] for r in cur.fetchall()}
            
            selected_borough = filters.get('borough') if filters.get('borough') != 'all' else None
            start_date = filters.get('start_date')
            end_date = filters.get('end_date')
            
            # 2. Base Query: Group by location_id FIRST (This avoids 1M join operations!)
            # We calculate all raw sums and counts by zone
            where_clauses = []
            params = []
            
            if start_date:
                where_clauses.append("pickup_date >= ?")
                params.append(start_date)
            if end_date:
                where_clauses.append("pickup_date <= ?")
                params.append(end_date)
            if filters.get('zone_id'):
                where_clauses.append("pickup_location_id = ?")
                params.append(filters['zone_id'])
                
            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            
            query = f"""
                SELECT 
                    pickup_location_id,
                    COUNT(*) as trip_count,
                    COALESCE(SUM(fare_amount), 0) as total_fare,
                    COALESCE(SUM(total_amount), 0) as total_rev,
                    COALESCE(SUM(trip_distance), 0) as total_dist,
                    COALESCE(SUM(speed_mph), 0) as total_speed,
                    COALESCE(SUM(CASE WHEN speed_mph > 80 THEN 1 ELSE 0 END), 0) as speed_anomalies,
                    COALESCE(SUM(CASE WHEN trip_distance < 1 AND fare_amount > 100 THEN 1 ELSE 0 END), 0) as fare_anomalies,
                    COALESCE(SUM(CASE WHEN speed_mph <= 80 THEN speed_mph ELSE 0 END), 0) as f_speed_sum,
                    COALESCE(SUM(CASE WHEN speed_mph <= 80 THEN 1 ELSE 0 END), 0) as f_speed_count
                FROM trips
                {where_str}
                GROUP BY 1
            """
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            # 3. Post-Aggregation in Python (Extremely fast for 263 rows)
            borough_data = {}
            for r in rows:
                loc_id, count, fare, rev, dist, speed, speed_anom, fare_anom, f_sum, f_count = r
                b_name = loc_to_borough.get(loc_id, 'Other')
                
                if b_name not in borough_data:
                    borough_data[b_name] = {
                        "trips": 0, "fare": 0, "rev": 0, "dist": 0, 
                        "speed": 0, "speed_anom": 0, "fare_anom": 0, "f_sum": 0, "f_count": 0
                    }
                
                s = borough_data[b_name]
                s['trips'] += count
                s['fare'] += fare
                s['rev'] += rev
                s['dist'] += dist
                s['speed'] += speed
                s['speed_anom'] += speed_anom
                s['fare_anom'] += fare_anom
                s['f_sum'] += f_sum
                s['f_count'] += f_count

            # Final Calculations
            global_trips = 0
            global_fare = 0
            global_rev = 0
            global_dist = 0
            global_speed_sum = 0
            global_speed_anom = 0
            global_fare_anom = 0
            global_f_sum = 0
            global_f_count = 0
            choke_points = 0
            
            congestion_index = {}

            for b_name, s in borough_data.items():
                avg_b_speed = s['f_sum'] / max(s['f_count'], 1)
                congestion_index[b_name] = round(20 / avg_b_speed, 2) if avg_b_speed > 0 else 0
                
                if not selected_borough or b_name == selected_borough:
                    global_trips += s['trips']
                    global_fare += s['fare']
                    global_rev += s['rev']
                    global_dist += s['dist']
                    global_speed_sum += s['speed']
                    global_speed_anom += s['speed_anom']
                    global_fare_anom += s['fare_anom']
                    global_f_sum += s['f_sum']
                    global_f_count += s['f_count']
            
            # Choke points calculated from the already grouped data
            for loc_id, r in zip(loc_to_borough.keys(), rows):
                # r[5] is total_speed, r[1] is trip_count
                avg_loc_speed = r[5] / max(r[1], 1)
                if 0 < avg_loc_speed < 4.5:
                    choke_points += 1

            reliability_score = round(((global_trips - (global_speed_anom + global_fare_anom)) / max(global_trips, 1)) * 100, 4)
            
            return {
                "summary": {
                    "totalTrips": global_trips,
                    "avgFare": round(global_fare / max(global_trips, 1), 2) if global_trips > 0 else 0,
                    "totalRevenue": round(global_rev, 2),
                    "avgDistance": round(global_dist / max(global_trips, 1), 2) if global_trips > 0 else 0,
                    "avgSpeed": round(global_speed_sum / max(global_trips, 1), 2) if global_trips > 0 else 0,
                    "systemHealth": reliability_score,
                    "avgMobilitySpeed": round(global_f_sum / max(global_f_count, 1), 1) if global_f_count > 0 else 0,
                    "totalAnomalies": global_speed_anom + global_fare_anom,
                    "activeChokePoints": choke_points,
                    "anomalyDetails": {
                        "speed": global_speed_anom,
                        "fare": global_fare_anom
                    }
                },
                "congestion": congestion_index
            }
        finally:
            conn.close()



    @staticmethod
    def get_hourly_stats(filters):
        """Calculates volume and speed per hour for Rush Hour identification"""
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'taxi_data.db')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        try:
            start_date = filters.get('start_date')
            end_date = filters.get('end_date')
            
            where_clauses = []
            params = []
            
            if start_date:
                where_clauses.append("pickup_date >= ?")
                params.append(start_date)
            if end_date:
                where_clauses.append("pickup_date <= ?")
                params.append(end_date)
            
            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            
            query = f"""
                SELECT 
                    pickup_hour,
                    COUNT(*) as trip_count,
                    AVG(speed_mph) as avg_speed
                FROM trips
                {where_str}
                GROUP BY pickup_hour
                ORDER BY pickup_hour ASC
            """
            cur.execute(query, params)
            rows = cur.fetchall()
            
            # Ensure all 24 hours are present
            hourly_data = {h: {"trips": 0, "speed": 0} for h in range(24)}
            for r in rows:
                hour, count, speed = r
                hourly_data[hour] = {"trips": count, "speed": round(speed or 0, 2)}
            
            return hourly_data
        finally:
            conn.close()

    @staticmethod
    def get_congestion_index():
        """Legacy - now handled by get_global_summary to save scans"""
        return {}



    @staticmethod
    def get_coverage_gaps(filters=None):
        """Identifies underserviced neighborhoods (Optimized with filter support)"""
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'taxi_data.db')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        try:
            date_clauses = []
            date_params = []
            borough_val = None
            
            if filters:
                if filters.get('start_date'):
                    date_clauses.append("pickup_date >= ?")
                    date_params.append(filters['start_date'])
                if filters.get('end_date'):
                    date_clauses.append("pickup_date <= ?")
                    date_params.append(filters['end_date'])
                if filters.get('borough') and filters.get('borough') != 'all':
                    borough_val = filters['borough']
            
            date_where = f"WHERE {' AND '.join(date_clauses)}" if date_clauses else ""
            
            # Reconstruct query to be robust: Dates in CTEs, Borough in main Join
            query = f"""
                WITH PU AS (SELECT pickup_location_id as loc, COUNT(*) as cnt FROM trips {date_where} GROUP BY 1),
                     DO AS (SELECT dropoff_location_id as loc, COUNT(*) as cnt FROM trips {date_where} GROUP BY 1)
                SELECT z.zone, z.borough, DO.cnt, PU.cnt, z.location_id
                FROM DO
                LEFT JOIN PU ON DO.loc = PU.loc
                JOIN taxi_zones z ON DO.loc = z.location_id
                WHERE (DO.cnt * 1.0 / NULLIF(PU.cnt, 0)) > 2.0
                { "AND z.borough = ?" if borough_val else "" }
                ORDER BY (DO.cnt * 1.0 / NULLIF(PU.cnt, 0)) DESC
                LIMIT 5
            """
            
            final_params = date_params + date_params # For PU and DO CTEs
            if borough_val:
                final_params.append(borough_val)

            cur.execute(query, final_params)
            rows = cur.fetchall()
            return [{"zone": r[0], "borough": r[1], "ratio": round(r[2]/r[3], 2), "id": r[4]} for r in rows if r[3]]
        finally:
            conn.close()
    @staticmethod
    def get_detailed_report(filters):
        """Compiles a comprehensive diagnostic report dataset"""
        # 1. Get baseline summary metrics
        summary_data = TripAggregator.get_global_summary(filters)
        
        # 2. Get Top 5 Zones by Volume in this scope
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'taxi_data.db')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        try:
            where_clauses = []
            params = []
            if filters.get('start_date'):
                where_clauses.append("pickup_date >= ?")
                params.append(filters['start_date'])
            if filters.get('end_date'):
                where_clauses.append("pickup_date <= ?")
                params.append(filters['end_date'])
            
            borough = filters.get('borough')
            if borough and borough != 'all':
                where_clauses.append("pickup_location_id IN (SELECT location_id FROM taxi_zones WHERE borough = ?)")
                params.append(borough)

            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            
            query = f"""
                SELECT z.zone, z.borough, COUNT(*) as trip_count, AVG(speed_mph) as speed
                FROM trips t
                JOIN taxi_zones z ON t.pickup_location_id = z.location_id
                {where_str}
                GROUP BY 1, 2
                ORDER BY trip_count DESC
                LIMIT 5
            """
            cur.execute(query, params)
            top_zones = [{"zone": r[0], "borough": r[1], "trips": r[2], "speed": round(r[3], 1)} for r in cur.fetchall()]
            
            # 3. Get Coverage Gaps for this specific scope
            gaps = TripAggregator.get_coverage_gaps(filters)
            
            # 4. Integrate extra Borough metadata if applicable
            borough_data = {}
            if borough and borough != 'all':
                b_stats = TripAggregator.get_borough_stats(borough, filters)
                borough_data = {
                    "totalTrips": b_stats['totalTrips'],
                    "avgSpeed": b_stats['avgSpeed'],
                    "avgDistance": b_stats['avgDistance'],
                    "zoneCount": b_stats['zoneCount'],
                    "dropoffPassengers": b_stats['dropoffPassengers'],
                    "pickupPassengers": b_stats['pickupPassengers'],
                    "totalPassengers": b_stats['totalPassengers'],
                    "underservedCount": b_stats['underservedCount'],
                    "underservedZones": b_stats['underservedZones']
                }

            return {
                "metadata": {
                    "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "scope": borough if borough != 'all' else "Citywide",
                    "period": f"{filters.get('start_date', 'All')} to {filters.get('end_date', 'All')}",
                    "boroughMetadata": borough_data
                },
                "summary": summary_data['summary'],
                "topZones": top_zones,
                "coverageGaps": gaps
            }
        finally:
            conn.close()

    @staticmethod
    def get_borough_stats(borough, filters=None):
        """Calculates comprehensive stats for a specific borough (supports filters)"""
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'taxi_data.db')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        where_clauses = ["pickup_location_id IN (SELECT location_id FROM taxi_zones WHERE borough = ?)"]
        params = [borough]
        
        if filters:
            if filters.get('start_date'):
                where_clauses.append("pickup_date >= ?")
                params.append(filters['start_date'])
            if filters.get('end_date'):
                where_clauses.append("pickup_date <= ?")
                params.append(filters['end_date'])
        
        where_str = f"WHERE {' AND '.join(where_clauses)}"
        
        try:
            # 1. Main Stats
            query_1 = f"""
                SELECT 
                    COUNT(*) as total_trips,
                    AVG(speed_mph) as avg_speed,
                    AVG(trip_distance) as avg_distance,
                    SUM(passenger_count) as pickup_passengers
                FROM trips t
                {where_str}
            """
            cur.execute(query_1, params)
            res = cur.fetchone() or (0, 0, 0, 0)
            total_trips, avg_speed, avg_distance, pickup_passengers = res[:4]

            # 2. Inbound Passengers (Drop-offs)
            where_do = ["dropoff_location_id IN (SELECT location_id FROM taxi_zones WHERE borough = ?)"]
            params_do = [borough]
            if filters:
                if filters.get('start_date'):
                    where_do.append("pickup_date >= ?")
                    params_do.append(filters['start_date'])
                if filters.get('end_date'):
                    where_do.append("pickup_date <= ?")
                    params_do.append(filters['end_date'])
            
            where_do_str = f"WHERE {' AND '.join(where_do)}"
            cur.execute(f"SELECT SUM(passenger_count) FROM trips {where_do_str}", params_do)
            dropoff_passengers = cur.fetchone()[0] or 0

            # 3. Top 3 Zones in this Borough
            query_3 = f"""
                SELECT z.zone, COUNT(*) as trip_count
                FROM trips t
                JOIN taxi_zones z ON t.pickup_location_id = z.location_id
                {where_str}
                GROUP BY z.zone
                ORDER BY trip_count DESC
                LIMIT 3
            """
            cur.execute(query_3, params)
            top_zones = [{"zone": r[0], "trips": r[1]} for r in cur.fetchall()]

            # 4. List of Underserved Zones (also filtered by date)
            date_where = ""
            date_params = []
            if filters:
                if filters.get('start_date'):
                    date_where += " AND pickup_date >= ?"
                    date_params.append(filters['start_date'])
                if filters.get('end_date'):
                    date_where += " AND pickup_date <= ?"
                    date_params.append(filters['end_date'])

            query_4 = f"""
                WITH PU AS (SELECT pickup_location_id as loc, COUNT(*) as cnt FROM trips WHERE 1=1 {date_where} GROUP BY 1),
                     DO AS (SELECT dropoff_location_id as loc, COUNT(*) as cnt FROM trips WHERE 1=1 {date_where} GROUP BY 1)
                SELECT z.zone, z.location_id
                FROM DO
                LEFT JOIN PU ON DO.loc = PU.loc
                JOIN taxi_zones z ON DO.loc = z.location_id
                WHERE z.borough = ? AND (DO.cnt * 1.0 / NULLIF(PU.cnt, 0)) > 2.0
                ORDER BY (DO.cnt * 1.0 / NULLIF(PU.cnt, 0)) DESC
            """
            cur.execute(query_4, date_params + date_params + [borough])
            underserved_results = [{"zone": r[0], "id": r[1]} for r in cur.fetchall()]
            underserved_count = len(underserved_results)

            # 5. Total Zones in this Borough
            cur.execute("SELECT COUNT(*) FROM taxi_zones WHERE borough = ?", (borough,))
            zone_count = cur.fetchone()[0] or 0

            return {
                "borough": borough,
                "totalTrips": total_trips or 0,
                "avgSpeed": round(avg_speed, 1) if avg_speed else 0,
                "avgDistance": round(avg_distance, 2) if avg_distance else 0,
                "pickupPassengers": pickup_passengers or 0,
                "dropoffPassengers": dropoff_passengers,
                "totalPassengers": (pickup_passengers or 0) + dropoff_passengers,
                "topZones": top_zones,
                "underservedCount": underserved_count,
                "underservedZones": underserved_results,
                "zoneCount": zone_count
            }
        finally:
            conn.close()
