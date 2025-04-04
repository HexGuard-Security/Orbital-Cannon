#!/usr/bin/env python3
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import json
import datetime
import math
import requests
import time
from sgp4.earth_gravity import wgs72
from sgp4.io import twoline2rv

# Initialize Flask app
app = Flask(__name__, static_folder='orbital-cannon/static')
CORS(app)  # Enable CORS for all routes

# Directory where we'll store satellite data
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# File path for satellites cache
SATELLITES_CACHE_FILE = os.path.join(DATA_DIR, 'satellites.json')

# URLs for fetching TLE data
TLE_URLS = {
    'active': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle',
    'stations': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle',
    'visual': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle',
    'amateur': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle',
    'weather': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle',
    'gps': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=tle',
    'starlink': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle'
}

def parse_tles(tle_data):
    """Parse TLE data into a list of satellite dictionaries"""
    lines = tle_data.strip().split('\n')
    satellites = []
    
    # Process three lines at a time (name line + two TLE lines)
    for i in range(0, len(lines), 3):
        if i + 2 < len(lines):
            name = lines[i].strip()
            line1 = lines[i + 1].strip()
            line2 = lines[i + 2].strip()
            
            # Extract NORAD ID from the TLE
            try:
                norad_id = int(line1[2:7])
                
                satellites.append({
                    'id': norad_id,
                    'name': name,
                    'tle_line1': line1,
                    'tle_line2': line2
                })
            except (ValueError, IndexError):
                # Skip malformed TLEs
                continue
    
    return satellites

def fetch_satellites():
    """Fetch satellite TLE data from CelesTrak and cache it"""
    satellites = []
    
    try:
        # Try to load from cache first
        if os.path.exists(SATELLITES_CACHE_FILE):
            cache_stats = os.stat(SATELLITES_CACHE_FILE)
            cache_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(cache_stats.st_mtime)
            
            # If cache is less than 24 hours old, use it
            if cache_age.total_seconds() < 86400:  # 24 hours
                with open(SATELLITES_CACHE_FILE, 'r') as f:
                    print(f"Loading satellites from cache file: {SATELLITES_CACHE_FILE}")
                    return json.load(f)
                    
        print("Fetching satellites from CelesTrak...")
        # Fetch new data from CelesTrak
        for category, url in TLE_URLS.items():
            try:
                print(f"Fetching {category} satellites from {url}")
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    category_satellites = parse_tles(response.text)
                    for sat in category_satellites:
                        sat['category'] = category
                    satellites.extend(category_satellites)
                    print(f"  - Got {len(category_satellites)} {category} satellites")
                else:
                    print(f"  - Failed to fetch {category} satellites: HTTP {response.status_code}")
            except Exception as e:
                print(f"  - Error fetching {category} satellites: {e}")
        
        print(f"Total satellites fetched: {len(satellites)}")
        
        # Cache the fetched data
        if satellites:
            with open(SATELLITES_CACHE_FILE, 'w') as f:
                json.dump(satellites, f)
            print(f"Satellites cached to: {SATELLITES_CACHE_FILE}")
        
        return satellites
    except Exception as e:
        print(f"Error fetching satellites: {e}")
        
        # If there was an error but we have a cache, use that
        if os.path.exists(SATELLITES_CACHE_FILE):
            print("Loading from cache after error")
            with open(SATELLITES_CACHE_FILE, 'r') as f:
                return json.load(f)
        
        # Otherwise return empty list
        return []

def calculate_satellite_position(tle_line1, tle_line2, timestamp=None):
    """Calculate the position of a satellite at a given time using SGP4"""
    if timestamp is None:
        timestamp = datetime.datetime.utcnow()
    
    # Create satellite object from TLE data
    satellite = twoline2rv(tle_line1, tle_line2, wgs72)
    
    # Calculate time since epoch in minutes
    epoch_year = satellite.epochyr
    epoch_day = satellite.epochdays
    
    # Convert two-digit year to four digits
    if epoch_year < 57:  # Sputnik 1 launched in 1957
        epoch_year += 2000
    else:
        epoch_year += 1900
    
    # Create epoch datetime
    epoch_datetime = datetime.datetime(epoch_year, 1, 1) + datetime.timedelta(days=epoch_day - 1)
    
    # Calculate minutes since epoch
    time_diff = timestamp - epoch_datetime
    minutes_since_epoch = time_diff.total_seconds() / 60.0
    
    # Get position and velocity
    position, velocity = satellite.propagate(
        satellite.epochyr,
        satellite.epochdays,
        minutes_since_epoch
    )
    
    # Convert position to geographic coordinates
    pos_x, pos_y, pos_z = position
    vel_x, vel_y, vel_z = velocity
    
    # Convert from TEME frame to lat/long (simplified)
    r = math.sqrt(pos_x**2 + pos_y**2)
    lat = math.atan2(pos_z, r) * 180 / math.pi
    lon = math.atan2(pos_y, pos_x) * 180 / math.pi
    
    # Calculate altitude (km)
    alt = math.sqrt(pos_x**2 + pos_y**2 + pos_z**2) - 6371.0  # Earth radius in km
    
    # Calculate velocity magnitude
    vel_magnitude = math.sqrt(vel_x**2 + vel_y**2 + vel_z**2)
    
    return {
        'timestamp': timestamp.isoformat(),
        'latitude': lat,
        'longitude': lon,
        'altitude': alt,
        'position_x': pos_x,
        'position_y': pos_y,
        'position_z': pos_z,
        'velocity_x': vel_x,
        'velocity_y': vel_y,
        'velocity_z': vel_z,
        'velocity': vel_magnitude
    }

