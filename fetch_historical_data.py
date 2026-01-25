import requests
from datetime import datetime, timedelta
import json
import os
from trino.dbapi import connect
from trino.auth import OAuth2Authentication

# Dade-Collier bounding box (10km radius)
MIN_LAT = 25.7675
MAX_LAT = 25.9475
MIN_LON = -80.9869
MAX_LON = -80.8069

# Altitude threshold (meters) - only get low-altitude aircraft
MAX_ALTITUDE = 500  # Likely landing/taking off

# Your OpenSky credentials
OPENSKY_USERNAME = "jnealon"  # Use lowercase!

def get_hour_timestamps(start_date, end_date):
    """Generate Unix timestamps for each hour in date range"""
    timestamps = []
    current = start_date
    while current <= end_date:
        timestamps.append(int(current.timestamp()))
        current += timedelta(hours=1)
    return timestamps

def connect_to_trino():
    """Connect to OpenSky Trino database"""
    conn = connect(
        host='trino.opensky-network.org',
        port=443,
        http_scheme='https',
        auth=OAuth2Authentication(),
        catalog='minio',
        schema='osky',
        user=OPENSKY_USERNAME
    )
    return conn

def query_hour(conn, hour_timestamp):
    """Query one hour of data for Dade-Collier area"""
    
    query = f"""
    SELECT 
        time,
        icao24,
        lat,
        lon,
        velocity,
        heading,
        vertrate,
        callsign,
        onground,
        baroaltitude,
        geoaltitude,
        lastposupdate,
        lastcontact
    FROM state_vectors_data4
    WHERE hour = {hour_timestamp}
        AND lat BETWEEN {MIN_LAT} AND {MAX_LAT}
        AND lon BETWEEN {MIN_LON} AND {MAX_LON}
        AND baroaltitude < {MAX_ALTITUDE}
        AND time - lastcontact <= 15
    """
    
    cursor = conn.cursor()
    cursor.execute(query)
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'timestamp': datetime.fromtimestamp(row[0]).isoformat(),
            'icao24': row[1],
            'latitude': row[2],
            'longitude': row[3],
            'velocity_ms': row[4],
            'heading': row[5],
            'vertrate': row[6],
            'callsign': row[7].strip() if row[7] else 'Unknown',
            'on_ground': row[8],
            'baroaltitude_m': row[9],
            'geoaltitude_m': row[10],
            'lastposupdate': row[11],
            'lastcontact': row[12],
            'hour_queried': hour_timestamp
        })
    
    return results

def save_historical_data(data, start_date):
    """Save historical data to file"""
    os.makedirs('historical_data', exist_ok=True)
    
    filename = f"historical_data/dade_collier_{start_date.strftime('%Y-%m')}.json"
    
    # Read existing data if present
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            existing = json.load(f)
    else:
        existing = []
    
    # Append new data
    existing.extend(data)
    
    # Write back
    with open(filename, 'w') as f:
        json.dump(existing, f, indent=2)
    
    print(f"Saved {len(data)} detections to {filename}")

if __name__ == "__main__":
    # Example: Query one week in July 2025
    # IMPORTANT: Start with small date range to test!
    
    start = datetime(2025, 7, 1, 0, 0, 0)  # July 1, 2025 00:00
    end = datetime(2025, 7, 7, 23, 0, 0)   # July 7, 2025 23:00 (one week)
    
    print(f"Querying historical data from {start} to {end}")
    print("This will query hour by hour (following OpenSky performance guidelines)")
    
    hours = get_hour_timestamps(start, end)
    print(f"Total hours to query: {len(hours)}")
    
    conn = connect_to_trino()
    
    all_data = []
    for i, hour in enumerate(hours):
        try:
            print(f"Querying hour {i+1}/{len(hours)}: {datetime.fromtimestamp(hour)}")
            results = query_hour(conn, hour)
            all_data.extend(results)
            print(f"  Found {len(results)} low-altitude aircraft")
        except Exception as e:
            print(f"  Error: {e}")
    
    conn.close()
    
    print(f"\nTotal detections: {len(all_data)}")
    save_historical_data(all_data, start)
