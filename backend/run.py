# backend\run.py
# Main Backend Server: Flask application that defines all API endpoints for dashboard data, authentication, and health checks.

from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import sys
import json
import sqlite3

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.security.validator import RequestValidator
from backend.logic.aggregators import TripAggregator
from backend.security.auth_logic import AuthLogic

app = Flask(__name__)
CORS(app) # Enable CORS for frontend integration

# For simplicity in this demo, we'll use a secret key and a simple token storage
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'nyc-taxi-secret-key')
tokens = {} # In-memory token storage (resets on restart)

def get_db_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'taxi_data.db')

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    hashed_password = AuthLogic.hash_password(password)
    
    try:
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, hashed_password))
        conn.commit()
        conn.close()
        return jsonify({"message": "User created successfully"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "User already exists"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    try:
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        conn.close()

        if row and AuthLogic.verify_password(password, row[0]):
            token = AuthLogic.generate_token()
            tokens[token] = email # Store session
            return jsonify({"token": token, "email": email}), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "NYC Taxi API"})

@app.before_request
def log_request():
    print(f"📡 API Request: {request.method} {request.path} {request.args}")

@app.route('/api/trips/summary', methods=['GET'])
def get_trip_summary():
    """Returns combined mobility metrics (Optimized single-pass)"""
    try:
        from backend.logic.aggregators import TripAggregator
        filters = {
            "month": request.args.get('month', 'all'),
            "borough": request.args.get('borough', 'all')
        }
        
        # Super-Aggregator pass
        full_data = TripAggregator.get_global_summary(filters)
        health_data = TripAggregator.get_health_metrics(filters)
        
        # Merge summary with extra health metrics (choke points)
        return jsonify({**full_data['summary'], **health_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/trips/revenue', methods=['GET'])
def get_congestion_report():
    """Returns Congestion Index (Optimized)"""
    try:
        from backend.logic.aggregators import TripAggregator
        # Call super-aggregator - it's fast now!
        full_data = TripAggregator.get_global_summary({"borough": "all"})
        return jsonify(full_data['congestion'])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/trips/gaps', methods=['GET'])
def get_coverage_gaps():
    """Returns top 5 underserved zones"""
    try:
        from backend.logic.aggregators import TripAggregator
        data = TripAggregator.get_coverage_gaps()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/boroughs/<borough>/stats', methods=['GET'])
def get_borough_stats(borough):
    """Returns aggregated stats for a specific borough"""
    try:
        from backend.logic.aggregators import TripAggregator
        data = TripAggregator.get_borough_stats(borough)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/zones', methods=['GET'])
def get_zones():
    """Returns spatial data for the map"""
    try:
        # We can reuse the DAL or call it directly
        from backend.dal.trip_dal import TripDAL
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'taxi_data.db')
        dal = TripDAL(db_path)
        
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT location_id, borough, zone, geojson FROM taxi_zones")
        rows = cur.fetchall()
        
        zones = []
        for r in rows:
            zones.append({
                "id": r[0],
                "borough": r[1],
                "zone": r[2],
                "geometry": json.loads(r[3]) if r[3] else None
            })
        return jsonify(zones)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/zones/<int:zone_id>/stats', methods=['GET'])
def get_zone_stats(zone_id):
    """Returns detailed statistics for a specific zone"""
    try:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'taxi_data.db')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Get zone info
        cur.execute("SELECT zone, borough FROM taxi_zones WHERE location_id = ?", (zone_id,))
        zone_info = cur.fetchone()
        
        if not zone_info:
            return jsonify({"error": "Zone not found"}), 404
        
        zone_name, borough = zone_info
        
        # Get pickup statistics
        cur.execute("""
            SELECT 
                COUNT(*) as trip_count,
                AVG(trip_distance) as avg_distance,
                AVG(speed_mph) as avg_speed,
                AVG(fare_amount) as avg_fare,
                AVG(trip_duration_seconds) as avg_duration,
                SUM(passenger_count) as total_passengers
            FROM trips
            WHERE pickup_location_id = ?
        """, (zone_id,))
        
        pickup_stats = cur.fetchone()
        
        # Get dropoff statistics
        cur.execute("""
            SELECT 
                COUNT(*) as dropoff_count,
                SUM(passenger_count) as dropoff_passengers
            FROM trips
            WHERE dropoff_location_id = ?
        """, (zone_id,))
        
        dropoff_res = cur.fetchone()
        dropoff_count = dropoff_res[0] or 0
        dropoff_passengers = dropoff_res[1] or 0
        
        # Get borough average for comparison
        cur.execute("""
            SELECT AVG(t.speed_mph) as borough_avg_speed
            FROM trips t
            JOIN taxi_zones z ON t.pickup_location_id = z.location_id
            WHERE z.borough = ?
        """, (borough,))
        
        borough_avg = cur.fetchone()[0] or 0
        
        # Calculate coverage ratio
        pickup_count = pickup_stats[0] or 0
        pickup_passengers = pickup_stats[5] or 0
        coverage_ratio = round(dropoff_count / pickup_count, 2) if pickup_count > 0 else 0
        
        stats = {
            "zone": zone_name,
            "borough": borough,
            "pickupCount": pickup_count,
            "dropoffCount": dropoff_count,
            "coverageRatio": coverage_ratio,
            "pickupPassengers": pickup_passengers,
            "dropoffPassengers": dropoff_passengers,
            "totalPassengers": pickup_passengers + dropoff_passengers,
            "avgDistance": round(pickup_stats[1], 2) if pickup_stats[1] else 0,
            "avgSpeed": round(pickup_stats[2], 2) if pickup_stats[2] else 0,
            "avgFare": round(pickup_stats[3], 2) if pickup_stats[3] else 0,
            "avgDuration": round(pickup_stats[4] / 60, 1) if pickup_stats[4] else 0,  # Convert to minutes
            "boroughAvgSpeed": round(borough_avg, 2),
            "speedComparison": round(((pickup_stats[2] or 0) / borough_avg * 100) - 100, 1) if borough_avg > 0 else 0
        }
        
        conn.close()
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/trips/revenue', methods=['GET'])
def get_revenue():
    try:
        data = TripAggregator.get_revenue_by_day()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