def predict_passes(tle_line1, tle_line2, lat, lon, alt, days=3, min_elevation=10):
    """Predict satellite passes over a ground station using SGP4"""
    # This implementation uses SGP4 propagation to find actual passes
    
    # Create a satellite object
    satellite = twoline2rv(tle_line1, tle_line2, wgs72)
    
    # Store passes
    passes = []
    
    # Convert observer coordinates
    observer_lat = math.radians(lat)
    observer_lon = math.radians(lon)
    observer_alt = alt / 1000.0  # Convert to km
    
    # Get current time and generate time range
    now = datetime.datetime.utcnow()
    
    # Determine step size based on orbital period (faster satellites need smaller steps)
    mean_motion = satellite.no  # Revolutions per day
    period_minutes = 1440.0 / mean_motion  # Minutes per revolution (1440 min = 24 hours)
    
    # Use smaller step for fast-moving satellites, larger for slow ones
    step_minutes = min(5.0, period_minutes / 12)  # At least 12 points per orbit, max 5 minutes
    
    # Total number of steps to simulate
    total_minutes = days * 1440
    num_steps = int(total_minutes / step_minutes)
    
    # Variables to track pass status
    current_pass = None
    is_visible = False
    
    # Simulate satellite position at each time step
    for i in range(num_steps):
        # Calculate time for this step
        time_delta = datetime.timedelta(minutes=i * step_minutes)
        curr_time = now + time_delta
        
        # Time since TLE epoch
        time_since = (curr_time - now).total_seconds() / 60.0
        
        # Get satellite position at this time
        pos, vel = satellite.propagate(
            satellite.epochyr,
            satellite.epochdays,
            time_since
        )
        
        if pos[0] is None or math.isnan(pos[0]):
            # Skip invalid positions
            continue
        
        # Convert satellite position to lat/lon
        sat_x, sat_y, sat_z = pos
        sat_r = math.sqrt(sat_x**2 + sat_y**2)
        sat_lat = math.atan2(sat_z, sat_r)
        sat_lon = math.atan2(sat_y, sat_x)
        sat_alt = math.sqrt(sat_x**2 + sat_y**2 + sat_z**2) - 6371.0
        
        # Calculate observer-to-satellite vector
        # Convert lat/lon to ECEF coordinates
        observer_x = (6371.0 + observer_alt) * math.cos(observer_lat) * math.cos(observer_lon)
        observer_y = (6371.0 + observer_alt) * math.cos(observer_lat) * math.sin(observer_lon)
        observer_z = (6371.0 + observer_alt) * math.sin(observer_lat)
        
        # Vector from observer to satellite
        rx = sat_x - observer_x
        ry = sat_y - observer_y
        rz = sat_z - observer_z
        
        # Distance to satellite
        distance = math.sqrt(rx**2 + ry**2 + rz**2)
        
        # Calculate elevation angle
        # Convert observer coordinates to local ENU reference frame
        sin_lat = math.sin(observer_lat)
        cos_lat = math.cos(observer_lat)
        sin_lon = math.sin(observer_lon)
        cos_lon = math.cos(observer_lon)
        
        # Transform vector from ECEF to ENU
        e = -rx * sin_lon + ry * cos_lon
        n = -rx * sin_lat * cos_lon - ry * sin_lat * sin_lon + rz * cos_lat
        u = rx * cos_lat * cos_lon + ry * cos_lat * sin_lon + rz * sin_lat
        
        # Calculate elevation
        elevation = math.asin(u / distance) * 180.0 / math.pi
        
        # Check if satellite is visible (above min_elevation)
        was_visible = is_visible
        is_visible = elevation >= min_elevation
        
        # Start of a new pass
        if is_visible and not was_visible:
            current_pass = {
                'aos_time': curr_time.isoformat(),
                'max_elevation': elevation,
                'max_elevation_time': curr_time.isoformat(),
            }
        
        # During a pass, update max elevation
        elif is_visible and current_pass:
            if elevation > current_pass['max_elevation']:
                current_pass['max_elevation'] = elevation
                current_pass['max_elevation_time'] = curr_time.isoformat()
        
        # End of a pass
        elif not is_visible and was_visible and current_pass:
            current_pass['los_time'] = curr_time.isoformat()
            
            # Calculate duration
            aos_time = datetime.datetime.fromisoformat(current_pass['aos_time'])
            los_time = curr_time
            current_pass['duration_seconds'] = (los_time - aos_time).total_seconds()
            
            # Add to list of passes
            passes.append(current_pass)
            current_pass = None
    
    # Check if we have an unfinished pass at the end of the simulation
    if current_pass:
        # Set the end time to the last simulated time
        last_time = now + datetime.timedelta(minutes=total_minutes)
        current_pass['los_time'] = last_time.isoformat()
        
        # Calculate duration
        aos_time = datetime.datetime.fromisoformat(current_pass['aos_time'])
        los_time = last_time
        current_pass['duration_seconds'] = (los_time - aos_time).total_seconds()
        
        # Add to list of passes
        passes.append(current_pass)
    
    return passes

