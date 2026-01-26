import json
from collections import defaultdict
from datetime import datetime, timedelta

# Load July and August data
print("Loading data...")
with open('historical_data/dade_collier_2025-07.json', 'r') as f:
    july_data = json.load(f)
with open('historical_data/dade_collier_2025-08.json', 'r') as f:
    august_data = json.load(f)

all_data = july_data + august_data
all_data.sort(key=lambda x: x['timestamp'])

print(f"Total detections: {len(all_data):,}")

# Dade-Collier coordinates
AIRPORT_LAT = 25.8575
AIRPORT_LON = -80.8969

def distance_to_airport(lat, lon):
    """Rough distance in degrees (0.01 deg ≈ 1km)"""
    return ((lat - AIRPORT_LAT)**2 + (lon - AIRPORT_LON)**2)**0.5

def parse_timestamp(ts):
    return datetime.fromisoformat(ts.replace('Z', '+00:00'))

# Group by aircraft and date
aircraft_tracks = defaultdict(lambda: defaultdict(list))
for d in all_data:
    date = d['timestamp'][:10]
    aircraft_tracks[d['icao24']][date].append(d)

print(f"Unique aircraft: {len(aircraft_tracks)}")

# Analyze each aircraft's daily tracks
potential_landings = []
potential_takeoffs = []

for icao, dates in aircraft_tracks.items():
    for date, detections in dates.items():
        if len(detections) < 3:  # Need at least 3 points to see pattern
            continue
        
        # Sort by time
        detections.sort(key=lambda x: x['timestamp'])
        
        # Get distances and altitudes over time
        track = []
        for d in detections:
            if d['baroaltitude_m']:
                track.append({
                    'time': d['timestamp'],
                    'distance': distance_to_airport(d['latitude'], d['longitude']),
                    'altitude': d['baroaltitude_m'],
                    'callsign': d['callsign']
                })
        
        if len(track) < 3:
            continue
        
        # Check for landing pattern:
        # 1. Getting closer to airport
        # 2. Descending
        # 3. Track terminates near airport
        
        first_distance = track[0]['distance']
        last_distance = track[-1]['distance']
        first_altitude = track[0]['altitude']
        last_altitude = track[-1]['altitude']
        
        # Landing criteria
        approaching = first_distance > last_distance  # Getting closer
        descending = first_altitude > last_altitude   # Going down
        ends_near = last_distance < 0.02              # Within ~2km
        low_at_end = last_altitude < 500              # Below 500m at end
        
        if approaching and descending and ends_near and low_at_end:
            # Check if track continues past airport (NOT a landing)
            continues_past = False
            for i, point in enumerate(track):
                if i > 0:
                    # If distance starts increasing again, it passed through
                    if track[i-1]['distance'] < 0.02 and point['distance'] > track[i-1]['distance']:
                        continues_past = True
                        break
            
            if not continues_past:
                potential_landings.append({
                    'icao': icao,
                    'callsign': track[0]['callsign'],
                    'date': date,
                    'time': track[-1]['time'],
                    'final_altitude': last_altitude,
                    'final_distance_km': last_distance * 111,  # Convert to km
                    'altitude_drop': first_altitude - last_altitude,
                    'detections': len(track),
                    'confidence': 'HIGH' if low_at_end and last_distance < 0.01 else 'MEDIUM'
                })
        
        # Takeoff criteria
        # 1. Starts near airport
        # 2. Climbing  
        # 3. Moving away
        
        leaving = last_distance > first_distance      # Moving away
        climbing = last_altitude > first_altitude     # Going up
        starts_near = first_distance < 0.02           # Within ~2km
        low_at_start = first_altitude < 500           # Below 500m at start
        
        if leaving and climbing and starts_near and low_at_start:
            potential_takeoffs.append({
                'icao': icao,
                'callsign': track[0]['callsign'],
                'date': date,
                'time': track[0]['time'],
                'initial_altitude': first_altitude,
                'initial_distance_km': first_distance * 111,
                'altitude_gain': last_altitude - first_altitude,
                'detections': len(track),
                'confidence': 'HIGH' if low_at_start and first_distance < 0.01 else 'MEDIUM'
            })

print("\n" + "="*80)
print("TRACK TERMINATION ANALYSIS - JULY & AUGUST 2025")
print("="*80)

print(f"\n🛬 POTENTIAL LANDINGS DETECTED: {len(potential_landings)}")
print("-"*80)

for landing in sorted(potential_landings, key=lambda x: x['date']):
    print(f"\n{landing['date']} {landing['time'][11:19]}")
    print(f"  Aircraft: {landing['callsign']} ({landing['icao']})")
    print(f"  Final altitude: {landing['final_altitude']:.0f}m ({landing['final_altitude']*3.28:.0f}ft)")
    print(f"  Final distance from airport: {landing['final_distance_km']:.1f}km")
    print(f"  Descended: {landing['altitude_drop']:.0f}m over {landing['detections']} detections")
    print(f"  Confidence: {landing['confidence']}")

print(f"\n🛫 POTENTIAL TAKEOFFS DETECTED: {len(potential_takeoffs)}")
print("-"*80)

for takeoff in sorted(potential_takeoffs, key=lambda x: x['date']):
    print(f"\n{takeoff['date']} {takeoff['time'][11:19]}")
    print(f"  Aircraft: {takeoff['callsign']} ({takeoff['icao']})")
    print(f"  Initial altitude: {takeoff['initial_altitude']:.0f}m ({takeoff['initial_altitude']*3.28:.0f}ft)")
    print(f"  Initial distance from airport: {takeoff['initial_distance_km']:.1f}km")
    print(f"  Climbed: {takeoff['altitude_gain']:.0f}m over {takeoff['detections']} detections")
    print(f"  Confidence: {takeoff['confidence']}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Likely landings: {len([l for l in potential_landings if l['confidence'] == 'HIGH'])}")
print(f"Likely takeoffs: {len([t for t in potential_takeoffs if t['confidence'] == 'HIGH'])}")
print(f"Total operations: {len(potential_landings) + len(potential_takeoffs)}")
