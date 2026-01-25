import requests
from datetime import datetime
import json
import os
import pytz

# Dade-Collier Training and Transition Airport (TNT)
AIRPORT_LAT = 25.8575
AIRPORT_LON = -80.8969
RADIUS_KM = 10  # Monitor within 10km of airport

# Altitude thresholds (in meters)
LANDING_ALTITUDE = 500  # Below this = likely landing/departing
GROUND_ALTITUDE = 100   # Below this = definitely on ground or very low

# After-hours window (Eastern Time)
AFTER_HOURS_START = 22  # 10 PM
AFTER_HOURS_END = 6     # 6 AM

# Watch list - callsigns of interest
WATCH_CALLSIGNS = ['RPN', 'GXA']

# Military ICAO prefixes (US military typically starts with 'AE')
MILITARY_PREFIXES = ['AE']

def is_after_hours():
    """Check if current time is within after-hours window (10 PM - 6 AM Eastern)"""
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    hour = now.hour
    
    # After hours if between 10 PM and 6 AM
    return hour >= AFTER_HOURS_START or hour < AFTER_HOURS_END

def check_alert_conditions(aircraft):
    """Determine if aircraft meets any alert conditions"""
    alerts = []
    
    # Check for watch list callsigns
    callsign = aircraft['callsign'].upper()
    for watch in WATCH_CALLSIGNS:
        if callsign.startswith(watch):
            alerts.append(f"WATCH_CALLSIGN:{watch}")
    
    # Check for N/A or empty callsign
    if not callsign or callsign == 'N/A' or callsign == 'UNKNOWN':
        alerts.append("NO_CALLSIGN")
    
    # Check for military ICAO
    icao24 = aircraft['icao24'].upper()
    for prefix in MILITARY_PREFIXES:
        if icao24.startswith(prefix):
            alerts.append("MILITARY")
    
    # Check for after-hours activity
    if is_after_hours():
        alerts.append("AFTER_HOURS")
    
    # Check for low-altitude activity (potential landing/takeoff)
    if aircraft['status'] in ['LOW_ALTITUDE', 'VERY_LOW', 'ON_GROUND']:
        alerts.append("LOW_ALTITUDE")
    
    return alerts

def get_aircraft_near_airport():
    """Query OpenSky Network for aircraft near Dade-Collier"""
    
    # Calculate bounding box
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
        aircraft = {
            'timestamp': datetime.now().isoformat(),
            'icao24': state[0],
            'callsign': state[1].strip() if state[1] else 'Unknown',
            'latitude': state[6],
            'longitude': state[5],
            'altitude_m': state[7],
            'altitude_ft': int(state[7] * 3.28084) if state[7] else None,
            'velocity_ms': state[9],
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
        
        # Check for alert conditions
        alerts = check_alert_conditions(aircraft)
        aircraft['alerts'] = alerts
        aircraft['is_alert'] = len(alerts) > 0
            
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
            alert_str = f" ⚠️  ALERTS: {', '.join(aircraft['alerts'])}" if aircraft['is_alert'] else ""
            print(f"  {aircraft['callsign']} ({aircraft['icao24']}) - {alt_str} - {aircraft['status']}{alert_str}")
    else:
        print("No aircraft detected near Dade-Collier")

def save_alerts(aircraft_list):
    """Save high-priority alerts to separate file"""
    alerts = [a for a in aircraft_list if a['is_alert']]
    
    if not alerts:
        return
    
    os.makedirs('flight_data', exist_ok=True)
    alert_filename = f"flight_data/ALERTS_{datetime.now().strftime('%Y-%m')}.json"
    
    # Read existing alerts
    if os.path.exists(alert_filename):
        with open(alert_filename, 'r') as f:
            alert_data = json.load(f)
    else:
        alert_data = []
    
    # Add new alerts
    alert_data.extend(alerts)
    
    # Write back
    with open(alert_filename, 'w') as f:
        json.dump(alert_data, f, indent=2)
    
    print(f"\n🚨 {len(alerts)} HIGH-PRIORITY ALERTS logged to {alert_filename}")

if __name__ == "__main__":
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    after_hours_status = "AFTER HOURS" if is_after_hours() else "normal hours"
    
    print(f"Checking for aircraft near Dade-Collier Airport at {now.strftime('%Y-%m-%d %H:%M %Z')} ({after_hours_status})")
    aircraft = get_aircraft_near_airport()
    save_detections(aircraft)
    save_alerts(aircraft)
