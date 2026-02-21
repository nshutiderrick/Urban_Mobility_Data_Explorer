# Urban Taxi Mobility Analyst

A comprehensive urban mobility data exploration platform designed to analyze and visualize NYC Taxi trip data. The system provides insights into mobility patterns, identifies coverage gaps, detects system anomalies, and analyzes rush hour trends through a high-performance backend and an interactive frontend dashboard.

## Project Structure

```text
taxi_sumtv/
├── backend/
│   ├── dal/
│   │   ├── init_db.py          # Database initialization
│   │   └── trip_dal.py         # Data Access Layer
│   ├── etl/
│   │   ├── features/
│   │   │   └── feature_engineer.py
│   │   ├── ingestion/
│   │   │   └── loaders.py
│   │   ├── processing/
│   │   │   └── cleaner.py
│   │   └── pipeline.py         # ETL Orchestrator
│   ├── logic/
│   │   ├── aggregators.py      # SQL Business Logic
│   │   └── algorithms.py       # Custom DSA ranking
│   ├── security/
│   │   ├── auth_logic.py       # Password hashing/Tokens
│   │   └── validator.py        # Request validation
│   └── run.py                  # Main Flask entry point
├── data/
│   ├── yellow_tripdata_2019-01.csv
│   ├── taxi_zone_lookup.csv
│   └── taxi_zones/
│       ├── taxi_zones.dbf
│       ├── taxi_zones.prj
│       ├── taxi_zones.sbn
│       ├── taxi_zones.sbx
│       ├── taxi_zones.shp
│       ├── taxi_zones.shp.xml
│       └── taxi_zones.shx
├── database/
│   ├── schema.sql
│   ├── taxi_data.db
│   ├── taxi_data.db-shm
│   └── taxi_data.db-wal
├── frontend/
│   ├── app.js                  # Frontend logic
│   ├── dashboard.html          # Main Dashboard UI (formerly index.html)
│   ├── index.html              # Login page (formerly login.html)
│   ├── signup.html             # Signup page
│   └── style.css               # Main Stylesheet
└── README.md                   # Project Documentation
```

## Key Features

- Interactive Spatial Map: Visualize taxi zones and mobility hot-spots using Leaflet.js.
- Real-time Analytics: Dynamic dashboard with metrics on trip volume, passenger counts, and average speeds.
- Coverage Gap Analysis: Identification of underserved areas using drop-off to pick-up ratios.
- Rush Hour Trends: Hourly activity visualization to identify peak congestion periods.
- Diagnostic Reporting: Comprehensive system health monitoring and anomaly detection.
- Secure Authentication: User login and signup system with hashed password storage.

## Technology Stack

- Backend: Python, Flask, Flask-CORS, SQLite3, Pandas, NumPy.
- Frontend: HTML5, Vanilla CSS, JavaScript (ES6+), Leaflet.js (Mapping), Chart.js (Data Visualization).
- Data Processing: Custom ETL pipeline with automated cleaning and feature engineering.

## Data Structures and Algorithms (DSA)

The project implements custom algorithms to optimize data processing and provide advanced insights:

- QuickSort Implementation: A manual QuickSort algorithm is used to rank taxi zones by coverage gap ratios and other performance metrics without relying on built-in library sorting.
- Anomaly Detection: Custom logic to identify "System Noise" (impossible speeds) and "Economic Noise" (suspicious fare-to-distance ratios).
- Supply-Demand Balancing: Algorithmic identification of supply-demand imbalances in urban zones to pinpoint underserved neighborhoods.

## ETL Pipeline

The data lifecycle is managed through a multi-stage pipeline:

1. Ingestion: Loading raw taxi trip records (CSV) and spatial zone data (Shapefiles).
2. Cleaning: Filtering invalid records, handling missing values, and normalizing geospatial data.
3. Feature Engineering: Calculating trip duration, average speed, and time-based metrics (hour, date).
4. Storage: Bulk insertion of processed data into the SQLite database via the Data Access Layer.

## API Endpoints

### Authentication
- POST /api/auth/signup: Register a new user.
- POST /api/auth/login: Authenticate user and receive a session token.

### Analytics
- GET /api/trips/summary: Global mobility metrics with temporal and spatial filters.
- GET /api/trips/hourly: Trip volume and speed distribution by hour.
- GET /api/trips/gaps: List of top underserved zones.
- GET /api/trips/revenue: Congestion index and revenue trends.

### Spatial and Reports
- GET /api/zones: GeoJSON data for map rendering.
- GET /api/zones/<id>/stats: Detailed metrics for a specific taxi zone.
- GET /api/boroughs/<name>/stats: Aggregated performance data for a borough.
- GET /api/report: Consolidated diagnostic report for the entire system.

## How to Run

### 1. Backend Setup
Initialize the database and start the Flask server:
```bash
python backend/run.py
```
The server will run on http://127.0.0.1:5000.

### 2. Run ETL Pipeline
To process the raw data and populate the database:
```bash
python backend/etl/pipeline.py
```

### 3. Frontend Access
Open `frontend/index.html` in a web browser or serve it through the Flask server by visiting http://127.0.0.1:5000. Accessing the root URL will automatically take you to the login page.

## Security
- Authentication: Passwords are hashed before storage.
- Validation: All incoming API requests are validated for required fields and data types.
- CORS: Configured to allow secure interaction between the frontend and backend services.
