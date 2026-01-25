import requests
from datetime import datetime
import json
import os

# Dade-Collier Training and Transition Airport (TNT)
AIRPORT_LAT = 25.8575
AIRPORT_LON = -80.8969
RADIUS_KM = 10  # Monitor within 10km of airport

# Altitude thresholds (in meters)
LANDING_ALTITUDE = 500  # Below this = likely landing/departing
GROUND_ALTITUDE = 100   # Below this = definitely on ground or very low

def get_aircraft_near_airport():
    """Query OpenSky Network for aircraft near Dade-Collier"""
    
    # Calculate bounding box (rough approximation)
    # 1 degree lat/lon ≈ 111km
    lat_offset = RADIUS_KM / 111
    lon_offset = RADIUS_KM / (111 * abs(AIRPORT_LAT / 90))
    
    min_lat = AIRPORT_LAT - lat_offset
    max_lat = AIRPORT_LAT + lat_offset
    min_lon = AIRPORT_LON - lon_offset
    max_lon = AIRPORT_LON + lon_offset
    
    url = f"https://opensky-network.org/api/states/all?lamin={min_lat}&lomin={min_lon}&lamax={max_lat}&lomax={max_lon}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data and 'states' in data and data['states']:
            return parse_aircraft_data(data['states'])
        else:
            return []
            
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

def parse_aircraft_data(states):
    """Parse OpenSky state vectors into useful format"""
    aircraft_list = []
    
    for state in states:
        # OpenSky state vector format:
        # [0] icao24, [1] callsign, [5] longitude, [6] latitude, 
        # [7] baro_altitude, [9] velocity, [10] true_track
        
        aircraft = {
            'timestamp': datetime.now().isoformat(),
            'icao24': state[0],
            'callsign': state[1].strip() if state[1] else 'Unknown',
            'latitude': state[6],
            'longitude': state[5],
            'altitude_m': state[7],  # barometric altitude in meters
            'altitude_ft': int(state[7] * 3.28084) if state[7] else None,  # convert to feet
            'velocity_ms': state[9],  # m/s
            'heading': state[10],
            'on_ground': state[8]
        }
        
        # Classify activity
        if aircraft['on_ground']:
            aircraft['status'] = 'ON_GROUND'
        elif aircraft['altitude_m'] and aircraft['altitude_m'] < GROUND_ALTITUDE:
            aircraft['status'] = 'VERY_LOW'
        elif aircraft['altitude_m'] and aircraft['altitude_m'] < LANDING_ALTITUDE:
            aircraft['status'] = 'LOW_ALTITUDE'
        else:
            aircraft['status'] = 'CRUISING'
            
        aircraft_list.append(aircraft)
    
    return aircraft_list

def save_detections(aircraft_list):
    """Save aircraft detections to monthly log file"""
    os.makedirs('flight_data', exist_ok=True)
    
    filename = f"flight_data/dade_collier_{datetime.now().strftime('%Y-%m')}.json"
    
    # Read existing data
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
    else:
        data = []
    
    # Add new detections
    data.extend(aircraft_list)
    
    # Write back
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Print summary
    if aircraft_list:
        print(f"Detected {len(aircraft_list)} aircraft near Dade-Collier:")
        for aircraft in aircraft_list:
            alt_str = f"{aircraft['altitude_ft']}ft" if aircraft['altitude_ft'] else "Unknown"
            print(f"  {aircraft['callsign']} ({aircraft['icao24']}) - {alt_str} - {aircraft['status']}")
    else:
        print("No aircraft detected near Dade-Collier")

if __name__ == "__main__":
    print(f"Checking for aircraft near Dade-Collier Airport at {datetime.now()}")
    aircraft = get_aircraft_near_airport()
    save_detections(aircraft)