# Routes
@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('orbital-cannon/static', 'index.html')

@app.route('/orbit-visualizer.js')
def serve_orbit_visualizer():
    """Serve the orbit visualizer script"""
    return send_from_directory('orbital-cannon/static', 'orbit-visualizer.js')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('orbital-cannon/static', path)

@app.route('/api/satellites', methods=['GET'])
def get_satellites():
    """Get list of satellites with pagination and search support"""
    start_time = time.time()
    print("API request: /api/satellites")
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 100, type=int)  # Default 100 per page
    search = request.args.get('search', '', type=str)
    category = request.args.get('category', 'all', type=str)
    
    # Limit to reasonable values
    limit = min(limit, 500)  # Max 500 satellites per page
    
    # Get all satellites
    satellites = fetch_satellites()
    
    # Apply filtering for search and category
    if search:
        search = search.lower()
        satellites = [s for s in satellites if search in s['name'].lower()]
    
    if category != 'all':
        satellites = [s for s in satellites if s.get('category') == category]
    
    # Calculate pagination values
    total_satellites = len(satellites)
    total_pages = (total_satellites + limit - 1) // limit  # Ceiling division
    
    # Ensure page is within bounds
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    
    # Paginate the results
    start_idx = (page - 1) * limit
    end_idx = min(start_idx + limit, total_satellites)
    paginated_satellites = satellites[start_idx:end_idx]
    
    # Add timing info for debugging
    elapsed = time.time() - start_time
    print(f"Returning {len(paginated_satellites)} satellites (page {page}/{total_pages}, {total_satellites} total) (took {elapsed:.2f}s)")
    
    return jsonify({
        'success': True,
        'data': paginated_satellites,
        'meta': {
            'total': total_satellites,
            'page': page,
            'limit': limit,
            'pages': total_pages
        }
    })

@app.route('/api/satellites/<int:satellite_id>/position', methods=['GET'])
def get_satellite_position(satellite_id):
    """Get current position of a satellite"""
    print(f"API request: /api/satellites/{satellite_id}/position")
    
    satellites = fetch_satellites()
    
    # Find satellite by ID
    satellite = next((s for s in satellites if s['id'] == satellite_id), None)
    
    if not satellite:
        return jsonify({
            'success': False,
            'message': f'Satellite with ID {satellite_id} not found'
        }), 404
    
    # Calculate position
    position = calculate_satellite_position(
        satellite['tle_line1'],
        satellite['tle_line2']
    )
    
    return jsonify({
        'success': True,
        'data': position
    })

@app.route('/api/satellites/<int:satellite_id>/passes', methods=['POST'])
def predict_satellite_passes(satellite_id):
    """Predict passes for a satellite over a ground station"""
    print(f"API request: /api/satellites/{satellite_id}/passes")
    
    satellites = fetch_satellites()
    
    # Find satellite by ID
    satellite = next((s for s in satellites if s['id'] == satellite_id), None)
    
    if not satellite:
        return jsonify({
            'success': False,
            'message': f'Satellite with ID {satellite_id} not found'
        }), 404
    
    # Get ground station parameters from request
    data = request.json
    lat = data.get('latitude', 0)
    lon = data.get('longitude', 0)
    alt = data.get('altitude', 0)
    days = data.get('days', 3)
    min_elevation = data.get('min_elevation', 10)
    
    # Predict passes
    passes = predict_passes(
        satellite['tle_line1'],
        satellite['tle_line2'],
        lat, lon, alt, days, min_elevation
    )
    
    return jsonify({
        'success': True,
        'data': passes
    })

if __name__ == '__main__':
    # Ensure the data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    print("Starting Orbital Cannon Flask server...")
    print(f"Data directory: {DATA_DIR}")
    
    # Start the Flask app
    port = 8085
    print(f"Server listening on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
